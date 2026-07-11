"""
Reporting aggregation (spec §7.4, §10). Pure-ish query functions kept out
of the views. Voided sales are excluded from every report (§7.2).

Accounting model::

    gross_profit     = revenue - cost_of_goods_sold
    net_profit       = gross_profit - operating_expenses
    capital_returned = cost_of_goods_sold   # money recovered from inventory
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from apps.expenses.models import Expense
from apps.sales.models import Sale, SaleItem
from common.enums import SaleStatus
from common.money import round_cents

_SORT_FIELDS = {
    "revenue": "revenue_cents",
    "profit": "profit_cents",
    "quantity": "quantity_sold",
}


def _completed_sales(start, end):
    qs = Sale.objects.filter(status=SaleStatus.COMPLETED)
    if start is not None:
        qs = qs.filter(created_at__gte=start)
    if end is not None:
        qs = qs.filter(created_at__lt=end)
    return qs


def _completed_items(start, end):
    qs = SaleItem.objects.filter(sale__status=SaleStatus.COMPLETED)
    if start is not None:
        qs = qs.filter(sale__created_at__gte=start)
    if end is not None:
        qs = qs.filter(sale__created_at__lt=end)
    return qs


def _expenses(start, end):
    qs = Expense.objects.all()
    if start is not None:
        qs = qs.filter(occurred_at__gte=start)
    if end is not None:
        qs = qs.filter(occurred_at__lt=end)
    return qs


def summary(start, end) -> dict:
    sales = _completed_sales(start, end)
    agg = sales.aggregate(
        revenue=Sum("total_revenue_cents"),
        cogs=Sum("total_cost_cents"),
        count=Count("id"),
    )
    revenue = agg["revenue"] or 0
    cogs = agg["cogs"] or 0
    sale_count = agg["count"] or 0
    gross_profit = revenue - cogs

    expenses_total = _expenses(start, end).aggregate(t=Sum("amount_cents"))["t"] or 0
    net_profit = gross_profit - expenses_total

    quantity_sold = _completed_items(start, end).aggregate(q=Sum("quantity"))[
        "q"
    ] or Decimal("0")

    average_sale_value = (
        round_cents(Decimal(revenue) / Decimal(sale_count)) if sale_count else 0
    )
    margin = float(gross_profit) / float(revenue) * 100 if revenue else 0.0

    return {
        "revenue_cents": revenue,
        "cost_of_goods_sold_cents": cogs,
        "capital_returned_cents": cogs,
        "gross_profit_cents": gross_profit,
        "expenses_cents": expenses_total,
        "net_profit_cents": net_profit,
        "sale_count": sale_count,
        "quantity_sold": quantity_sold,
        "average_sale_value_cents": average_sale_value,
        "gross_profit_margin_percent": round(margin, 2),
    }


def product_stats(start, end, sort: str = "revenue") -> list[dict]:
    order_field = _SORT_FIELDS.get(sort, "revenue_cents")
    rows = (
        _completed_items(start, end)
        .values("product_id", "product__name")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue_cents=Sum("line_revenue_cents"),
            cost_cents=Sum("line_cost_cents"),
            profit_cents=Sum("line_profit_cents"),
        )
        .order_by(f"-{order_field}")
    )
    return [
        {
            "product_id": r["product_id"],
            "name": r["product__name"],
            "quantity_sold": r["quantity_sold"],
            "revenue_cents": r["revenue_cents"],
            "cost_cents": r["cost_cents"],
            "profit_cents": r["profit_cents"],
        }
        for r in rows
    ]


def category_stats(start, end) -> list[dict]:
    rows = (
        _completed_items(start, end)
        .values("product__category_id", "product__category__name")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue_cents=Sum("line_revenue_cents"),
            cost_cents=Sum("line_cost_cents"),
            profit_cents=Sum("line_profit_cents"),
        )
        .order_by("-revenue_cents")
    )
    return [
        {
            "category_id": r["product__category_id"],
            "name": r["product__category__name"],
            "quantity_sold": r["quantity_sold"],
            "revenue_cents": r["revenue_cents"],
            "cost_cents": r["cost_cents"],
            "profit_cents": r["profit_cents"],
        }
        for r in rows
    ]


def expense_stats(start, end) -> list[dict]:
    rows = (
        _expenses(start, end)
        .values("category_id", "category__name")
        .annotate(total_cents=Sum("amount_cents"), expense_count=Count("id"))
        .order_by("-total_cents")
    )
    return [
        {
            "category_id": r["category_id"],
            "name": r["category__name"],
            "total_cents": r["total_cents"],
            "expense_count": r["expense_count"],
        }
        for r in rows
    ]
