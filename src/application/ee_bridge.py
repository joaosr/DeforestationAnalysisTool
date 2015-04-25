# -*- coding: utf-8 -*-

"""A set of EE API calls that compute deforestation statistics."""

# pylint: disable-msg=bad-indentation
# pylint: disable-msg=g-line-too-long
# pylint: disable-msg=g-continuation-in-parens-misaligned
# pylint: disable-msg=g-bad-name
# pylint: disable-msg=g-wrong-space
# pylint: disable-msg=g-illegal-space


import ast
import datetime
import logging
import re
import time

from google.appengine.api import users
from yaml import tokens

from application.models import Report, Baseline, ImagePicker, Downscalling, Tile, \
    TimeSeries, CellGrid
import ee
import settings


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
CLASSES_COUNT = 10


# Values that signify maximum and invalid NDFI.
MAX_NDFI = 200
INVALID_NDFI = MAX_NDFI + 1

# The length of a "long" time period in milliseconds.
LONG_SPAN_SIZE_MS = 1000 * 60 * 60 * 24 * 30 * 9


# MODIS projection specification.
MODIS_CRS = 'SR-ORG:6974'
MODIS_WIDTH = 20015100
MODIS_CELLS = 18
MODIS_250_SCALE = 231.65635681152344
MODIS_TRANSFORM = [
    MODIS_250_SCALE, 0, -8895720,
    0, -MODIS_250_SCALE, 1112066.375
]

# The ID of the Fusion Table containing the selected MODIS days for each month.
MODIS_INCLUSIONS_TABLE = 'ft:1zqKClXoaHjUovWSydYDfOvwsrLVw-aNU4rh3wLc'
# The ID of the Fusion Table containing kriging parameters.
KRIGING_PARAMS_TABLE = 'ft:17Qn-29xy2JwFFeBam5YL_EjsvWo40zxkkOEq1Eo'


class Stats(object):
    """A class for calculating deforestation/degradation area stats."""
    DEFORESTATION = CLS_EDITED_DEFORESTATION
    DEGRADATION = CLS_EDITED_DEGRADATION

    def get_stats_for_polygon(self, reports, polygon):
        """Computes deforestation area stats for a polygon on multiple images.

        Args:
          reports: A list of reports, each report a tuple of a numeric
                   report ID (used to filter the rows of the table
                   specified by settings.FT_TABLE_ID) and a string image ID.
          polygon: The coordinates of the polygon to use. Must be wound in a
              counter-clockwise order. Example:
              [[[-62,-11],[-62,-12],[-61,-12],[-61,-11]]]

        Returns:
          A list of stats, one for each entry in reports, in the same order.
          Each stats item includes:
            total_area: total classified polygon area in square km.
            def: total deforested area in square km.
            deg: total degradation area in square km.
        """
        feature = ee.Feature(ee.Feature.Polygon(polygon), {'name': 'myPoly'})
        polygons = ee.FeatureCollection([ee.Feature(feature)])

        report_stats = []
        for report_id, asset_id in reports:
            result = self._get_area(report_id, asset_id, polygons)
            if result is None: return None
            report_stats.append(result[0])

        stats = []
        for x in report_stats:
            stats.append({
                'total_area': x['total'] * METER2_TO_KM2,
                'def': x[str(Stats.DEFORESTATION)] * METER2_TO_KM2,
                'deg': x[str(Stats.DEGRADATION)] * METER2_TO_KM2,
            })
        return stats

    def get_stats(self, report_id, frozen_image, table_id):
        """Computes deforestation area stats for a given report.

        Args:
          report_id: The report ID, an integer. This is used to filter the
              rows of the table specified by settings.FT_TABLE_ID.
          frozen_image: The ID of the baseline image.
          table_id: The numeric ID of the Fusion Table containing the polygons
              to analyse.

        Returns:
          A dictionaty from polygon ID (<table_id>_<name>) to its stats,
          which include:
            table: the ID of the input table.
            id: the "name" column for this row in the table.
            total_area: total classified polygon area in square km.
            def: total deforested area in square km.
            deg: total degradation area in square km.
        """
        result = self._get_area(
            report_id, frozen_image, ee.FeatureCollection(int(table_id)))
        if result is None: return None
        stats = {}
        for row in result:
            name = row['name']
            if isinstance(name, float): name = int(name)
            stats['%s_%s' % (table_id, name)] = {
                'id': str(name),
                'table': table_id,
                'total_area': row['total'] * METER2_TO_KM2,
                'def': row[str(Stats.DEFORESTATION)] * METER2_TO_KM2,
                'deg': row[str(Stats.DEGRADATION)] * METER2_TO_KM2,
            }

        return stats

    def _get_historical_freeze(self, report_id, frozen_image):
        """Paints deforestation onto an image.

        Args:
          report_id: The report ID, a number. Used to filter the
              rows of the table specified by settings.FT_TABLE_ID.
          frozen_image: A single-bane baseline ee.Image to paint onto.

        Returns:
          The input ee.Image with its band renamed to "class" if needed
          and with deforestation and degradation painted.
        """
        # Remap CLS_EDITED_DEFORESTATION and CLS_EDITED_DEGRADATION to CLS_FOREST.
        remapped = frozen_image.remap([0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                      [0, 1, 2, 3, 4, 5, 6, 1, 1, 9])
        def_image = _paint(remapped, settings.FT_TABLE_ID, report_id,
                           Stats.DEFORESTATION)
        deg_image = _paint(def_image, settings.FT_TABLE_ID, report_id,
                           Stats.DEGRADATION)
        return deg_image.select(['remapped'], ['class'])

    def _get_area(self, report_id, image_id, polygons):
        """Computes the deforestation and degradation for each polygon.

        Args:
          report_id: The report ID, a number. Used to filter the
              rows of the table specified by settings.FT_TABLE_ID.
          image_id: The string ID od a single-band image with class-valued
              pixels.
          polygons: An ee.FeatureCollection of polygons to analyse.

        Returns:
          A list of dictionaries, one for each polygon in the polygons
          collection in the same order as they are returned from the collection.
          Each dictionary has three entries keyed by "total",
          Stats.DEFORESTATION and Stats.DEGRADATION, specifying the area in
          square meters of each.
        """
        freeze = self._get_historical_freeze(report_id, ee.Image(image_id))
        return _get_area_histogram(
            freeze, polygons, [Stats.DEFORESTATION, Stats.DEGRADATION])


class EELandsat(object):
    """A helper for accessing Landsat 7 images."""
    LANDSAT5 = 'L5_L1T_SR'
    LANDSAT7 = 'LE7_L1T_SR'
    LANDSAT8 = 'LC8_L1T'
    SENSORS  = [LANDSAT5, LANDSAT7, LANDSAT8]

    def __init__(self, start, end, sensor=''):
        self.start = start
        self.end = end
        self.sensor = sensor

    def list(self, bounds):
        """Returns a list of IDs of Landsat 7 images intersecting a given area.

        Args:
          bounds: The bounding box to intersect, a comma-separated string.
              E.g.: "110,60,120,70"

        Returns:
          A list of ID strings.
        """
        bbox = ee.Feature.Rectangle(
            *[float(i.strip()) for i in bounds.split(',')])
        # NOTE: Can technically use LE7_L1T, but then we'll get IDs without the
        # "LANDSAT/" base, and that confuses some of the callers.
        images = ee.ImageCollection('LANDSAT/LE7_L1T').filterBounds(bbox).getInfo()
        if 'features' in images:
            return [x['id'] for x in images['features']]
        return []

    @staticmethod
    def from_class(map_image):
        for a in EELandsat.SENSORS:
            if a == map_image:
                return True

        return False

    @staticmethod
    def get_image_bands(map_image):
        logging.info("=========>>>>> Sensor: "+map_image)

        if map_image == EELandsat.LANDSAT5:
            return {'bands': ['B5', 'B4', 'B3'], 'gain': ['0.08', '0.05', '0.08']}
        elif map_image == EELandsat.LANDSAT7:
            return {'bands': ['B5', 'B4', 'B3'], 'gain': ['0.08', '0.05', '0.08']}
        elif map_image == EELandsat.LANDSAT8:
            return {'bands': ['B7', 'B5', 'B4'], 'gain': ['0.013','0.009','0.013']}

    def find_mapid_from_sensor(self, bound=None):
        PREVIEW_GAIN = 500

        map_image_bands = self.get_image_bands().get('bands')

        image = self.find_map_image(bound)

        if image:
           return _get_raw_mapid(image.getMapId({
               'bands': ','.join(map_image_bands),
               'gain': PREVIEW_GAIN
            }))
        else:
           return _get_raw_mapid(None)

    def get_thumbs(self, tiles, bounds=None):
        results = {}

        for tile in tiles:
            MAX_ERROR_METERS = 30.0
            thumbs_info = []
            tile = tile.replace("_","/")
            cloud_cover = tiles[tiles.keys()[0]]
            region = Tile.find_geo_region(tile)
            region = ee.Geometry.Polygon(region)
    
            feature = ee.Feature(region)
            region = feature.bounds(MAX_ERROR_METERS)
            reprojected = ee.data.getValue({'json': feature.serialize()})['geometry']['coordinates']
    
            collections = self.find_image_tile_from_all_sensors(tile, cloud_cover)
    
            for i in range(len(collections)):
                images = collections[i].getInfo().get('features')
        
                for j in range(len(images)):
                    map_image = images[j].get('id').split('/')[0]
                    logging.info(map_image)
                    result = ee.data.getThumbId({
                        'image': ee.Image(images[j].get('id')).serialize(False),
                        'bands': ','.join(EELandsat.get_image_bands(map_image).get('bands')),
                        'region': reprojected,     
                        'gain': ','.join(EELandsat.get_image_bands(map_image).get('gain'))                         
                    })
        
                    date = images[j].get('properties').get('DATE_ACQUIRED') 
        
                    thumbs_info.append({'thumb': result['thumbid'], 'token': result['token'], 'date': date, 'map_image': map_image, 'tile': tile.replace("/","_")})
                    
                results[tile] = thumbs_info

        return results

    def find_map_image(self, bounds=None):

        image = self.find_map_collection(bounds)

        if image:
           return image.mosaic()
        else:
           return None
    
    @staticmethod
    def find_collection_tile(sensor, tile, start_date, end_date=None):
        wrs_path =  tile.split('/')[0];
        wrs_row =  tile.split('/')[1];
        
        if end_date:
            collection = ee.ImageCollection(sensor).filterMetadata('WRS_PATH', 'equals', int(wrs_path)).filterMetadata('WRS_ROW', 'equals', int(wrs_row)).filterDate(start_date, end_date)
        else:
            collection = ee.ImageCollection(sensor).filterMetadata('WRS_PATH', 'equals', int(wrs_path)).filterMetadata('WRS_ROW', 'equals', int(wrs_row)).filterMetadata('DATE_ACQUIRED', 'equals', start_date)
        
        return collection
       
    def find_image_tile_from_all_sensors(self, tile, cloud_cover=30):        
        wrs_path =  tile.split('/')[0];
        wrs_row =  tile.split('/')[1];
        collections = []
                 
        collection_l8 = ee.ImageCollection(EELandsat.LANDSAT8).filterMetadata('WRS_PATH', 'equals', int(wrs_path)).filterMetadata('WRS_ROW', 'equals', int(wrs_row)).filterDate(self.start, self.end).filterMetadata('CLOUD_COVER', 'less_than', int(cloud_cover))
        
        size_l8 = len(collection_l8.getInfo().get('features'))        
        
        if size_l8 > 0:
            collections.append(collection_l8)
        
        collection_l7 = ee.ImageCollection(EELandsat.LANDSAT7).filterMetadata('WRS_PATH', 'equals', int(wrs_path)).filterMetadata('WRS_ROW', 'equals', int(wrs_row)).filterDate(self.start, self.end).filterMetadata('CLOUD_COVER', 'less_than', int(cloud_cover))
        
        
        size_l7 = len(collection_l7.getInfo().get('features'))        
         
        if size_l7 > 0: 
            collections.append(collection_l7)
        
        collection_l5 = ee.ImageCollection(EELandsat.LANDSAT5).filterMetadata('WRS_PATH', 'equals', int(wrs_path)).filterMetadata('WRS_ROW', 'equals', int(wrs_row)).filterDate(self.start, self.end).filterMetadata('CLOUD_COVER', 'less_than', int(cloud_cover))
        
        size_l5 = len(collection_l5.getInfo().get('features'))
        
        if size_l5 > 0: 
            collections.append(collection_l5)
           
                
        return collections
    
    def find_image_tile_from_L5(self, tile, cloud_cover=30):
        wrs_path =  tile.split('/')[0];
        wrs_row =  tile.split('/')[1];        
          
        collection = ee.ImageCollection(EELandsat.LANDSAT5).filterMetadata('WRS_PATH', 'equals', int(wrs_path)).filterMetadata('WRS_ROW', 'equals', int(wrs_row)).filterDate(self.start, self.end).filterMetadata('CLOUD_COVER', 'less_than', int(cloud_cover))
          
        return collection
        

    def find_map_collection(self, bounds=None):

        if bounds:
            bbox = ee.Geometry.Rectangle(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))
            collection = ee.ImageCollection(self.sensor)
            collection = collection.filterDate(self.start, self.end).filterBounds(bbox)
        else:
            collection = ee.ImageCollection(self.sensor)
            collection = collection.filterDate(self.start, self.end)

        collection_size = len(collection.getInfo().get('features'))

        logging.info("==========>>> Collections: "+str(collection_size))

        if collection_size != 0:
           return collection
        else:
           return None
       
    def find_full_map_collection(self, bounds=None):

        if bounds:
            bbox = ee.Geometry.Rectangle(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))
            collection = ee.ImageCollection(self.sensor)
            collection = collection.filterDate(self.start, self.end).filterBounds(bbox)
        else:
            collection = ee.ImageCollection(self.sensor)
            collection = collection.filterDate(self.start, self.end)

        if collection:
           return collection
        else:
           return None


    def mapid(self, start, end):
        """Returns a Map ID for a Landsat 7 TOA mosaic for a given time period.

        Args:
          start: The start of the time period as a Unix timestamp.
          end: The end of the time period as a Unix timestamp.

        Returns:
          A dictionary containing "mapid" and "token".
        """
        MAP_IMAGE_BANDS = ['B3', 'B2', 'B1']
        PREVIEW_GAIN = 500
        return _get_raw_mapid(_get_landsat_toa(start, end).mosaic().getMapId({
            'bands': ','.join(MAP_IMAGE_BANDS),
            'gain': PREVIEW_GAIN
        }))

    def mapid_landsat8(self, start, end):
        MAP_IMAGE_BANDS = ['B4', 'B3', 'B2']
        PREVIEW_GAIN = 500
        return _get_raw_mapid(_get_landsat8(start, end).mosaic().getMapId({
            'bands': ','.join(MAP_IMAGE_BANDS),
            'gain': PREVIEW_GAIN
        }))

