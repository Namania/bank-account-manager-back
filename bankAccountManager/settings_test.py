"""Test settings: in-memory SQLite, production-like flags."""
# pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
import os

_TEST_ENV = {
    'SECRET_KEY': 'test-only-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz-ABCDEF',
    'DEBUG': 'False',
    'HTTPS_ONLY': 'False',
    'ALLOWED_HOSTS': 'testserver',
    'CSRF_TRUSTED_ORIGINS': 'http://testserver',
    'CORS_ALLOWED_ORIGINS': 'http://testserver',
    'POSTGRES_DB': 'unused',
    'POSTGRES_USER': 'unused',
    'POSTGRES_PASSWORD': 'unused',
    'POSTGRES_PORT': '5432',
    'POSTGRES_HOST': 'unused',
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

from .settings import *

DATABASES['default'].update(ENGINE='django.db.backends.sqlite3', NAME=':memory:')

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
