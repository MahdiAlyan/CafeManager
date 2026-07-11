"""
Permissions. There is only ever one user (the owner), so plain
``IsAuthenticated`` is sufficient everywhere. ``IsOwner`` is provided as a
named alias for readability/intent and future-proofing (spec §4).
"""

from rest_framework.permissions import IsAuthenticated


class IsOwner(IsAuthenticated):
    """The single authenticated owner. Behaves as ``IsAuthenticated`` for v1."""