class SMA(object):
    LANDSAT5_T0 = 'SMA T0 (L5_L1T_SR)'
    LANDSAT5_T1 = 'SMA T1 (L5_L1T_SR)'
    LANDSAT7_T0 = 'SMA T0 (LE7_L1T_SR)'
    LANDSAT7_T1 = 'SMA T1 (LE7_L1T_SR)'
    LANDSAT8_T0 = 'SMA T0 (LC8_L1T)'
    LANDSAT8_T1 = 'SMA T1 (LC8_L1T)'
    MODIS_T0    = 'SMA T0 (MODIS)'
    MODIS_T1    = 'SMA T1 (MODIS)'
    SENSORS     = [LANDSAT5_T0, LANDSAT5_T1, LANDSAT7_T0, LANDSAT7_T1, LANDSAT8_T0, LANDSAT8_T1, MODIS_T0, MODIS_T1]

    def __init__(self, last_period, work_period, map_image):
        self.last_period = dict(start=last_period[0], end=last_period[1])
        self.work_period = dict(start=work_period[0], end=work_period[1])
        self.map_image   = map_image
        self.name_sensor = re.findall(r'\((.*?)\)', map_image)[0]

        if 'T0' in self.map_image:
            self.start_time = datetime.datetime.fromtimestamp(self.last_period['start'] / 1e3).strftime("%Y-%m-%d")
            self.start_time = datetime.datetime.strptime(self.start_time, "%Y-%m-%d")
            self.end_time   = datetime.datetime.fromtimestamp(self.last_period['end'] / 1e3).strftime("%Y-%m-%d")
            self.end_time = datetime.datetime.strptime(self.end_time, "%Y-%m-%d")
            
        elif 'T1' in self.map_image:
            self.start_time = datetime.datetime.fromtimestamp(self.work_period['start'] / 1e3).strftime("%Y-%m-%d")
            self.start_time = datetime.datetime.strptime(self.start_time, "%Y-%m-%d")
            self.end_time   = datetime.datetime.fromtimestamp(self.work_period['end'] / 1e3).strftime("%Y-%m-%d")
            self.end_time = datetime.datetime.strptime(self.end_time, "%Y-%m-%d")
                        
            
        #logging.info(self.start_time.strftime("%Y-%m-%d")+' === TIME === '+self.end_time.strftime("%Y-%m-%d"))

    @staticmethod
    def from_class(map_image):
        for a in SMA.SENSORS:
            if a == map_image:
                return True

        return False

    def find_mapid_from_sensor(self, bounds=None):
        image = self.find_map_unmixed(bounds)

        if image:
            if EELandsat.from_class(self.name_sensor):
                return _get_raw_mapid(image.getMapId({
                    'bands': ','.join(EELandsat.get_image_bands(self.name_sensor).get('bands')),
                    'gain': 500
                }))
            else:
                return _get_raw_mapid(image.getMapId({
                    'bands': 'gv,soil,npv',
                    'gain': 256,
                    'bias': 0.0,
                    'gamma': 1.6
                }))
        else:
            return _get_raw_mapid(None)

    def find_map_unmixed(self, bounds=None, long_span=False):
        initial_map = ''
        sma_map     = ''

        if EELandsat.from_class(self.name_sensor):
            sensor = EELandsat(self.start_time, self.end_time, self.name_sensor)
            initial_map = sensor.find_map_image(bounds)
            if initial_map:
                sma_map     = self._unmixed_landsat(initial_map)
            else:
                return None
        else:
            sma_map = self._unmixed_modis(long_span)


        return sma_map

    def _unmixed_landsat(self, image):
        ENDMEMBERS = [
                      [ 119.0,  475.0,  169.0, 6250.0, 2399.0,  675.0], #GV
                      [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0], #NPV
                      [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0], #SOIL
                      [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0]  #CLOUD
                    ]

        """periodo = '' #['2001-01-01', '2001-02-01']
        if self.start_time == 1409529600000:
            logging.info("Start: "+str(self.start_time))
            periodo = ['2011-05-01', '2011-06-01']
        else:
            logging.info("End: "+str(self.end_time))
            periodo = ['2011-06-01', '2011-07-01']"""

        unmixed = ee.Image(image).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)

        return unmixed

    def _unmixed_modis(self, long_span=False):
        """Returns a mosaic with GV, SOIL and NPV indices based on MODIS.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with the following bands:
          0. gv: float, valid in [0, 1] but may contain negative values.
          1. soil: float, valid in [0, 1] but may contain negative values.
          2. npv: float, valid in [0, 1] but may contain negative values.
          3. gv_100: int, in [0, 100].
          4. soil_100: int, in [0, 100].
          5. npv_100: int, in [0, 100].

          The last 3 bands are integer percentage versions of the first 3,
          with any negative values clamped to 0.
        """
        BAND_FORMAT = 'sur_refl_b0%d'
        BANDS = [3, 4, 1, 2, 6, 7]
        ENDMEMBERS = [
            [226.0,  710.0,  349.0, 5736.0, 2213.0,  520.0],  # GV
            [838.0, 1576.0, 2527.0, 4305.0, 5885.0, 3760.0],  # Soil
            [696.0, 1235.0, 1841.0, 2763.0, 4443.0, 4232.0]   # NPV
        ]
        OUTPUTS = ['gv', 'soil', 'npv']

        base = self._kriged_mosaic(long_span)
        unmixed = base.select([BAND_FORMAT % i for i in BANDS]).unmix(ENDMEMBERS)
        result = unmixed.expression('addBands(b(0,1,2), round(max(b(0,1,2), 0) * 100))')
        return result.select(['.*'], OUTPUTS + [i + '_100' for i in OUTPUTS])

    def _kriged_mosaic(self, long_span=False):
        """Returns an upscaled MODIS mosaic for a given period.

        See _make_mosaic() for details on how the mosaic images are selected.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with the following bands:
          0. sur_refl_b01_250m
          1. sur_refl_b02_250m
          2. sur_refl_b05_500m
          3. sur_refl_b03_250m
          4. sur_refl_b04_250m
          5. sur_refl_b06_250m
          6. sur_refl_b07_250m
        """
        work_month = self._getMidMonth(self.start_time, self.end_time)
        work_year = self._getMidYear(self.start_time, self.end_time)
        date = '%04d%02d' % (work_year, work_month)
        krig_filter = ee.Filter.eq('Compounddate', int(date))
        params = ee.FeatureCollection(KRIGING_PARAMS_TABLE).filter(krig_filter)
        mosaic = self._make_mosaic(long_span)
        return ee.Algorithms.SAD.KrigeModis(mosaic, params)

    def _make_mosaic(self, long_span=False):
        """Returns a mosaic of MODIS images for a given period.

        This selects images from the MODIS GA and GQ collections, filtered to
        the specified time range, based on an inclusions table.

        The inclusions table lists the days to include in the mosaic for each
        month, for each MODIS tile. Currently it is a Fusion Table specified
        by MODIS_INCLUSIONS_TABLE, with a row for each (month, modis tile).
        Each row has a geometry of the tile and a comma-separated list of day
        numbers to include in the mosaic.

        Rows that do not have a corresponding image in each collection are
        skipped. If no features overlap an output pixel, we'll fall back on a
        composite constructed from the week of images preceding the period end.

        Args:
          period: The mosaic period, as a dictionary with "start" and "end",
              keys, both containing Unix timestamps.
          long_span: Whether to use an extended period.
              If False, the period is used as is and only the month at the
              midpoint of the period range is used to select from the
              inclusions table.
              If True, the start of the specified period is ignored and a new
              start is computed by extending the end of the period back by
              LONG_SPAN_SIZE_MS milliseconds.

        Returns:
          An ee.Image with the following bands:
          0. num_observations_1km
          1. state_1km
          2. sur_refl_b01_500m
          3. sur_refl_b02_500m
          4. sur_refl_b03_500m
          5. sur_refl_b04_500m
          6. sur_refl_b05_500m
          7. sur_refl_b06_500m
          8. sur_refl_b07_500m
          9. sur_refl_b01_250m
          10. sur_refl_b02_250m
          11. num_observations_250m
        """

        # Calculate the time span.
        if long_span:
          start_time = self.end_time - LONG_SPAN_SIZE_MS
          end_time = self.end_time
          start_month = time.gmtime(start_time / 1000).tm_mon
          start_year = time.gmtime(start_time / 1000).tm_year
          end_month = time.gmtime(end_time / 1000).tm_mon
          end_year = time.gmtime(end_time / 1000).tm_year
          start = '%04d%02d' % (start_year, start_month)
          end = '%04d%02d' % (end_year, end_month)
          inclusions_filter = ee.Filter.And(
              ee.Filter.gte('compounddate', start),
              ee.Filter.lte('compounddate', end))
        else:
          start_time = self.start_time
          end_time = self.end_time
          month = self._getMidMonth(start_time, end_time)
          year = self._getMidYear(start_time, end_time)
          inclusions_filter = ee.Filter.eq(
              'compounddate', '%04d%02d' % (year, month))

        # Prepare source image collections.
        modis_ga = ee.ImageCollection('MODIS/MOD09GA').filterDate(start_time, end_time)
        modis_gq = ee.ImageCollection('MODIS/MOD09GQ').filterDate(start_time, end_time)

        # Prepare the inclusions table.
        inclusions = ee.FeatureCollection(MODIS_INCLUSIONS_TABLE)
        inclusions = inclusions.filter(inclusions_filter)

        object1 = ee.call(
          'SAD/com.google.earthengine.examples.sad.MakeMosaic',
          modis_ga, modis_gq, inclusions, start_time, end_time)

        #logging.info("Make MOsaic: "+str(object1))

        return object1

    def _getMidMonth(self, start, end):
        """Returns the month part of the midpoint of two Unix timestamps."""
        middle_seconds = int((end + start) / 2000)
        return time.gmtime(middle_seconds).tm_mon

    def _getMidYear(self, start, end):
        """Returns the year part of the midpoint of two Unix timestamps."""
        middle_seconds = int((end + start) / 2000)
        return time.gmtime(middle_seconds).tm_year


