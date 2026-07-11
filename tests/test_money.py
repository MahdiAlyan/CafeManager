"""Pure money/quantity math (spec §7.1, §7.3, §10) — no DB involved."""

from decimal import Decimal

from common.money import (
    calculate_purchase_unit_cost_cents,
    line_cost_cents,
    line_profit_cents,
    line_revenue_cents,
    round_cents,
)


def test_round_half_away_from_zero():
    # Matches Dart's num.round(), not Python's banker's rounding.
    assert round_cents(Decimal("0.5")) == 1
    assert round_cents(Decimal("1.5")) == 2
    assert round_cents(Decimal("2.5")) == 3


def test_line_revenue_single_unit():
    assert line_revenue_cents(250, Decimal("1")) == 250


def test_line_revenue_multiple_units():
    assert line_revenue_cents(250, Decimal("3")) == 750


def test_line_revenue_fractional_quantity():
    # 1500 c/kg * 0.250 kg = 375 c
    assert line_revenue_cents(1500, Decimal("0.250")) == 375


def test_line_revenue_rounds_to_cent():
    # 100 c * 1.005 = 100.5 -> 101 (half away from zero)
    assert line_revenue_cents(100, Decimal("1.005")) == 101


def test_line_profit():
    revenue = line_revenue_cents(250, Decimal("2"))
    cost = line_cost_cents(100, Decimal("2"))
    assert line_profit_cents(revenue, cost) == 300


def test_purchase_unit_cost_carton_of_cans():
    # 1 carton of 24 cans for 1200c -> 50 c/can (spec §7.3 worked example)
    assert (
        calculate_purchase_unit_cost_cents(1200, Decimal("1"), Decimal("24")) == 50
    )


def test_purchase_unit_cost_rounds():
    # 1000 / (1 * 3) = 333.33 -> 333
    assert (
        calculate_purchase_unit_cost_cents(1000, Decimal("1"), Decimal("3")) == 333
    )


def test_purchase_unit_cost_zero_quantity_returns_zero():
    # Division-by-zero guard: matches Flutter's Money.zero (spec §7.3).
    assert (
        calculate_purchase_unit_cost_cents(1200, Decimal("0"), Decimal("24")) == 0
    )
    assert (
        calculate_purchase_unit_cost_cents(1200, Decimal("1"), Decimal("0")) == 0
    )
