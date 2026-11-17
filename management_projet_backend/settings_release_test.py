"""Isolated SQLite release checks; never connect to the configured database."""
from .settings_test import *  # noqa: F403
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/management-projet-release.sqlite3", "TEST": {"NAME": ":memory:"}}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
INSTALLED_APPS = [*INSTALLED_APPS, "simple_history"]  # noqa: F405
AI_PDF_TRANSLATION_ENABLED = False
