"""
settings.py

Configuration for Flask app

Important: Place your keys in the secret_keys.py module,
           which should be kept out of version control.

"""

from google.appengine.api import app_identity
import os

from secret_keys import *
import ee
from oauth2client import appengine


# Auto-set debug mode based on App Engine dev environ
DEBUG_MODE = ('SERVER_SOFTWARE' in os.environ and
              os.environ['SERVER_SOFTWARE'].startswith('Dev'))

if DEBUG_MODE:
    EE_API_URL = 'https://earthengine.sandbox.google.com'
    EE_CREDENTIALS = ee.ServiceAccountCredentials(EE_ACCOUNT, EE_PRIVATE_KEY_FILE)
    FT_TABLE = 'imazon_testing.csv'
    FT_TABLE_ID = '2676501'
else:
    EE_API_URL = 'https://earthengine.googleapis.com'
    EE_CREDENTIALS = appengine.AppAssertionCredentials(ee.OAUTH2_SCOPE)
    app_id  = app_identity.get_application_id()
    if app_id == 'imazon-sad-tool':
        FT_TABLE = 'areas'
        FT_TABLE_ID = '1089491'
    elif app_id == 'imazon-prototype':
        FT_TABLE = 'imazon_testing.csv'
        FT_TABLE_ID = '2676501'
    elif app_id == 'sad-training':
        FT_TABLE = 'areas_training'
        FT_TABLE_ID = '1898803'
    elif app_id == 'sad-ee':
        FT_TABLE = 'SAD EE Polygons'
        FT_TABLE_ID = '2949980'

# Initialize the EE API.
EE_TILE_SERVER = EE_API_URL + '/map/'
ee.data.DEFAULT_DEADLINE = 60 * 20
ee.Initialize(EE_CREDENTIALS, EE_API_URL)

# Set secret keys for CSRF protection
SECRET_KEY = CSRF_SECRET_KEY
CSRF_SESSION_KEY = SESSION_KEY

CSRF_ENABLED = True

