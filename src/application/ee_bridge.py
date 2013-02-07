#encoding: utf-8

import logging
import settings
import simplejson as json
import collections
import urllib
import re
import time

import ee

from time_utils import timestamp
from datetime import timedelta, date

# A multiplier to convert square meters to square kilometers.
METER2_TO_KM2 = 1.0/(1000*1000)

# The class values used to represent pixels of different types.
CLS_UNCLASSIFIED = 0
CLS_FOREST = 1
CLS_DEFORESTED = 2
CLS_DEGRADED = 3
CLS_BASELINE = 4
CLS_CLOUD = 5
CLS_OLD_DEFORESTATION = 6
CLS_EDITED_DEFORESTATION = 7
CLS_EDITED_DEGRADATION = 8
CLS_EDITED_OLD_DEGRADATION = 9

# A value that signifies invalid NDFI.
INVALID_NDFI = 201

# The length of a "long" time period in milliseconds.
LONG_SPAN_SIZE_MS = 1000 * 60 * 60 * 24 * 30 * 3

# MODIS projection specification.
MODIS_CRS = 'SR-ORG:6974'
MODIS_250_SCALE = 231.65635681152344
MODIS_TRANSFORM = [
    MODIS_250_SCALE,  0, -8895720,
    0, -MODIS_250_SCALE, 1112066.375
]

# Initialize the EE API.
ee.data.DEFAULT_DEADLINE = 60 * 20
ee.Initialize(settings.EE_CREDENTIALS, 'http://maxus.mtv:12345/')


class Stats(object):
    DEFORESTATION = CLS_EDITED_DEFORESTATION
    DEGRADATION = CLS_EDITED_DEGRADATION

    def _get_historical_freeze(self, report_id, frozen_image):
        remapped = frozen_image.remap([0,1,2,3,4,5,6,7,8,9],
                                      [0,1,2,3,4,5,6,1,1,9])
        def_image = _paint(remapped, report_id, settings.FT_TABLE_ID, 7)
        deg_image = _paint(def_image, report_id, settings.FT_TABLE_ID, 8)
        return deg_image.select(['remapped'], ['class'])

    def _get_area(self, report_id, image_id, polygons):
        freeze = self._get_historical_freeze(report_id, ee.Image(image_id))
        return _get_area_histogram(
            freeze, polygons, [Stats.DEFORESTATION, Stats.DEGRADATION])

    def get_stats_for_polygon(self, assetids, polygon):
        """ example polygon, must be CCW
            #polygon = [[[-61.9,-11.799],[-61.9,-11.9],[-61.799,-11.9],[-61.799,-11.799],[-61.9,-11.799]]]
        """
        feature = ee.Feature(ee.Feature.Polygon(polygon), {'name': 'myPoly'})
        polygons = ee.FeatureCollection([ee.Feature(feature)])

        # javascript way, lovely
        if not hasattr(assetids, '__iter__'):
            assetids = [assetids]

        reports = []
        for report_id, asset_id in assetids:
            result = self._get_area(report_id, asset_id, polygons)
            if result is None: return None
            reports.append(result[0])

        stats = []
        for x in reports:
            stats.append({
                'total_area': x['total']['area'] * METER2_TO_KM2,
                'def': x[str(Stats.DEFORESTATION)]['area'] * METER2_TO_KM2,
                'deg': x[str(Stats.DEGRADATION)]['area'] * METER2_TO_KM2,
            })
        return stats

    def get_stats(self, report_id, frozen_image, table_id):
        result = self._get_area(
            report_id, frozen_image, ee.FeatureCollection(int(table_id)))
        if result is None: return None
        stats = {}
        for x in result:
            name = x['name']
            if isinstance(name, float): name = int(name)
            stats['%s_%s' % (table_id, name)] = {
                'id': str(name),
                'table': table_id,
                'total_area': x['total']['area'] * METER2_TO_KM2,
                'def': x[str(Stats.DEFORESTATION)]['area'] * METER2_TO_KM2,
                'deg': x[str(Stats.DEGRADATION)]['area'] * METER2_TO_KM2,
            }

        return stats


