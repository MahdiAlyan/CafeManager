"""StockMovement model — the append-only stock ledger (spec §5.8)."""

from __future__ import annotations

from django.db import models

from common.enums import StockMovementType


class StockMovement(models.Model):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="stock_movements"
    )
    type = models.CharField(max_length=20, choices=StockMovementType.choices)
    # Signed: positive = increase (§5.8 sign convention).
    quantity_change = models.DecimalField(max_digits=12, decimal_places=3)
    # Product's stock immediately after this movement.
    resulting_stock = models.DecimalField(max_digits=12, decimal_places=3)
    related_sale = models.ForeignKey(
        "sales.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    related_purchase = models.ForeignKey(
        "purchases.Purchase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.type} {self.quantity_change} (product {self.product_id})"
