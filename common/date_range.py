"""
Half-open date-range filtering for list/report endpoints (spec §6):
``?from=<ISO>&to=<ISO>`` where ``from`` is inclusive and ``to`` is
exclusive — matching ``DateRange`` in the Flutter app.

A bare date (``2026-07-11``) is interpreted at midnight in the active
timezone (``Asia/Beirut``); a full ISO datetime is honoured as given.
"""

from __future__ import annotations

from datetime import date, datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError


def _parse_bound(value: str, field_name: str) -> datetime:
    """Parse an ISO date or datetime query param into an aware datetime."""
    dt = parse_datetime(value)
    if dt is None:
        d = parse_date(value)
        if d is None:
            raise ValidationError(
                {field_name: "Expected an ISO date (YYYY-MM-DD) or datetime."}
            )
        dt = datetime.combine(d, time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def apply_date_range(queryset, request, field: str):
    """
    Filter ``queryset`` by ``request``'s ``from``/``to`` query params on the
    given datetime ``field``. ``from`` -> ``__gte``, ``to`` -> ``__lt``.
    Missing params are simply not applied.
    """
    start, end = parse_date_range(request)
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def parse_date_range(request):
    """Return ``(start, end)`` aware datetimes (either may be ``None``)."""
    start_raw = request.query_params.get("from")
    end_raw = request.query_params.get("to")
    start = _parse_bound(start_raw, "from") if start_raw else None
    end = _parse_bound(end_raw, "to") if end_raw else None
    return start, end
