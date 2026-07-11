"""Development settings — plain venv + SQLite, DEBUG on."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])

# Loosen password validators in dev so create_owner with a short password
# during local testing isn't a hassle. Prod keeps the full set.
AUTH_PASSWORD_VALIDATORS = []
