"""Stock ledger sign conventions + API (spec §5.8, §7.5, §10)."""

from decimal import Decimal

import pytest

from apps.stock.services import adjust_stock
from common.enums import (
    STOCK_INCREASE_TYPES,
    StockMovementType,
    is_increase,
    signed_quantity,
)

pytestmark = pytest.mark.django_db


def test_sign_convention_for_every_type():
    increases = {
        StockMovementType.OPENING,
        StockMovementType.PURCHASE,
        StockMovementType.SALE_REVERSAL,
        StockMovementType.MANUAL_INCREASE,
    }
    decreases = {
        StockMovementType.SALE,
        StockMovementType.MANUAL_DECREASE,
        StockMovementType.DAMAGED,
        StockMovementType.EXPIRED,
        StockMovementType.PERSONAL_USE,
    }
    assert STOCK_INCREASE_TYPES == increases
    for t in increases:
        assert is_increase(t) is True
        assert signed_quantity(t, Decimal("3")) == Decimal("3")
    for t in decreases:
        assert is_increase(t) is False
        assert signed_quantity(t, Decimal("3")) == Decimal("-3")


def test_adjust_damaged_decreases(tracked_product):
    movement = adjust_stock(
        tracked_product.id, StockMovementType.DAMAGED, Decimal("3"), note="broke"
    )
    tracked_product.refresh_from_db()
    assert tracked_product.current_stock == Decimal("97.000")
    assert movement.quantity_change == Decimal("-3.000")
    assert movement.resulting_stock == Decimal("97.000")


def test_adjust_manual_increase(tracked_product):
    adjust_stock(
        tracked_product.id, StockMovementType.MANUAL_INCREASE, Decimal("10")
    )
    tracked_product.refresh_from_db()
    assert tracked_product.current_stock == Decimal("110.000")


def test_adjust_rejects_non_manual_type(tracked_product):
    from rest_framework.exceptions import ValidationError

    with pytest.raises(ValidationError):
        adjust_stock(tracked_product.id, StockMovementType.SALE, Decimal("1"))


def test_enable_stock_tracking_opening_movement(make_product):
    from apps.catalog.services import enable_stock_tracking

    p = make_product()
    enable_stock_tracking(p.id, Decimal("0"), Decimal("5"))
    p.refresh_from_db()
    assert p.track_stock is True
    assert p.current_stock == Decimal("0.000")
    opening = p.stock_movements.get(type=StockMovementType.OPENING)
    assert opening.quantity_change == Decimal("0.000")


def test_api_stock_list_only_tracked(auth_client, tracked_product, product):
    resp = auth_client.get("/api/stock/")
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.data["results"]]
    assert tracked_product.id in ids
    assert product.id not in ids


def test_api_stock_movements_and_adjust(auth_client, tracked_product):
    resp = auth_client.post(
        f"/api/stock/{tracked_product.id}/adjust/",
        {"type": "damaged", "quantity": "3", "note": "x"},
        format="json",
    )
    assert resp.status_code == 200
    resp = auth_client.get(f"/api/stock/{tracked_product.id}/movements/")
    assert resp.status_code == 200
    assert resp.data["count"] >= 2  # opening + damaged