class NDFI(object):
    """A helper for computing NDFI status on MODIS image over a time period."""
    MODIS_NAME = 'MODIS'
    LANDSAT5_T0 = 'NDFI T0 (L5_L1T_SR)'
    LANDSAT5_T1 = 'NDFI T1 (L5_L1T_SR)'
    LANDSAT7_T0 = 'NDFI T0 (LE7_L1T_SR)'
    LANDSAT7_T1 = 'NDFI T1 (LE7_L1T_SR)'
    LANDSAT8_T0 = 'NDFI T0 (LC8_L1T)'
    LANDSAT8_T1 = 'NDFI T1 (LC8_L1T)'
    MODIS_T0    = 'NDFI T0 (MODIS)'
    MODIS_T1    = 'NDFI T1 (MODIS)'

    def __init__(self, last_period, work_period):
        """Construct an NDFI helper for comparing to periods.

        Args:
          last_period: The old period, as a 2-tuple of Unix timestamps.
          work_period: The new period, as a 2-tuple of Unix timestamps.
        """
        self.last_period = dict(start=last_period[0], end=last_period[1])
        self.work_period = dict(start=work_period[0], end=work_period[1])

    def _define_period(self, map_image):

        if 'T0' in map_image:
            self.start_time = self.last_period['start']
            self.end_time   = self.last_period['end']
            self.long_span  = True
        elif 'T1' in map_image:
            self.start_time = self.work_period['start']
            self.end_time   = self.work_period['end']
            self.long_span  = False

    @staticmethod
    def from_class(map_image):

        if (NDFI.LANDSAT5_T0 or NDFI.LANDSAT5_T1 or NDFI.LANDSAT7_T0 or NDFI.LANDSAT7_T1 or NDFI.LANDSAT8_T0 or NDFI.LANDSAT8_T1 or NDFI.MODIS_T0 or NDFI.MODIS_T1) in map_image:
            return True
        else:
            return False

    def find_mapid_from_sensor(self, map_image, bounds=None):

        image = self._ndfi_image_rgb(map_image, bounds)

        if EELandsat.from_class(map_image):
            return _get_raw_mapid(image.getMapId({
                 'bands': ','.join(EELandsat.get_image_bands(map_image).get('bands')),
                 'gain': 500
            }))
        else:
            return _get_raw_mapid(image.getMapId({
                'bands': 'gv,soil,npv',
                'gain': 256,
                'bias': 0.0,
                'gamma': 1.6
            }))

    def _ndfi_image_rgb(self, map_image, bounds):
        """Returns an RGB visualization of an NDFI mosaic for a given period.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with 3 byte bands, vis-red, vis-green, vis-blue.
        """
        ndfi = self._ndfi_image(map_image, bounds)

        red = ndfi.interpolate([150, 185], [255, 0], 'clamp')
        green = ndfi.interpolate([  0, 100, 125, 150, 185, 200, 201],
                                 [255,   0, 255, 165, 140,  80,   0], 'clamp')
        blue = ndfi.interpolate([100, 125], [255, 0], 'clamp')

        rgb = ee.Image.cat(red, green, blue).round().byte()

        return rgb.select([0, 1, 2], ['vis-red', 'vis-green', 'vis-blue'])

    def _ndfi_image(self, map_image, bounds):

        """Returns an NDFI mosaic based on MODIS for a given period.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with a single integer band called "ndfi", ranging from
          0 (no GV) to 200 (all GV), plus the special INVALID_NDFI value (201),
          which indicates that the unmixed values were out of range.
        """
        base = 0
        clamped_expression = ''
        gv = ''
        npv = ''
        soil = ''

        if EELandsat.from_class(map_image):
            clamped_expression = 'b(0) + b(1) + b(2) + b(3)'
            gv = 0
            npv = 1
            soil = 2
        else:
            clamped_expression = 'b("gv") + b("soil") + b("npv")'
            gv = 'gv'
            npv = 'npv'
            soil = 'soil'

        sma = SMA(self.work_period, self.last_period)
        base = sma.find_map_unmixed(map_image, bounds, self.long_span)
        clamped = base.max(0)

        summed = clamped.expression(clamped_expression)
        gv_shade = clamped.select(gv).divide(summed)
        npv_plus_soil = clamped.select(npv).add(clamped.select(soil))

        raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()

        ndfi = raw_ndfi.multiply(100).add(100).byte()
        ndfi = ndfi.where(summed.eq(0), INVALID_NDFI)

        return ndfi.select([0], ['ndfi'])

    def mapid2(self, asset_id, sensor):
        """Returns a Map ID for a visualization of the NDFI difference between last_period and work_period."""
        return _get_raw_mapid(
		#self._ndfi_change(asset_id, sensor).getMapId({'format': 'png'}))
            self._ndfi_delta(asset_id, sensor).getMapId({'format': 'png'}))


    def rgb0id(self):
        """Returns a Map ID for the RGB visualization of a MODIS mosaic for last_period."""
        return self._RGB_image_command(self.last_period, True)

    def rgb1id(self):
        """Returns a Map ID for the RGB visualization of a MODIS mosaic for work_period."""
        return self._RGB_image_command(self.work_period)

    def ndfi0id(self, sensor):
        """Returns a Map ID for the RGB visualization of a MODIS NDFI mosaic for last_period."""
        ndfi = self._NDFI_period_image_command(self.last_period, sensor,True)
        return ndfi

    def ndfi1id(self, sensor):
        """Returns a Map ID for the RGB visualization of a MODIS NDFI mosaic for work_period."""
        return self._NDFI_period_image_command(self.work_period, sensor)

    def smaid(self):
        """Returns a Map ID for the NDFI SMA image for work_period."""
        return self._SMA_image_command(self.work_period)

    def baseline(self, asset_id):
        """Returns a Map ID for the given classification asset, masked to only show CLS_BASELINE areas."""
        classification = ee.Image(asset_id).select(0)
        return _get_raw_mapid(
            classification.mask(classification.eq(CLS_BASELINE)).getMapId())

    def freeze_map(self, asset_id, table_id, report_id):
        """Saves a new baseline image as an asset.

        Args:
          asset_id: The ID of the baseline PRODES image.
          table_id: The numeric ID of the Fusion Table containing the report
              polygons.
          report_id: The report ID, an integer. This is used to filter the
              rows of the specified table.

        Returns:
          A description of the saved image which includes an ID.
        """
        result = self._make_map_to_freeze(asset_id, table_id, report_id)
        return ee.data.createAsset(result.serialize(False))

    def rgb_stretch(self, polygon, sensor, bands, std_devs=2):
        """Returns a Map ID for a stretched mosaic visualized as RGB.

        Args:
          polygon: The GeoJSON polygon describing the region that will be
              visualized. The stats for this region will be used to calculate
              the stretch ranges.
          sensor: The type of mosaic, either "landsat" or "modis".
          bands: The three band numbers to use. For sensor="modis", the valid
              values are 1,2,3,4,5,6,7. For sensor="landsat", the valid values
              are B1, B2, B3, B4, B5, B6_VCID_1, B6_VCID_2, B7, B8
          std_devs: The number of standard deviations from the mean to stretch.
              Defaults to 2.

        Returns:
          The Map ID for the stretched RGB image.

        Raises:
          RuntimeError: If a sensor other than "landsat" or "modis" is specified.
        """
        NUM_SAMPLES = 10 ** 6
        RGB_BANDS = ['vis-red', 'vis-green', 'vis-blue']

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
            bands = ['B%d' % i for i in bands]
            yesterday = datetime.date.today() - datetime.timedelta(1)
            collection = _get_landsat_toa(
                self.work_period['start'] - 3 * 30 * 24 * 60 * 60 * 1000,
                self.work_period['end'],
                int(time.mktime(yesterday.timetuple()) * 1000000))
            stats_image = display_image = collection.mosaic()
        else:
            raise RuntimeError('Sensor %s neither modis nor landsat.' % sensor)
        stats_image = stats_image.select(bands, RGB_BANDS)
        display_image = display_image.select(bands, RGB_BANDS)

        # Calculate stats.
        bbox = ee.Feature.Rectangle(*self._get_polygon_bbox(polygon))
        stats = ee.data.getValue({
            'image': stats_image.stats(NUM_SAMPLES, bbox).serialize(False),
            'fields': ','.join(RGB_BANDS)
        })
        mins = []
        maxs = []
        for band in RGB_BANDS:
            band_stats = stats['properties'][band]['values']
            min_value = band_stats['mean'] - std_devs * band_stats['total_sd']
            max_value = band_stats['mean'] + std_devs * band_stats['total_sd']
            if min_value == max_value:
                min_value -= 1
                max_value += 1
            mins.append(min_value)
            maxs.append(max_value)

        # Get stretched image.
        return _get_raw_mapid(display_image.clip(polygon).getMapId({
            'bands': ','.join(RGB_BANDS),
            'min': ','.join(str(i) for i in mins),
            'max': ','.join(str(i) for i in maxs)
        }))

    def ndfi_change_value(self, asset_id, polygon, rows=5, cols=5):
        """Calculates NDFI delta stats between two periods in a given polygon.

        This method splits the supplied polygon using a grid specified by the
        rows and cols parameters, then for each cell, computes the number of
        valid pixels and the total NDFI of all those pixels.

        Args:
          asset_id: The string ID of the baseline classification image. Should
              have one band whose values are the CLS_* constants defined in
              this file.
          polygon: The GeoJSON polygon to analyse.
          rows: The number of rows to divide the polygon into.
          cols: The number of columns to divide the polygon into.

        Returns:
          The counts and sums of NDFI pixels for each cell in row-major order.
          For backward-compatibility, returned in the awkward old EE format.
          Example:
          {
            "properties": {
              "ndfiSum": {
                "type": "DataDictionary",
                "values": {
                  "count": [0, 0, 42, 1, 30, 12],
                  "sum": [0, 0, 925, 3, 879, 170]
                }
              }
            }
          }
        """

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
        # cells. We can't clip to geometry because that way some pixels may be
        # included in multiple cells.
        lngLat = ee.Image.pixelLonLat().clip(rect)
        lng = lngLat.select(0)
        lat = lngLat.select(1)

        lng = lng.subtract(min_x).unitScale(0, x_step).int()
        lat = lat.subtract(min_y).unitScale(0, y_step).int()
        index_image = lat.multiply(cols).add(lng)

        # Get the NDFI data.
        diff = self._delta(asset_id).select(0)
        masked = diff.mask(diff.mask().And(diff.lte(MAX_NDFI)))

        # Aggregate each cell.
        count_reducer = ee.Reducer.count()
        sum_reducer = ee.Reducer.sum()
        results = []
        for y in range(rows):
            for x in range(cols):
                # Compose the reduction query for the cell.
                index = y * cols + x
                cell_img = masked.mask(masked.mask().And(index_image.eq(index)))
                count_query = cell_img.reduceRegion(
                    count_reducer, rect, None, MODIS_CRS, MODIS_TRANSFORM)
                sum_query = cell_img.reduceRegion(
                    sum_reducer, rect, None, MODIS_CRS, MODIS_TRANSFORM)
                # Run the aggregations.
                count = ee.data.getValue(
                    {'json': ee.serializer.toJSON(count_query, False)})
                summed = ee.data.getValue(
                    {'json': ee.serializer.toJSON(sum_query, False)})
                results.append([count, summed])

        # Repackages the results in a backward-compatible form:
        counts = [int(i[0]['ndfi']) for i in results]
        sums = [int(i[1]['ndfi']) for i in results]
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

    def _make_map_to_freeze(self, asset_id, table_id, report_id):
        """Returns a description of a new baseline image to be saved.

        Args:
          asset_id: The ID of the baseline PRODES image.
          table_id: The numeric ID of the Fusion Table containing the report
              polygons.
          report_id: The report ID, an integer. This is used to filter the
              rows of the specified table.

        Returns:
          A description of the image to save. The image is not yet saved.
        """
        asset = ee.Image(asset_id)
        frozen_image = _remap_prodes_classes(asset)[0]
        # Remap CLS_EDITED_DEFORESTATION and CLS_EDITED_DEGRADATION to
        # CLS_DEFORESTED and CLS_DEGRADED.
        remapped = frozen_image.remap([0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                      [0, 1, 2, 3, 4, 5, 6, 2, 3, 9])
        # Paint new areas.
        def_image = _paint(remapped, table_id, int(report_id), CLS_EDITED_DEFORESTATION)
        deg_image = _paint(def_image, table_id, int(report_id), CLS_EDITED_DEGRADATION)
        map_image = deg_image.select(['remapped'], ['classification'])
        # Make sure we keep the metadata.
        return asset.addBands(map_image, ['classification'], True)

    def _RGB_image_command(self, period, long_span=False):
        """Returns a Map ID for the RGB visualization of a MODIS mosaic for a given period."""
        return _get_raw_mapid(self._kriged_mosaic(period, long_span).getMapId({
            'bands': 'sur_refl_b01,sur_refl_b04,sur_refl_b03',
            'gain': 0.1,
            'bias': 0.0,
            'gamma': 1.6
        }))

    def _SMA_image_command(self, period):
        """Returns a Map ID for the NDFI SMA image for a given period."""
        return _get_raw_mapid(self._unmixed_mosaic(period).getMapId({
            'bands': 'gv,soil,npv',
            'gain': 256,
            'bias': 0.0,
            'gamma': 1.6
        }))

    def _NDFI_period_image_command(self, period, sensor, long_span=False):
        """Returns a Map ID for the RGB visualization of a MODIS NDFI mosaic for a given period."""
        return _get_raw_mapid(self._NDFI_visualize(period, sensor, long_span).getMapId({
            'bands': 'vis-red,vis-green,vis-blue',
            'gain': 1,
            'bias': 0.0,
            'gamma': 1.6
        }))

    # Joao code
    def _ndfi_change(self, asset_id, sensor):
        # Constants.
        CLASSIFICATION_OFFSET = MAX_NDFI + 1
        DEFORESTATION_THRES_MAX = -20
        DEGRADATION_THRES_MAX = -5
        # Get base NDFIs.
        work_month = self._getMidMonth(self.work_period['start'],
                                       self.work_period['end'])
        work_year = self._getMidYear(self.work_period['start'],
                                     self.work_period['end'])
        baseline = self._paint_edited_deforestation(
            asset_id, work_month, work_year)
        
        # Get ndfi images to make the difference.
        ndfi0 = self._NDFI_image(self.last_period, sensor, True)
        ndfi1 = self._NDFI_image(self.work_period, sensor)
        
        # Basic difference.
        diff = ndfi1.subtract(ndfi0)
        
        raw_result = diff#.multiply(0)
        
        # Classification rules
        deforest = diff.lte(DEFORESTATION_THRES_MAX)
        degradat = diff.lte(DEGRADATION_THRES_MAX).And(deforest.neq(1))
        #forest   = diff.gt(DEGRADATION_THRES_MAX)
        
        raw_result = raw_result.where(deforest.eq(1), CLASSIFICATION_OFFSET + CLS_DEFORESTED)
        raw_result = raw_result.where(degradat.eq(1), CLASSIFICATION_OFFSET + CLS_DEGRADED)
        #raw_result = raw_result.where(forest.eq(1), CLASSIFICATION_OFFSET + CLS_FOREST)
        #raw_result = baseline.where(out_shifted_baseline, CLS_BASELINE)
        
        # Unclassify previously unclassified pixels and small forests.
        #cloud_mask = ndfi1.neq(CLS_UNCLASSIFIED)
        #raw_result = raw_result.where(1, CLS_CLOUD)
        result = raw_result
        
        return result.byte().addBands(baseline)

    def _ndfi_delta(self, asset_id, sensor):
        """Computes a classification based on an difference in NDFI.

        This method computes a delta between the NDFI of two periods, specified
        by the object's last_period and work_period member variables, with
        last_period extended backwards to LONG_SPAN_SIZE_MS in length.

        The resulting delta is used to derive a new classification from a
        specified baseline classification.

        Args:
          asset_id: The string ID of the baseline classification image. Should
              have one band whose values are the CLS_* constants defined in
              this file.

        Returns:
          An ee.Image with two bands:
          0. ndfi: An unsigned byte value representing either the difference
             between the NDFIs (if it's <= 200), or the value of the baseline
             classification shifted up by 201 (MAX_NDFI + 1).
          1. classification: the original baseline classification with
             areas of CLS_EDITED_DEFORESTATION for the work period converted
             to CLS_BASELINE.
        """

        # Constants.
        MIN_FOREST_SIZE = 41
        MIN_UNMASKED_SIZE = 21
        ALREADY_DEFORESTED_NDFI = 100
        CLASSIFICATION_OFFSET = MAX_NDFI + 1

        # Get base NDFIs.
        work_month = self._getMidMonth(self.work_period['start'],
                                       self.work_period['end'])
        work_year = self._getMidYear(self.work_period['start'],
                                     self.work_period['end'])
        baseline = self._paint_edited_deforestation(
            asset_id, work_month, work_year)

        # Get ndfi images to make the difference.
        ndfi0 = self._NDFI_image(self.last_period, sensor, True)
        ndfi1 = self._NDFI_image(self.work_period, sensor)

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

    def _paint_edited_deforestation(self, asset_id, month, year):  # pylint: disable-msg=unused-argument
        """Returns an image from an asset with edited deforestation painted on.

        Selects all rows for the given year and month (NOTE: month currently
        ignored) from the Fusion Table whose class is CLS_EDITED_DEFORESTATION
        and paints them onto the image specified by asset_id with the value
        CLS_BASELINE.

        Args:
          asset_id: The string ID of the baseline image. Should have one band.
          month: The month number. CURRENTLY UNUSED.
          year: The year number.

        Returns:
          An ee.Image with the same band name(s) as the specified asset.
        """
        date = '%04d' % year
        # date = '%04d_%02d' % (year, month)
        table = ee.FeatureCollection(int(settings.FT_TABLE_ID))
        table = table.filterMetadata('type', 'equals', CLS_EDITED_DEFORESTATION)
        table = table.filterMetadata('asset_id', 'contains', date)
        return ee.Image(asset_id).paint(table, CLS_BASELINE)

    def _NDFI_visualize(self, period, sensor, long_span=False):
        """Returns an RGB visualization of an NDFI mosaic for a given period.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with 3 byte bands, vis-red, vis-green, vis-blue.
        """
        ndfi = self._NDFI_image(period, sensor,long_span)

        red = ndfi.interpolate([150, 185], [255, 0], 'clamp')
        green = ndfi.interpolate([  0, 100, 125, 150, 185, 200, 201],
                                 [255,   0, 255, 165, 140,  80,   0], 'clamp')
        blue = ndfi.interpolate([100, 125], [255, 0], 'clamp')

        rgb = ee.Image.cat(red, green, blue).round().byte()

        return rgb.select([0, 1, 2], ['vis-red', 'vis-green', 'vis-blue'])

    def _NDFI_image(self, period, sensor='modis',long_span=False):
        """Returns an NDFI mosaic based on MODIS for a given period.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with a single integer band called "ndfi", ranging from
          0 (no GV) to 200 (all GV), plus the special INVALID_NDFI value (201),
          which indicates that the unmixed values were out of range.
        """
        base = 0
        clamped_expression = ''
        gv = ''
        npv = ''
        soil = ''

        if sensor == 'landsat5':
            base = self._unmixed_landsat_L5(period)
            clamped_expression = 'b(0) + b(1) + b(2) + b(3)'
            gv = 0
            npv = 1
            soil = 2
        elif sensor == 'landsat7':
            base = self._unmixed_landsat_L7(period)
            clamped_expression = 'b(0) + b(1) + b(2) + b(3)'
            gv = 0
            npv = 1
            soil = 2
        else:
            base = self._unmixed_mosaic(period, long_span)
            clamped_expression = 'b("gv") + b("soil") + b("npv")'
            gv = 'gv'
            npv = 'npv'
            soil = 'soil'

        clamped = base.max(0)

        summed = clamped.expression(clamped_expression)
        gv_shade = clamped.select(gv).divide(summed)
        npv_plus_soil = clamped.select(npv).add(clamped.select(soil))

        raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()

        ndfi = raw_ndfi.multiply(100).add(100).byte()
        ndfi = ndfi.where(summed.eq(0), INVALID_NDFI)

        return ndfi.select([0], ['ndfi'])

    def _unmixed_mosaic(self, period, long_span=False):
        """Returns a mosaic with GV, SOIL and NPV indices based on MODIS.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with the following bands:
          0. gv: float, valid in [0, 1] but may contain negative values.
          1. soil: float, valid in [0, 1] but may contain negative values.
          2. npv: float, valid in [0, 1] but may contain negative values.
          3. gv_100: int, in [0, 100].
          4. soil_100: int, in [0, 100].
          5. npv_100: int, in [0, 100].

          The last 3 bands are integer percentage versions of the first 3,
          with any negative values clamped to 0.
        """
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
        result = unmixed.expression('addBands(b(0,1,2), round(max(b(0,1,2), 0) * 100))')
        return result.select(['.*'], OUTPUTS + [i + '_100' for i in OUTPUTS])

    def _unmixed_landsat_L5(self, period):
        ENDMEMBERS = [
                      [ 119.0,  475.0,  169.0, 6250.0, 2399.0,  675.0], #GV
                      [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0], #NPV
                      [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0], #SOIL
                      [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0]  #CLOUD
                    ]

        periodo = '' #['2001-01-01', '2001-02-01']
        if period['start'] == 1409529600000:
            logging.info("Start: "+str(period['start']))
            periodo = ['2011-05-01', '2011-06-01']
        else:
            logging.info("End: "+str(period['end']))
            periodo = ['2011-06-01', '2011-07-01']

        #collection = ee.ImageCollection('L5_L1T_SR').filterMetadata('WRS_PATH', 'equals', 227).filterMetadata('WRS_ROW', 'equals', 65).filterMetadata('CLOUD_COVER', 'less_than', 30).filterDate(periodo[0], periodo[1])
        bounder = ee.Geometry.Rectangle(-74.0, -18.0, -44, 5.0)

        collection = ee.ImageCollection('L5_L1T_SR').filterDate(periodo[0], periodo[1]).filterBounds(bounder)

        image = collection.mosaic()

        unmixed = ee.Image(image).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)

        return unmixed

    def _unmixed_landsat_L7(self, period):
        ENDMEMBERS = [
                      [ 119.0,  475.0,  169.0, 6250.0, 2399.0,  675.0], #GV
                      [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0], #NPV
                      [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0], #SOIL
                      [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0]  # CLOUD
                    ]

        periodo = '' #['2001-01-01', '2001-02-01']
        if period['start'] == 1409529600000:
            logging.info("Start: "+str(period['start']))
            periodo = ['2011-05-01', '2011-06-01']
        else:
            logging.info("End: "+str(period['end']))
            periodo = ['2011-06-01', '2011-07-01']

        #collection = ee.ImageCollection('L5_L1T_SR').filterMetadata('WRS_PATH', 'equals', 227).filterMetadata('WRS_ROW', 'equals', 65).filterMetadata('CLOUD_COVER', 'less_than', 30).filterDate(periodo[0], periodo[1])
        bounder = ee.Geometry.Rectangle(-74.0, -18.0, -44, 5.0)

        collection = ee.ImageCollection('L7_L1T_SR').filterDate(periodo[0], periodo[1]).filterBounds(bounder)

        image = collection.mosaic()

        unmixed = ee.Image(image).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)

        return unmixed

    def _kriged_mosaic(self, period, long_span=False):
        """Returns an upscaled MODIS mosaic for a given period.

        See _make_mosaic() for details on how the mosaic images are selected.

        Args:
          period: The mosaic period. See _make_mosaic() for details.
          long_span: Whether to extend the period. See _make_mosaic() for details.

        Returns:
          An ee.Image with the following bands:
          0. sur_refl_b01_250m
          1. sur_refl_b02_250m
          2. sur_refl_b05_500m
          3. sur_refl_b03_250m
          4. sur_refl_b04_250m
          5. sur_refl_b06_250m
          6. sur_refl_b07_250m
        """
        work_month = self._getMidMonth(period['start'], period['end'])
        work_year = self._getMidYear(period['start'], period['end'])
        date = '%04d%02d' % (work_year, work_month)
        downscalling = Downscalling.find_by_compounddate(date)
        feature_collection = Downscalling.return_feature_collection(downscalling)
        params = ''
        
        if feature_collection:
            params = feature_collection
        else:
            krig_filter = ee.Filter.eq('Compounddate', int(date))
            params = ee.FeatureCollection(KRIGING_PARAMS_TABLE).filter(krig_filter)
        
        mosaic = self._make_mosaic(period, long_span)
        return ee.Algorithms.SAD.KrigeModis(mosaic, params)

    def _make_mosaic(self, period, long_span=False):
        """Returns a mosaic of MODIS images for a given period.

        This selects images from the MODIS GA and GQ collections, filtered to
        the specified time range, based on an inclusions table.

        The inclusions table lists the days to include in the mosaic for each
        month, for each MODIS tile. Currently it is a Fusion Table specified
        by MODIS_INCLUSIONS_TABLE, with a row for each (month, modis tile).
        Each row has a geometry of the tile and a comma-separated list of day
        numbers to include in the mosaic.

        Rows that do not have a corresponding image in each collection are
        skipped. If no features overlap an output pixel, we'll fall back on a
        composite constructed from the week of images preceding the period end.

        Args:
          period: The mosaic period, as a dictionary with "start" and "end",
              keys, both containing Unix timestamps.
          long_span: Whether to use an extended period.
              If False, the period is used as is and only the month at the
              midpoint of the period range is used to select from the
              inclusions table.
              If True, the start of the specified period is ignored and a new
              start is computed by extending the end of the period back by
              LONG_SPAN_SIZE_MS milliseconds.

        Returns:
          An ee.Image with the following bands:
          0. num_observations_1km
          1. state_1km
          2. sur_refl_b01_500m
          3. sur_refl_b02_500m
          4. sur_refl_b03_500m
          5. sur_refl_b04_500m
          6. sur_refl_b05_500m
          7. sur_refl_b06_500m
          8. sur_refl_b07_500m
          9. sur_refl_b01_250m
          10. sur_refl_b02_250m
          11. num_observations_250m
        """
        inclusions = ''

        
        if long_span:
            # Calculate the time span.
            start_time = period['end'] - LONG_SPAN_SIZE_MS
            end_time = period['end']
            start_month = time.gmtime(start_time / 1000).tm_mon
            start_year = time.gmtime(start_time / 1000).tm_year
            end_month = time.gmtime(end_time / 1000).tm_mon
            end_year = time.gmtime(end_time / 1000).tm_year
            start = '%04d%02d' % (start_year, start_month)
            end = '%04d%02d' % (end_year, end_month)
            image_picker = ImagePicker.find_by_compounddate_period(start, end)
            feature_collection = ImagePicker.return_feature_collection(image_picker)
            
            # Prepare the inclusions table.
            if feature_collection:
                inclusions = feature_collection
            else:
                inclusions_filter = ee.Filter.And(
                                       ee.Filter.gte('compounddate', start),
                                       ee.Filter.lte('compounddate', end))
                # Prepare the inclusions table.
                inclusions = ee.FeatureCollection(MODIS_INCLUSIONS_TABLE)
                inclusions = inclusions.filter(inclusions_filter)
                
        else:
            # Calculate the time span.
            start_time = period['start']
            end_time = period['end']
            month = self._getMidMonth(start_time, end_time)
            year = self._getMidYear(start_time, end_time)
            compounddate = '%04d%02d' % (year, month)
            image_picker = ImagePicker.find_by_compounddate(compounddate)
            feature_collection = ImagePicker.return_feature_collection(image_picker)
            
            # Prepare the inclusions table.
            if feature_collection:
                inclusions = feature_collection
            else:
                inclusions_filter = ee.Filter.eq(
                'compounddate', compounddate)
                inclusions = ee.FeatureCollection(MODIS_INCLUSIONS_TABLE)
                inclusions = inclusions.filter(inclusions_filter)

        # Prepare source image collections.
        modis_ga = ee.ImageCollection('MODIS/MOD09GA').filterDate(start_time, end_time)
        modis_gq = ee.ImageCollection('MODIS/MOD09GQ').filterDate(start_time, end_time)

        

        object1 = ee.call(
          'SAD/com.google.earthengine.examples.sad.MakeMosaic',
          modis_ga, modis_gq, inclusions, start_time, end_time)

        #logging.info("Make MOsaic: "+str(object1))

        return object1

    def _get_polygon_bbox(self, polygon):
        """Returns the bounding box of a polygon.

        Args:
          polygon: A GeoJSON polygon.

        Returns:
          A 4-tuple describing a bounding box in the format:
          (min_lng, min_lat, max_lng, max_lat)
        """
        coordinates = sum(polygon['coordinates'], [])
        lngs = [x[0] for x in coordinates]
        lats = [x[1] for x in coordinates]
        max_lng = max(lngs)
        min_lng = min(lngs)
        max_lat = max(lats)
        min_lat = min(lats)
        return (min_lng, min_lat, max_lng, max_lat)

    def _getMidMonth(self, start, end):
        """Returns the month part of the midpoint of two Unix timestamps."""
        middle_seconds = int((end + start) / 2000)
        return time.gmtime(middle_seconds).tm_mon

    def _getMidYear(self, start, end):
        """Returns the year part of the midpoint of two Unix timestamps."""
        middle_seconds = int((end + start) / 2000)
        return time.gmtime(middle_seconds).tm_year


