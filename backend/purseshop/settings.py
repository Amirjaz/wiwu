"""Settings for the purse store. Secrets, hosts and providers come from backend/.env (see .env.example)."""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

DEVELOPMENT = os.getenv('Development', 'False') == 'True'
DEBUG = DEVELOPMENT


def env_list(name, default):
    value = os.getenv(name)
    return [item.strip() for item in value.split(',') if item.strip()] if value else default


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEVELOPMENT:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY (see backend/.env.example).')
    SECRET_KEY = 'django-insecure-development-only'

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', ['localhost'])
if DEVELOPMENT:
    ALLOWED_HOSTS += ['127.0.0.1']

# The address in SMS links, e.g. https://example.ir (no trailing slash).
PUBLIC_URL = os.getenv('PUBLIC_URL', 'http://127.0.0.1:8030' if DEVELOPMENT else '').rstrip('/')
if not PUBLIC_URL:
    raise ImproperlyConfigured('Set PUBLIC_URL (see backend/.env.example).')

# Staging: keep search engines out (meta robots + X-Robots-Tag + robots.txt).
NOINDEX = os.getenv('SITE_NOINDEX', 'True' if DEVELOPMENT else 'False') == 'True'

# nginx (behind ArvanCloud) terminates TLS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', [PUBLIC_URL])
if DEVELOPMENT:
    CSRF_TRUSTED_ORIGINS += [f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (8030, 5180)]
if not DEVELOPMENT:
    # On an https site, plain-http visitors are sent to https (Arvan serves both, and the secure-only
    # cookies below would otherwise break checkout over http).
    SECURE_SSL_REDIRECT = SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = PUBLIC_URL.startswith('https://')

SESSION_COOKIE_AGE = 14 * 24 * 3600  # staff stay signed in for two weeks
SESSION_COOKIE_HTTPONLY = True

INSTALLED_APPS = [
    'shop.apps.ShopConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shop.middleware.noindex_middleware',
]

ROOT_URLCONF = 'purseshop.urls'

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
                'shop.context.store',
            ],
        },
    },
]

WSGI_APPLICATION = 'purseshop.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # WAL: the panel and the payment checks read while an order is being written.
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
            'transaction_mode': 'IMMEDIATE',
            'timeout': 20,
        },
    }
}

# Shared by all gunicorn workers, so rate limits (OTP, sign-in) hold across them.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    },
    # Rendered home and policy pages (shop/pagecache.py), in their own table so emptying it leaves
    # the rate limits alone. Off in development, where templates change all the time.
    'pages': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache' if DEVELOPMENT
        else 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'page_cache_table',
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Transfer screenshots buyers upload. Never served by nginx: they can show card numbers, so only
# signed-in staff get them, through the panel API.
PRIVATE_ROOT = BASE_DIR / 'private'
UPLOAD_MAX_MB = 6
DATA_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_MB * 1024 * 1024 + 64 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# The Vite build. In development the pages load modules straight from the Vite dev server;
# in production they read the manifest the build wrote (deploy puts it next to the assets).
VITE_DEV_SERVER = os.getenv('VITE_DEV_SERVER', 'http://127.0.0.1:5180' if DEVELOPMENT else '').rstrip('/')
VITE_MANIFEST = Path(os.getenv('VITE_MANIFEST', BASE_DIR.parent / 'frontend' / 'dist' / '.vite' / 'manifest.json'))
VITE_ASSETS_URL = os.getenv('VITE_ASSETS_URL', '/')  # where the build's assets/ folder is served

# SMS: 'console' (development: printed and logged in the panel only) or 'kavenegar'.
SMS_BACKEND = os.getenv('SMS_BACKEND', 'console' if DEVELOPMENT else 'kavenegar')
KAVENEGAR_API_KEY = os.getenv('KAVENEGAR_API_KEY', '')
# Plain messages go from this line (empty: the account's default line). The kinds listed in
# KAVENEGAR_TEMPLATES (comma-separated, e.g. 'otp,paid', or 'all') use templates approved in the
# Kavenegar panel instead. See shop/sms.py.
KAVENEGAR_SENDER = os.getenv('KAVENEGAR_SENDER', '').strip()
KAVENEGAR_TEMPLATES = [k.strip().lower().replace('-', '_') for k in os.getenv('KAVENEGAR_TEMPLATES', '').split(',') if k.strip()]

# Payment confirmation: 'manual' (staff confirm in the panel) or 'cartbecart' (automatic, from the
# bank's deposit SMS). Card-to-card either way; see shop/payments.py. The API key (cb_…) and the
# webhook's signing key both come from cartbecart's dashboard → Settings.
PAYMENT_PROVIDER = os.getenv('PAYMENT_PROVIDER', 'manual')
CARTBECART_API_URL = os.getenv('CARTBECART_API_URL', 'https://api.cartbecart.com').rstrip('/')
CARTBECART_API_KEY = os.getenv('CARTBECART_API_KEY', '')
CARTBECART_WEBHOOK_SECRET = os.getenv('CARTBECART_WEBHOOK_SECRET', '')

# Tests never text anyone or register orders with cartbecart, whatever .env holds: the tests that check
# those calls fake them. (A .env with the real Kavenegar key once made the suite send for real.)
if sys.argv[1:2] == ['test']:
    SMS_BACKEND, KAVENEGAR_API_KEY, KAVENEGAR_TEMPLATES = 'console', '', []
    PAYMENT_PROVIDER, CARTBECART_API_KEY, CARTBECART_WEBHOOK_SECRET = 'manual', '', ''

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'shop': {'handlers': ['console'], 'level': 'INFO'}},
}
