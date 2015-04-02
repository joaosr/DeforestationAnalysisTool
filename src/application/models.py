"""
models.py

App Engine datastore models

"""

import ast
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import logging
import operator

from google.appengine.ext import db
from google.appengine.ext import deferred

from application import settings
import ee
from ft import FT
from kml import path_to_kml
from mercator import Mercator
import simplejson as json
from time_utils import timestamp
from google.appengine.api.validation import Repeated


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
           if r[0].finished:
              r = Report(start=start_date, end=end_date, assetid=assetid)
              r.put()
              return {'message': 'New period of analyse saved!', 'data': None}
          
           else:
              return {'message': 'Last period not finalized!', 'data': None}


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
    map_one_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                     '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                     '"LANDSAT/LE7_L1T","false","LANDSAT/LC8_L1T","false","SMA","false","RGB","false","NDFI T0","false",'
                                                     '"NDFI T1","false","NDFI T0 (LANDSAT5)","false","NDFI T1 (LANDSAT5)","false","NDFI analysis","false",'
                                                     '"NDFI (LANDSAT5) analysis","true","True color RGB141","false","False color RGB421","false",'
                                                     '"F color infrared RGB214","false","Validated polygons","true",*')

    map_two_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                    '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                     '"LANDSAT/LE7_L1T","false","LANDSAT/LC8_L1T","false","SMA","false","RGB","false","NDFI T0","false",'
                                                     '"NDFI T1","false","NDFI T0 (LANDSAT5)","true","NDFI T1 (LANDSAT5)","false","NDFI analysis","false",'
                                                     '"NDFI (LANDSAT5) analysis","true","True color RGB141","false","False color RGB421","false",'
                                                     '"F color infrared RGB214","false","Validated polygons","true",*')

    map_three_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                       '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                       '"LANDSAT/LE7_L1T","false","LANDSAT/LC8_L1T","false","SMA","false","RGB","false","NDFI T0","false",'
                                                       '"NDFI T1","false","NDFI T0 (LANDSAT5)","false","NDFI T1 (LANDSAT5)","true","NDFI analysis","false",'
                                                       '"NDFI (LANDSAT5) analysis","true","True color RGB141","false","False color RGB421","false",'
                                                       '"F color infrared RGB214","false","Validated polygons","true",*')

    map_four_layer_status = db.TextProperty(default='"Brazil Legal Amazon","false","Brazil Municipalities Public","false","Brazil States Public","false",'
                                                      '"Brazil Federal Conservation Unit Public","false","Brazil State Conservation Unit Public","false",'
                                                      '"Terrain","true","Satellite","false","Hybrid","false","Roadmap","false","LANDSAT/LE7_L1T","false",'
                                                      '"LANDSAT/LC8_L1T","true","NDFI T0","false","True color RGB141","false","False color RGB421","false",'
                                                      '"F color infrared RGB214","false",*')


    @staticmethod
    def get_cell(report, x, y, z):
        q = Cell.all()
        q.filter("z =", z)
        q.filter("x =", x)
        q.filter("y =", y)
        q.filter("report =", report)
        cell = q.fetch(1)
        if cell:
            return cell[0]
        return None

    def child(self, i, j):
        zz = self.z+1
        xx = (SPLITS**self.z)*self.x + i
        yy = (SPLITS**self.z)*self.y + j
        return Cell.get_or_create(self.report, xx, yy, zz)

    def children(self):
        """ return child cells """
        eid = self.external_id()
        childs = Cell.all()
        childs.filter('report =', self.report)
        childs.filter('parent_id =', eid)

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
                    cell = Cell.default_cell(self.report, xx, yy, zz)
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
        return Cell.get_or_default(self.report, x, y, z)

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
    def get_or_create(r, x, y ,z):
        c = Cell.get_cell(r, x, y, z)
        if not c:
            c = Cell.default_cell(r, x, y ,z)
            c.put()
        return c

    @staticmethod
    def get_or_default(r, x, y, z):
        cell = Cell.get_cell(r, x, y, z)
        if not cell:
            cell = Cell.default_cell(r, x, y, z)
        return cell

    @staticmethod
    def default_cell(r, x, y, z):
        return Cell(z=z, x=x, y=y, ndfi_low=0.2, ndfi_high=0.3, report=r)

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

        try:
            self.key()
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
                #'key': str(self.key()),
                'id': self.external_id(),
                'z': self.z,
                'x': self.x,
                'y': self.y,
                'report_id': str(self.report.key()),
                'ndfi_low': self.ndfi_low,
                'ndfi_high': self.ndfi_high,
                'ndfi_change_value': self.ndfi_change_value,
                'compare_view':self.compare_view,
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
        r = q.fetch(10)
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

    added_on = db.DateTimeProperty(auto_now_add=True)
    added_by = db.UserProperty()
    report = db.ReferenceProperty(Report)
    sensor = db.StringProperty(required=True)
    cell = db.StringProperty(required=True)
    year = db.StringProperty(required=True)
    month = db.StringProperty(required=True)
    day = db.StringListProperty(required=True)
    location = db.TextProperty(required=True)
    compounddate = db.StringProperty(required=True)

    def as_dict(self):
        return {
                'id': str(self.key()),
                'key': str(self.key()),
                #'cell': str(self.cell.key()),
                #'paths': json.loads(self.geo),
                #'type': self.type,
                'cell': self.cell,
                'year': self.year,
                'month': self.month,
                'day': self.day,
                'Location': json.loads(self.location),
                'compounddate': self.compounddate,
                'fusion_tables_id': self.fusion_tables_id,
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname())
        }



    def as_json(self):
        return json.dumps(self.as_dict())

    @staticmethod
    def find_by_compounddate_period(start, end):
        q = ImagePicker.all().filter('compounddate >=', start).filter('compounddate <=', end)
        r = q.fetch(10)
        if r:
            return r
        else:
            return None
        
    @staticmethod
    def find_by_period(start_compounddate, end_compounddate, tile):
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
    def find_by_compounddate(compounddate):
        q = ImagePicker.all().filter('compounddate =', compounddate)
        r = q.fetch(10)
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
                    properties = {'cell': r[i].cell,
                                  'compounddate': r[i].compounddate,
                                  'day': ','.join(r[i].day),
                                  'month': r[i].month,
                                  'year': r[i].year
                                 }
                    feature = ee.Feature(geometry, properties)
                    feature_collection.append(feature)
                
                return ee.FeatureCollection(feature_collection)
        
        else:
            return None

    def save(self):
        q = ImagePicker.all().filter('compounddate =', self.compounddate).filter('cell =', self.cell)
        r = q.fetch(1)

        try:
            if r:
                #r[0].day = self.day
                for day in self.day: 
                    if day not in r[0].day:
                        r[0].day.append(day)               
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
        r = q.fetch(40)
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
                
                return ee.FeatureCollection(feature_collection)
        
        else:
            return None

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

    added_on = db.DateTimeProperty(auto_now_add=True)
    added_by = db.UserProperty(required=True)
    name     = db.StringProperty(required=True)
    cell     = db.ReferenceProperty(CellGrid)
    start    = db.DateProperty(required=True)
    end      = db.DateProperty()
    mapid    = db.StringProperty(required=True)
    token    = db.StringProperty(required=True)

    def as_dict(self):
        return {
                'id': str(self.key()),
                'key': str(self.key()),
                'start': self.start,
                'end': self.end(),
                'mapid': self.mapid,
                'token': self.token,
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname())
        }



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
                               'id':          r[i].mapid,
                               'token':       r[i].token,
                               'type':        'baseline',
                               'visibility':  True,
                               'description': r[i].name,
                               'url': 'https://earthengine.googleapis.com/map/'+r[i].mapid+'/{Z}/{X}/{Y}?token='+r[i].token
                               })
            return result
        else:
            return None
            

    def save(self):
        q = ''
        if self.end:
            q = Baseline.all().filter('start =', self.start).filter('end =', self.end)
        else:
            q = Baseline.all().filter('start =', self.start)
            
        r = q.fetch(1)

        try:
            if r:
                r[0].mapid   = self.mapid
                r[0].token  = self.token
                r[0].put()
                return {'message': 'Baseline updated.', 
                       'data': {
                                    'id':          r[0].mapid,
                                    'token':       r[0].token,
                                    'type':        'baseline',
                                    'visibility':  True,
                                    'description': self.name,
                                    'url': 'https://earthengine.googleapis.com/map/'+r[0].mapid+'/{Z}/{X}/{Y}?token='+r[0].token
                                   }
                       }
            else:
                self.put()
                return {'message': 'Baseline created.', 
                       'data': {
                                    'id':          self.mapid,
                                    'token':       self.token,
                                    'type':        'baseline',
                                    'visibility':  True,
                                    'description': self.name,
                                    'url': 'https://earthengine.googleapis.com/map/'+self.mapid+'/{Z}/{X}/{Y}?token='+self.token
                                   }
                       }

            
        except:
            return 'Could not save baseline.'



