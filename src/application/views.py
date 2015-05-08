# encoding: utf-8

import datetime
import logging
import os
import re
from shutil import copyfile
import sys
import time

from google.appengine.api import memcache, users
from google.appengine.api import urlfetch

from app import app
from application import settings
from application.api import landstat
from application.ee_bridge import EELandsat, SMA, NDFI, get_modis_thumbnails_list, get_modis_location, create_baseline, \
    create_time_series, create_tile_baseline
from application.models import Baseline, Tile, TimeSeries, CellGrid
from application.time_utils import timestamp, past_month_range
from decorators import login_required, admin_required
import ee
from models import Report, User, Error, ImagePicker, Downscalling
import simplejson as json


#from chardet.test import result
sys.modules['ssl'] = None

try:
    from flask import render_template,  redirect, abort, request, make_response, jsonify
except:
    # nose tests require zipped packages to be manually loadedi
    import zipimport
    gflags = zipimport.zipimporter('packages/gflags.zip').load_module('gflags')
    jinja2 = zipimport.zipimporter('packages/jinja2.zip').load_module('jinja2')
    flask = zipimport.zipimporter('packages/flask.zip').load_module('flask')
    wtforms = zipimport.zipimporter('packages/wtforms.zip').load_module('wtforms')


#from forms import ExampleForm


#from google.appengine.ext.db import Key


def default_maps():
    maps = []
    r = Report.current()
    logging.info("report " + unicode(r))
    landsat = EELandsat(timestamp(r.start), datetime.datetime.now())
    ndfi = NDFI(past_month_range(r.start), r.range())

    logging.info('Past_month_range: '+str(past_month_range(r.start))+', Range: '+str(r.range)+', Timestamp: '+str(timestamp(r.start))+', Datetime: '+str(datetime.datetime.now()) )

    d = landsat.mapid(timestamp(r.start), datetime.datetime.now())
    maps.append({'data' :d, 'info': 'LANDSAT/LE7_L1T'})

    d = landsat.mapid_landsat8(timestamp(r.start), datetime.datetime.now())
    maps.append({'data':d, 'info': 'LANDSAT/LC8_L1T'})

    assetid = r.previous().as_dict().get('assetid')
    logging.info("Assetid :"+str(assetid))
    
    """
    sma = SMA(past_month_range(r.start), r.range(), SMA.LANDSAT7_T1)
    bbox = [-74.0, -18.0, -44.0, 5.0]    
    d = sma.find_mapid_from_sensor(bbox)
    if d: maps.append({'data': d, 'info': SMA.LANDSAT7_T1})
    d = ndfi.ndfi0id('landsat5')
    logging.info('Image ID: '+str(d))
    if d: maps.append({'data': d, 'info': 'NDFI T0 (LANDSAT5)'})
    d = ndfi.ndfi1id('landsat5')
    logging.info('Image ID: '+str(d))
    if d: maps.append({'data': d, 'info': 'NDFI T1 (LANDSAT5)'})
    d = ndfi.ndfi0id('landsat7')
    logging.info('Image ID: '+str(d))
    if d: maps.append({'data': d, 'info': 'NDFI T0 (LANDSAT7)'})
    d = ndfi.ndfi1id('landsat7')
    logging.info('Image ID: '+str(d))
    if d: maps.append({'data': d, 'info': 'NDFI T1 (LANDSAT7)'})
    """
    
    d = ndfi.smaid()
    if d: maps.append({'data': d, 'info': 'SMA'})    
    d = ndfi.rgb1id()
    if d: maps.append({'data': d, 'info': 'RGB'})
    d = ndfi.ndfi0id('modis')
    if d: maps.append({'data': d, 'info': 'NDFI T0 (MODIS)'})
    d = ndfi.ndfi1id('modis')
    if d: maps.append({'data' :d, 'info': 'NDFI T1 (MODIS)'})
    d = ndfi.baseline(r.base_map())
    if d: maps.append({'data' :d, 'info': 'Baseline'})
    d = ndfi.rgb0id()
    if d: maps.append({'data': d, 'info': 'Previous RGB'})
    return maps

