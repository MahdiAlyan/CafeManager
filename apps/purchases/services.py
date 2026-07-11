"""Purchase business logic (spec §6.5, §7.3)."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from common.enums import StockMovementType
from common.money import calculate_purchase_unit_cost_cents

from .models import Purchase


@transaction.atomic
def record_purchase(
    *,
    product_id: int,
    quantity_purchased: Decimal,
    purchase_unit: str,
    units_per_purchase_unit: Decimal,
    total_cost_cents: int,
    supplier: str | None = None,
    notes: str | None = None,
    update_product_cost: bool = False,
    purchase_date=None,
) -> Purchase:
    """
    Record a purchase, all inside one transaction (spec §6.5):

    * compute ``calculated_unit_cost_cents`` (§7.3);
    * optionally update the product's ``cost_per_unit_cents``;
    * if the product tracks stock, increment ``current_stock`` by the total
      base units purchased and write a ``purchase`` StockMovement.
    """
    from apps.catalog.models import Product
    from apps.stock.services import record_movement

    if quantity_purchased is None or quantity_purchased <= 0:
        raise ValidationError({"quantity_purchased": "Must be > 0."})
    if units_per_purchase_unit is None or units_per_purchase_unit <= 0:
        raise ValidationError({"units_per_purchase_unit": "Must be > 0."})
    if total_cost_cents < 0:
        raise ValidationError({"total_cost_cents": "Must be >= 0."})

    product = Product.objects.select_for_update().get(pk=product_id)

    unit_cost = calculate_purchase_unit_cost_cents(
        total_cost_cents, quantity_purchased, units_per_purchase_unit
    )

    purchase_kwargs = {
        "product": product,
        "quantity_purchased": quantity_purchased,
        "purchase_unit": purchase_unit,
        "units_per_purchase_unit": units_per_purchase_unit,
        "total_cost_cents": total_cost_cents,
        "calculated_unit_cost_cents": unit_cost,
        "supplier": supplier or None,
        "notes": notes or None,
        "product_cost_updated": update_product_cost,
    }
    if purchase_date is not None:
        purchase_kwargs["purchase_date"] = purchase_date

    purchase = Purchase.objects.create(**purchase_kwargs)

    if update_product_cost:
        product.cost_per_unit_cents = unit_cost
        product.save(update_fields=["cost_per_unit_cents", "updated_at"])

    if product.track_stock:
        base_units_added = Decimal(quantity_purchased) * Decimal(
            units_per_purchase_unit
        )
        record_movement(
            product,
            StockMovementType.PURCHASE,
            base_units_added,
            related_purchase=purchase,
        )

    return purchase
