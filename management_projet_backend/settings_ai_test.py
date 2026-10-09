"""Isolated assistant development/test database; never production coordinates."""
import getpass,os
from .settings_test import *  # noqa
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':'chat_ai_management_projet_dev','USER':os.environ.get('CHAT_AI_TEST_DB_USER',getpass.getuser()),'HOST':'localhost','PORT':'5432','TEST':{'NAME':'test_chat_ai_management_projet'}}}
CHAT_AI_ASSISTANT_ENABLED=True
ALLOWED_HOSTS=['localhost','127.0.0.1','testserver']
PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
SECURE_SSL_REDIRECT=False
