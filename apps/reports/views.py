"""Reports API + CSV exports (spec §6.8). Voided sales are always excluded."""

from __future__ import annotations

import csv

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.expenses.models import Expense
from apps.purchases.models import Purchase
from apps.sales.models import SaleItem
from common.date_range import parse_date_range
from common.enums import SaleStatus

from . import services
from .serializers import (
    CategoryStatSerializer,
    ExpenseStatSerializer,
    ProductStatSerializer,
    ReportSummarySerializer,
)

_RANGE_PARAMS = [OpenApiParameter("from", str), OpenApiParameter("to", str)]


@extend_schema(parameters=_RANGE_PARAMS, responses=ReportSummarySerializer)
@api_view(["GET"])
def summary(request):
    start, end = parse_date_range(request)
    data = services.summary(start, end)
    return Response(ReportSummarySerializer(data).data)


@extend_schema(
    parameters=_RANGE_PARAMS
    + [OpenApiParameter("sort", str, enum=["revenue", "profit", "quantity"])],
    responses=ProductStatSerializer(many=True),
)
@api_view(["GET"])
def products(request):
    start, end = parse_date_range(request)
    sort = request.query_params.get("sort", "revenue")
    data = services.product_stats(start, end, sort)
    return Response(ProductStatSerializer(data, many=True).data)


@extend_schema(parameters=_RANGE_PARAMS, responses=CategoryStatSerializer(many=True))
@api_view(["GET"])
def categories(request):
    start, end = parse_date_range(request)
    data = services.category_stats(start, end)
    return Response(CategoryStatSerializer(data, many=True).data)


@extend_schema(parameters=_RANGE_PARAMS, responses=ExpenseStatSerializer(many=True))
@api_view(["GET"])
def expenses(request):
    start, end = parse_date_range(request)
    data = services.expense_stats(start, end)
    return Response(ExpenseStatSerializer(data, many=True).data)


# --- CSV exports ----------------------------------------------------------


class _Echo:
    """A write-only file-like object that just returns what it's given."""

    def write(self, value):
        return value


def _stream_csv(filename, header, rows):
    """Build a StreamingHttpResponse of text/csv from an iterable of rows."""
    writer = csv.writer(_Echo())

    def generate():
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(generate(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _filtered(qs, request, field):
    start, end = parse_date_range(request)
    if start is not None:
        qs = qs.filter(**{f"{field}__gte": start})
    if end is not None:
        qs = qs.filter(**{f"{field}__lt": end})
    return qs


@extend_schema(parameters=_RANGE_PARAMS, responses={(200, "text/csv"): bytes})
@api_view(["GET"])
def export_sales_csv(request):
    # One row per sale line. Voided sales excluded (report invariant, §7.2).
    qs = (
        SaleItem.objects.filter(sale__status=SaleStatus.COMPLETED)
        .select_related("sale", "product")
        .order_by("sale__created_at", "id")
    )
    qs = _filtered(qs, request, "sale__created_at")
    header = [
        "sale_id",
        "created_at",
        "status",
        "product_name",
        "quantity",
        "unit",
        "selling_price_cents",
        "cost_per_unit_cents",
        "line_revenue_cents",
        "line_cost_cents",
        "line_profit_cents",
    ]
    rows = (
        [
            item.sale_id,
            item.sale.created_at.isoformat(),
            item.sale.status,
            item.product_name_snapshot,
            item.quantity,
            item.unit_snapshot,
            item.selling_price_cents_snapshot,
            item.cost_per_unit_cents_snapshot,
            item.line_revenue_cents,
            item.line_cost_cents,
            item.line_profit_cents,
        ]
        for item in qs
    )
    return _stream_csv("sales.csv", header, rows)


@extend_schema(parameters=_RANGE_PARAMS, responses={(200, "text/csv"): bytes})
@api_view(["GET"])
def export_purchases_csv(request):
    qs = (
        Purchase.objects.select_related("product")
        .order_by("purchase_date", "id")
    )
    qs = _filtered(qs, request, "purchase_date")
    header = [
        "purchase_id",
        "purchase_date",
        "product_name",
        "quantity_purchased",
        "purchase_unit",
        "units_per_purchase_unit",
        "total_cost_cents",
        "calculated_unit_cost_cents",
        "supplier",
        "product_cost_updated",
        "notes",
    ]
    rows = (
        [
            p.id,
            p.purchase_date.isoformat(),
            p.product.name,
            p.quantity_purchased,
            p.purchase_unit,
            p.units_per_purchase_unit,
            p.total_cost_cents,
            p.calculated_unit_cost_cents,
            p.supplier or "",
            p.product_cost_updated,
            p.notes or "",
        ]
        for p in qs
    )
    return _stream_csv("purchases.csv", header, rows)


@extend_schema(parameters=_RANGE_PARAMS, responses={(200, "text/csv"): bytes})
@api_view(["GET"])
def export_expenses_csv(request):
    qs = (
        Expense.objects.select_related("category").order_by("occurred_at", "id")
    )
    qs = _filtered(qs, request, "occurred_at")
    header = [
        "expense_id",
        "occurred_at",
        "title",
        "category",
        "amount_cents",
        "notes",
    ]
    rows = (
        [
            e.id,
            e.occurred_at.isoformat(),
            e.title,
            e.category.name,
            e.amount_cents,
            e.notes or "",
        ]
        for e in qs
    )
    return _stream_csv("expenses.csv", header, rows)
