"""Reports math + API (spec §7.4, §10)."""

from decimal import Decimal

import pytest

from apps.expenses.models import Expense
from apps.reports import services as reports
from apps.sales.services import complete_sale, void_sale

pytestmark = pytest.mark.django_db


def _worked_example(make_product, expense_category):
    """revenue=100, cogs=65, expenses=5 -> gross=35, net=30 (spec §10)."""
    p = make_product(selling_price_cents=100, cost_per_unit_cents=65)
    complete_sale([{"product_id": p.id, "quantity": Decimal("1")}])
    Expense.objects.create(
        title="misc", category=expense_category, amount_cents=5
    )


def test_summary_worked_example(make_product, expense_category):
    _worked_example(make_product, expense_category)
    s = reports.summary(None, None)
    assert s["revenue_cents"] == 100
    assert s["cost_of_goods_sold_cents"] == 65
    assert s["capital_returned_cents"] == 65  # == cogs, not profit (§7.4)
    assert s["gross_profit_cents"] == 35
    assert s["expenses_cents"] == 5
    assert s["net_profit_cents"] == 30
    assert s["sale_count"] == 1


def test_expenses_reduce_net_but_not_gross_or_cogs(make_product, expense_category):
    p = make_product(selling_price_cents=100, cost_per_unit_cents=65)
    complete_sale([{"product_id": p.id, "quantity": Decimal("1")}])

    before = reports.summary(None, None)
    Expense.objects.create(
        title="rent", category=expense_category, amount_cents=20
    )
    after = reports.summary(None, None)

    assert after["cost_of_goods_sold_cents"] == before["cost_of_goods_sold_cents"]
    assert after["gross_profit_cents"] == before["gross_profit_cents"]
    assert after["net_profit_cents"] == before["net_profit_cents"] - 20


def test_voided_sale_excluded_from_summary(make_product):
    p = make_product(selling_price_cents=100, cost_per_unit_cents=65)
    sale = complete_sale([{"product_id": p.id, "quantity": Decimal("1")}])
    assert reports.summary(None, None)["revenue_cents"] == 100
    void_sale(sale.id)
    s = reports.summary(None, None)
    assert s["revenue_cents"] == 0
    assert s["sale_count"] == 0
    assert s["net_profit_cents"] == 0


def test_margin_and_average(make_product):
    p = make_product(selling_price_cents=100, cost_per_unit_cents=65)
    complete_sale([{"product_id": p.id, "quantity": Decimal("1")}])
    s = reports.summary(None, None)
    assert s["average_sale_value_cents"] == 100
    assert s["gross_profit_margin_percent"] == 35.0


def test_product_and_category_stats(make_product):
    p = make_product(selling_price_cents=100, cost_per_unit_cents=65)
    complete_sale([{"product_id": p.id, "quantity": Decimal("2")}])
    prod_stats = reports.product_stats(None, None, "revenue")
    assert prod_stats[0]["product_id"] == p.id
    assert prod_stats[0]["revenue_cents"] == 200
    cat_stats = reports.category_stats(None, None)
    assert cat_stats[0]["revenue_cents"] == 200


# --- API + CSV ------------------------------------------------------------


def test_api_summary(auth_client, make_product, expense_category):
    _worked_example(make_product, expense_category)
    resp = auth_client.get("/api/reports/summary/")
    assert resp.status_code == 200
    assert resp.data["net_profit_cents"] == 30
    # quantity_sold serialized as a decimal string (DRF DecimalField).
    assert resp.data["quantity_sold"] == "1.000"


def test_api_export_sales_csv(auth_client, make_product):
    p = make_product(selling_price_cents=100, cost_per_unit_cents=65)
    complete_sale([{"product_id": p.id, "quantity": Decimal("1")}])
    resp = auth_client.get("/api/reports/export/sales.csv")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    body = b"".join(resp.streaming_content).decode()
    assert "sale_id" in body
    assert "line_revenue_cents" in body


def test_api_export_expenses_csv(auth_client, expense_category):
    Expense.objects.create(title="rent", category=expense_category, amount_cents=500)
    resp = auth_client.get("/api/reports/export/expenses.csv")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "rent" in body
