"""
models.py

App Engine datastore models

"""

import ast
from datetime import datetime, date, time
from dateutil.relativedelta import relativedelta
import calendar
import re
import logging
import operator
import types

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import deferred

from application import settings
import ee
from ft import FT
from kml import path_to_kml
from mercator import Mercator
import simplejson as json
from time_utils import timestamp


CELL_BLACK_LIST = ['1_4_0', '1_0_4', '1_1_4', '1_4_4']

METER2_TO_KM2 = 1.0/(1000*1000)

class User(db.Model):

    current_cells = db.IntegerProperty(default=0);
    user = db.UserProperty()
    role = db.StringProperty(default='editor')
    mail = db.StringProperty()

    @staticmethod
    def reset():
        """reset cell count """
        for x in User.all():
            x.current_cells = 0;
            x.put()


    @staticmethod
    def get_user(user):
        q = User.all().filter('user =', user)
        u = q.fetch(1)
        if u:
            return u[0]
        return None

    @staticmethod
    def get_or_create(user):
        u = User.get_user(user)
        if not u:
            u = User(user=user)
            u.put()
        return u

    def is_admin(self):
        return self.role == 'admin'

    def as_dict(self):
        return {
                'id': str(self.key()),
                'current_cells': self.current_cells,
                'mail': self.user.email(), 'is_admin': self.is_admin()
        }

    def as_json(self):
        return json.dumps(self.as_dict())


class Report(db.Model):

    start = db.DateProperty();
    end = db.DateProperty();
    finished = db.BooleanProperty(default=False);
    cells_finished = db.IntegerProperty(default=0)
    total_cells = db.IntegerProperty(default=(25-len(CELL_BLACK_LIST))*25)
    assetid = db.StringProperty()

    # some stats
    degradation = db.FloatProperty(default=0.0)
    deforestation = db.FloatProperty(default=0.0)

    @staticmethod
    def current():
        q = Report.all().filter('finished =', False).order("-start")
        r = q.fetch(1)
        if r:
            return r[0]
        return None
    
    @staticmethod
    def find_by_assetid(assetid):
        q = Report.all().filter('asssetid =', assetid)
        r = q.fetch(1)
        if r:
            return r[0]
        return None
    
    @staticmethod
    def find_by_period(start, end):
        q = Report.all().filter('start =', start).filter("end =", end)
        r = q.fetch(1)
        if r:
            return r[0]
        return None
    
    @staticmethod
    def all_period():
        q = Report.all().order('-assetid')
        r = q.fetch(200)
        
        if r:
            result = []
            for i in range(len(r)):
                result.append({
                               'id': str(r[i].key()),
                               'fusion_tables_id': str(r[i].key().id()),
                               'start': timestamp(r[i].start),
                               'end': timestamp(r[i].end or date.today()),
                               'finished': r[i].finished,
                               'cells_finished': r[i].cells_finished(),
                               'type': 'report',
                               'visibility': True,
                               'total_cells': r[i].total_cells,
                               'str': r[i].start.strftime("%Y-%b-%d"),
                               'str_end': (r[i].end or date.today()).strftime("%Y-%b-%d"),
                               'assetid': r[i].assetid,
                               'deforestation': r[i].deforestation,
                               'degradation': r[i].degradation
                              })
                
            return {'message': 'All reports', 'data': result}
        
        return {'message': 'Nothing', 'data': None}
    
    
    
    def cells_finished(self):
        return Cell.all().filter('report =', self).filter('done =', True).count()

    def as_dict(self):
        return {
                'id': str(self.key()),
                'fusion_tables_id': str(self.key().id()),
                'start': timestamp(self.start),
                'end': timestamp(self.end or date.today()),
                'finished': self.finished,
                'cells_finished': self.cells_finished(),
                'total_cells': self.total_cells,
                'str': self.start.strftime("%Y-%b-%d"),
                'str_end': (self.end or date.today()).strftime("%Y-%b-%d"),
                'assetid': self.assetid,
                'deforestation': self.deforestation,
                'degradation': self.degradation
        }

    def close(self, assetid):
        if not self.finished:
            self.end = date.today();
            self.finished = True
            self.assetid = assetid
            self.put()
            User.reset()
            #deferred.defer(self.update_fusion_tables)

    def as_json(self):
        return json.dumps(self.as_dict())

    def comparation_range(self):
        r = self.previous()
        if r:
            d = r.start
        else:
            st = date(self.start.year, self.start.month, self.start.day)
            d = st - relativedelta(months=1)
        return tuple(map(timestamp, (d, self.start)))

    @staticmethod
    def add_report(start, end, assetid='null'):
        logging.info(start+', '+end)
        start_date = datetime.strptime(start, "%d/%b/%Y").date()
        end_date   = datetime.strptime(end, "%d/%b/%Y").date()

        q = Report.all().filter('start', start_date).filter('end', end_date)
        r = q.fetch(1)
        logging.info(r)
        if len(r) > 0:
            return {'message': 'Period already created, try another one!', 'data': None}
        else:
            r_last = Report.all().filter('start <', start_date).order('-start').fetch(1)
            if len(r_last) > 0:
                r = r_last[0]
                if not r.finished and r.assetid == 'null':
                    r.finished = True;
                    r.assetid = r.previous().assetid
                    r_new = Report(start=start_date, end=end_date, assetid=assetid)
                    r.put()
                    r_new.put()
                    return {'message': 'New period of analyse saved!', 'data': None}
                else:
                    return {'message': 'New period of analyse not saved!', 'data': None}
            else:
                return {'message': 'Period not accepted!', 'data': None}


    def base_map(self):
        r = self.previous()
        if r:
            return r.assetid
        #return "PRODES_2009"
        return "PRODES_IMAZON_2011a"

    def previous(self):
        r = Report.all().filter('start <', self.start).order('-start').fetch(1)
        if r:
            return r[0]
        return None

    def range(self):
        end = self.end or datetime.now()
        return tuple(map(timestamp, (self.start, end)))

    def __unicode__(self):
        r1 = self.comparation_range()
        return u"(%s, %s) -> %s" % (datetime.fromtimestamp(r1[0]/1000).isoformat(),
                                   datetime.fromtimestamp(r1[1]/1000).isoformat(),
                                   self.start.isoformat())

