"""
Superset configuration cho Retail Analytics
"""
import os

# Secret key
SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'thisisasecretkeyforretailsuperset123')

# Database
SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{os.environ.get('DATABASE_USER', 'superset')}:"
    f"{os.environ.get('DATABASE_PASSWORD', 'superset')}@"
    f"{os.environ.get('DATABASE_HOST', 'superset-db')}:"
    f"{os.environ.get('DATABASE_PORT', '5432')}/"
    f"{os.environ.get('DATABASE_DB', 'superset')}"
)

# Redis cache
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': os.environ.get('REDIS_HOST', 'superset-cache'),
    'CACHE_REDIS_PORT': int(os.environ.get('REDIS_PORT', '6379')),
    'CACHE_REDIS_DB': 1,
    'CACHE_REDIS_URL': f"redis://{os.environ.get('REDIS_HOST', 'superset-cache')}:6379/1"
}

# Enable CORS
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['*']
}

# Feature flags
FEATURE_FLAGS = {
    'ENABLE_TEMPLATE_PROCESSING': True,
    'DASHBOARD_CROSS_FILTERS': True,
    'DASHBOARD_RBAC': True,
    'EMBEDDED_SUPERSET': True,
    'ALERT_REPORTS': True,
    'ESTIMATE_QUERY_COST': True,
}

# Webdriver
WEBDRIVER_BASEURL = "http://localhost:8088/"

# Query timeout
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 300

# Upload folders
UPLOAD_FOLDER = '/app/superset_home/uploads/'
IMG_UPLOAD_FOLDER = '/app/superset_home/uploads/images/'

# Charts and dashboards
DEFAULT_ROW_LIMIT = 10000
SAMPLES_ROW_LIMIT = 1000

# Custom time grains
TIME_GRAIN_ADDON_FUNCTIONS = {
    'postgresql': {
        'PT15M': 'DATE_TRUNC(\'hour\', {col}) + INTERVAL \'15 min\' * EXTRACT(MINUTE FROM {col})::INT / 15',
        'PT30M': 'DATE_TRUNC(\'hour\', {col}) + INTERVAL \'30 min\' * EXTRACT(MINUTE FROM {col})::INT / 30',
    }
}

# Mapbox
MAPBOX_API_KEY = os.environ.get('MAPBOX_API_KEY', '')

# Localization - dùng English để tránh lỗi i18n
BABEL_DEFAULT_LOCALE = 'en'
BABEL_DEFAULT_FOLDER = '/app/superset/translations'
LANGUAGES = {
    'en': {'flag': 'us', 'name': 'English'},
}

# Fix loading issues
TALISMAN_ENABLED = False
CONTENT_SECURITY_POLICY_WARNING = False
WTF_CSRF_ENABLED = False

# Static files
STATIC_ASSETS_LOAD_TIMEOUT = 120
