import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "management_projet_backend.settings")

application = get_wsgi_application()
