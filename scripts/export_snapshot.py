"""
Make a downloadable, credential-scrubbed snapshot of the production database.

Run this on PythonAnywhere when you need to hand the live data to someone for
diagnosis. It uses SQLite's online backup API (safe while the web app is
serving requests, same mechanism as ``manage.py backup_db``), then removes
everything that is a secret rather than business data:

    * ``auth_user.password``   - replaced with an unusable placeholder hash
    * ``authtoken_token``      - emptied (live API tokens)
    * ``django_session``       - emptied
    * ``django_admin_log``     - emptied

Sales, products, purchases, expenses, stock movements, and settings are left
completely untouched, so every reported figure stays reproducible.

Usage (from the project root, prod virtualenv active)::

    python scripts/export_snapshot.py
    python scripts/export_snapshot.py --db ~/radwan-cafe-backend/db.sqlite3 --out ~/snapshot.sqlite3

The source database is only ever read; all edits happen on the copy.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Tables emptied entirely - live credentials and audit noise, no business value.
PURGE_TABLES = ["authtoken_token", "django_session", "django_admin_log"]

# Django's marker for "this account cannot log in with a password".
UNUSABLE_PASSWORD = "!scrubbed-for-export"


def default_db_path() -> Path:
    """Ask Django for the configured DB path, falling back to the repo default."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    try:
        import django
        from django.conf import settings

        django.setup()
        return Path(settings.DATABASES["default"]["NAME"])
    except Exception as exc:
        print(f"(could not load Django settings: {exc}; using the repo default path)")
        return PROJECT_ROOT / "db.sqlite3"


def snapshot(source: Path, target: Path) -> None:
    """Consistent copy via the online backup API (safe under concurrent writes)."""
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def scrub(target: Path) -> list[str]:
    conn = sqlite3.connect(str(target))
    existing = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    notes = []
    try:
        for table in PURGE_TABLES:
            if table not in existing:
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.execute(f"DELETE FROM {table}")
            notes.append(f"emptied {table} ({count} row(s))")

        if "auth_user" in existing:
            users = conn.execute("SELECT COUNT(*) FROM auth_user").fetchone()[0]
            conn.execute("UPDATE auth_user SET password = ?", (UNUSABLE_PASSWORD,))
            notes.append(f"scrubbed password hash for {users} user(s)")

        conn.commit()
        # Reclaim the pages holding the deleted rows so they aren't recoverable
        # from the file's free list.
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.close()
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="Source database")
    parser.add_argument("--out", type=Path, default=None, help="Output snapshot path")
    args = parser.parse_args()

    source = args.db or default_db_path()
    if not source.exists():
        print(f"Source database not found: {source}")
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = args.out or (Path.home() / f"cafe-snapshot-{stamp}.sqlite3")
    target = target.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"Refusing to overwrite existing file: {target}")
        return 2

    print(f"Source : {source}")
    snapshot(source, target)
    for note in scrub(target):
        print(f"  - {note}")

    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    sales = conn.execute("SELECT COUNT(*) FROM sales_sale").fetchone()[0]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(total_revenue_cents), 0) FROM sales_sale"
        " WHERE status = 'completed'"
    ).fetchone()[0]
    conn.close()

    print(f"\nSnapshot written: {target}")
    print(f"Size            : {target.stat().st_size:,} bytes")
    print(f"Contains        : {sales} sale(s), {revenue / 100:,.2f} completed revenue")
    print("\nDownload this file from the PythonAnywhere Files tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