def get_prodes_stats(assetids, table_id):
    """Computes the area of each class in each polygon in each PRODES image.

    Args:
      assetids: A list of PRODES image IDs.
      table_id: The ID of a Fusion Table of polygons to analyse.

    Returns:
      A description of the area of each (image, polygon, class) tuple. For
      backward-compatibility, returned in the awkward old EE format. Example:
      {
        "data": {
          "properties": {
            "classHistogram": [
              <image entry 1>,
              <image entry 2>,
              ...
            ]
          }
        }
      }

      Where each <image entry> looks like:
      {
        "type": "DataDictionary",
         "values": {
           <polygon entry>,
           <polygon entry>,
           ...
         }
       }

      Where each <polygon entry> looks like:
      {
        "type": "DataDictionary",
        "values": {
          "<class value>": <area of that class in square meters>,
          "<class value>": <area of that class in square meters>,
          ...
        }
      }

      Where each <class value> is a number.
    """
    results = []
    for assetid in assetids:
        prodes_image, classes = _remap_prodes_classes(ee.Image(assetid))
        collection = ee.FeatureCollection(table_id)
        raw_stats = _get_area_histogram(prodes_image, collection, classes)
        stats = {}
        for raw_stat in raw_stats:
            values = {}
            for class_value in range(max(classes) + 1):
                class_label = str(class_value)
                if class_label in raw_stat:
                    values[class_label] = raw_stat[class_label]
                else:
                    values[class_label] = 0.0
            stats[str(int(raw_stat['name']))] = {
                'values': values,
                'type': 'DataDictionary'
            }
        results.append({'values': stats, 'type': 'DataDictionary'})
    return {'data': {'properties': {'classHistogram': results}}}

