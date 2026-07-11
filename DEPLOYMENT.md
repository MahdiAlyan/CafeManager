# Deployment — radwan-cafe-backend

Target: **https://radwancafe.pythonanywhere.com/** on
[PythonAnywhere](https://www.pythonanywhere.com/). SQLite database, no
Docker, no gunicorn. Static files (Django admin + Swagger UI assets) are
served by PythonAnywhere's static-file mapping, not by Django.

---

## 0. Local development (quick reference)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py create_owner --username owner        # prompts for password
python manage.py runserver
```

- API root: `http://127.0.0.1:8000/api/`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Run tests: `pytest`

`manage.py`, `wsgi.py`, and `asgi.py` default to `config.settings.dev`.
Production uses `config.settings.prod` (set in the WSGI file below).

---

## 1. Create the web app

1. Log in to PythonAnywhere as user **`radwancafe`** (so the app is served at
   `radwancafe.pythonanywhere.com`).
2. **Web** tab → **Add a new web app** → **Manual configuration** (NOT the
   "Django" auto-setup) → pick the **newest Python 3.x** offered (3.12 or
   later; Django 6.0 requires ≥ 3.12).

## 2. Clone the repo

Open a **Bash console** and clone into your home directory:

```bash
cd ~
git clone <YOUR_REPO_URL> radwan-cafe-backend
cd radwan-cafe-backend
```

Final path: `/home/radwancafe/radwan-cafe-backend` (contains `manage.py`).

## 3. Create the virtualenv

```bash
mkvirtualenv --python=python3.12 radwan-cafe
# If 3.12 is unavailable, use the newest PythonAnywhere offers, e.g.:
#   mkvirtualenv --python=python3.13 radwan-cafe
pip install -r requirements.txt
```

`mkvirtualenv` creates it at `/home/radwancafe/.virtualenvs/radwan-cafe`
and activates it. Re-enter later with `workon radwan-cafe`.

## 4. Configure environment (`.env`)

```bash
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Edit `.env` and set at least:

```ini
SECRET_KEY=<paste the generated key>
DEBUG=False
ALLOWED_HOSTS=radwancafe.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://radwancafe.pythonanywhere.com
SQLITE_PATH=/home/radwancafe/radwan-cafe-backend/db.sqlite3
```

`config/settings/base.py` reads this `.env` automatically (it lives at the
project root). The WSGI file below also loads it, belt-and-braces.

## 5. Migrate, seed, create the owner, collect static

Run these once on first deploy (NOT on every reload):

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py create_owner --username owner        # prompts for password
```

`migrate` also runs the data migrations that seed the default categories,
expense categories, and the `AppSettings` singleton.

## 6. Point the web app at the virtualenv

**Web** tab → **Virtualenv** section → enter:

```
/home/radwancafe/.virtualenvs/radwan-cafe
```

## 7. WSGI configuration file

**Web** tab → **Code** → **WSGI configuration file** (it opens
`/var/www/radwancafe_pythonanywhere_com_wsgi.py`). **Delete its entire
contents** and replace with:

```python
import os
import sys

# 1. Put the project on the import path.
PROJECT_ROOT = "/home/radwancafe/radwan-cafe-backend"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2. Use production settings.
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"

# 3. Load environment variables from .env (SECRET_KEY, ALLOWED_HOSTS, ...).
import environ
environ.Env.read_env(os.path.join(PROJECT_ROOT, ".env"))

# 4. Serve the app.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Save it.

## 8. Static files mapping

**Web** tab → **Static files** section → add this mapping so
`/static/` is served directly (Django does not serve static in production):

| URL        | Directory                                              |
|------------|--------------------------------------------------------|
| `/static/` | `/home/radwancafe/radwan-cafe-backend/staticfiles`     |

(Matches `STATIC_URL = "static/"` and `STATIC_ROOT = BASE_DIR/staticfiles`.)

## 9. Reload

**Web** tab → big green **Reload** button. Then verify:

- `https://radwancafe.pythonanywhere.com/api/docs/` — Swagger UI renders.
- `POST https://radwancafe.pythonanywhere.com/api/auth/login/` with the owner
  credentials returns `{ "token": ..., "shop_name": ... }`.
- `https://radwancafe.pythonanywhere.com/admin/` — admin login works
  (static/CSS loads, proving the static mapping).

---

## 10. Backups (scheduled task)

Backups are consistent SQLite copies made with `manage.py backup_db` (online
backup API — safe while the app is writing). It writes a timestamped file to
`~/backups/` and prunes anything older than 30 days.

**Tasks** tab → **Add a new scheduled task** (daily). Command:

```bash
source /home/radwancafe/.virtualenvs/radwan-cafe/bin/activate && \
cd /home/radwancafe/radwan-cafe-backend && \
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py backup_db --dest /home/radwancafe/backups --keep-days 30
```

Backups land in `/home/radwancafe/backups/db-YYYYMMDD-HHMMSS.sqlite3`.

**Restore** (manual, by an operator — there is intentionally no restore API):

```bash
workon radwan-cafe
cd ~/radwan-cafe-backend
# stop writes first: on the Web tab, temporarily disable the app, or do this
# during a quiet period, then:
cp /home/radwancafe/backups/db-YYYYMMDD-HHMMSS.sqlite3 db.sqlite3
# Reload the web app.
```

---

## 11. Deploying updates

```bash
workon radwan-cafe
cd ~/radwan-cafe-backend
git pull
pip install -r requirements.txt          # if deps changed
export DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py migrate                 # if models changed
python manage.py collectstatic --noinput # if static changed
# Web tab -> Reload
```

## 12. Known gaps

- **No password reset** for the single owner (v1, spec §4/§12.3). If the
  password is lost, reset it from a Bash console:
  `python manage.py changepassword owner`.