SPLITS = 5
class Cell(db.Model):

    z = db.IntegerProperty(required=True)
    x = db.IntegerProperty(required=True)
    y = db.IntegerProperty(required=True)
    # used for speedup queries
    parent_id = db.StringProperty()
    report = db.ReferenceProperty(Report)
    ndfi_low = db.FloatProperty(default=0.2)
    ndfi_high = db.FloatProperty(default=0.3)
    ndfi_change_value = db.FloatProperty(default=0.0)
    done = db.BooleanProperty(default=False);
    last_change_by = db.UserProperty()
    last_change_on = db.DateTimeProperty(auto_now=True)
    compare_view = db.StringProperty(default='four')
    operation = db.StringProperty(default='sad')
    map_one_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                   '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                   '"LANDSAT/LE7_L1T","false","LANDSAT/LC8_L1T","false","SMA","false","RGB","false","NDFI T0 (MODIS)","false",'
                                                   '"NDFI T1 (MODIS)","false","NDFI analysis","true","True color RGB141","false","False color RGB421","false",'
                                                   '"F color infrared RGB214","false","Validated polygons","true",*')

    map_two_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                   '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                   '"LANDSAT/LE7_L1T","false","LANDSAT/LC8_L1T","false","SMA","false","RGB","false","NDFI T0 (MODIS)",'
                                                   '"true","NDFI T1 (MODIS)","false","NDFI analysis","true","True color RGB141","false","False color RGB421","false",'
                                                   '"F color infrared RGB214","false","Validated polygons","true",*')

    map_three_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                     '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                     '"LANDSAT/LE7_L1T","false","LANDSAT/LC8_L1T","false","SMA","false","RGB","false","NDFI T0 (MODIS)","false",'
                                                     '"NDFI T1 (MODIS)","true","NDFI analysis","true","True color RGB141","false","False color RGB421","false",'
                                                     '"F color infrared RGB214","false","Validated polygons","true",*')

    map_four_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                      '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                      '"Terrain","true","Satellite","false","Hybrid","false","Roadmap","false","LANDSAT/LE7_L1T","false",'
                                                      '"LANDSAT/LC8_L1T","true","NDFI T0","false","True color RGB141","false","False color RGB421","false",'
                                                      '"F color infrared RGB214","false",*')


    @staticmethod
    def get_cell(report, operation, x, y, z):
        q = Cell.all()
        q.filter("z =", z)
        q.filter("x =", x)
        q.filter("y =", y)
        if operation == 'null':
            q.filter("operation =", 'sad')
        else:    
            q.filter("operation =", operation)
        q.filter("report =", report)
        cell = q.fetch(1)
        if cell:
            return cell[0]
        return None

    def child(self, i, j):
        zz = self.z+1
        xx = (SPLITS**self.z)*self.x + i
        yy = (SPLITS**self.z)*self.y + j
        return Cell.get_or_create(self.report, self.operation, xx, yy, zz)

    def children(self):
        """ return child cells """
        eid = self.external_id()
        childs = Cell.all()
        childs.filter('report =', self.report)
        childs.filter('parent_id =', eid)
        childs.filter('operation = ', self.operation)

        children_cells = dict((x.external_id(), x) for x in childs.fetch(SPLITS*SPLITS))

        cells = []
        for i in xrange(SPLITS):
            for j in xrange(SPLITS):
                zz = self.z+1
                xx = (SPLITS**self.z)*self.x + i
                yy = (SPLITS**self.z)*self.y + j

                cid= "_".join(map(str,(zz, xx, yy)))
                if cid in children_cells:
                    cell = children_cells[cid]
                else:
                    cell = Cell.default_cell(self.report, self.operation, xx, yy, zz)
                cells.append(cell)
        return cells

    def calculate_ndfi_change_from_childs(self):
        ndfi = 0.0
        ch = self.children()
        for c in ch:
            ndfi += c.ndfi_change_value
        self.ndfi_change_value = ndfi/len(ch)
        self.put()

    def calc_parent_id(self):
        return '_'.join((str(self.z - 1), str(self.x/SPLITS), str(self.y/SPLITS)))

    def get_parent(self):
        if self.z == 0:
            return None
        pid = self.calc_parent_id()
        z, x, y = Cell.cell_id(pid)
        return Cell.get_or_default(self.report, self.operation, x, y, z)

    def put(self):
        self.parent_id = self.calc_parent_id()
        p = self.get_parent()
        # update parent
        if p:
            p.last_change_by = self.last_change_by
            p.put()
        super(Cell, self).put()

    @staticmethod
    def cell_id(id):
        return tuple(map(int, id.split('_')))

    @staticmethod
    def get_or_create(r, operation, x, y ,z):
        c = Cell.get_cell(r, operation, x, y, z)
        if not c:
            c = Cell.default_cell(r, operation, x, y ,z)
            c.put()
        return c

    @staticmethod
    def get_or_default(r, operation, x, y, z):
        cell = Cell.get_cell(r, operation, x, y, z)
        if not cell:
            cell = Cell.default_cell(r, operation, x, y, z)
        return cell

    @staticmethod
    def default_cell(r, operation, x, y, z):
        if operation == 'null':
            return Cell(z=z, x=x, y=y, ndfi_low=0.2, ndfi_high=0.3, report=r, operation='sad')
        else:
            return Cell(z=z, x=x, y=y, ndfi_low=0.2, ndfi_high=0.3, report=r, operation=operation)
    
    @staticmethod
    def find_by_operation_parent(operation, parent_name):
        q = Cell.all().filter('operation =', operation).filter("parent_id =", parent_name)
        r = q.fetch(50)
        if r:
            return r 
        else:
            return None
    
    @staticmethod
    def find_by_operation_xyz(operation, x, y, z):
        q = Cell.all().filter('operation =', operation).filter("x =", x).filter("y =", y).filter("z =", z)
        r = q.fetch(1)
        if r:
            return r 
        else:
            return None

    def external_id(self):
        return "_".join(map(str,(self.z, self.x, self.y)))

    def as_dict(self):
        #latest = self.latest_polygon()
        t = 0
        by = 'Nobody'
        """
        if latest:
            t = timestamp(latest.added_on)
            by = latest.added_by.nickname()
        """

        key_id = '' 
        try:
            key_id = self.key()
            note_count = self.note_set.count()
            t = timestamp(self.last_change_on)
            if self.last_change_by:
                by = self.last_change_by.nickname()
            children_done = self.children_done()
        except:
            note_count = 0
            t = 0
            children_done = 0

        return {                
                'key': str(key_id),
                'id': self.external_id(),
                'z': self.z,
                'x': self.x,
                'y': self.y,
                'report_id': str(self.report.key()),
                'ndfi_low': self.ndfi_low,
                'ndfi_high': self.ndfi_high,
                'ndfi_change_value': self.ndfi_change_value,
                'compare_view': self.compare_view,
                'operation': self.operation,
                'map_one_layer_status': self.map_one_layer_status,
                'map_two_layer_status': self.map_two_layer_status,
                'map_three_layer_status': self.map_three_layer_status,
                'map_four_layer_status': self.map_four_layer_status,
                'done': self.done,
                'latest_change': t,
                'added_by': by,
                'polygon_count': self.polygon_count(),
                'note_count': note_count,
                'children_done': children_done,
                'blocked': self.external_id() in CELL_BLACK_LIST
        }

    def polygon_count(self):
        try:
            self.key()
        except:
            #not saved
            return 0
        return Area.all().filter('cell =', self).order('-added_on').count();
    
    @staticmethod
    def polygon_by_report(report):
        q = Cell.all().filter('report =', report).order('-last_change_on')
        r = q.fetch(100)
        if r:
            features = []
            for i in range(len(r)):
                if r[i].operation == 'sad' or r[i].operation == types.NoneType:
                    q = Area.all().filter('cell =', r[i]).order('-added_on')
                    a = q.fetch(100)
                    if a:
                        for j in range(len(a)):
                            if a[j]:
                                features.append(a[j].as_feature())
                            
            return ee.FeatureCollection(features).getInfo()     
                
        else:
            return None        

    def children_done(self):
        eid = self.external_id()
        childs = Cell.all()
        childs.filter('report =', self.report)
        childs.filter('parent_id =', eid)
        childs.filter('done =', True)
        return childs.count()

    def latest_polygon(self):
        try:
            self.key()
        except:
            #not saved
            return None
        q = Area.all().filter('cell =', self).order('-added_on')
        o = q.fetch(1)
        if o:
            return o[0]
        return None

    def as_json(self):
        return json.dumps(self.as_dict())

    def bounds(self, top_level_bounds):
        """ return lat,lon bounds given toplevel BB bounds
            ``top_level_bounds`` is a tuple with (ne, sw) being
            ne and sw a (lat, lon) tuple
            return bounds in the same format
        """
        righttop = Mercator.project(*top_level_bounds[0]) #ne
        leftbottom = Mercator.project(*top_level_bounds[1]) #sw
        topx = leftbottom[0]
        topy = righttop[1]
        w = righttop[0] - leftbottom[0];
        h = -righttop[1] + leftbottom[1];
        sp = SPLITS**self.z
        sx = w/sp;
        sy = h/sp;
        return (
            Mercator.unproject((self.x + 1)*sx + topx, (self.y)*sy + topy),
            Mercator.unproject(self.x*sx + topx, topy + (self.y+1)*sy)
        )

    def bbox_polygon(self, top_bounds):
        bounds = self.bounds(top_bounds)
        ne = bounds[0]
        sw = bounds[1]
        # spcify lon, lat
        #return [[[ (sw[1], sw[0]), (sw[1], ne[0]), (ne[1], ne[0]), (ne[1], sw[0]) ]]]
        return {"type":"Polygon", "coordinates": [[ (sw[1], sw[0]), (sw[1], ne[0]), (ne[1], ne[0]), (ne[1], sw[0]) ]]}
    