def get_modis_thumbnails_list(year, month, tile, bands='sur_refl_b05,sur_refl_b04,sur_refl_b03', gain=[2.0,2.0,2.0]):
    result_final = []
    nextYear = year
    nextMonth = str(int(month) + 1).zfill(2)

    if month == '12':
        nextYear = str(int(year) + 1)
        nextMonth = '01'

    collection = ee.ImageCollection('MOD09GA').filterDate(year+'-'+month+'-01', nextYear+'-'+nextMonth+'-01')
    images = collection.getInfo().get('features')

    MAX_ERROR_METERS = 500.0
    #tile = _get_modis_tile(*cell)
    p = re.compile('\d+')
    p = p.findall(tile)
    logging.info(tile)
    tile = _get_modis_tile(int(p[0]), int(p[1]))
    feature = ee.Feature(tile)
    region = feature.bounds(MAX_ERROR_METERS)
    reprojected = ee.data.getValue({'json': region.serialize()})['geometry']['coordinates']

    for i in range(len(images)):
        result = ee.data.getThumbId({
           'image': ee.Image(images[i].get('id')).serialize(False),
           'bands': bands,
           'region': reprojected,
           'gain': gain
        })

        imageId = images[i].get('id')
        imageIdSplit = imageId.split('_')
        date = imageIdSplit[4]+'-'+imageIdSplit[3]+'-'+imageIdSplit[2]

        result_final.append({'thumb': result['thumbid'], 'token': result['token'], 'date': date})

    return result_final


