# devduel/settings.py
import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST    = True

# ── Security ──
SECRET_KEY   = config('SECRET_KEY')
DEBUG        = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS', 
    default='127.0.0.1,localhost', 
    cast=Csv()
    )

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST    = True
SECURE_SSL_REDIRECT     = not DEBUG   # redirect http → https in production

CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://devduel-production-cf37.up.railway.app',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]

# ── Apps ──
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'users',
    'problems',
    'battle',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # ← serve static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'devduel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ── ASGI ──
ASGI_APPLICATION = 'devduel.asgi.application'

# ── Database ──
# Railway provides DATABASE_URL — dj_database_url parses it
# Locally we still use .env individual variables
DATABASE_URL = config('DATABASE_URL', default=None)

if DATABASE_URL:
    # production — Railway MySQL URL
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            engine='django.db.backends.mysql',
            conn_max_age=600,
        )
    }
    DATABASES['default']['OPTIONS'] = {'charset': 'utf8mb4'}
else:
    # local development — individual env vars
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.mysql',
            'NAME':     config('DB_NAME'),
            'USER':     config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST':     config('DB_HOST', default='localhost'),
            'PORT':     config('DB_PORT', default='3306'),
            'OPTIONS':  {'charset': 'utf8mb4'},
        }
    }

# ── Channel Layer ──
# Railway provides REDIS_URL — use it if available
# ── Channel Layer ──
REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379')

# InMemoryChannelLayer: Railway runs 1 replica — no Redis needed for messaging
# Redis is still used for the leaderboard (ZADD/ZRANGE) — unaffected
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# ── Judge URL ──
# In production: the Railway URL of the FastAPI judge service
# Locally: http://127.0.0.1:8001
JUDGE_URL = config('JUDGE_URL', default='http://127.0.0.1:8001')

# ── Auth ──
LOGIN_URL          = '/auth/login/'
LOGIN_REDIRECT_URL = '/battle/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Localisation ──
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_TZ        = True

# ── Static files ──
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'    # collectstatic dumps here
STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Media ──
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
}