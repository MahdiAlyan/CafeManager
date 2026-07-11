"""
Stock ledger services (spec §5.8, §7.5).

``record_movement`` is the single choke point for every stock change: it
updates the denormalized ``Product.current_stock`` and writes one
``StockMovement`` row in the same call. Callers MUST already be inside a
``transaction.atomic()`` block and should hold a row lock on the product
(``select_for_update``) so ``current_stock`` stays consistent under
concurrency.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from common.enums import (
    MANUAL_ADJUSTMENT_TYPES,
    StockMovementType,
    signed_quantity,
)

from .models import StockMovement


def record_movement(
    product,
    movement_type: str,
    quantity_change: Decimal,
    *,
    note: str | None = None,
    related_sale=None,
    related_purchase=None,
) -> StockMovement:
    """
    Apply a **signed** ``quantity_change`` to ``product.current_stock`` and
    append a ledger row. Returns the created ``StockMovement``.
    """
    new_stock = product.current_stock + quantity_change
    product.current_stock = new_stock
    product.save(update_fields=["current_stock", "updated_at"])
    return StockMovement.objects.create(
        product=product,
        type=movement_type,
        quantity_change=quantity_change,
        resulting_stock=new_stock,
        related_sale=related_sale,
        related_purchase=related_purchase,
        note=note,
    )


@transaction.atomic
def adjust_stock(
    product_id: int,
    movement_type: str,
    magnitude: Decimal,
    note: str | None = None,
) -> StockMovement:
    """
    Manual stock adjustment (spec §7.5). ``magnitude`` is always a positive
    quantity; the sign is derived from ``movement_type`` per §5.8.
    """
    from apps.catalog.models import Product

    if movement_type not in MANUAL_ADJUSTMENT_TYPES:
        raise ValidationError(
            {
                "type": (
                    "Must be one of: "
                    + ", ".join(sorted(MANUAL_ADJUSTMENT_TYPES))
                    + "."
                )
            }
        )
    if magnitude is None or magnitude <= 0:
        raise ValidationError({"quantity": "Must be a positive magnitude."})

    product = Product.objects.select_for_update().get(pk=product_id)
    if not product.track_stock:
        raise ValidationError(
            {"product": "This product does not have stock tracking enabled."}
        )

    change = signed_quantity(movement_type, Decimal(magnitude))
    return record_movement(product, movement_type, change, note=note)


# Re-exported for callers that build movements of a specific type.
__all__ = ["record_movement", "adjust_stock", "StockMovementType"]
