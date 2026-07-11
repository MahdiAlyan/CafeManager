"""WSGI config for radwan-cafe-backend.

Defaults to prod on PythonAnywhere, dev elsewhere. Set
``DJANGO_SETTINGS_MODULE`` explicitly to override.
"""

from django.core.wsgi import get_wsgi_application

from config.env import configure_default_settings

configure_default_settings()

application = get_wsgi_application()