@app.route('/map/level/<level>/<bbox>/')
def maps_level(level, bbox):
    result = []
    if level == '0':
        result.append(map_from_bbox(EELandsat.LANDSAT5, bbox))
        result.append(map_from_bbox(EELandsat.LANDSAT7, bbox))
        result.append(map_from_bbox(EELandsat.LANDSAT8, bbox))
    elif level == '1':
        result.append(map_from_bbox(SMA.LANDSAT5_T0, bbox))
        result.append(map_from_bbox(SMA.LANDSAT5_T1, bbox))
        result.append(map_from_bbox(SMA.LANDSAT7_T0, bbox))
        result.append(map_from_bbox(SMA.LANDSAT7_T1, bbox))
        result.append(map_from_bbox(SMA.LANDSAT8_T0, bbox))
        result.append(map_from_bbox(SMA.LANDSAT8_T1, bbox))
    elif level == '2':
        result.append(map_from_bbox(NDFI.LANDSAT5_T0, bbox))
        result.append(map_from_bbox(NDFI.LANDSAT5_T1, bbox))
        result.append(map_from_bbox(NDFI.LANDSAT7_T0, bbox))
        result.append(map_from_bbox(NDFI.LANDSAT7_T1, bbox))
        result.append(map_from_bbox(NDFI.LANDSAT8_T0, bbox))
        result.append(map_from_bbox(NDFI.LANDSAT8_T1, bbox))

    return jsonify({'result': result})

def map_from_bbox(map_image, bbox):
    bounds = bbox.split(',')
    report = Report.current()
    map_data = ''
    map_type = ''

    if EELandsat.from_class(map_image):
        logging.info("==================> Map image landsat: "+map_image)
        landsat = EELandsat(timestamp(report.start), datetime.datetime.now(), map_image)
        map_data = landsat.find_mapid_from_sensor(bounds)
        map_type = 'base_map'
    elif SMA.from_class(map_image):
        logging.info("==================> Map image SMA: "+map_image)
        sma = SMA(past_month_range(report.start), report.range(), map_image)
        map_data = sma.find_mapid_from_sensor(bounds)
        map_type = 'processed'
    elif NDFI.from_class(map_image):
        logging.info("==================> Map image NDFI: "+map_image)
        ndfi     = NDFI(past_month_range(report.start), report.range())
        map_data = ndfi.find_mapid_from_sensor(map_image, bounds)
        map_type = 'analysis'

    if map_data == '':
        return None
    else:
        return {
            'id': map_data.get('mapid'),
            'token': map_data.get('token'),
            'type': map_type,
            'description': map_image,
            'visibility': True,
            'url': 'https://earthengine.googleapis.com/map/'+map_data.get('mapid')+'/{Z}/{X}/{Y}?token='+map_data.get('token')
        }

def get_or_create_user():
    user = users.get_current_user()
    u = User.get_user(user)
    if not u and users.is_current_user_admin():
        u = User(user=user, role='admin')
        u.put()
    return u

@app.route('/')
def start():
    return redirect('/analysis')


@app.route('/analysis')
@login_required
def home(cell_path=None):
    import sys
    logging.info("Version python: "+sys.version);
    
    maps = memcache.get('default_maps')

    if maps:
        maps = json.loads(maps)
    else:
        maps = default_maps()
        memcache.add(key='default_maps', value=json.dumps(maps), time=60*10)

    # send only the active report
    reports = json.dumps([Report.current().as_dict()])
    report_base = json.dumps([Report.current().previous().as_dict()])
    logging.info("Reports: "+str(reports))
    logging.info("Maps: "+str(maps))
    u = get_or_create_user()
    if not u:
        abort(403)


    logout_url = users.create_logout_url('/')
    return render_template('home.html',
            reports_json=reports,
            report_base_json=report_base,
            user=u,
            maps=maps,
            polygons_table=settings.FT_TABLE_ID,
            logout_url=logout_url)



@app.route('/vis')
@login_required
def vis():
    u = get_or_create_user()
    if not u:
        abort(403)

    logout_url = users.create_logout_url('/')
    #TODO show only finished
    reports = [x.as_dict() for x in Report.all().filter("finished =", True).order("start")]
    return render_template('vis/index.html',
            user=u,
            logout_url=logout_url,
            polygons_table=settings.FT_TABLE_ID,
            reports=json.dumps(reports))

@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/error_track',  methods=['GET', 'POST'])
def error_track():
    d = request.form
    logging.info(request.form)
    Error(msg=d['msg'], url=d['url'], line=d['line'], user=users.get_current_user()).put()
    return 'thanks'

