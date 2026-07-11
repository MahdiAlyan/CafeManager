"""Catalog models: Category and Product (spec §5.1, §5.2)."""

from __future__ import annotations

from django.db import models

from common.enums import ProductUnit


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=120)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    selling_unit = models.CharField(max_length=20, choices=ProductUnit.choices)
    selling_price_cents = models.IntegerField(default=0)
    cost_per_unit_cents = models.IntegerField(default=0)
    barcode = models.CharField(max_length=64, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    # Never hard-delete a product referenced by sales — archive instead.
    is_active = models.BooleanField(default=True)
    track_stock = models.BooleanField(default=False)
    # Denormalized running total, kept in sync by the stock ledger (§5.8).
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    low_stock_threshold = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    default_purchase_unit = models.CharField(max_length=20, null=True, blank=True)
    default_units_per_purchase_unit = models.DecimalField(
        max_digits=12, decimal_places=3, default=1
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
