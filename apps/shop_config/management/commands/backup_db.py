"""
``backup_db`` — safe SQLite backup for the PythonAnywhere scheduled task
(override 3, replaces the spec's pg_dump strategy).

Uses SQLite's online backup API (``sqlite3.Connection.backup``) rather than
a raw file copy, so it is safe to run while the web app may be writing.
Writes a timestamped copy into the backup directory and prunes copies older
than ``--keep-days`` (default 30).

Usage (see DEPLOYMENT.md for the scheduled-task setup)::

    python manage.py backup_db
    python manage.py backup_db --dest ~/backups --keep-days 30
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BACKUP_SUFFIX = ".sqlite3"


class Command(BaseCommand):
    help = "Create a timestamped, consistent backup of the SQLite database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dest",
            default=str(Path.home() / "backups"),
            help="Directory to write backups into (default: ~/backups).",
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=30,
            help="Delete backups older than this many days (default: 30).",
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            raise CommandError(f"Database file not found: {db_path}")

        dest_dir = Path(options["dest"]).expanduser()
        dest_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = dest_dir / f"db-{stamp}{BACKUP_SUFFIX}"

        # Online backup — consistent even under concurrent writes.
        source = sqlite3.connect(str(db_path))
        try:
            backup = sqlite3.connect(str(target))
            try:
                source.backup(backup)
            finally:
                backup.close()
        finally:
            source.close()

        self.stdout.write(self.style.SUCCESS(f"Backup written: {target}"))
        self._prune(dest_dir, options["keep_days"])

    def _prune(self, dest_dir: Path, keep_days: int):
        if keep_days <= 0:
            return
        cutoff = time.time() - timedelta(days=keep_days).total_seconds()
        removed = 0
        for path in dest_dir.glob(f"db-*{BACKUP_SUFFIX}"):
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        if removed:
            self.stdout.write(
                f"Pruned {removed} backup(s) older than {keep_days} days."
            )
