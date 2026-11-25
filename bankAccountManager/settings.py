import os

from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static

from .env import env_bool, env_list, check_production_settings

load_dotenv('.env')

ENV_NEEDS = [
    'SECRET_KEY',
    'DEBUG',
    'ALLOWED_HOSTS',
    'CSRF_TRUSTED_ORIGINS',
    'CORS_ALLOWED_ORIGINS',
    'POSTGRES_DB',
    'POSTGRES_USER',
    'POSTGRES_PASSWORD',
    'POSTGRES_PORT',
    'POSTGRES_HOST'
]
for x in ENV_NEEDS:
    ENV = os.getenv(x)
    if not ENV:
        raise ValueError(f"{x} environment variable not set")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = env_bool('DEBUG')

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')

if not DEBUG:
    check_production_settings(SECRET_KEY, ALLOWED_HOSTS)

# HTTPS is mandatory outside DEBUG unless explicitly disabled. It expects a TLS
# reverse proxy in front of gunicorn that forwards X-Forwarded-Proto.
HTTPS_ONLY = env_bool('HTTPS_ONLY', default=not DEBUG)
if HTTPS_ONLY:
    SECURE_SSL_REDIRECT = True
    # The container health check calls gunicorn directly, over plain HTTP.
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS') or 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

X_FRAME_OPTIONS = 'DENY'

# JWT cookies. Use SameSite=None only when the front-end is served from another
# site than the API; browsers then require HTTPS.
AUTH_COOKIE_ACCESS = 'access_token'
AUTH_COOKIE_REFRESH = 'refresh_token'
AUTH_COOKIE_SECURE = HTTPS_ONLY
AUTH_COOKIE_SAMESITE = os.getenv('AUTH_COOKIE_SAMESITE') or 'Lax'
if AUTH_COOKIE_SAMESITE not in ('Lax', 'Strict', 'None'):
    raise ImproperlyConfigured("AUTH_COOKIE_SAMESITE must be Lax, Strict or None")
if AUTH_COOKIE_SAMESITE == 'None' and not HTTPS_ONLY:
    raise ImproperlyConfigured("AUTH_COOKIE_SAMESITE=None requires HTTPS_ONLY")
CSRF_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE

# The front-end sends the auth cookies on cross-origin requests.
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

INSTALLED_APPS = [
    'unfold',
    'drf_redesign',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',
    'app.apps.BankAppConfig',
    'colorfield',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

UNFOLD = {
    "SITE_TITLE": "Bank Account Manager",
    "SITE_HEADER": "Account Manager",
    "SITE_ICON": lambda request: static("logo.svg"),
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/svg+xml", "href": lambda request: static("logo.svg")},
        {"rel": "alternate icon", "type": "image/png", "href": lambda request: static("logo.png")},
    ],
    "COLORS": {
        # Tailwind "emerald", the stock palette closest to the logo green (#2BB58A).
        "primary": {
            "50": "oklch(97.9% 0.021 166.113)",
            "100": "oklch(95% 0.052 163.051)",
            "200": "oklch(90.5% 0.093 164.15)",
            "300": "oklch(84.5% 0.143 164.978)",
            "400": "oklch(76.5% 0.177 163.223)",
            "500": "oklch(69.6% 0.17 162.48)",
            "600": "oklch(59.6% 0.145 163.225)",
            "700": "oklch(50.8% 0.118 165.612)",
            "800": "oklch(43.2% 0.095 166.913)",
            "900": "oklch(37.8% 0.077 168.94)",
            "950": "oklch(26.2% 0.051 172.552)",
        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'app.authentication.CookieJWTAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Only views that declare a throttle_scope are limited (the token endpoints).
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'token': '5/min',
        'token_refresh': '30/min',
        'password': '5/min',
        'share': '10/min',
    },
    # Trusted reverse proxies in front of the app: the client address used for
    # throttling is read that many entries from the end of X-Forwarded-For.
    'NUM_PROXIES': int(os.getenv('NUM_PROXIES') or 1),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Bank Account Manager API',
    'DESCRIPTION': 'Amounts are decimal euros as strings ("10.50"). Authentication uses HttpOnly cookies; '
                   'every write needs the X-CSRFToken header.',
    'VERSION': '1.0.0',
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],
}

if DEBUG:
    # Browsable API and session login are development conveniences only.
    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].append('rest_framework.authentication.SessionAuthentication')
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'].append('rest_framework.renderers.BrowsableAPIRenderer')

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'app.middleware.SecurityHeadersMiddleware',
    'app.middleware.AdminLoginThrottleMiddleware',
    'app.middleware.MaintenanceMiddleware',
]

ROOT_URLCONF = 'bankAccountManager.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
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

WSGI_APPLICATION = 'bankAccountManager.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT'),
        'ATOMIC_REQUESTS': True,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'loggers': {
        'app.security': {'handlers': ['console'], 'level': 'INFO'},
        'app.audit': {'handlers': ['console'], 'level': 'INFO'},
        'django.security': {'handlers': ['console'], 'level': 'WARNING'},
    },
}