class CellGrid(db.Model):     
    name = db.StringProperty(required=True)
    parent_name = db.StringProperty()        
    last_change_on = db.DateTimeProperty(auto_now=True)
    geo = db.TextProperty(required=True)
    
    @property
    def tiles(self):
        geo_cell_grid = ee.Geometry.Polygon(ast.literal_eval(self.geo))
        q = Tile.all().filter('cells =', self.name)
        r = q.fetch(300)                
        result = []
        
        for i in range(len(r)):
            geo_tile = ee.Geometry.Polygon(ast.literal_eval(r[i].geo))
            #intersection = geo_cell_grid.intersection(geo_tile, ee.ErrorMargin(30.0, "meters"), "EPSG:4326")
                        
            #if len(intersection.getInfo()['coordinates']) > 0:
            if geo_cell_grid.intersects(geo_tile, ee.ErrorMargin(30.0, "meters"), "EPSG:4326").getInfo():
                logging.info(r[i].name)
                r[i].save_cells(self.name, False)
                #logging.info(geo_cell_grid.intersects(geo_tile, ee.ErrorMargin(30.0, "meters"), "EPSG:4326").getInfo())
                result.append(r[i])
            else:
                r[i].save_cells(self.name, True)
                logging.info(r[i].name)
        
        return result
    
    def tiles_as_dict(self):
        tiles = self.tiles
        if tiles:
            results = {}
            for i in range(len(tiles)):
                results.update({'tile'+str(i): tiles[i].as_dict()})
            return results
        else:
            return None
    
    def as_dict(self):
        return {
                #'id': str(self.ID),
                'name': self.name,
                'parent_name': self.parent_name,
                'geo': self.geo
        }
    
    def as_json(self):
        return json.dumps(self.as_dict())
    
    @staticmethod
    def find_by_name(name):
        q = CellGrid.all().filter("name =", name)
        r = q.fetch(1)
        if r:
            return r[0] 
        else:
            return None
    
    @staticmethod
    def find_by_parent_name(parent_name):
        q = CellGrid.all().filter("parent_name =", parent_name)
        r = q.fetch(50)
        if r:
            return r 
        else:
            return None

    def save(self):
        z, x, y = self.name.split('_')
        z_parent = str(int(z) - 1)
        x_parent = int(x)/5
        y_parent = int(y)/5
        self.parent_name = str(z_parent)+'_'+str(x_parent)+'_'+str(y_parent) 
         
        q = CellGrid.all().filter('name =', self.name)
        r = q.fetch(1)

        try:
            if r:
                r[0].geo         = self.geo   
                r[0].parent_name = self.parent_name                        
                r[0].put()
                return 'Cell updated.'  
            else:
                self.put()
                return 'Cell saved.'

            
        except:
            return 'Could not save cell.'
        
