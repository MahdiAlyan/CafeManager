"""
Sales business logic (spec §7.1, §7.2). The single most important
invariant: SaleItem snapshot fields are captured from the product's
*current* state at sale time and are never recomputed afterwards.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.enums import SaleStatus, StockMovementType
from common.money import line_cost_cents, line_profit_cents, line_revenue_cents

from .models import Sale, SaleItem


@transaction.atomic
def complete_sale(items: list[dict]) -> Sale:
    """
    Create a completed sale from ``[{"product_id", "quantity"}, ...]``.

    Server re-fetches each product inside the transaction and snapshots its
    **current** price/cost — client-sent prices are never trusted (§7.1).
    Sale + items + stock decrements are one atomic unit.
    """
    from apps.catalog.models import Product
    from apps.stock.services import record_movement

    if not items:
        raise ValidationError({"items": "A sale must have at least one item."})

    sale = Sale.objects.create(status=SaleStatus.COMPLETED)

    total_revenue = 0
    total_cost = 0

    for line in items:
        quantity = Decimal(line["quantity"])
        if quantity <= 0:
            raise ValidationError({"quantity": "Must be > 0."})

        product = Product.objects.select_for_update().get(pk=line["product_id"])

        price = product.selling_price_cents
        cost = product.cost_per_unit_cents
        revenue = line_revenue_cents(price, quantity)
        cost_total = line_cost_cents(cost, quantity)
        profit = line_profit_cents(revenue, cost_total)

        SaleItem.objects.create(
            sale=sale,
            product=product,
            product_name_snapshot=product.name,
            unit_snapshot=product.selling_unit,
            quantity=quantity,
            selling_price_cents_snapshot=price,
            cost_per_unit_cents_snapshot=cost,
            line_revenue_cents=revenue,
            line_cost_cents=cost_total,
            line_profit_cents=profit,
        )

        total_revenue += revenue
        total_cost += cost_total

        if product.track_stock:
            record_movement(
                product,
                StockMovementType.SALE,
                -quantity,
                related_sale=sale,
            )

    sale.total_revenue_cents = total_revenue
    sale.total_cost_cents = total_cost
    sale.total_profit_cents = total_revenue - total_cost
    sale.save(
        update_fields=[
            "total_revenue_cents",
            "total_cost_cents",
            "total_profit_cents",
        ]
    )
    return sale


@transaction.atomic
def void_sale(sale_id: int, reason: str | None = None) -> Sale:
    """
    Void a sale (spec §7.2). Never deletes it. Reverses stock for tracked
    products via ``sale_reversal`` movements. Idempotent: voiding an
    already-voided sale is a no-op (returns 200).
    """
    from apps.stock.services import record_movement

    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.status == SaleStatus.VOIDED:
        return sale  # idempotent no-op

    sale.status = SaleStatus.VOIDED
    sale.voided_at = timezone.now()
    sale.void_reason = reason or None
    sale.save(update_fields=["status", "voided_at", "void_reason"])

    for item in sale.items.select_related("product"):
        product = item.product
        if product.track_stock:
            locked = product.__class__.objects.select_for_update().get(pk=product.pk)
            record_movement(
                locked,
                StockMovementType.SALE_REVERSAL,
                Decimal(item.quantity),
                related_sale=sale,
            )

    return sale