@app.route('/tiles/<path:tile_path>')
def tiles(tile_path):
    """ serve static tiles """
    # save needed tiles
    if False:
        base = os.path.dirname(tile_path)
        try:
            os.makedirs("static/tiles/" + base)
        except OSError:
            pass #java rocks
        copyfile("static/maps/%s" % tile_path, "static/tiles/%s" % tile_path)
    return redirect('/static/tiles/%s' % tile_path)
    #return redirect('/static/maps/%s' % tile_path)


EARTH_ENGINE_TILE_SERVER = settings.EE_TILE_SERVER

@app.route('/ee/tiles/<path:tile_path>')
def earth_engine_tile_proyx(tile_path):
    token = request.args.get('token', '')
    if not token:
        abort(401)
    result = urlfetch.fetch(EARTH_ENGINE_TILE_SERVER + tile_path + '?token='+ token, deadline=10)

    response = make_response(result.content)
    response.headers['Content-Type'] = result.headers['Content-Type']
    return response

@app.route('/proxy/<path:tile_path>')
def proxy(tile_path):
    result = urlfetch.fetch('https://'+ tile_path, deadline=10)
    response = make_response(result.content)
    response.headers['Content-Type'] = result.headers['Content-Type']
    response.headers['Expires'] = 'Thu, 15 Apr 2020 20:00:00 GMT'
    return response

@app.route('/admin_only')
@admin_required
def admin_only():
    """This view requires an admin account"""
    return 'Super-seekrit admin page.'


@app.route('/_ah/warmup')
def warmup():
    """App Engine warmup handler
    See http://code.google.com/appengine/docs/python/config/appconfig.html#Warming_Requests

    """
    return ''
FT_TABLE_DOWNSCALLING = '17Qn-29xy2JwFFeBam5YL_EjsvWo40zxkkOEq1Eo'

@app.route('/range_report/', methods=['POST', 'GET'])
def range_report():
    date_start = request.form.get('date_start')
    date_end   = request.form.get('date_end')
    message = ''
    #try:
    message =  Report.add_report(date_start, date_end)
    #except:
    #    return jsonify({'result': 'error'})

    return jsonify({'result': message})

@app.route('/tiles_sensor/<sensor>/', methods=['POST', 'GET'])
def tiles_sensor(sensor=None):
    tile_array = []
    if request.method == 'POST':
        return jsonify({'result': 'post method'})
    else:
        if sensor == 'modis':
            tile_array = [
                          { 'name': 'h10v09', 'value': 'h10v09'},
                          { 'name': 'h11v08', 'value': 'h11v08'},
                          { 'name': 'h11v09', 'value': 'h11v09'},
                          { 'name': 'h11v10', 'value': 'h11v10'}, 
                          { 'name': 'h12v08', 'value': 'h12v08'},
                          { 'name': 'h12v09', 'value': 'h12v09'},                       
                          { 'name': 'h12v10', 'value': 'h12v10'},
                          { 'name': 'h13v09', 'value': 'h13v09'},
                          { 'name': 'h13v10', 'value': 'h13v10'}
                        ]
            
            r = Report.current()
            start_date = r.start
            compounddate = '%04d%02d' % (start_date.year, start_date.month) 
            
            for i in range(len(tile_array)):
                image_picker = ImagePicker.find_by_compounddate_and_cell(compounddate, tile_array[i]['name'])
                if image_picker:
                    tile_array[i]['done'] = True
                else:
                    tile_array[i]['done'] = False
                

    return jsonify({'result': tile_array})


