"""
Money & quantity math, mirroring the Flutter app's
``lib/core/finance/finance_calculator.dart`` and ``core/utils/money.dart``.

All monetary values are **integer minor units (cents)**. Quantities are
``Decimal`` (the models use ``DecimalField(12, 3)``). Every function here is
pure and independently unit-tested (spec §7, §10) — keep this math out of
views and serializers.

Rounding matches Dart's ``num.round()`` (round half away from zero), so
``0.5 -> 1`` and ``2.5 -> 3``. Python's built-in ``round`` uses banker's
rounding, so we use ``Decimal.quantize(ROUND_HALF_UP)`` instead.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def round_cents(value: Decimal) -> int:
    """Round a Decimal amount to the nearest whole cent (half away from zero)."""
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def line_revenue_cents(unit_price_cents: int, quantity: Decimal) -> int:
    """Revenue for a single sale line: ``unit_price * quantity`` (rounded)."""
    return round_cents(Decimal(unit_price_cents) * Decimal(quantity))


def line_cost_cents(unit_cost_cents: int, quantity: Decimal) -> int:
    """Cost for a single sale line: ``unit_cost * quantity`` (rounded)."""
    return round_cents(Decimal(unit_cost_cents) * Decimal(quantity))


def line_profit_cents(line_revenue: int, line_cost: int) -> int:
    """Profit for a single sale line: ``revenue - cost``."""
    return line_revenue - line_cost


def calculate_purchase_unit_cost_cents(
    total_cost_cents: int,
    quantity_purchased: Decimal,
    units_per_purchase_unit: Decimal,
) -> int:
    """
    Convert a purchase total into a per-unit cost (spec §7.3)::

        unit_cost = round(total_cost / (quantity_purchased * units_per_purchase_unit))

    Example: 1 carton of 24 cans for 1200 cents -> 1200 / (1 * 24) = 50.

    Edge case: a non-positive denominator returns ``0`` (matching the
    Flutter side, which returns ``Money.zero``).
    """
    denominator = Decimal(quantity_purchased) * Decimal(units_per_purchase_unit)
    if denominator <= 0:
        return 0
    return round_cents(Decimal(total_cost_cents) / denominator)