def create_tile_baseline(start_date, end_date, cell):  
    
    baselines = []
    ndfis     = [] 
    smas      = []
    resutls   = []
    
    #image_picker = ImagePicker.find_by_period(start_compounddate, end_compounddate, tile_name)
    baseline     = Baseline.find_by_cell(cell)
    image_picker = ''
    
    if baseline:
        image_picker = baseline.image_picker
    else: 
        cell_grid = CellGrid.find_by_name(cell)
        baseline  = Baseline(added_by=users.get_current_user(), cell=cell_grid, name='null', start=start_date.date(), end=end_date.date())
        image_picker = baseline.image_picker
        
    
    logging.info('===== >>>>>>>>> image_picker <<<<<<<<< ========')
    logging.info(image_picker)
    for i in range(len(image_picker)):
        sensor     = image_picker[i]['sensor']
        tile_name  = image_picker[i]['cell']
        
        days  = image_picker[i]['day']
        month = image_picker[i]['month']
        year  = image_picker[i]['year']
        
        if len(days) == 1:
            date_star  = year+'-'+month+'-'+days[0]
            collection = EELandsat.find_collection_tile(sensor, tile_name, date_star)
        
            #image_num = len(collection.getInfo()['features'])
        
        
            logging.info(collection.getInfo()['features'][0])
            image = ee.Image(collection.getInfo()['features'][0]['id'])
            
            feature_image = image.getMapId({
                           'bands': ','.join(EELandsat.get_image_bands(sensor).get('bands')),
                           'gain': ','.join(EELandsat.get_image_bands(sensor).get('gain'))                          
                          })
            
            resutls.append({'id':          feature_image['mapid'],
                            'token':       feature_image['token'],
                            'type':        'baseline',
                            'visibility':  True,
                            'description': 'RGB/'+sensor,
                            'url': 'https://earthengine.googleapis.com/map/'+feature_image['mapid']+'/{Z}/{X}/{Y}?token='+feature_image['token']
                          })
            
            classifications = baseline_image(image, sensor, start_date, None, cell)
            baselines.append(classifications['baseline'])
            ndfis.append(classifications['ndfi'])
            smas.append(classifications['sma'])
            
        elif len(days) > 1 :
            resutls.append("Process with temporal composition")
        else:
            resutls.append(None)

    if len(baselines) > 0:                
        images_baseline = ee.ImageCollection(baselines)
        images_ndfi = ee.ImageCollection(ndfis)
        images_sma = ee.ImageCollection(smas)
        
        image_baseline  = images_baseline.mosaic()
        image_ndfi  = images_ndfi.mosaic()
        image_sma  = images_sma.mosaic()
        
        cell_grid = CellGrid.find_by_name(cell)
        geo  = ast.literal_eval(cell_grid.geo)
        polygon = ee.Geometry(ee.Geometry.Polygon(geo), "EPSG:4326")
        #polygon = ee.Geometry.Polygon(geo)
        
        image_baseline = image_baseline.clip(polygon)
        image_ndfi     = image_ndfi.clip(polygon)
        image_sma      = image_sma.clip(polygon) 
        
        feature_baseline = ee.Image(image_baseline).getMapId({
                              'bands': 'nd', 
                              'palette': '000000,00994d,00ffff,000000,0000ff,666666'                            
                              })
        
        mapid = feature_baseline['mapid']
        token = feature_baseline['token']    
        
        name = 'BASELINE/'+cell+'/'+sensor+'/'+start_date.strftime("%Y-%b-%d")
        
        #baseline = Baseline(added_by=users.get_current_user(), cell=cell_grid, name=name, start=start_date.date(), end=end_date.date())
        baseline.added_by = users.get_current_user()
        baseline.name     = name
         
        baseline_result          = baseline.save()['data']
        baseline_result['mapid'] = mapid
        baseline_result['token'] = token
        baseline_result['url']   = 'https://earthengine.googleapis.com/map/'+mapid+'/{Z}/{X}/{Y}?token='+token 
        
        resutls.append(baseline_result)
        
        feature_ndfi = ee.Image(image_ndfi).getMapId({
                              'bands': 'vis-red,vis-green,vis-blue',
                              'gain': 1,
                              'bias': 0.0,
                              'gamma': 1.6                            
                              })
        
        resutls.append({'id':          feature_ndfi['mapid'],
                        'token':       feature_ndfi['token'],
                        'type':        'baseline',
                        'visibility':  True,
                        'description': 'NDFI',
                        'url': 'https://earthengine.googleapis.com/map/'+feature_ndfi['mapid']+'/{Z}/{X}/{Y}?token='+feature_ndfi['token']
                        })
        
        feature_sma = ee.Image(image_sma).getMapId({
                              'bands': 'band_2, band_1, band_0',                              
                              'gain': '0.06, 0.06, 0.06'                           
                              })
        
        resutls.append({'id':          feature_sma['mapid'],
                        'token':       feature_sma['token'],
                        'type':        'baseline',
                        'visibility':  True,
                        'description': 'SMA',
                        'url': 'https://earthengine.googleapis.com/map/'+feature_sma['mapid']+'/{Z}/{X}/{Y}?token='+feature_sma['token']
                        })
        
        return resutls
    else:
        return None
                
            
    
