# encoding: utf-8

import datetime
import logging
import time
import os
import simplejson as json
from shutil import copyfile
import sys

from google.appengine.api import urlfetch
from google.appengine.api import users

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

from application.time_utils import timestamp, past_month_range

from decorators import login_required, admin_required
#from forms import ExampleForm
from application.ee_bridge import EELandsat, SMA, NDFI, get_modis_thumbnails_list, get_modis_location

from app import app

from models import Report, User, Error, ImagePicker
from google.appengine.api import memcache, users
#from google.appengine.ext.db import Key

from application import settings

def default_maps():
    maps = []
    r = Report.current()
    logging.info("report " + unicode(r))
    landsat = EELandsat(timestamp(r.start), datetime.datetime.now())
    ndfi = NDFI(past_month_range(r.start), r.range())

    logging.info('Past_month_range: '+str(past_month_range(r.start))+', Range: '+str(r.range)+', Timestamp: '+str(timestamp(r.start))+', Datetime: '+str(datetime.datetime.now()) )

    d = landsat.mapid(timestamp(r.start), datetime.datetime.now())
    maps.append({'data' :d, 'info': 'LANDSAT/LE7_L1T'})

    d = landsat.mapid_landsat_oito(timestamp(r.start), datetime.datetime.now())
    maps.append({'data':d, 'info': 'LANDSAT/LC8_L1T'})

    assetid = r.previous().as_dict().get('assetid')
    logging.info("Assetid :"+str(assetid))

    d = ndfi.smaid()
    if d: maps.append({'data': d, 'info': 'SMA'})
    d = ndfi.rgb1id()
    if d: maps.append({'data': d, 'info': 'RGB'})
    d = ndfi.ndfi0id('modis')
    if d: maps.append({'data': d, 'info': 'NDFI T0'})
    d = ndfi.ndfi1id('modis')
    if d: maps.append({'data' :d, 'info': 'NDFI T1'})
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
import re
import urllib2
import urllib
FT_TABLE_DOWNSCALLING = '17Qn-29xy2JwFFeBam5YL_EjsvWo40zxkkOEq1Eo'

@app.route('/range_report/', methods=['POST', 'GET'])
def range_report():
    range_picker = request.form.get('range_picker')
    date_start = range_picker.split(' to ')[0]
    date_end   = range_picker.split(' to ')[1]
    message = ''
    try:
       message =  Report.add_report(date_start, date_end)
    except:
        return jsonify({'result': 'error'})

    return jsonify({'result': message})

@app.route('/tiles_sensor/<sensor>/', methods=['POST', 'GET'])
def tiles_sensor(sensor=None):
    tile_array = []
    if request.method == 'POST':
        return jsonify({'result': 'post method'})
    else:
        if sensor == 'modis':
           tile_array = [
                         { 'name': 'h11v08', 'value': 'h11v08'},
                         { 'name': 'h12v08', 'value': 'h12v08'},
                         { 'name': 'h10v09', 'value': 'h10v09'},
                         { 'name': 'h11v09', 'value': 'h11v09'},
                         { 'name': 'h12v09', 'value': 'h12v09'},
                         { 'name': 'h13v09', 'value': 'h13v09'},
                         { 'name': 'h11v10', 'value': 'h11v10'},
                         { 'name': 'h12v10', 'value': 'h12v10'},
                         { 'name': 'h13v10', 'value': 'h13v10'}
                        ]

    return jsonify({'result': tile_array})

import ee