class Tile(db.Model):
    sensor = db.StringProperty(required=True)
    name = db.StringProperty(required=True)
    cells = db.StringListProperty(required=True)
    last_change_on = db.DateTimeProperty(auto_now=True)
    geo = db.TextProperty(required=True)
    
    
    
    def as_dict(self):
        return {
                #'id': str(self.ID),
                'sensor': self.sensor,
                'name': self.name,
                'cells': self.cells,
                'geo': self.geo
        }
    
    def as_json(self):
        return json.dumps(self.as_dict())
    
    @staticmethod
    def find_by_cell_name(cell_name):
        q = Tile.all().filter('cells =', cell_name)
        r = q.fetch(100)
        if r:
            tiles = {}
            for i in range(len(r)):
                tiles.update({'tile'+str(i): r[i].as_dict()})
            return tiles
        else:
            return None
        
        
    @staticmethod
    def find_tiles_by_sensor(sensor):
        q = Tile.all().filter('sensor =', sensor)
        r = q.fetch(500)
        if r:
            tiles = []
            for i in range(len(r)):
                tiles.append(r[i].name)
            return tiles
        else:
            return []
        
    @staticmethod
    def find_geo_region(name):
        q = Tile.all().filter('name =', name)
        r = q.fetch(1)
        if r:             
            return  ast.literal_eval(r[0].geo) 
        else:
            return None
        
    def save_cells(self, name, remove):
        if remove:
            self.cells.remove(name)
            self.put()
        else:
            if name in self.cells:
                pass
            else:
                self.cells.append(name)
                self.put()    
            
                
    
    def save(self):  
        q = Tile.all().filter('name =', self.name)
        r = q.fetch(1)
        
        try:
            if r:
                logging.info(type(self.cells))
                logging.info(type(r[0].cells))
                for cell in self.cells: 
                    if cell not in r[0].cells:
                        r[0].cells.append(cell)
                                
                r[0].sensor = self.sensor
                r[0].geo    = self.geo   
                r[0].put()
                
                return 'Cell updated.' 
            else:
                self.put()
                return 'Cell saved.'

            
        except:
            return 'Could not save cell.'


class Area(db.Model):
    """ area selected by user """

    DEGRADATION = 0
    DEFORESTATION = 1

    geo = db.TextProperty(required=True)
    added_by = db.UserProperty()
    added_on = db.DateTimeProperty(auto_now_add=True)
    type = db.IntegerProperty(required=True)
    fusion_tables_id = db.IntegerProperty()
    cell = db.ReferenceProperty(Cell)

    def as_dict(self):
        return {
                'id': str(self.key()),
                'key': str(self.key()),
                'cell': str(self.cell.key()),
                'paths': json.loads(self.geo),
                'type': self.type,
                'fusion_tables_id': self.fusion_tables_id,
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname())
        }

    def as_json(self):
        return json.dumps(self.as_dict())
    
    @staticmethod
    def find_feature_collection_by_cell(cell):
        q = Area.all().filter('cell =', cell)
        r = q.fetch(100)
        logging.info("+++++++++++++++ Polygons ++++++++++++++++++++++++")
        logging.info(len(r))
        if r: 
            result = []
            for i in range(len(r)):
                result.append(r[i].as_feature())
            
            return ee.FeatureCollection(result)
        else:
            return None
    
    def as_feature(self):
        geo = self.geo
        polygon = ast.literal_eval(geo)
        for i in range(len(polygon[0])):
            polygon[0][i] = polygon[0][i][::-1]
        geometry = ee.Geometry.Polygon(polygon)
        properties = self.as_dict()
        return ee.Feature(geometry, properties)

    def save(self):
        """ wrapper for put makes compatible with django"""
        exists = True
        try:
            self.key()
        except db.NotSavedError:
            exists = False
        ret = self.put()
        # call defer AFTER saving instance
        if not exists:
            deferred.defer(self.create_fusion_tables)
        else:
            deferred.defer(self.update_fusion_tables)
        return ret

    def delete(self):
        super(Area, self).delete()
        deferred.defer(self.delete_fusion_tables)
    @staticmethod
    def _get_ft_client():
        cl = FT(settings.FT_CONSUMER_KEY,
                settings.FT_CONSUMER_SECRET,
                settings.FT_TOKEN,
                settings.FT_SECRET)
        table_id = cl.table_id(settings.FT_TABLE)
        if not table_id:
            raise Exception("Create areas %s first" % settings.FT_TABLE)
        return cl

    def fusion_tables_type(self):
        """ custom type id for FT """
        if self.type == self.DEGRADATION:
            return 8
        return 7

    def delete_fusion_tables(self):
        """ delete area from fusion tables. Do not use this method directly, call delete method"""
        cl = self._get_ft_client()
        table_id = cl.table_id(settings.FT_TABLE)
        cl.sql("delete from %s where rowid = '%s'" % (table_id, self.fusion_tables_id))
    def update_fusion_tables(self):
        """ update polygon in fusion tables. Do not call this method, use save method when change instance data """
        logging.info("updating fusion tables %s" % self.key())
        cl = self._get_ft_client()
        table_id = cl.table_id(settings.FT_TABLE)
        geo_kml = path_to_kml(json.loads(self.geo))
        cl.sql("update  %s set geo = '%s', type = '%s' where rowid = '%s'" % (table_id, geo_kml, self.fusion_tables_type(), self.fusion_tables_id))

    def create_fusion_tables(self):
        logging.info("saving to fusion tables report %s" % self.key())
        cl = self._get_ft_client()
        table_id = cl.table_id(settings.FT_TABLE)
        geo_kml = path_to_kml(json.loads(self.geo))
        rowid = cl.sql("insert into %s ('geo', 'added_on', 'type', 'report_id') VALUES ('%s', '%s', %d, %d)" % (table_id, geo_kml, self.added_on, self.fusion_tables_type(), self.cell.report.key().id()))
        self.fusion_tables_id = int(rowid.split('\n')[1])
        rowid = cl.sql("update %s set rowid_copy = '%s' where rowid = '%s'" % (table_id, self.fusion_tables_id, self.fusion_tables_id))
        self.put()