@app.route('/downscalling/', methods=['POST', 'GET'])
@app.route('/downscalling/<tile>/')
def downscalling(tile=None):

    if request.method == 'POST':
        range3 = request.form.get('range3')
        range4 = request.form.get('range4')
        range6 = request.form.get('range6')
        range7 = request.form.get('range7')

        sill3 = request.form.get('sill3') 
        sill4 = request.form.get('sill4')
        sill6 = request.form.get('sill6')
        sill7 = request.form.get('sill7')

        nugget3 = request.form.get('nugget3')
        nugget4 = request.form.get('nugget4')
        nugget6 = request.form.get('nugget6')
        nugget7 = request.form.get('nugget7')

        cell = request.form.get('tile')
        cell = cell.upper()

        location = get_modis_location(cell.lower())

        compounddate = request.form.get('compounddate')

        report = Report.current()

        model = 'exponential'

        downscalling3 = Downscalling(report=report,
                                 added_by= users.get_current_user(),
                                 cell=str(cell),
                                 region=location,
                                 compounddate=str(compounddate),
                                 band=3,
                                 model=model,
                                 sill=long(sill3),
                                 range=long(range3),
                                 nugget=long(nugget3)
                                 )
        message1 = downscalling3.save()

        downscalling4 = Downscalling(report=report,
                                 added_by= users.get_current_user(),
                                 cell=str(cell),
                                 region=location,
                                 compounddate=str(compounddate),
                                 band=4,
                                 model=model,
                                 sill=long(sill4),
                                 range=long(range4),
                                 nugget=long(nugget4)
                                 )
        message2 = downscalling4.save()

        downscalling6 = Downscalling(report=report,
                                 added_by= users.get_current_user(),
                                 cell=str(cell),
                                 region=location,
                                 compounddate=str(compounddate),
                                 band=6,
                                 model=model,
                                 sill=long(sill6),
                                 range=long(range6),
                                 nugget=long(nugget6)
                                 )
        message3 = downscalling6.save()

        downscalling7 = Downscalling(report=report,
                                 added_by= users.get_current_user(),
                                 cell=str(cell),
                                 region=location,
                                 compounddate=str(compounddate),
                                 band=7,
                                 model=model,
                                 sill=long(sill7),
                                 range=long(range7),
                                 nugget=long(nugget7)
                                 )
        message4 = downscalling7.save()

        if message1 == message2 == message3 == message4:
            return jsonify({'result': message1})
        else:
            return jsonify({'result': 'Could not save values.'})

    else:
        result = []
        if tile:
            filter_fc = ee.Filter.eq('Cell', tile.upper())
            fc        = ee.FeatureCollection('ft:17Qn-29xy2JwFFeBam5YL_EjsvWo40zxkkOEq1Eo').filter(filter_fc)
            logging.info("==================  Aqui ================")
            logging.info(fc.getInfo())
            for feature in fc.getInfo().get('features'):
                result.append({'Band':  feature.get('properties').get('Band'),
                            'Sill':  feature.get('properties').get('Sill'),
                            'Range': feature.get('properties').get('Range'),
                            'Nugget': feature.get('properties').get('Nugget')
                            })
                logging.info(feature);

            return jsonify({'result': result})

    return jsonify({'result': 'success'});




@app.route('/picker/', methods=['POST', 'GET'])
@app.route('/picker/<tile>/')
def picker(tile=None):
    
    if request.method == 'POST':
        logging.info(request.form.get('thumb'))

        cell   = request.form.get('tile')
        p      = re.compile('\d+')
        p      = p.findall(cell)
        cell   = 'h' + p[0] + 'v' + p[1]

        thumbs = request.form.get('thumb').split(',')
        days   = []
        day, month, year = ['', '', '']

        for thumb in thumbs:
            day, month, year = thumb.split('-')
            days.append(day)

        #day          = ','.join(days)
        compounddate = year + month

        location = get_modis_location(cell)

        report = Report.current()

        imagePicker = ImagePicker(sensor='MODIS', report=report, added_by= users.get_current_user(), cell=str(cell),  year=str(year), month=str(month), day=days, location=location, compounddate=str(compounddate))
        return jsonify({'result': imagePicker.save()})

    else:
        #cell = request.args.get('cell', '')
        reports = Report.current().as_dict()
        date = time.gmtime(reports['start'] / 1000)
        year = time.strftime("%Y", date)
        month = time.strftime("%m", date)

        if tile:
            bands = 'sur_refl_b01,sur_refl_b04,sur_refl_b03'
            gain = 0.1
            results = get_modis_thumbnails_list(year, month, tile, bands, gain)
            return jsonify({'result': results})
        else:
            return jsonify({'result': []})

@app.route('/baseline_list/')
def baseline_list():
    result = Baseline.all_formated()
    return jsonify({'result': result})

@app.route('/time_series_historical_results/')
def time_series_historical_results():
    result = TimeSeries.all_formated()
    return jsonify({'result': result})

@app.route('/reports_list/')
def reports_list():
    result = Report.all_period()
    return jsonify(result)


@app.route('/baseline_report/', methods=['POST', 'GET'])
def baseline_report():

    if request.method == 'POST':
        date_start = request.form.get('date_start')
        date_end = request.form.get('date_end')
        result      = create_baseline(date_start, date_end, EELandsat.LANDSAT5)
        return jsonify({'result': result})
    else:
        return jsonify({'result': 'Other method'})

