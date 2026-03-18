from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='change-me')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'route',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fuel_route_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fuel_route_api.wsgi.application'

DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# Mapbox
MAPBOX_TOKEN = env('MAPBOX_TOKEN', default='')
MAPBOX_GEOCODING_URL = env('MAPBOX_GEOCODING_URL', default='https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json')
MAPBOX_DIRECTIONS_URL = env('MAPBOX_DIRECTIONS_URL', default='https://api.mapbox.com/directions/v5/mapbox/driving/{coords}')

# API Constants
VEHICLE_RANGE_MILES = 500
VEHICLE_MPG = 10
TANK_CAPACITY_GALLONS = 50
ROUTE_CORRIDOR_MILES = 5
ROUTE_WAYPOINT_INTERVAL_MILES = 25
SAFETY_BUFFER_MILES = 100

SPECTACULAR_SETTINGS = {
    'TITLE': 'Fuel Route Optimizer API',
    'DESCRIPTION': 'Find optimal fuel stops along a US driving route',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
