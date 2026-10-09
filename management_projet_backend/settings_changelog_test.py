"""Isolated local database for release tests and browser previews."""
import getpass
import os

os.environ.setdefault("SECRET_KEY", "changelog-local-tests-only-20261009-abcdef123456")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("API_URL", "http://localhost:8037")
from .settings_test import *  # noqa: E402,F401,F403

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "management_projet_changelog_preview",
    "USER": getpass.getuser(),
    "HOST": "localhost",
    "PORT": "5432",
    "TEST": {"NAME": "test_management_projet_changelog"},
}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
CORS_ALLOWED_ORIGINS = ["http://localhost:3037", "http://127.0.0.1:3037"]
CORS_ORIGIN_WHITELIST = tuple(CORS_ALLOWED_ORIGINS)
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AXES_ENABLED = False
