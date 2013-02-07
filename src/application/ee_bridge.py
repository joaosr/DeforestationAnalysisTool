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
        return self._mapid2_cmd(asset_id).getMapId({'format': 'png'})

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
        bbox = self._get_polygon_bbox(polygon)
        stats = ee.data.getValue({
            'image': stats_image.stats(NUM_SAMPLES, bbox).serialize(False),
            'fields': ','.join(bands)
        })
        mins = []
        maxs = []
        for band in bands:
          band_stats = stats['properties'][band]['values'];
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
        return ee.data.getValue({
            'image': self._mapid2_cmd(asset_id, polygon, rows, cols).serialize(),
            'fields': 'ndfiSum'
        })

    def _mapid2_cmd(self, asset_id, polygon=None, rows=5, cols=5):
        # Calculate dates.
        year_msec = 1000 * 60 * 60 * 24 * 365
        month_msec = 1000 * 60 * 60 * 24 * 30
        six_months_ago = self.work_period['end'] - month_msec * 6
        one_month_ago = self.work_period['end'] - month_msec
        last_month = time.gmtime(int(six_months_ago / 1000))[1]
        last_year = time.gmtime(int(six_months_ago / 1000))[0]
        previous_month = time.gmtime(int(one_month_ago / 1000))[1]
        previous_year = time.gmtime(int(one_month_ago / 1000))[0]
        work_month = self._getMidMonth(self.work_period['start'], self.work_period['end'])
        work_year = self._getMidYear(self.work_period['start'], self.work_period['end'])
        start = "%04d%02d" % (last_year, last_month)
        end = "%04d%02d" % (work_year, work_month)
        previous = "%04d%02d" % (previous_year, previous_month)

        # Prepare dates.
        t0_start = self.last_period['start'] - year_msec
        t0_end = self.last_period['end']
        t1_start = self.work_period['start']
        t1_end = self.work_period['end']

        # Prepare imagery.
        baseline = self._paint_deforestation(asset_id, work_month, work_year)
        modis_ga = ee.ImageCollection('MODIS/MOD09GA')
        modis_gq = ee.ImageCollection('MODIS/MOD09GQ')

        # Prepare tables.
        inclusions = ee.FeatureCollection('ft:1zqKClXoaHjUovWSydYDfOvwsrLVw-aNU4rh3wLc')
        t0_inclusions = inclusions.filter(
            ee.Filter.And(ee.Filter.gt('compounddate', start),
                          ee.Filter.lt('compounddate', end)))
        t1_inclusions = inclusions.filter(ee.Filter.eq('compounddate', end))

        kriging_params = ee.FeatureCollection(4468280)
        t0_kriging_params = kriging_params.filter(
            ee.Filter.eq('compounddate', int(previous)))
        t1_kriging_params = kriging_params.filter(
            ee.Filter.eq('compounddate', int(end)))

        # Construct the final query.
        return ee.Image({
            "creator":"SAD/com.google.earthengine.examples.sad.GetNDFIDelta",
            "args": [
                t0_start,
                t0_end,
                t1_start,
                t1_end,
                modis_ga,
                modis_gq,
                t0_inclusions,
                t1_inclusions,
                t0_kriging_params,
                t1_kriging_params,
                baseline,
                polygon,
                rows,
                cols
            ]
        })

    def _paint_deforestation(self, asset_id, month, year):
        date = '%04d' % year
        # date = '%04d_%02d' % (year, month)
        table = ee.FeatureCollection(int(settings.FT_TABLE_ID))
        table = table.filterMetadata('type', 'equals', CLS_EDITED_DEFORESTATION)
        table = table.filterMetadata('asset_id', 'contains', date)
        return ee.Image(asset_id).paint(table, CLS_BASELINE)

    def _NDFI_image(self, period, long_span=0):
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

    def _NDFI_visualize(self, period, long_span=0):
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

    def _NDFI_period_image_command(self, period, long_span=0):
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

    def _make_mosaic(self, period, long_span=0):
        middle_seconds = int((period['end'] + period['start']) / 2000)
        this_time = time.gmtime(middle_seconds)
        month = this_time[1]
        year = this_time[0]
        yesterday = date.today() - timedelta(1)
        micro_yesterday = long(time.mktime(yesterday.timetuple()) * 1000000)

        if long_span == 0:
          filter = ee.Filter.eq('compounddate', '%04d%02d' % (year, month))
          start_time = period['start']
        else:
          start = '%04d%02d' % (year - 1, month)
          end = '%04d%02d' % (year, month)
          filter = ee.Filter.And(
              ee.Filter.gt('compounddate', start),
              ee.Filter.lte('compounddate', end))
          start_time = period['start'] - 1000 * 60 * 60 * 24 * 365

        ga = ee.ImageCollection({"id":"MODIS/MOD09GA", "version": micro_yesterday})
        gq = ee.ImageCollection({"id":"MODIS/MOD09GQ", "version": micro_yesterday})
        table = ee.FeatureCollection('ft:1zqKClXoaHjUovWSydYDfOvwsrLVw-aNU4rh3wLc')
        table = table.filter(filter)

        return ee.Image({
            "creator": 'SAD/com.google.earthengine.examples.sad.MakeMosaic',
            "args": [ga, gq, table, start_time, period['end']]
        })

    def _SMA_image_command(self, period):
        return self._unmixed_mosaic(period).getMapId({
            "bands": 'gv,soil,npv',
            "gain": 256,
            'bias': 0.0,
            'gamma': 1.6
        })

    def _unmixed_mosaic(self, period, long_span=0):
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

    def _kriged_mosaic(self, period, long_span=0):
        work_month = self._getMidMonth(period['start'], period['end'])
        work_year = self._getMidYear(period['start'], period['end'])
        date = "%04d%02d" % (work_year, work_month)
        krig_filter = ee.Filter.eq('Compounddate', int(date))
        return ee.Image({
            "creator": "kriging/com.google.earthengine.examples.kriging.KrigedModisImage",
            "args": [
                self._make_mosaic(period, long_span),
                {
                    'type': 'FeatureCollection',
                    'table_id': 4468280,
                    'filter': json.loads(krig_filter.serialize()),
                    'mark': str(timestamp())
                }
            ]
        })

    def _get_polygon_bbox(self, polygon):
        coordinates = sum(polygon['coordinates'], [])
        lngs = [x[0] for x in coordinates]
        lats = [x[1] for x in coordinates]
        max_lng = max(lngs)
        min_lng = min(lngs)
        max_lat = max(lats)
        min_lat = min(lats)
        return ee.Feature.Rectangle(min_lng, min_lat, max_lng, max_lat)

    def _getMidMonth(self, start, end):
        middle_seconds = int((end + start) / 2000)
        this_time = time.gmtime(middle_seconds)
        return this_time[1]

    def _getMidYear(self, start, end):
        middle_seconds = int((end + start) / 2000)
        this_time = time.gmtime(middle_seconds)
        return this_time[0]


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
