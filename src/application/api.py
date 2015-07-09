#encoding: utf-8

from StringIO import StringIO
import calendar
import csv
from datetime import datetime, timedelta, date, time
from dateutil.parser import parse
import logging
import random
from symbol import compound_stmt

from google.appengine.ext.db import Key

from app import app
from application.constants import amazon_bounds
from application.models import Cell
from ee_bridge import NDFI, EELandsat, Stats, get_prodes_stats
from flask import jsonify, request, abort, Response
from kml import path_to_kml
from models import Area, Note, Report, StatsStore, FustionTablesNames
from report_types import ReportType, CSVReportType, KMLReportType
from resources.report import ReportAPI, CellAPI, NDFIMapApi, PolygonAPI, NoteAPI, UserAPI
from resources.stats import RegionStatsAPI
import settings
import simplejson as json
from time_utils import timestamp, first_of_current_month, past_month_range


ReportAPI.add_urls(app, '/api/v0/report')
ReportAPI.add_custom_url(app, '/api/v0/report/<report_id>/close', 'close', ("POST",))

CellAPI.add_urls(app,       '/api/v0/report/<report_id>/operation/<operation>/cell')
CellAPI.add_custom_url(app, '/api/v0/report/<report_id>/operation/<operation>/cell/<id>/children', 'children')
CellAPI.add_custom_url(app, '/api/v0/report/<report_id>/cell/<id>/ndfi_change', 'ndfi_change')
CellAPI.add_custom_url(app, '/api/v0/report/<report_id>/cell/<id>/bounds', 'bounds')
CellAPI.add_custom_url(app, '/api/v0/report/<report_id>/operation/<operation>/cell/<id>/landsat', 'landsat')
CellAPI.add_custom_url(app, '/api/v0/report/<report_id>/operation/<operation>/cell/<id>/rgb/<r>/<g>/<b>/sensor/<sensor>', 'rgb_mapid')
#CellAPI.add_custom_url(app, '/api/v0/report/<report_id>/cell/<id>/rgb/<r>/<g>/<b>/sensor', 'sensor')

#NDFIMapApi.add_urls(app, '/api/v0/report/<report_id>/map')
NDFIMapApi.add_urls(app, '/api/v0/report/<report_id>/<sensor>/map')

PolygonAPI.add_urls(app, '/api/v0/report/<report_id>/operation/<operation>/cell/<cell_pos>/polygon')
NoteAPI.add_urls(app, '/api/v0/report/<report_id>/cell/<cell_pos>/note')
UserAPI.add_urls(app, '/api/v0/user')

RegionStatsAPI.add_urls(app, '/api/v0/report/<report_id>/stats')
RegionStatsAPI.add_custom_url(app, '/api/v0/stats/polygon', 'polygon', methods=('POST',))

#TODO: this function needs a huge refactor
@app.route('/api/v0/stats/<table>/<format>/<zone>')
@app.route('/api/v0/stats/<table>/<format>')
@app.route('/api/v0/stats/<table>')
def stats(table, zone=None, format="csv"):

    reports = request.args.get('reports', None)
    if not reports:
        abort(400)
    try:
        reports = map(int, reports.split(','))
    except ValueError:
        logging.error("bad format for report id")
        abort(400)

    this_report = ReportType.factory(format)
    this_report.init(zone)
    this_report.write_header()

    logging.info("table id is %s ", table)
    logging.info("and we see %s ", FustionTablesNames.all().filter('table_id =', table).fetch(1))
    logging.info("and zone %s ", zone)
    logging.info("and format %s ", format)

    reports = [Report.get_by_id(x) for x in reports]
    for r in reports:
        if not r:
            logging.error("report not found")
            abort(404)

        stats = this_report.get_stats(r, table)

        for s in stats:
            this_report.write_row(r, s, table)

    this_report.write_footer()
    return this_report.response("report_%s" % table)


@app.route('/api/v0/stats/polygon/<format>')
def polygon_stats(format=None):
    reports = request.args.get('reports', None)
    if not reports:
        abort(400)
    try:
        reports = map(int, reports.split(','))
    except ValueError:
        logging.error("bad format for report id")
        abort(400)

    try:
        reports = [Report.get_by_id(x) for x in reports]
    except ValueError:
        logging.error("can't find some report")
        abort(404)

    #TODO: test if polygon is ccw
    # exchange lat, lon -> lon, lat
    polygon = json.loads(request.args.get('polygon', None))
    polygon.append(polygon[0])
    if not polygon:
        abort(404)
    ee = Stats()
    normalized_poly = [(coord[1], coord[0]) for coord in polygon]
    stats = ee.get_stats_for_polygon([(str(r.key().id()), r.assetid) for r in reports], [normalized_poly])

    this_report = ReportType.factory(format)
    this_report.init("custom polygon")
    try:
        this_report.write_header()
        for i,s in enumerate(stats):
            r = reports[i]
            this_report.write_row(r, s, None, path_to_kml([polygon]))

        this_report.write_footer()
        return this_report.response("report_polygon")
    except (KeyError, ValueError, IndexError):
        abort(404)

def landstat():
    e = EELandsat()
    #return jsonify(images=e.list())
    return jsonify(map={'data': e.mapid()})

@app.route('/api/v0/test')
def testing():
    """
    r = Report.current()
    #r = Report.get(Key('ahBpbWF6b24tcHJvdG90eXBlcg4LEgZSZXBvcnQYiaECDA'))
    logging.info("report " + unicode(r))
    ee_resource = 'MOD09GA'
    s = Stats()
    polygon = [[[-61.9,-11.799],[-61.9,-11.9],[-61.799,-11.9],[-61.799,-11.799],[-61.9,-11.799]]]
    return str(s.get_stats_for_polygon("PRODES_2009", polygon))
    #return str(ndfi.mapid2())
    #return str(ndfi.freeze_map(1089491, r.key().id()))
    """
    return jsonify(get_prodes_stats(["PRODES_2009", "PRODES_IMAZON_2011a"], 1505198))

