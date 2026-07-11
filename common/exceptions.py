"""
Custom DRF exception handling.

Translates Django's ``ProtectedError`` (raised when deleting a row still
referenced by an ``on_delete=PROTECT`` FK) into a clean ``400`` instead of
leaking a 500/DB integrity error to the client (spec §8).
"""

from __future__ import annotations

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        return Response(
            {
                "detail": (
                    "Cannot delete: this record is still referenced by other "
                    "records."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return exception_handler(exc, context)