class EELandsat(object):
    def list(self, bounds, params={}):
        bbox = ee.Feature.Rectangle(
            *[float(i.strip()) for i in bounds.split(',')])
        images = ee.ImageCollection('L7_L1T').filterBounds(bbox).getInfo()
        logging.info(images)
        if 'features' in images:
            return [x['id'] for x in images['features']]
        return []

    def mapid(self, start, end):
        MAP_IMAGE_BANDS = ['30','20','10']
        PREVIEW_GAIN = 500
        collection = _get_landsat_toa(start, end)
        return collection.mosaic().getMapId({
            'bands': ','.join(MAP_IMAGE_BANDS),
            'gain': PREVIEW_GAIN
        })


class NDFI(object):
    """NDFI info for a period of time."""

    def __init__(self, last_period, work_period):
        self.last_period = dict(start=last_period[0], end=last_period[1])
        self.work_period = dict(start=work_period[0], end=work_period[1])

    def mapid2(self, asset_id):
        return self._ndfi_delta(asset_id).getMapId({'format': 'png'})

    def freeze_map(self, asset_id, table, report_id):
        asset = ee.Image(asset_id)
        frozen_image = _remap_prodes_classes(asset)[0]
        remapped = frozen_image.remap([0,1,2,3,4,5,6,7,8,9],
                                      [0,1,2,3,4,5,6,2,3,9])
        def_image = _paint(remapped, int(report_id), table, 7)
        deg_image = _paint(def_image, int(report_id), table, 8)
        map_image = deg_image.select(['remapped'], ['classification'])
        # Make sure we keep the metadata.
        result = asset.addBands(map_image, ['classification'], True)
        return ee.data.createAsset(result.serialize(False))

    def rgbid(self):
        """Returns mapid to access NDFI RGB image."""
        return self._RGB_image_command(self.work_period)

    def smaid(self):
        """Returns mapid to access NDFI SMA image."""
        return self._SMA_image_command(self.work_period)

    def ndfi0id(self):
        """Returns mapid to access NDFI T0 image."""
        return self._NDFI_period_image_command(self.last_period, 1)

    def baseline(self, asset_id):
        classification = ee.Image(asset_id).select('classification')
        return classification.mask(classification.eq(4)).getMapId()

    def rgb0id(self):
        """Returns params to access NDFI RGB image for the last quarter."""
        quarter_msec = 1000 * 60 * 60 * 24 * 90
        last_start = self.last_period['start']
        last_period = dict(start=last_start - quarter_msec,
                           end=self.last_period['end'])
        return self._RGB_image_command(last_period)

    def ndfi1id(self):
        """Returns mapid to access NDFI T1 image."""
        return self._NDFI_period_image_command(self.work_period)

    def rgb_stretch(self, polygon, sensor, bands):
        NUM_SAMPLES = 999999
        STD_DEVS = 2

        if sensor == 'modis':
            bands = ['sur_refl_b0%d' % i for i in bands]
            # Kriging is very expensive and does not significantly affect
            # value distribution. Skip it for the stats aggregation.
            stats_image = self._make_mosaic(self.work_period)
            stats_image = stats_image.select(
                ['sur_refl_b01_250m',
                 'sur_refl_b02_250m',
                 'sur_refl_b03_500m',
                 'sur_refl_b04_500m',
                 'sur_refl_b05_500m',
                 'sur_refl_b06_500m',
                 'sur_refl_b07_500m'],
                ['sur_refl_b01',
                 'sur_refl_b02',
                 'sur_refl_b03',
                 'sur_refl_b04',
                 'sur_refl_b05',
                 'sur_refl_b06',
                 'sur_refl_b07'])
            display_image = self._kriged_mosaic(self.work_period)
        elif sensor == 'landsat':
            bands = ['%d' % i for i in bands]
            yesterday = date.today() - timedelta(1)
            collection = _get_landsat_toa(
                self.work_period['start'] - 3 * 30 * 24 * 60 * 60 * 1000,
                self.work_period['end'],
                int(time.mktime(yesterday.timetuple()) * 1000000))
            stats_image = display_image = collection.mosaic()
        else:
            raise RuntimeError('Sensor %s neither modis nor landsat.' % sensor)
        stats_image = stats_image.select(bands)
        display_image = display_image.select(bands)

        # Calculate stats.
        bbox = ee.Feature.Rectangle(*self._get_polygon_bbox(polygon))
        stats = ee.data.getValue({
            'image': stats_image.stats(NUM_SAMPLES, bbox).serialize(False),
            'fields': ','.join(bands)
        })
        mins = []
        maxs = []
        for band in bands:
            band_stats = stats['properties'][band]['values']
            min = band_stats['mean'] - STD_DEVS * band_stats['total_sd']
            max = band_stats['mean'] + STD_DEVS * band_stats['total_sd']
            if min == max:
                min -= 1
                max += 1
            mins.append(min)
            maxs.append(max)

        # Get stretched image.
        return display_image.clip(polygon).getMapId({
            'bands': ','.join(bands),
            'min': ','.join(str(i) for i in mins),
            'max': ','.join(str(i) for i in maxs)
        })

    def ndfi_change_value(self, asset_id, polygon, rows=5, cols=5):
        """Returns the NDFI difference between two periods inside the specified polygons."""
        # Get region bound.
        bbox = self._get_polygon_bbox(polygon)
        rect = ee.Feature.Rectangle(*bbox)
        min_x = bbox[0]
        min_y = bbox[1]
        max_x = bbox[2]
        max_y = bbox[3]
        x_span = max_x - min_x
        y_span = max_y - min_y
        x_step = x_span / cols
        y_step = y_span / rows

        # Make a numbered grid image that will be used as a mask when selecting
        # cells. We can't clip to geometry because that way some pixels will be
        # included in multiple cells.
        lngLat = ee.Image.pixelLonLat().clip(rect)
        lng = lngLat.select(0)
        lat = lngLat.select(1)

        lng = lng.subtract(min_x).unitScale(0, x_step).int()
        lat = lat.subtract(min_y).unitScale(0, x_step).int()
        index_image = lat.multiply(cols).add(lng)

        # Get the NDFI data.
        diff = self._ndfi_delta(asset_id).select(0)
        masked = diff.mask(diff.mask().And(diff.lt(INVALID_NDFI)))

        # Compose the reduction query for each cell.
        count_reducer = ee.call('Reducer.count')
        sum_reducer = ee.call('Reducer.sum')
        def grid(img):
            count_queries = []
            sum_queries = []
            for y in range(rows):
                for x in range(cols):
                    index = y * cols + x
                    cell_img = img.mask(img.mask().And(index_image.eq(index)))
                    count_queries.append(cell_img.reduceRegion(
                        count_reducer, rect, None, MODIS_CRS, MODIS_TRANSFORM))
                    sum_queries.append(cell_img.reduceRegion(
                        sum_reducer, rect, None, MODIS_CRS, MODIS_TRANSFORM))
            return [count_queries, sum_queries]
        func = ee.lambda_(['img'], grid(ee.variable(ee.Image, 'img')))
        final_query = ee.call(func, masked)

        # Run the aggregations.
        json = ee.serializer.toJSON(final_query, False)
        result = ee.data.getValue({'json': json})

        # Repackages the results in a backward-compatible form:
        counts = [int(i['ndfi']) for i in result[0]]
        sums = [int(i['ndfi']) for i in result[1]]
        return {
            'properties': {
                'ndfiSum': {
                    'values': {
                        'count': counts,
                        'sum': sums
                    },
                    'type': 'DataDictionary'
                }
            }
        }

    def _ndfi_delta(self, asset_id):
        # Constants.
        MIN_FOREST_SIZE = 41
        MIN_UNMASKED_SIZE = 21
        ALREADY_DEFORESTED_NDFI = 100
        CLASSIFICATION_OFFSET = 201

        # Get base NDFIs.
        work_month = self._getMidMonth(self.work_period['start'],
                                       self.work_period['end'])
        work_year = self._getMidYear(self.work_period['start'],
                                     self.work_period['end'])
        baseline = self._paint_deforestation(asset_id, work_month, work_year)
        ndfi0 = self._NDFI_image(self.last_period, 1)
        ndfi1 = self._NDFI_image(self.work_period)

        # Basic difference.
        diff = ndfi1.subtract(ndfi0)

        # Initialize outcomes.
        out_shifted_baseline = baseline.add(CLASSIFICATION_OFFSET)
        out_shifted_deforestation = CLS_DEFORESTED + CLASSIFICATION_OFFSET
        out_shifted_unclassified = CLS_UNCLASSIFIED + CLASSIFICATION_OFFSET
        out_negated_diff = diff.multiply(-1)

        # Start with the diff.
        raw_result = out_negated_diff

        # Mask out improved areas.
        raw_result = raw_result.where(diff.gt(0), out_shifted_baseline)

        # Mask out already deforested areas.
        already_deforested = ndfi0.lt(ALREADY_DEFORESTED_NDFI)
        raw_result = raw_result.where(already_deforested,
                                      out_shifted_deforestation)

        # Mask out pixels that are unknown or not in a large enough forest.
        baseline_segment_size = baseline.connectedPixelCount(MIN_FOREST_SIZE)
        considered = baseline.neq(CLS_BASELINE).And(
            baseline.neq(CLS_UNCLASSIFIED)).And(
            baseline.neq(CLS_OLD_DEFORESTATION)).And(
            ndfi0.neq(INVALID_NDFI)).And(
            ndfi1.neq(INVALID_NDFI)).And(
            baseline_segment_size.gte(MIN_FOREST_SIZE))
        raw_result = raw_result.where(considered.Not(), out_shifted_baseline)

        # Unclassify previously unclassified pixels and small forests.
        cloud_mask = ndfi1.neq(CLS_UNCLASSIFIED)
        mask_segment_size = cloud_mask.connectedPixelCount(MIN_UNMASKED_SIZE)
        to_unclassify = baseline.eq(CLS_FOREST).And(
            baseline_segment_size.gte(MIN_FOREST_SIZE)).And(
            mask_segment_size.lt(MIN_UNMASKED_SIZE))
        result = raw_result.where(to_unclassify, out_shifted_unclassified)

        return result.byte().addBands(baseline)

    def _paint_deforestation(self, asset_id, month, year):
        date = '%04d' % year
        # date = '%04d_%02d' % (year, month)
        table = ee.FeatureCollection(int(settings.FT_TABLE_ID))
        table = table.filterMetadata('type', 'equals', CLS_EDITED_DEFORESTATION)
        table = table.filterMetadata('asset_id', 'contains', date)
        return ee.Image(asset_id).paint(table, CLS_BASELINE)

    def _NDFI_image(self, period, long_span=False):
        base = self._unmixed_mosaic(period, long_span)

        # Calculate NDFI.
        clamped = base.max(0)
        sum = clamped.expression('b("gv") + b("soil") + b("npv")')
        gv_shade = clamped.select('gv').divide(sum)
        npv_plus_soil = clamped.select('npv').add(clamped.select('soil'))
        raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()
        ndfi = raw_ndfi.multiply(100).add(100).byte()
        ndfi = ndfi.where(sum.eq(0), INVALID_NDFI)
        return ndfi.select([0], ['ndfi'])

    def _NDFI_visualize(self, period, long_span=False):
        ndfi = self._NDFI_image(period, long_span)

        # Visualize.
        red = ndfi.interpolate([150, 185], [255, 0], 'clamp')
        green = ndfi.interpolate([  0, 100, 125, 150, 185, 200, 201],
                                 [255,   0, 255, 165, 140,  80,   0], 'clamp')
        blue = ndfi.interpolate([100, 125], [255, 0], 'clamp')
        vis = ee.Image.cat(red, green, blue).round().byte()
        vis = vis.select([0, 1, 2], ['vis-red', 'vis-green', 'vis-blue'])

        # Collect the bands.
        return ee.Image.cat(ndfi, vis, base)

    def _NDFI_period_image_command(self, period, long_span=False):
        """ get NDFI command to get map of NDFI for a period of time """
        return self._NDFI_visualize(period, long_span).getMapId({
            "bands": 'vis-red,vis-green,vis-blue',
            "gain": 1,
            "bias": 0.0,
            "gamma": 1.6
        })

    def _RGB_image_command(self, period):
        """ commands for RGB image """
        return self._kriged_mosaic(period).getMapId({
            'bands': 'sur_refl_b01,sur_refl_b04,sur_refl_b03',
            'gain': 0.1,
            'bias': 0.0,
            'gamma': 1.6
        })

    def _make_mosaic(self, period, long_span=False):
        if long_span:
          start_time = period['end'] - LONG_SPAN_SIZE_MS
          end_time = period['end']
          start_month = time.gmtime(start_time / 1000).tm_mon
          start_year = time.gmtime(start_time / 1000).tm_year
          end_month = time.gmtime(end_time / 1000).tm_mon
          end_year = time.gmtime(end_time / 1000).tm_year
          start = '%04d%02d' % (start_year, start_month)
          end = '%04d%02d' % (end_year, end_month)
          filter = ee.Filter.And(
              ee.Filter.gte('compounddate', start),
              ee.Filter.lte('compounddate', end))
        else:
          start_time = period['start']
          end_time = period['end']
          month = self._getMidMonth(start_time, end_time)
          year = self._getMidYear(start_time, end_time)
          filter = ee.Filter.eq('compounddate', '%04d%02d' % (year, month))

        yesterday = date.today() - timedelta(1)
        micro_yesterday = long(time.mktime(yesterday.timetuple()) * 1000000)
        modis_ga = ee.ImageCollection({
            "id":"MODIS/MOD09GA",
            "version": micro_yesterday
        })
        modis_gq = ee.ImageCollection({
            "id":"MODIS/MOD09GQ", "version": micro_yesterday
        })
        table = ee.FeatureCollection('ft:1zqKClXoaHjUovWSydYDfOvwsrLVw-aNU4rh3wLc')
        table = table.filter(filter)

        return ee.Image({
            "creator": 'SAD/com.google.earthengine.examples.sad.MakeMosaic',
            "args": [modis_ga, modis_gq, table, start_time, period['end']]
        })

    def _SMA_image_command(self, period):
        return self._unmixed_mosaic(period).getMapId({
            "bands": 'gv,soil,npv',
            "gain": 256,
            'bias': 0.0,
            'gamma': 1.6
        })

    def _unmixed_mosaic(self, period, long_span=False):
        BAND_FORMAT = 'sur_refl_b0%d'
        BANDS = [3, 4, 1, 2, 6, 7]
        ENDMEMBERS = [
            [226.0,  710.0,  349.0, 5736.0, 2213.0,  520.0],  # GV
            [838.0, 1576.0, 2527.0, 4305.0, 5885.0, 3760.0],  # Soil
            [696.0, 1235.0, 1841.0, 2763.0, 4443.0, 4232.0]   # NPV
        ]
        OUTPUTS = ['gv', 'soil', 'npv']

        base = self._kriged_mosaic(period, long_span)
        unmixed = base.select([BAND_FORMAT % i for i in BANDS]).unmix(ENDMEMBERS)
        percents = unmixed.max(0).multiply(100).round()
        result = unmixed.addBands(percents)
        return result.select([0, 1, 2, 3, 4, 5],
                             OUTPUTS + [i + '_100' for i in OUTPUTS])

    def _kriged_mosaic(self, period, long_span=False):
        work_month = self._getMidMonth(period['start'], period['end'])
        work_year = self._getMidYear(period['start'], period['end'])
        date = "%04d%02d" % (work_year, work_month)
        krig_filter = ee.Filter.eq('Compounddate', int(date))
        params = ee.FeatureCollection(
            'ft:17Qn-29xy2JwFFeBam5YL_EjsvWo40zxkkOEq1Eo').filter(krig_filter)
        return ee.Image({
            "creator": "kriging/com.google.earthengine.examples.kriging.KrigedModisImage",
            "args": [self._make_mosaic(period, long_span), params]
        })

    def _get_polygon_bbox(self, polygon):
        coordinates = sum(polygon['coordinates'], [])
        lngs = [x[0] for x in coordinates]
        lats = [x[1] for x in coordinates]
        max_lng = max(lngs)
        min_lng = min(lngs)
        max_lat = max(lats)
        min_lat = min(lats)
        return (min_lng, min_lat, max_lng, max_lat)

    def _getMidMonth(self, start, end):
        middle_seconds = int((end + start) / 2000)
        return time.gmtime(middle_seconds).tm_mon

    def _getMidYear(self, start, end):
        middle_seconds = int((end + start) / 2000)
        return time.gmtime(middle_seconds).tm_year


