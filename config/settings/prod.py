"""
Production settings — PythonAnywhere, SQLite, HTTPS behind a proxy.

Target host: https://radwancafe.pythonanywhere.com/

The WSGI file sets ``DJANGO_SETTINGS_MODULE=config.settings.prod`` and
loads the ``.env`` file (see DEPLOYMENT.md). No Docker, no gunicorn.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Documented production value; overridable via env.
ALLOWED_HOSTS = env(
    "ALLOWED_HOSTS", default=["radwancafe.pythonanywhere.com"]
)

CSRF_TRUSTED_ORIGINS = env(
    "CSRF_TRUSTED_ORIGINS",
    default=["https://radwancafe.pythonanywhere.com"],
)

# PythonAnywhere terminates TLS at its proxy and forwards this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Secure cookies / HTTPS hardening.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# SECRET_KEY must be provided via .env in production (no insecure default).
SECRET_KEY = env("SECRET_KEY")
