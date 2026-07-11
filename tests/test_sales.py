"""Sales business logic + API (spec §7.1, §7.2, §10)."""

from decimal import Decimal

import pytest

from apps.sales.models import Sale, SaleItem
from apps.sales.services import complete_sale, void_sale
from common.enums import SaleStatus, StockMovementType

pytestmark = pytest.mark.django_db


# --- services: totals -----------------------------------------------------


def test_complete_sale_single_line(product):
    sale = complete_sale([{"product_id": product.id, "quantity": Decimal("2")}])
    assert sale.total_revenue_cents == 500
    assert sale.total_cost_cents == 200
    assert sale.total_profit_cents == 300
    assert sale.status == SaleStatus.COMPLETED
    assert sale.items.count() == 1


def test_complete_sale_multiple_lines(product, make_product):
    other = make_product(selling_price_cents=100, cost_per_unit_cents=60)
    sale = complete_sale(
        [
            {"product_id": product.id, "quantity": Decimal("2")},
            {"product_id": other.id, "quantity": Decimal("3")},
        ]
    )
    assert sale.total_revenue_cents == 500 + 300
    assert sale.total_cost_cents == 200 + 180
    assert sale.total_profit_cents == 800 - 380


def test_complete_sale_fractional_quantity(make_product):
    p = make_product(selling_price_cents=1500, cost_per_unit_cents=900)
    sale = complete_sale([{"product_id": p.id, "quantity": Decimal("0.250")}])
    assert sale.total_revenue_cents == 375
    assert sale.total_cost_cents == 225


def test_empty_cart_rejected():
    from rest_framework.exceptions import ValidationError

    with pytest.raises(ValidationError):
        complete_sale([])
    assert Sale.objects.count() == 0


# --- the critical snapshot-immutability invariant (spec §5.4, §10) --------


def test_snapshot_is_immutable_after_product_price_change(product):
    sale = complete_sale([{"product_id": product.id, "quantity": Decimal("2")}])
    item = sale.items.first()
    assert item.selling_price_cents_snapshot == 250
    assert item.cost_per_unit_cents_snapshot == 100

    # Change the product's price/cost/name afterwards.
    product.selling_price_cents = 999
    product.cost_per_unit_cents = 500
    product.name = "Renamed"
    product.save()

    item.refresh_from_db()
    assert item.selling_price_cents_snapshot == 250
    assert item.cost_per_unit_cents_snapshot == 100
    assert item.product_name_snapshot == "Espresso"
    assert item.line_revenue_cents == 500

    sale.refresh_from_db()
    assert sale.total_revenue_cents == 500  # unchanged


# --- the critical atomicity invariant (spec §7.1, §10) --------------------


def test_sale_is_atomic_rollback_on_bad_last_item(product):
    # A non-existent product on the last line must roll the whole sale back.
    with pytest.raises(Exception):
        complete_sale(
            [
                {"product_id": product.id, "quantity": Decimal("1")},
                {"product_id": 999999, "quantity": Decimal("1")},
            ]
        )
    assert Sale.objects.count() == 0
    assert SaleItem.objects.count() == 0


# --- stock decrement on sale ---------------------------------------------


def test_sale_decrements_tracked_stock(tracked_product):
    sale = complete_sale(
        [{"product_id": tracked_product.id, "quantity": Decimal("5")}]
    )
    tracked_product.refresh_from_db()
    assert tracked_product.current_stock == Decimal("95.000")
    movement = tracked_product.stock_movements.filter(
        type=StockMovementType.SALE
    ).latest("id")
    assert movement.quantity_change == Decimal("-5.000")
    assert movement.related_sale_id == sale.id


# --- voiding (spec §7.2) --------------------------------------------------


def test_void_sets_status_and_keeps_history(product):
    sale = complete_sale([{"product_id": product.id, "quantity": Decimal("1")}])
    voided = void_sale(sale.id, reason="mistake")
    assert voided.status == SaleStatus.VOIDED
    assert voided.voided_at is not None
    assert voided.void_reason == "mistake"
    # History survives.
    assert Sale.objects.filter(id=sale.id).exists()
    assert SaleItem.objects.filter(sale=sale).exists()


def test_void_restores_tracked_stock(tracked_product):
    sale = complete_sale(
        [{"product_id": tracked_product.id, "quantity": Decimal("5")}]
    )
    tracked_product.refresh_from_db()
    assert tracked_product.current_stock == Decimal("95.000")

    void_sale(sale.id)
    tracked_product.refresh_from_db()
    assert tracked_product.current_stock == Decimal("100.000")
    reversal = tracked_product.stock_movements.filter(
        type=StockMovementType.SALE_REVERSAL
    ).latest("id")
    assert reversal.quantity_change == Decimal("5.000")


def test_double_void_is_idempotent(tracked_product):
    sale = complete_sale(
        [{"product_id": tracked_product.id, "quantity": Decimal("5")}]
    )
    void_sale(sale.id)
    void_sale(sale.id)  # no-op
    tracked_product.refresh_from_db()
    # Stock restored exactly once, not twice.
    assert tracked_product.current_stock == Decimal("100.000")
    assert (
        tracked_product.stock_movements.filter(
            type=StockMovementType.SALE_REVERSAL
        ).count()
        == 1
    )


# --- API layer ------------------------------------------------------------


def test_api_create_sale_ignores_client_prices(auth_client, product):
    resp = auth_client.post(
        "/api/sales/",
        {
            "items": [
                {
                    "product_id": product.id,
                    "quantity": "2",
                    "selling_price_cents": 999999,  # should be ignored
                }
            ]
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["total_revenue_cents"] == 500  # server used its own price


def test_api_create_sale_empty_items_400(auth_client):
    resp = auth_client.post("/api/sales/", {"items": []}, format="json")
    assert resp.status_code == 400


def test_api_sale_no_update_or_delete(auth_client, product):
    sale = complete_sale([{"product_id": product.id, "quantity": Decimal("1")}])
    assert auth_client.put(f"/api/sales/{sale.id}/", {}, format="json").status_code == 405
    assert auth_client.delete(f"/api/sales/{sale.id}/").status_code == 405


def test_api_void_endpoint(auth_client, product):
    sale = complete_sale([{"product_id": product.id, "quantity": Decimal("1")}])
    resp = auth_client.post(
        f"/api/sales/{sale.id}/void/", {"reason": "oops"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["status"] == "voided"