def get_prodes_stats(assetids, table_id):
    results = []
    for assetid in assetids:
        prodes_image, classes = _remap_prodes_classes(ee.Image(assetid))
        collection = ee.FeatureCollection(table_id)
        raw_stats = _get_area_histogram(prodes_image, collection, classes)
        stats = {}
        for raw_stat in raw_stats:
            values = {}
            for class_value in range(max(classes) + 1):
                class_value = str(class_value)
                if class_value in raw_stat:
                    values[class_value] = raw_stat[class_value]['area']
                else:
                    values[class_value] = 0.0
            stats[str(int(raw_stat['name']))] = {
                'values': values,
                'type': 'DataDictionary'
            }
        results.append({'values': stats, 'type': 'DataDictionary'})
    return {'data': {'properties': {'classHistogram': results}}}


def get_thumbnail(landsat_image_id):
    return ee.data.getThumbId({
        'image': ee.Image(landsat_image_id).serialize(False),
        'bands': '30,20,10'
    })


def _get_area_histogram(image, polygons, classes, scale=120):
    area = ee.Image.pixelArea()
    sum_reducer = ee.call('Reducer.sum')

    def calculateArea(feature):
        geometry = feature.geometry()
        total = area.mask(image.mask())
        total_area = total.reduceRegion(
            sum_reducer, geometry, scale, bestEffort=True)
        properties = {'total': total_area}

        for class_value in classes:
            masked = area.mask(image.eq(class_value))
            class_area = masked.reduceRegion(
                sum_reducer, geometry, scale, bestEffort=True)
            properties[str(class_value)] = class_area

        return ee.call('SetProperties', feature, properties)

    result = polygons.map(calculateArea).getInfo()
    return [i['properties'] for i in result['features']]