def baseline_image(image, sensor, start_date, end_date=None, cell=None):
    ENDMEMBERS = [
                  [ 119.0,  475.0,  169.0, 6250.0, 2399.0,  675.0], #GV
                  [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0], #NPV
                  [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0], #SOIL
                  [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0]  # CLOUD
                 ]    
    
    ## SMA ===========================================================================
    unmixed = ee.Image(image).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)

    ## NDFI calc =====================================================================
    clamped = unmixed.max(0)
    summed = clamped.expression('b(0) + b(1) + b(2) + b(3)')
    gv_shade = clamped.select(0).divide(summed)

    npv_plus_soil = clamped.select(1).add(clamped.select(2))
    raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()
    ndfi = raw_ndfi.multiply(100).add(100).byte()
    
    ndfi_vizualize = ndfi.where(summed.eq(0), INVALID_NDFI)
    ndfi_vizualize = ndfi_vizualize.select([0], ['ndfi']) 
    red = ndfi_vizualize.interpolate([150, 185], [255, 0], 'clamp')
    green = ndfi_vizualize.interpolate([  0, 100, 125, 150, 185, 200, 201],
                                 [255,   0, 255, 165, 140,  80,   0], 'clamp')
    blue = ndfi_vizualize.interpolate([100, 125], [255, 0], 'clamp')

    rgb = ee.Image.cat(red, green, blue).round().byte()

    classification_ndfi = rgb.select([0, 1, 2], ['vis-red', 'vis-green', 'vis-blue'])     

    ## Cloud mask ====================================================================
    cloudThresh = [0.15, 0.07] # % 0-1
    bufferSize  = 10 #pixels

    cloudMask1 = unmixed.select(3).gte(cloudThresh[0])
 
    kernel = ee.Kernel.circle(bufferSize, 'pixels')

    buffered = cloudMask1.convolve(kernel)
    buffered = (buffered.add(cloudMask1)).gt(0)

    cloudMask2 = buffered.eq(1).And(unmixed.select([3]).gte(cloudThresh[1]))

    ## Classification =================================================================
    classification_baseline = ndfi.multiply(0)
    classification_baseline = classification_baseline.where(ndfi.gte(175), 1) #Forest
    classification_baseline = classification_baseline.where(ndfi.gte(165).And(ndfi.lte(174)), 2) #Degradation
    classification_baseline = classification_baseline.where(ndfi.lte(164), 3) #Deforestation
    classification_baseline = classification_baseline.where(summed.lte(0.15), 4) #Water
    classification_baseline = classification_baseline.where(cloudMask2.eq(1), 5) #Cloud
    
    return {'baseline': classification_baseline, 'ndfi': classification_ndfi, 'sma': unmixed}
    


def create_baseline(start_date, end_date, sensor=EELandsat.LANDSAT5):
    ENDMEMBERS = [
                  [ 119.0,  475.0,  169.0, 6250.0, 2399.0,  675.0], #GV
                  [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0], #NPV
                  [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0], #SOIL
                  [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0]  # CLOUD
                 ]

    start_date = datetime.datetime.strptime(start_date,"%d/%b/%Y")
    end_date = datetime.datetime.strptime(end_date,"%d/%b/%Y")

    image_L5 = EELandsat(start_date, end_date, EELandsat.LANDSAT5)
    
    image_L7 = EELandsat(start_date, end_date, EELandsat.LANDSAT7)

    bbox = [-74.0, -18.0, -44.0, 5.0]

    #bounder = ee.Geometry.Rectangle(-74.0, -18.0, -44.0, 5.0)

    #collection = ee.ImageCollection('L5_L1T_SR').filterDate(start_date, end_date).filterBounds(bounder)

    #image = collection.mosaic()
    
    image_L5 = image_L5.find_map_image(bbox)
    sensor = ''
    
    
    image = ''
    
    if image_L5:
        image = image_L5
        sensor = EELandsat.LANDSAT5
    else:
        image_L7 = image_L7.find_map_image(bbox)        
        if image_L7:
            image = image_L7
            sensor = EELandsat.LANDSAT7 

    
    ## SMA ===========================================================================
    unmixed = ee.Image(image).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)

    ## NDFI calc =====================================================================
    clamped = unmixed.max(0)
    summed = clamped.expression('b(0) + b(1) + b(2) + b(3)')
    gv_shade = clamped.select(0).divide(summed)

    npv_plus_soil = clamped.select(1).add(clamped.select(2))
    raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()
    ndfi = raw_ndfi.multiply(100).add(100).byte()

    ## Cloud mask ====================================================================
    cloudThresh = [0.15, 0.07] # % 0-1
    bufferSize  = 10 #pixels

    cloudMask1 = unmixed.select(3).gte(cloudThresh[0])
 
    kernel = ee.Kernel.circle(bufferSize, 'pixels')

    buffered = cloudMask1.convolve(kernel)
    buffered = (buffered.add(cloudMask1)).gt(0)

    cloudMask2 = buffered.eq(1).And(unmixed.select([3]).gte(cloudThresh[1]))

    ## Classification =================================================================
    classification = ndfi.multiply(0)
    classification = classification.where(ndfi.gte(175), 1) #Forest
    classification = classification.where(ndfi.gte(165).And(ndfi.lte(174)), 2) #Degradation
    classification = classification.where(ndfi.lte(164), 3) #Deforestation
    classification = classification.where(summed.lte(0.15), 4) #Water
    classification = classification.where(cloudMask2.eq(1), 5) #Cloud
    
    feature = ee.Image(classification).getMapId({
                              'bands': 'nd', 
                              'palette': '000000,00994d,00ffff,000000,0000ff,666666'                            
                              })

    mapid = feature['mapid']
    token = feature['token']
    name = 'BASELINE/'+sensor+'/'+start_date.strftime("%Y-%b-%d")+' to '+end_date.date().strftime("%Y-%b-%d")

    baseline = Baseline(added_by= users.get_current_user(), name=name, start= start_date.date(), end=end_date.date(), mapid=mapid, token=token)
    
    return baseline.save()

def create_time_series(start_date, end_date, sensor=EELandsat.LANDSAT5):    
    ENDMEMBERS = [
                  [ 119.0,  475.0,  169.0, 6250.0, 2399.0,  675.0], #GV
                  [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0], #NPV
                  [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0], #SOIL
                  [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0]  # CLOUD
                 ]
    
    tiles = Tile.find_tiles_by_sensor('landsat')

    start_date = datetime.datetime.strptime(start_date,"%d/%b/%Y")
    end_date = datetime.datetime.strptime(end_date,"%d/%b/%Y")

    first_year = start_date.year
    last_year  = end_date.year
    years      = range(first_year, last_year + 1)
    
    ## Define a color to each one of years ================================================================================
    start = 0xff0000
    end   = 0xffff00
    colors = []
    for i in xrange(start, end+1):
        colors.append(format(i, 'X'))
    
    colors = colors[0: len(colors): int(len(colors)/len(years))]

    years_images = {}

    landstat = EELandsat(start_date, end_date, EELandsat.LANDSAT5)
    
    for i in xrange(len(years)):
        date_first = str(start_date.day).zfill(2) +"/"+ str(start_date.month).zfill(2) +"/"+ str(years[i])
        date_last = str(end_date.day).zfill(2) +"/"+ str(end_date.month).zfill(2) +"/"+ str(years[i] + 1)
    
        date_first = datetime.datetime.strptime(date_first,"%d/%m/%Y")
        date_last = datetime.datetime.strptime(date_last,"%d/%m/%Y")   
        
        landstat = EELandsat(date_first, date_last, EELandsat.LANDSAT5)  
        
        years_images[str(years[i])] = {'color': colors[i], 'class_image': landstat}
    
    images_cumulated = []
    nImages = 0;
    
    for i in xrange(len(years)):
        logging.info(str(years[i]))
        year_image = years_images[str(years[i])]
        collection = year_image['class_image'].find_full_map_collection()
        image = collection.mosaic() 
        ## SMA ===========================================================================
        unmixed = ee.Image(image).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)
        
        ## NDFI calc =====================================================================
        clamped = unmixed.max(0)
        summed = clamped.expression('b(0) + b(1) + b(2) + b(3)')
        gv_shade = clamped.select(0).divide(summed)
    
        npv_plus_soil = clamped.select(1).add(clamped.select(2))
        raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()
        ndfi = raw_ndfi.multiply(100).add(100).byte()
        
        ## Classification ================================================================
        #classificationName = ''
        classification = ndfi.multiply(0)
        
        if i == 0:
            baseline = ndfi.multiply(0)
            cumulated = ndfi.multiply(0)
            
            classification = classification.where(ndfi.gte(175), 1) #Forest
            classification = classification.where(ndfi.gte(165).And(ndfi.lte(174)), 3) #Degradation
            classification = classification.where(ndfi.lte(164), 4) #Non-Forest baseline
            classification = classification.where(summed.lte(0.15), 5) #Water
            classification = classification.where(clamped.select(3).gte(0.10), 6) #Cloud
            
            baseline = baseline.where(classification.eq(4), 1)
            
            cumulated = cumulated.where(classification.eq(4), i+1)
            
        else:
            classification = classification.where(ndfi.gte(175), 1) #Forest
            classification = classification.where(ndfi.gte(165).And(ndfi.lte(174)), 3) #Degradation
            classification = classification.where(ndfi.lte(164), 7) #Deforestation
            classification = classification.where(summed.lte(0.15), 5) #Water
            classification = classification.where(clamped.select(3).gte(0.10), 6) #Cloud  
            classification = classification.where(baseline.eq(1), 4) #Non-Forest 
            
            baseline = baseline.where(classification.eq(7), 1)
            
            cumulated = cumulated.where(classification.eq(7), i+1)
            
    
    noDeforestation = cumulated.neq(0)
    cumulatedFinal = cumulated.mask(noDeforestation)
    
    logging.info(years)
    logging.info(colors)
    
    feature = ee.Image(cumulatedFinal).getMapId({
                                                'bands': 'nd',
                                                'min': 1,
                                                'max': len(years),
                                                'palette': ','.join(colors)                            
                                              })
    
    mapid = feature['mapid']
    token = feature['token']
    name = 'TIME_SERIES/'+sensor+'/'+start_date.strftime("%Y-%b-%d")+' to '+end_date.date().strftime("%Y-%b-%d")

    time_series = TimeSeries(added_by= users.get_current_user(), name=name, start= start_date.date(), end=end_date.date(), mapid=mapid, token=token)
    
    return time_series.save()
    
    """
    for i in range(len(tiles)):
        cumulated = None
        collection = landstat.find_image_tile_from_L5(tiles[i])
        
        images = collection.getInfo().get('features')
        
        for i in range(len(images)):
            nImages = nImages + 1
            ## SMA ===========================================================================
            unmixed = ee.Image(images[i]['id']).select([0,1,2,3,4,6]).unmix(ENDMEMBERS)
            
            ## NDFI calc =====================================================================
            clamped = unmixed.max(0)
            summed = clamped.expression('b(0) + b(1) + b(2) + b(3)')
            gv_shade = clamped.select(0).divide(summed)
        
            npv_plus_soil = clamped.select(1).add(clamped.select(2))
            raw_ndfi = ee.Image.cat(gv_shade, npv_plus_soil).normalizedDifference()
            ndfi = raw_ndfi.multiply(100).add(100).byte()
            
            ## Classification ================================================================
            #classificationName = ''
            classification = ndfi.multiply(0)
            
            if i == 0:
                baseline = ndfi.multiply(0)
                cumulated = ndfi.multiply(0)
                
                classification = classification.where(ndfi.gte(175), 1) #Forest
                classification = classification.where(ndfi.gte(165).And(ndfi.lte(174)), 3) #Degradation
                classification = classification.where(ndfi.lte(164), 4) #Non-Forest baseline
                classification = classification.where(summed.lte(0.15), 5) #Water
                classification = classification.where(clamped.select(3).gte(0.10), 6) #Cloud
                
                baseline = baseline.where(classification.eq(4), 1)
                
                cumulated = cumulated.where(classification.eq(4), i+1)
                
            else:
                classification = classification.where(ndfi.gte(175), 1) #Forest
                classification = classification.where(ndfi.gte(165).And(ndfi.lte(174)), 3) #Degradation
                classification = classification.where(ndfi.lte(164), 7) #Deforestation
                classification = classification.where(summed.lte(0.15), 5) #Water
                classification = classification.where(clamped.select(3).gte(0.10), 6) #Cloud  
                classification = classification.where(baseline.eq(1), 4) #Non-Forest 
                
                baseline = baseline.where(classification.eq(7), 1)
                
                cumulated = cumulated.where(classification.eq(7), i+1)
                
        
        if cumulated:
            noDeforestation = cumulated.neq(0)
            cumulatedTile = cumulated.mask(noDeforestation)
            images_cumulated.append(cumulatedTile)
    
    
       
    image = ee.ImageCollection(images_cumulated)    


    
    
    
    feature = ee.Image(image.mosaic()).getMapId({
                                                'bands': 'nd',
                                                'min': 1,
                                                'max': nImages,
                                                'palette': 'ffff00, ff0000'                            
                                              })

    mapid = feature['mapid']
    token = feature['token']
    name = 'TIME_SERIES/'+sensor+'/'+start_date.strftime("%Y-%b-%d")+' to '+end_date.date().strftime("%Y-%b-%d")

    time_series = TimeSeries(added_by= users.get_current_user(), name=name, start= start_date.date(), end=end_date.date(), mapid=mapid, token=token)
    
    return time_series.save()"""


