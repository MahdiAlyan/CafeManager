"""
Shared enums, mirroring the Flutter app. Used as ``choices`` on model
fields and for validation in services/serializers.
"""

from __future__ import annotations

from django.db import models


class ProductUnit(models.TextChoices):
    PIECE = "piece", "Piece"
    PACK = "pack", "Pack"
    BOX = "box", "Box"
    CARTON = "carton", "Carton"
    CUP = "cup", "Cup"
    KILOGRAM = "kilogram", "Kilogram"
    GRAM = "gram", "Gram"
    BOTTLE = "bottle", "Bottle"
    CAN = "can", "Can"
    OTHER = "other", "Other"


class SaleStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    VOIDED = "voided", "Voided"


class StockMovementType(models.TextChoices):
    OPENING = "opening", "Opening"
    PURCHASE = "purchase", "Purchase"
    SALE = "sale", "Sale"
    SALE_REVERSAL = "sale_reversal", "Sale reversal"
    MANUAL_INCREASE = "manual_increase", "Manual increase"
    MANUAL_DECREASE = "manual_decrease", "Manual decrease"
    DAMAGED = "damaged", "Damaged"
    EXPIRED = "expired", "Expired"
    PERSONAL_USE = "personal_use", "Personal use"


# Sign convention (spec §5.8). Positive types increase stock; the rest
# decrease it. ``quantity_change`` on a StockMovement is signed accordingly.
STOCK_INCREASE_TYPES = frozenset(
    {
        StockMovementType.OPENING,
        StockMovementType.PURCHASE,
        StockMovementType.SALE_REVERSAL,
        StockMovementType.MANUAL_INCREASE,
    }
)

# Types the manual ``/api/stock/{id}/adjust/`` endpoint accepts (spec §6.7,
# §7.5). opening/purchase/sale/sale_reversal are driven by their own flows.
MANUAL_ADJUSTMENT_TYPES = frozenset(
    {
        StockMovementType.MANUAL_INCREASE,
        StockMovementType.MANUAL_DECREASE,
        StockMovementType.DAMAGED,
        StockMovementType.EXPIRED,
        StockMovementType.PERSONAL_USE,
    }
)


def is_increase(movement_type: str) -> bool:
    """True if the given ``StockMovementType`` increases stock."""
    return movement_type in STOCK_INCREASE_TYPES


def signed_quantity(movement_type: str, magnitude):
    """
    Apply the sign convention for ``movement_type`` to a positive
    ``magnitude`` (a ``Decimal``), returning a signed quantity change.
    """
    return magnitude if is_increase(movement_type) else -magnitude