class Note(db.Model):
    """ user note on a cell """

    msg = db.TextProperty(required=True)
    added_by = db.UserProperty()
    added_on = db.DateTimeProperty(auto_now_add=True)
    cell = db.ReferenceProperty(Cell)

    def as_dict(self):
        return {'id': str(self.key()),
                'msg': self.msg,
                'author': self.added_by.nickname(),
                'date': timestamp(self.added_on)}

    def as_json(self):
        return json.dumps(self.as_dict())

class Error(db.Model):
    """ javascript errors registered """
    msg = db.TextProperty(required=True)
    url = db.StringProperty(required=True)
    line= db.StringProperty(required=True)
    user = db.UserProperty()


class StatsStore(db.Model):
    report_id = db.StringProperty()
    json = db.TextProperty()

    @staticmethod
    def get_for_report(id):
        try:
            s = StatsStore.all().filter('report_id =', id).fetch(1)[0]
            return s
        except IndexError:
            return None

    def as_dict(self):
        if not hasattr(self, '_as_dict'):
            self._as_dict = json.loads(self.json)
        return self._as_dict

    def for_table(self, table, zone=None):
        tb = [v for k, v in self.as_dict()['stats'].iteritems() if str(v['table']) == str(table)]
        if zone:
            return [x for x in tb if str(x['id']) == zone]

        return tb


    def table_accum(self, table, zone=None):
        table_stats = self.for_table(table, zone)
        if not table_stats:
            logging.info("no stats for %s on %s" % (table, self.report_id))
            return None
        return [{
            'id': zone,
            'def': reduce(operator.add, map(float, (x['def'] for x in table_stats))),
            'deg': reduce(operator.add, map(float, (x['deg'] for x in table_stats)))
        }]

class FustionTablesNames(db.Model):
    table_id = db.StringProperty()
    json = db.TextProperty()
    def as_dict(self):
        return json.loads(self.json)

#FT_TABLE_PICKER = 'Merged and Exported SAD inclusions - Testes Image Picker'