def get_modis_location(cell):
    inclusions_filter = ee.Filter.eq('cell', cell);

    MODIS_INCLUSIONS_TABLE_TEST = "ft:1zqKClXoaHjUovWSydYDfOvwsrLVw-aNU4rh3wLc"

    inclusions = ee.FeatureCollection(MODIS_INCLUSIONS_TABLE_TEST)

    inclusions = inclusions.filter(inclusions_filter).first()

    location = inclusions.getInfo()['geometry']['coordinates']

    return str(location)


def get_modis_thumbnail(image_id, cell, bands='sur_refl_b05,sur_refl_b04,sur_refl_b03', gain=[2.0,2.0,2.0]):
    """Returns a thumbnail ID for a given image ID.

    Args:
      image_id: The asset ID of the image to thumbnail.
      cell: MODIS cell coordinates as a (horizontal, vertical) tuple.
      bands: The bands of the image to render as a comma-separated string.
      gain: The visualization gain to apply to the image.

        Returns:
      A dictionary containing "thumbid" and "token".
    """
    MAX_ERROR_METERS = 500.0
    #tile = _get_modis_tile(*cell)
    logging.info(cell)
    tile = _get_modis_tile(int(cell[1:3]), int(cell[4:6]))
    feature = ee.Feature(tile)
    region = feature.bounds(MAX_ERROR_METERS)
    reprojected = ee.data.getValue({'json': region.serialize()})['geometry']['coordinates']
    # logging.info(type(region))
    #reprojected = region.getInfo()['geometry']['coordinates']
    #reprojected = [[-69.20956906378983,0.47249172764026187], [-58.06121657561447,0.47249172764026187], [-58.06121657561447,10.471033459067291],[-69.20956906378983,10.471033459067291], [-69.20956906378983,0.47249172764026187]]
    return ee.data.getThumbId({
        'image': ee.Image(image_id).serialize(False),
        'bands': bands,
        'region': reprojected,
        'gain': gain
    })


def _get_area_histogram(image, polygons, classes):
    """Computes the area of class in each polygon.

    Args:
      image: The single-band image with class-valued pixels.
      polygons: An ee.FeatureCollection of polygons to analyse.
      classes: The integer class values to compute area for.

    Returns:
      A list of dictionaries, one for each polygon in the polygons table in
      the same order as they are returned from the collection. Each dictionary
      includes a "name" property from the original polygon row, a "total"
      property with the total classified polygon area in square meters and an
      entry for each class, the key being the class value and the value being
      the area of that class in square meters.
    """
    area_image = ee.Image.pixelArea()
    classes_image = ee.Image().select([])
    for class_number in range(CLASSES_COUNT):
      masked = area_image.mask(image.select('class').eq(class_number))
      renamed = masked.select([0], ['cls-' + str(class_number)])
      classes_image = classes_image.addBands(renamed)
    reducer = ee.Reducer.sum().forEachBand(classes_image)
    proj = image.projection().getInfo()
    stats_query = classes_image.reduceRegions(
        polygons, reducer, None, proj['crs'], proj['transform'])
    stats = stats_query.getInfo()['features']

    result = []
    for feature in stats:
        properties = feature['properties']
        values = [properties['cls-' + str(i)] for i in range(CLASSES_COUNT)]
        row = {'name': properties['name'], 'total': sum(values)}
        for class_number in classes:
          row[str(class_number)] = values[class_number]
        result.append(row)

    return result


def _remap_prodes_classes(img):
    """Remaps the values of the first band of a PRODES classification image.

    Uses the metadata fields class_names and class_indexes, taken either from
    the band, or if that's not available, the image. The class names are
    checked against some simple regular expressions to map to the class values
    used by this application.

    Args:
      img: The single-band PRODES ee.Image.

    Returns:
      A 2-tuple, the first item being the remapped ee.Image with a "class" band
      and the second the set of class values in the output.
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
    info = img.getInfo()
    band_metadata = info['bands'][0].get('properties', {})
    image_metadata = info['properties']
    class_names = band_metadata.get(
        'class_names', image_metadata.get('class_names'))
    classes_from = band_metadata.get(
        'class_indexes', image_metadata.get('class_indexes'))
    classes_to = []

    for name in class_names:
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


def _paint(image, table_id, report_id, cls):
    """Paints a region from a Fusion Table onto an image.

    Args:
      image: The ee.Image to paint on.
      table_id: The numeric Fusion Table ID containing the regions.
      report_id: The numeric report ID. Only region rows with the report_id
          column matching this number will be included.
      cls: A numeric class value.The painted pixels will have this value.
          Only region rows with the type column matching this number will
          be included.

    Returns:
      An ee.Image with the regions painted.
    """
    fc = ee.FeatureCollection(int(table_id))
    fc = fc.filterMetadata('report_id', 'equals', int(report_id))
    fc = fc.filterMetadata('type', 'equals', cls)
    return image.paint(fc, cls)


def _get_landsat_toa(start_time, end_time, version=-1):
    """Returns a Landsat 7 TOA ee.ImageCollection for a given time period.

    Args:
      start_time: The start of the time period as a Unix timestamp.
      end_time: The end of the time period as a Unix timestamp.
      version: The version (timestamp) of the collection.

    Returns:
      An ee.ImageCollection of Landsat TOA images.
    """
    # Load a specific version of an image collection.
    collection = ee.ImageCollection.load('LE7_L1T', version)
    collection = collection.filterDate(start_time, end_time)
    return collection.map(ee.Algorithms.LandsatTOA)

def _get_landsat8(start_time, end_time, version=-1):
    collection = ee.ImageCollection.load('LC8_L1T', version)
    collection = collection.filterDate(start_time, end_time)
    return collection.map(ee.Algorithms.LandsatTOA)


def _get_modis_tile(horizontal, vertical):
    """Returns a GeoJSON geometry for a given MODIS tile.

    Args:
      horizontal: The horizontal cell number.
      vertical: The vertical cell number.

    Returns:
      A GeoJSON geometry for the selected cell.
    """
    cell_size = MODIS_WIDTH / MODIS_CELLS
    base_x = -MODIS_WIDTH
    base_y = -MODIS_WIDTH / 2
    min_x = base_x + horizontal * cell_size
    max_x = base_x + (horizontal + 1) * cell_size - MODIS_250_SCALE
    min_y = base_y + (MODIS_CELLS - vertical - 1) * cell_size
    max_y = base_y + (MODIS_CELLS - vertical) * cell_size - MODIS_250_SCALE

    logging.info(str(min_x)+", "+str(min_y)+", "+str(max_x)+", "+str(max_y))

    rectangle = ee.Geometry(
        ee.Geometry.Rectangle(min_x, min_y, max_x, max_y), MODIS_CRS)

    return rectangle


def _get_raw_mapid(mapid):
    """Strips any fields other than "mapid" and "token" from a MapId object."""
    if mapid:
        return {
            'token': mapid['token'],
            'mapid': mapid['mapid']
        }
    else:
        return {
            'token': '',
            'mapid': ''
        }