@app.route('/downscalling', methods=['POST', 'GET'])
@app.route('/downscalling/<tile>/')
def downscalling(tile=None):
    result = []

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
    else:
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
    """
    cell = request.args.get('cell','')
    scene = 'MOD09GA/MOD09GA_005_2010_01_01'
    bands = 'sur_refl_b01,sur_refl_b04,sur_refl_b03'
    gain = 0.1
    if scene:
       result = get_modis_thumbnail(scene, cell, bands, gain)
    else:
       result = {'thumbid': '', 'token': ''}
    return render_template('picker.html', **result)
    """

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

       day          = ','.join(days)
       compounddate = year + month

       location = get_modis_location(cell)

       report = Report.current()

       imagePicker = ImagePicker(report=report, added_by= users.get_current_user(), cell=str(cell),  year=str(year), month=str(month), day=str(day), location=location, compounddate=str(compounddate))
       return jsonify({'result': imagePicker.save()})


       #logging.info("hello" + str(request.form.keys()))
       #logging.info("json"  + str(json.dumps(request.form.keys())))
       """
       reports = Report.current().as_dict()
       date = time.gmtime(reports['start'] / 1000)

       #rowid = ""
       cell = request.args.get('cell','')
       logging.info("cell: " + str(cell))

       selected_days = request.form.keys()
       #logging.info("days: " + str(selected_days))
       selected_days.sort()
       #logging.info("days: " + str(selected_days))
       selected_days = selected_days[:-1]
       #logging.info("days: " + str(selected_days))
       day = ""
       for selected_day in selected_days:
          day += selected_day[14:].lstrip('0') + ","
          logging.info("day: " + str(day))
       #logging.info("days: " + str(day))
       day = day[:-1]
       #logging.info("day: " + str(day))

       year = time.strftime("%Y", date)
       logging.info("year: " + str(year))
       month = int(time.strftime("%m", date))
       #logging.info("month: " + str(month))
       #Location = ""
       compounddate = str(year) + str(month).zfill(2)
       #logging.info("compounddate: " + str(compounddate))
       #added_on = ""

       #return request.form['check-2013-01-01']
       return request.datai"""

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
          #result = {'thumbid': '', 'token': ''}
          #return render_template('picker.html', result=result)

from google.appengine.api import urlfetch
@app.route('/new_access_fusion_tables/', methods=['POST', 'GET'])
def new_access_fusion_tables():
    url_pattern = 'https://accounts.google.com/o/oauth2/auth'
    client_id = '1020234688983-a45r3i5uvpber4t21cmlqh9mrl951p3v.apps.googleusercontent.com'
    redirect_uri = 'http://localhost:8080/callbackOauth2/'
    scope = 'https://www.googleapis.com/auth/fusiontables'
    url = '%s?client_id=%s&redirect_uri=%s&scope=%s&response_type=code' % (url_pattern, client_id, redirect_uri, scope)

    return redirect(url)

@app.route('/callbackOauth2/', methods=['POST', 'GET'])
def callbackOauth2():
    client_id = '1020234688983-a45r3i5uvpber4t21cmlqh9mrl951p3v.apps.googleusercontent.com'
    client_secret = 'o0p27QRNfMhCGYsIF3awrLuO'
    redirect_uri = 'http://localhost:8080/callbackOauth2/'
    scope = 'https://www.googleapis.com/auth/fusiontables'
    auth_code = request.args.get('code')

    data= urllib.urlencode({
         'code': auth_code,
         'client_id': client_id,
         'client_secret': client_secret,
         'redirect_uri': redirect_uri,
         'grant_type': 'authorization_code'
       })

    req = urllib2.Request(
       url='https://accounts.google.com/o/oauth2/token',
       data=data)

    request_open = urllib2.urlopen(req)
    response = request_open.read()
    tokens = json.loads(response)

    logging.info("============ Request data =============")
    logging.info(tokens)

    access_token = tokens['access_token']
    refresh_token = ''
    try:
      refresh_token = tokens['refresh_token']
    except:
      pass

    req = urllib2.Request(
      url='https://www.googleapis.com/fusiontables/v2/query?%s' % \
         (urllib.urlencode({'access_token': access_token,#access_token,
                            'sql': "SELECT * FROM 1VPNcpgPM8rPs8dQ6g-9Fmei9aJIydJAjZys3XuxN WHERE cell = '%s' AND year = '%s' AND month = '%s'" % ('h11v10', '2012', '12')})))

    request_open = urllib2.urlopen(req)
    response = request_open.read()
    result   = json.loads(response)

    logging.info("============ Request data =============")
    logging.info(tokens)
    logging.info(result)
    return jsonify({'result': 'success'})