class ImagePicker(db.Model):
    """ images selected by user """

    added_on     = db.DateTimeProperty(auto_now_add=True)
    added_by     = db.UserProperty()
    report       = db.ReferenceProperty(Report)    
    cell         = db.StringProperty(required=True)
    location     = db.TextProperty(required=True)
    sensor_dates = db.StringListProperty(required=True)
    start        = db.DateTimeProperty(required=True)
    end          = db.DateTimeProperty(required=True)


    def as_dict(self):
        
        return {
                'id': str(self.key()),
                'key': str(self.key()),               
                'sensor': self.sensor,
                'cell': self.cell,
                'year': self.year,
                'month': self.month,
                'day': self.day,
                'Location': json.loads(self.location),
                'compounddate': self.compounddate,
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname())
        }



    def as_json(self):
        return json.dumps(self.as_dict())

    @staticmethod
    def find_by_period(start, end, long_span=False):
        if isinstance(start, types.IntType):
            start = datetime.fromtimestamp(start / 1e3)
            logging.info(start.strftime("%Y-%b-%d %H:%M:%S"))
        if isinstance(end, types.IntType):
            end = datetime.fromtimestamp(end / 1e3)
            logging.info(end.strftime("%Y-%b-%d %H:%M:%S"))
            
        if long_span:
            q = ImagePicker.all().filter('start <=', start)
        else:     
            q = ImagePicker.all().filter('start =', start).filter('end =', end)
        r = q.fetch(100)
        
        if r:
            for i in range(len(r)):                            
                for j in range(len(r[i].sensor_dates)):
                    if "modis" not in r[i].sensor_dates[j]:
                        r.remove(r[i])
            return r
        else:
            return None
        
    @staticmethod
    def find_by_compounddate_period(start_compounddate, end_compounddate, tile):
        q = ImagePicker.all().filter('compounddate >=', start_compounddate).filter('compounddate <=', end_compounddate).filter("cell =", tile)
        r = q.fetch(10)
        if r:
            result = {}
            for i in range(len(r)):
                for j in range(len(r[i].day)): 
                    date = r[i].year+'-'+r[i].month+'-'+r[i].day[j]
                    sensor = r[i].sensor
                    result[date] = sensor
                
            return result
        else:
            return None
    
    @staticmethod
    def is_day_selected(day, start, end, cell):
        q = ImagePicker.all().filter('start =', start).filter('end =', end).filter('cell =', cell)
        r = q.fetch(1)
        
        if len(r) > 0:
            for i in range(len(r)):
                for j in range(len(r[i].sensor_dates)):
                    if day in r[i].sensor_dates[j]:
                        return True
                        
            return False
        else:
            return False
        
    @staticmethod
    def list_by_period(start_compounddate, end_compounddate, tile):
        q = ImagePicker.all().filter('compounddate >=', start_compounddate).filter('compounddate <=', end_compounddate).filter("cell =", tile)
        r = q.fetch(100)
        if r:
            result = []
            for i in range(len(r)):
                result.append(r[i].as_dict())
                #for j in range(len(r[i].day)): 
                #    date = r[i].year+'-'+r[i].month+'-'+r[i].day[j]
                #    sensor = r[i].sensor
                #    result[date] = sensor
                
            return result
        else:
            return []
        
    @staticmethod
    def list_by_period_date(start, end, tile):
        q = ImagePicker.all().filter("cell =", tile).filter("start =", start).filter("end =", end)
        r = q.fetch(1)
        if r:
            result = []
            for i in range(len(r[0].sensor_dates)):
                sensor, date = r[0].sensor_dates[i].split('__')
                date = datetime.strptime(date, '%Y-%m-%d').date()
                
                if date < end and date > start:
                    result.append({                                  
                                   'sensor': sensor,
                                   'cell': r[0].cell,
                                   'year': date.year,
                                   'month': date.month,
                                   'day': date.day,
                                   'Location': json.loads(r[0].location),
                                   'compounddate': '%04d%02d' % (date.year, date.month),
                                   'added_on': timestamp(r[0].added_on),
                                   'added_by': str(r[0].added_by.nickname())})
                
                
            return result
        else:
            return []
        
     

    @staticmethod
    def find_by_compounddate(compounddate):
        q = ImagePicker.all().filter('compounddate =', compounddate)
        r = q.fetch(10)
        if r:
            return r
        else:
            return None
    
        
    @staticmethod
    def find_by_period_and_cell(start, end, cell):
        q = ImagePicker.all().filter('start =', start).filter('end =', end).filter('cell =', cell)
        r = q.fetch(1)
        if r:
            return r
        else:
            return None
        
    @staticmethod
    def return_feature_collection(r):
        feature_collection = []
        
        if r:
                for i in range(len(r)):
                    location = r[i].location
                    polygon = ast.literal_eval(location)
                    geometry = ee.Geometry.Polygon(polygon)
                    
                    days = []
                    for j in range(len(r[i].sensor_dates)):
                        sensor_date      = r[i].sensor_dates[j]
                        date_day         = re.search(r'(\d+-\d+-\d+)', sensor_date).group(1)
                        year, month, day = date_day.split('-')
                        days.append(str(int(day)).zfill(2))   
                        
                    
                    properties = {'cell': r[i].cell,
                                  'compounddate': int(year + month),
                                  'day': ','.join(days),
                                  'month': int(month),
                                  'year': int(year)
                                 }
                    feature = ee.Feature(geometry, properties)
                    feature_collection.append(feature)
                    
                result = ee.FeatureCollection(feature_collection) 
                #logging.info(result)
                return result 
        
        else:
            return None
    
    @staticmethod
    def save_feature_collection(feature_collection):
        logging.info("Image Picker feature size:"+str(len(feature_collection.getInfo()['features'])))        
        collections_ = feature_collection.getInfo()['features']
        report = Report.current()                
        
        for i in range(len(collections_)):
            collection_ = collections_[i]
            location = collection_['geometry']['coordinates']
            properties = collection_['properties']            
            cell = properties['cell']
            compounddate = properties['compounddate']
            days = properties['day'].split(',')
            month = properties['month']
            year = properties['year']                                    
            sensor_dates = []
            date_start = date(int(year), int(month), 1)
            date_start = datetime.combine(date_start, time())
            date_end   = date(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
            date_end = datetime.combine(date_end, time())
            
            for i in range(len(days)):
                day = str(int(days[i])).zfill(2)                
                sensor_dates.append("modis__" + year + '-' + str(int(month)).zfill(2) + '-' + day)  
            
            #image_picker = ImagePicker(sensor='MODIS', report=report, added_by= users.get_current_user(), cell=str(cell),  year=str(year), month=str(month), day=days.split(","), location=str(location), compounddate=str(compounddate))
            image_picker = ImagePicker(report=report, added_by= users.get_current_user(), cell=str(cell),  location=str(location), sensor_dates=sensor_dates, start=date_start, end=date_end)
            
            image_picker.save()

    def save(self):
        q = ImagePicker.all().filter('cell =', self.cell).filter('start =', self.start).filter('end =', self.end)
        r = q.fetch(1)

        try:
            if r:
                
                for index in range(len(self.sensor_dates)): 
                    if self.sensor_dates[index] not in r[0].sensor_dates:
                        r[0].sensor_dates.append(self.sensor_dates[index])               
                r[0].put()
            else:
                self.put()

            return 'Images saved.'
        except:
            return 'Could not save imagens.'



class Downscalling(db.Model):
    """ images selected by user """

    added_on     = db.DateTimeProperty(auto_now_add=True)
    added_by     = db.UserProperty()
    report       = db.ReferenceProperty(Report)
    cell         = db.StringProperty(required=True)
    region       = db.TextProperty(required=True)
    compounddate = db.StringProperty(required=True)
    band         = db.IntegerProperty(required=True)
    model        = db.StringProperty(required=True)
    sill         = db.IntegerProperty(required=True)
    range        = db.IntegerProperty(required=True)
    nugget       = db.IntegerProperty(required=True)

    def as_dict(self):
        return {
                'id': str(self.key()),
                'key': str(self.key()),
                'cell': self.cell,
                'region': json.loads(self.region),
                'compounddate': self.compounddate,
                'band': self.band,
                'model': self.model,
                'sill': self.sill,
                'range': self.range,
                'nugget': self.nugget,
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname())
        }



    def as_json(self):
        return json.dumps(self.as_dict())

    @staticmethod
    def find_by_compounddate(compounddate):
        q = Downscalling.all().filter('compounddate =', compounddate)
        r = q.fetch(50)
        if r:
            return r
        else:
            return None
    
    @staticmethod
    def return_feature_collection(r):
        feature_collection = []
        
        if r:
                for i in range(len(r)):
                    region = r[i].region
                    polygon = ast.literal_eval(region)
                    geometry = ee.Geometry.Polygon(polygon)
                    properties = {'Band': r[i].band,
                                  'Cell': r[i].cell,
                                  'Compounddate': int(r[i].compounddate),
                                  'Model': r[i].model,
                                  'Nugget': r[i].nugget,
                                  'Range': r[i].range,
                                  'Sill': r[i].sill,
                                 }
                    feature = ee.Feature(geometry, properties)
                    feature_collection.append(feature)
                
                result = ee.FeatureCollection(feature_collection)
                
                return result
        
        else:
            return None
    
    @staticmethod
    def save_feature_collection(feature_collection):
        logging.info("Downscalling feature size:"+str(len(feature_collection.getInfo()['features'])))        
        collections_ = feature_collection.getInfo()['features']
        report = Report.current()
        
        for i in range(len(collections_)):
            collection_ = collections_[i]
            location = collection_['geometry']['coordinates']
            properties = collection_['properties']
            band = properties['Band']
            cell = properties['Cell']
            compounddate = properties['Compounddate']
            model = properties['Model']
            range_ = properties['Range']
            sill = properties['Sill']
            nugget = properties['Nugget']
            
            downscalling = Downscalling(report=report,
                                        added_by= users.get_current_user(),
                                        cell=str(cell),
                                        region=str(location),
                                        compounddate=str(int(compounddate)),
                                        band= long(band),
                                        model=model,
                                        sill=long(sill),
                                        range=long(range_),
                                        nugget=long(nugget)
                                       )
            
            downscalling.save()

    def save(self):
        q = Downscalling.all().filter('compounddate =', self.compounddate).filter('cell =', self.cell).filter('band =', self.band)
        r = q.fetch(1)

        try:
            if r:
                r[0].sill   = self.sill
                r[0].range  = self.range
                r[0].nugget = self.nugget
                r[0].put()
            else:
                self.put()

            return 'Values saved.'
        except:
            return 'Could not save values.'


