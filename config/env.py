
"""
Settings-module selection shared by manage.py, wsgi.py and asgi.py.

Picks ``config.settings.prod`` automatically when running on PythonAnywhere
(which always exports ``PYTHONANYWHERE_DOMAIN``), otherwise
``config.settings.dev``. An explicit ``DJANGO_SETTINGS_MODULE`` in the
environment always wins, so nothing here can override a deliberate choice.
"""

from __future__ import annotations

import os


def default_settings_module() -> str:
    """Return the settings module to use when none is set in the environment."""
    if os.environ.get("PYTHONANYWHERE_DOMAIN"):
        return "config.settings.prod"
    return "config.settings.dev"


def configure_default_settings() -> str:
    """``setdefault`` the settings module and return the effective value."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings_module())
    return os.environ["DJANGO_SETTINGS_MODULE"]