class TimeSeries(db.Model):
    """ images selected by user """

    added_on = db.DateTimeProperty(auto_now_add=True)
    added_by = db.UserProperty(required=True)
    name     = db.StringProperty(required=True)
    start    = db.DateProperty(required=True)
    end      = db.DateProperty(required=True)
    mapid    = db.StringProperty(required=True)
    token    = db.StringProperty(required=True)

    def as_dict(self):
        return {
                'id': str(self.key()),
                'key': str(self.key()),
                'start': self.start,
                'end': self.end(),
                'mapid': self.mapid,
                'token': self.token,
                'added_on': timestamp(self.added_on),
                'added_by': str(self.added_by.nickname())
        }



    def as_json(self):
        return json.dumps(self.as_dict())

    @staticmethod
    def all_formated():
        result = []
        q = TimeSeries.all().order('-start')
        r = q.fetch(10)
        
        if r:
            for i in range(len(r)):
                result.append({
                               'id':          r[i].mapid,
                               'token':       r[i].token,
                               'type':        'time_series',
                               'visibility':  True,
                               'description': r[i].name,
                               'url': 'https://earthengine.googleapis.com/map/'+r[i].mapid+'/{Z}/{X}/{Y}?token='+r[i].token
                               })
            return result
        else:
            return None
            

    def save(self):
        q = TimeSeries.all().filter('start =', self.start).filter('end =', self.end)
        r = q.fetch(1)

        try:
            if r:
               r[0].mapid   = self.mapid
               r[0].token  = self.token
               r[0].put()
               return {'message': 'Time series updated.', 
                       'data': {
                                    'id':         r[0].mapid,
                                    'token':      r[0].token,
                                    'type':       'time_series',
                                    'visibility': True,
                                    'description':  self.name,
                                    'url': 'https://earthengine.googleapis.com/map/'+r[0].mapid+'/{Z}/{X}/{Y}?token='+r[0].token
                                   }
                       }
            else:
               self.put()
               return {'message': 'Time series created.', 
                       'data': {
                                    'id':         self.mapid,
                                    'token':      self.token,
                                    'type':       'time_series',
                                    'visibility': True,
                                    'description':  self.name,
                                    'url': 'https://earthengine.googleapis.com/map/'+self.mapid+'/{Z}/{X}/{Y}?token='+self.token
                                   }
                       }

            
        except:
            return 'Could not save baseline.'