def _remap_prodes_classes(img):
    """Remaps the values of the first band of a PRODES classification image.

    Uses the metadata fields class_names and class_indexes, taken either from
    the band, or if that's not available, the image. The class names are
    checked against some simple regular expressions to map to the class values
    used by this application.
    """
    RE_FOREST = re.compile(r'^floresta$')
    RE_BASELINE = re.compile(r'^(baseline|d[12]\d{3}.*)$')
    RE_DEFORESTATION = re.compile(r'^desmatamento$')
    RE_DEGRADATION = re.compile(r'^degradacao$')
    RE_CLOUD = re.compile(r'^nuvem$')
    RE_NEW_DEFORESTATION = re.compile(r'^new_deforestation$')
    RE_OLD_DEFORESTATION = re.compile(r'^desmat antigo$')
    RE_EDITED_DEFORESTATION = re.compile(r'^desmat editado$')
    RE_EDITED_DEGRADATION = re.compile(r'^degrad editado$')
    RE_EDITED_OLD_DEGRADATION = re.compile(r'^desmat antigo editado$')

    # Try band metadata first. If not available, use image metadata.
    band_metadata = img.getInfo()['bands'][0].get('properties', {})
    image_metadata = img.getInfo()['properties']
    class_names = band_metadata.get(
        'classes_from', image_metadata.get('class_names'))
    class_names = band_metadata.get(
        'class_indexes', image_metadata.get('class_indexes'))
    classes_to = []

    for src_class, name in zip(classes_from, class_names):
        dst_class = CLS_UNCLASSIFIED

        if RE_FOREST.match(name):
            dst_class = CLS_FOREST
        elif RE_BASELINE.match(name):
            dst_class = CLS_BASELINE
        elif RE_CLOUD.match(name):
            dst_class = CLS_CLOUD
        elif RE_NEW_DEFORESTATION.match(name):
            dst_class = CLS_DEFORESTED
        elif RE_DEFORESTATION.match(name):
            dst_class = CLS_DEFORESTED
        elif RE_DEGRADATION.match(name):
            dst_class = CLS_DEGRADED
        elif RE_OLD_DEFORESTATION.match(name):
            dst_class = CLS_OLD_DEFORESTATION
        elif RE_EDITED_DEFORESTATION.match(name):
            dst_class = CLS_EDITED_DEFORESTATION
        elif RE_EDITED_DEGRADATION.match(name):
            dst_class = CLS_EDITED_DEGRADATION
        elif RE_EDITED_OLD_DEGRADATION.match(name):
            dst_class = CLS_EDITED_OLD_DEGRADATION

        classes_to.append(dst_class)

    remapped = img.remap(classes_from, classes_to, CLS_UNCLASSIFIED)
    final = remapped.mask(img.mask()).select(['remapped'], ['class'])
    return (final, set(classes_to))


def _paint(current_asset, report_id, table, value):
    fc = ee.FeatureCollection(int(table))
    fc = fc.filterMetadata('report_id', 'equals', int(report_id))
    fc = fc.filterMetadata('type', 'equals', value)
    return current_asset.paint(fc, value)


def _get_landsat_toa(start_time, end_time, version=-1):
  collection = ee.ImageCollection({
      'id': 'L7_L1T',
      'version': version
  })
  collection = collection.filterDate(start_time, end_time)
  return collection.map(lambda img: ee.call('LandsatTOA', img))
