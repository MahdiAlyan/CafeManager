"""Purchase model (spec §5.5)."""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class Purchase(models.Model):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="purchases"
    )
    purchase_date = models.DateTimeField(default=timezone.now)
    quantity_purchased = models.DecimalField(max_digits=12, decimal_places=3)
    purchase_unit = models.CharField(max_length=20)
    units_per_purchase_unit = models.DecimalField(
        max_digits=12, decimal_places=3, default=1
    )
    total_cost_cents = models.IntegerField()
    calculated_unit_cost_cents = models.IntegerField()
    supplier = models.CharField(max_length=120, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    product_cost_updated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self) -> str:
        return f"Purchase #{self.pk} of {self.product_id}"