@app.route('/time_series/', methods=['POST', 'GET'])
def time_series():

    if request.method == 'POST':
        date_start = request.form.get('date_start')
        date_end = request.form.get('date_end')
        result      = create_time_series(date_start, date_end, EELandsat.LANDSAT5)
        return jsonify({'result': result})
    else:
        return jsonify({'result': 'Other method'})
    
@app.route('/baseline_search_tiles/', methods=['POST', 'GET'])
def baseline_search_tiles():
    if request.method == 'POST':
        cell_name = request.form.get('cell_name')
        cell_grid = CellGrid.find_by_name(cell_name)
        
        if cell_grid:
            result    = cell_grid.tiles_as_dict()
        else:
            bbox = request.form.get('bbox')
            bbox = bbox.replace(";", "],[")
            bbox = "[[[" + bbox + "]]]"
            cell_grid = CellGrid(name=cell_name, geo=bbox)
            cell_grid.save()
            result    = cell_grid.tiles_as_dict()
        
        #result = Tile.find_by_cell_name(cell_name)
        return jsonify({'tiles': result})


@app.route('/baseline_on_cell/<date_start>/<date_end>/<cell_name>/', methods=['POST', 'GET'])
def baseline_on_cell(date_start, date_end, cell_name):
    if request.method == 'POST':
        cell_name    = request.form.get('cell_name')
        logging.info(cell_name)
        start_date   = request.form.get('start_date')
        end_date     = request.form.get('end_date')
        start_date = datetime.datetime.strptime(start_date,"%d/%b/%Y")
        end_date = datetime.datetime.strptime(end_date,"%d/%b/%Y")
        
        result = create_tile_baseline(start_date, end_date, cell_name)
        return jsonify({'result': result})
    else:
        logging.info(cell_name)
        start_date   = date_start.replace("-", "/")
        end_date     = date_end.replace("-", "/")
        start_date = datetime.datetime.strptime(start_date,"%d/%b/%Y")
        end_date = datetime.datetime.strptime(end_date,"%d/%b/%Y")
        
        result = create_tile_baseline(start_date, end_date, cell_name)
        return jsonify({'result': result})

@app.route('/baseline/<cell_name>/', methods=['POST', 'GET'])
def baseline_cell(cell_name):
    if request.method == 'POST':
        return jsonify({'result': None})
    else:
        logging.info(cell_name)
        result = Baseline.formated_by_cell_parent(cell_name)        
        return jsonify({'result': result})            

    
@app.route('/imagepicker_baseline/', methods=['POST', 'GET'])
def imagepicker_baseline():    
       
    if request.method == 'POST' and request.form.get('list_cloud_percent') and request.form.get('date_start') and request.form.get('date_end'):
        

        date_start         = request.form.get('date_start')
        date_end           = request.form.get('date_end')
        date_start = datetime.datetime.strptime(date_start,"%d/%b/%Y")
        date_end = datetime.datetime.strptime(date_end,"%d/%b/%Y")
        
        list_cloud_percent = request.form.get('list_cloud_percent')
        list_cloud_percent = json.loads(list_cloud_percent)
        
        landstat = EELandsat(date_start, date_end)
        result = landstat.get_thumbs(list_cloud_percent)
                
        return jsonify({'result': result})
    elif request.method == 'POST' and request.form.get('thumbs_baseline'):
        
        logging.info(request.form.get('thumbs_baseline'))
        thumbs_baseline = request.form.get('thumbs_baseline')
        thumbs_baseline = thumbs_baseline.split(',')
        result = ""
        
        for i in range(len(thumbs_baseline)):
            date, tile, sensor = thumbs_baseline[i].split('__')
            #logging.info(request.form.get('thumb'))

            tile = tile.replace("_", "/")
            year, month, day  = date.split("-")  
            
            compounddate = year + month

            location = Tile.find_geo_region(tile)

            report = Report.current()

            imagePicker = ImagePicker(sensor=str(sensor), report=report, added_by= users.get_current_user(), cell=str(tile),  year=str(year), month=str(month), day=[day], location=str(location), compounddate=str(compounddate))
            result = imagePicker.save()
            
        
        return jsonify({'result': result})
    else:     
        return jsonify({'result': None})
        

