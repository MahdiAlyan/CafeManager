"""Catalog business logic (spec §6.3, §7): archive, restore, enable stock tracking."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from common.enums import StockMovementType

from .models import Product


def archive_product(product: Product) -> Product:
    """Soft-delete: set ``is_active=False`` (spec §6.3)."""
    if product.is_active:
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
    return product


def restore_product(product: Product) -> Product:
    """Un-archive: set ``is_active=True`` (spec §6.3)."""
    if not product.is_active:
        product.is_active = True
        product.save(update_fields=["is_active", "updated_at"])
    return product


@transaction.atomic
def enable_stock_tracking(
    product_id: int,
    opening_quantity: Decimal,
    low_stock_threshold: Decimal | None = None,
) -> Product:
    """
    Turn on stock tracking for a product, recording an ``opening``
    StockMovement for the starting balance (spec §6.3, §5.8).

    ``opening_quantity`` may be 0 (a brand-new tracked product can start
    empty — spec §8).
    """
    from apps.stock.services import record_movement

    if opening_quantity is None or opening_quantity < 0:
        raise ValidationError(
            {"opening_quantity": "Must be >= 0."}
        )

    product = Product.objects.select_for_update().get(pk=product_id)
    if product.track_stock:
        raise ValidationError(
            {"product": "Stock tracking is already enabled for this product."}
        )

    product.track_stock = True
    product.low_stock_threshold = low_stock_threshold
    product.current_stock = Decimal("0")
    product.save(
        update_fields=[
            "track_stock",
            "low_stock_threshold",
            "current_stock",
            "updated_at",
        ]
    )
    record_movement(
        product,
        StockMovementType.OPENING,
        Decimal(opening_quantity),
        note="Opening stock",
    )
    return product
