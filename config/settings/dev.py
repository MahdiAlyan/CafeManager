"""Development settings — plain venv + SQLite, DEBUG on."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)

# Belt-and-braces: include the PythonAnywhere host so a deploy that
# accidentally lands on dev settings still answers instead of 400-ing while
# the misconfiguration is fixed. Production should still run prod settings.
ALLOWED_HOSTS = env(
    "ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "radwancafe.pythonanywhere.com",
    ],
)

# Loosen password validators in dev so create_owner with a short password
# during local testing isn't a hassle. Prod keeps the full set.
AUTH_PASSWORD_VALIDATORS = []
