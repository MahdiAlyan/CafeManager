"""Purchase business logic + API (spec §6.5, §7.3, §10)."""

from decimal import Decimal

import pytest

from apps.purchases.services import record_purchase
from common.enums import StockMovementType

pytestmark = pytest.mark.django_db


def test_unit_cost_conversion(product):
    purchase = record_purchase(
        product_id=product.id,
        quantity_purchased=Decimal("1"),
        purchase_unit="carton",
        units_per_purchase_unit=Decimal("24"),
        total_cost_cents=1200,
    )
    assert purchase.calculated_unit_cost_cents == 50


def test_update_product_cost_flag(product):
    record_purchase(
        product_id=product.id,
        quantity_purchased=Decimal("1"),
        purchase_unit="carton",
        units_per_purchase_unit=Decimal("24"),
        total_cost_cents=1200,
        update_product_cost=True,
    )
    product.refresh_from_db()
    assert product.cost_per_unit_cents == 50


def test_no_update_product_cost_by_default(product):
    original = product.cost_per_unit_cents
    record_purchase(
        product_id=product.id,
        quantity_purchased=Decimal("1"),
        purchase_unit="carton",
        units_per_purchase_unit=Decimal("24"),
        total_cost_cents=1200,
        update_product_cost=False,
    )
    product.refresh_from_db()
    assert product.cost_per_unit_cents == original


def test_purchase_increments_tracked_stock(tracked_product):
    record_purchase(
        product_id=tracked_product.id,
        quantity_purchased=Decimal("2"),
        purchase_unit="carton",
        units_per_purchase_unit=Decimal("24"),
        total_cost_cents=2400,
    )
    tracked_product.refresh_from_db()
    # 100 opening + 2*24 = 148
    assert tracked_product.current_stock == Decimal("148.000")
    movement = tracked_product.stock_movements.filter(
        type=StockMovementType.PURCHASE
    ).latest("id")
    assert movement.quantity_change == Decimal("48.000")


def test_api_record_purchase(auth_client, product):
    resp = auth_client.post(
        "/api/purchases/",
        {
            "product_id": product.id,
            "quantity_purchased": "1",
            "purchase_unit": "carton",
            "units_per_purchase_unit": "24",
            "total_cost_cents": 1200,
            "update_product_cost": True,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["calculated_unit_cost_cents"] == 50
