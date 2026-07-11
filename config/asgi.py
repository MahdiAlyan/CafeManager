"""ASGI config for radwan-cafe-backend.

Defaults to prod on PythonAnywhere, dev elsewhere. Set
``DJANGO_SETTINGS_MODULE`` explicitly to override.
"""

from django.core.asgi import get_asgi_application

from config.env import configure_default_settings

configure_default_settings()

application = get_asgi_application()