class Baseline(db.Model):
    """ images selected by user """

    added_on     = db.DateTimeProperty(auto_now_add=True)
    added_by     = db.UserProperty(required=True)
    name         = db.StringProperty(required=True)
    cell         = db.ReferenceProperty(Cell)
    start        = db.DateProperty(required=True)
    end          = db.DateProperty()
    defo         = db.FloatProperty(default=165.0)
    deg          = db.FloatProperty(default=175.0)
    shade        = db.FloatProperty(default=65.0)
    gv           = db.FloatProperty(default=19.0)
    soil         = db.FloatProperty(default=4.0)
    cloud        = db.FloatProperty(default=42.0) 
    
    
    @property
    def image_picker(self):
        result = []
        cell_name = str(self.cell.z) +'_'+ str(self.cell.x) +'_'+ str(self.cell.y)
        tiles = Tile.find_by_cell_name(cell_name)
        
        for tile in tiles:
            tile_name = tiles[tile]['name']
            logging.info("======= Tiles =========");
            logging.info(tile_name);
            list_image_picker = ImagePicker.list_by_period_date(self.start, self.end, tile_name)
            result.append(list_image_picker)            
                
            
        return result

    def as_dict(self):
        cell_name = str(self.cell.z) +'_'+ str(self.cell.x) +'_'+ str(self.cell.y)
        return {
                #'key': str(self.key()),
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname()),                
                'name': self.name,
                'cell': cell_name,
                'start': self.start.strftime("%d/%b/%Y"),
                'end': self.end.strftime("%d/%b/%Y"),                                
                'def': self.defo,
                'deg': self.deg,
                'shade': self.shade,
                'gv': self.gv,
                'soil': self.soil,
                'cloud': self.cloud
        }
    
    @staticmethod    
    def change_baseline(baseline):
        q = Baseline.all().filter("name =", baseline['name'])
        r = q.fetch(1)
        if r:
            r[0].defo = float(baseline['def'])
            r[0].deg = float(baseline['deg'])
            r[0].shade = float(baseline['shade'])
            r[0].gv = float(baseline['gv'])
            r[0].soil = float(baseline['soil'])
            r[0].cloud = float(baseline['cloud'])
            r[0].put()
            return r[0]
        else:
            return None   

    def as_json(self):
        return json.dumps(self.as_dict())

    @staticmethod
    def all_formated():
        result = []
        q = Baseline.all().order('-start')
        r = q.fetch(10)
        
        if r:
            for i in range(len(r)):
                result.append({
                               #'id':          r[i].mapid,
                               #'token':       r[i].token,
                               'type':        'baseline',
                               'visibility':  True,
                               'description': r[i].name,
                               #'url': 'https://earthengine.googleapis.com/map/'+r[i].mapid+'/{Z}/{X}/{Y}?token='+r[i].token
                               })
            return result
        else:
            return None
    
    @staticmethod
    def find_by_cell(cell):
        if cell: 
            q = Baseline.all().filter('cell =', cell).order('-start')
            r = q.fetch(1)
            
            if r:
                return r[0] 
            else:
                return None
        else:
            return None
    
    @staticmethod
    def find_by_cell_xyz(cell):
        cell = Cell.find_by_operation_xyz('baseline', cell.x, cell.y, cell.z)
        if cell: 
            q = Baseline.all().filter('cell IN', cell).order('-start')
            r = q.fetch(1)
            
            if r:
                return r[0] 
            else:
                return None
        else:
            return None
    
    @staticmethod
    def find_by_cell_date(cell, start_date, end_date):
        if cell: 
            q = Baseline.all().filter('cell =', cell).filter('start =', start_date).filter('end =', end_date).order('-start')
            r = q.fetch(1)
            
            if r:
                return r[0]
            else:
                return None
        else:
            return None
    
    @staticmethod
    def formated_by_cell_parent(cell_name):
        result = []
        cells = Cell.find_by_operation_parent('baseline', cell_name)
        if cells: 
            q = Baseline.all().filter('cell IN', cells).order('-start')
            r = q.fetch(50)
            
            if r:
                for i in range(len(r)):
                    result.append(r[i].as_dict());
                return result
            else:
                return None
        else:
            return None
    
    @staticmethod
    def formated_by_cell_name(cell_name):
        z, x, y = cell_name.split('_')        
        cell = Cell.find_by_operation_xyz('baseline', int(x), int(y), int(z))
        if cell: 
            q = Baseline.all().filter('cell IN', cell).order('-start')
            r = q.fetch(1)
            
            if r:                
                return r[0].as_dict();
            else:
                return None
        else:
            return None

    def save(self):
        q = ''        
        if self.end:
            q = Baseline.all().filter('start =', self.start).filter('cell =', self.cell).filter('end =', self.end)
        else:
            q = Baseline.all().filter('start =', self.start)
            
        r = q.fetch(1)

        try:
            if r:                
                r[0].put()            
                return r[0].as_dict()                                         
            else:
                self.put()           
                return self.as_dict()      
            
        except:
            return None

