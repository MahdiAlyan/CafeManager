"""
``create_owner`` management command (spec §4).

Creates the single owner account. There is no signup endpoint. Idempotent
-safe: if an owner already exists it errors clearly rather than silently
creating a second user. The password may be passed via ``--password`` or,
when omitted, entered via a hidden secure prompt.
"""

from __future__ import annotations

import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Create the single owner account (idempotent-safe)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="owner")
        parser.add_argument(
            "--password",
            default=None,
            help="Owner password. If omitted, you are prompted securely.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        # Single-owner app: refuse to create a second account.
        if User.objects.exists():
            existing = User.objects.first()
            raise CommandError(
                "An owner account already exists "
                f"(username={existing.get_username()!r}). "
                "This is a single-owner app; delete the existing user via the "
                "Django admin or shell if you truly need to recreate it."
            )

        if not password:
            password = getpass.getpass("Owner password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise CommandError("Passwords did not match.")

        if not password:
            raise CommandError("Password must not be empty.")

        User.objects.create_superuser(username=username, password=password)
        self.stdout.write(
            self.style.SUCCESS(f"Owner account {username!r} created.")
        )
