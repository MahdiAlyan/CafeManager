"""Sale and SaleItem models (spec §5.3, §5.4)."""

from __future__ import annotations

from django.db import models

from common.enums import SaleStatus


class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    total_revenue_cents = models.IntegerField(default=0)
    total_cost_cents = models.IntegerField(default=0)
    total_profit_cents = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=SaleStatus.choices, default=SaleStatus.COMPLETED
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"Sale #{self.pk} ({self.status})"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="sale_items"
    )
    # Immutable snapshots captured at sale time — never recomputed (§5.4).
    product_name_snapshot = models.CharField(max_length=120)
    unit_snapshot = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    selling_price_cents_snapshot = models.IntegerField()
    cost_per_unit_cents_snapshot = models.IntegerField()
    line_revenue_cents = models.IntegerField()
    line_cost_cents = models.IntegerField()
    line_profit_cents = models.IntegerField()

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product_name_snapshot} x{self.quantity}"