class TimeSeries(db.Model):
    """ images selected by user """

    added_on = db.DateTimeProperty(auto_now_add=True)
    added_by = db.UserProperty(required=True)
    name     = db.StringProperty(required=True)
    cell     = db.ReferenceProperty(Cell)
    start    = db.DateProperty(required=True)
    end      = db.DateProperty(required=True)    
    defo     = db.FloatProperty(default=165.0)
    deg      = db.FloatProperty(default=175.0)
    shade    = db.FloatProperty(default=70.0)
    gv       = db.FloatProperty(default=15.0)
    soil     = db.FloatProperty(default=10.0)
    cloud    = db.FloatProperty(default=7.0)
    
    
    @property
    def last_map_cell(self):
        q = TimeSeries.all().filter('cell = ', self.cell).filter('start <', self.start).order('start') 
        r = q.fetch(100)
        
        if r:
            logging.info(len(r))
            result = []
            result.append(Baseline.find_by_cell_xyz(self.cell))            
            for i in range(len(r)):
                result.append(r[i])
            
            return result
        else:
            return [Baseline.find_by_cell_xyz(self.cell)]        
    
    @property
    def image_picker(self):
        result = []      
        cell_name = str(self.cell.z) +'_'+ str(self.cell.x) +'_'+ str(self.cell.y)  
        tiles = Tile.find_by_cell_name(cell_name)
        
        for tile in tiles:
            tile_name = tiles[tile]['name']
            logging.info("======= Tiles =========");
            logging.info(tiles[tile]['name']);
            list_image_picker = ImagePicker.list_by_period_date(self.start, self.end, tile_name)
            result.append(list_image_picker)                            
            
        return result

    def as_dict(self):
        cell_name = str(self.cell.z) +'_'+ str(self.cell.x) +'_'+ str(self.cell.y)
        return {                
                'key': str(self.key()),
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname()),
                'name': self.name,
                'cell': cell_name,
                'start': self.start.strftime("%d/%b/%Y"),
                'end': self.end.strftime("%d/%b/%Y"),
                'def': self.defo,
                'deg': self.deg,
                'shade': self.shade,
                'gv': self.gv,
                'soil': self.soil,
                'cloud': self.cloud                                
        }

    def as_json(self):
        return json.dumps(self.as_dict())
    
    @staticmethod
    def find_last_maps(cell_name):
        z, x, y = cell_name.split('_')        
        cells = Cell.find_by_operation_xyz('timeseries', int(x), int(y), int(z))        
        if cells:
            q = TimeSeries.all().filter('cell IN', cells).order('-start')
            r = q.fetch(100)
            if r:
                result = []
                for i in range(len(r)):
                    result.append(r[i].as_dict())
                return result
            else:
                return None
        else:
            return None
        
    @staticmethod
    def formated_by_cell_parent(cell_name):
        result = []
        cells = Cell.find_by_operation_parent('timeseries', cell_name)
        if cells: 
            q = TimeSeries.all().filter('cell IN', cells).order('-start')
            r = q.fetch(50)
            
            if r:
                for i in range(len(r)):
                    result.append(r[i].as_dict());
                return result
            else:
                return None
        else:
            return None
        
    @staticmethod
    def formated_by_cell_name(cell_name):
        z, x, y = cell_name.split('_')        
        cells = Cell.find_by_operation_xyz('timeseries', int(x), int(y), int(z))                
        if cells: 
            q = TimeSeries.all().filter('cell IN', cells).order('-start')
            r = q.fetch(1)
            
            if r:
                return r[0].as_dict()
                
            else:
                return None
        else:
            return None
        
    @staticmethod
    def find_cell_period(cell, start, end):        
        #z, x, y = cell_name.split('_')        
        #cells = Cell.find_by_operation_xyz('timeseries', int(x), int(y), int(z))        
        if cell: 
            q = TimeSeries.all().filter('cell =', cell).filter('start =', start).filter('end =', end)
            r = q.fetch(1)
            
            if r:
                return r[0]
                
            else:
                return None
        else:
            return None        

    @staticmethod
    def all_formated():
        result = []
        q = TimeSeries.all().order('-start')
        r = q.fetch(10)
        
        if r:
            for i in range(len(r)):
                result.append({                               
                               'type':        'time_series',
                               'visibility':  True,
                               'description': r[i].name
                               #'url': 'https://earthengine.googleapis.com/map/'+r[i].mapid+'/{Z}/{X}/{Y}?token='+r[i].token
                               })
            return result
        else:
            return None
            

    def save(self):
        q = TimeSeries.all().filter('start =', self.start).filter('end =', self.end)
        r = q.fetch(1)

        try:
            if r:                
                r[0].put()            
                return r[0].as_dict()                                         
            else:
                self.put()           
                return self.as_dict()      
            
        except:
            return None
        
