"""Catalog serializers (spec §5.1, §5.2, §6.2, §6.3)."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from common.enums import ProductUnit

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "is_default", "created_at"]
        read_only_fields = ["id", "is_default", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "category",
            "selling_unit",
            "selling_price_cents",
            "cost_per_unit_cents",
            "barcode",
            "notes",
            "is_active",
            "track_stock",
            "current_stock",
            "low_stock_threshold",
            "default_purchase_unit",
            "default_units_per_purchase_unit",
            "created_at",
            "updated_at",
        ]
        # Stock state is owned by the ledger / dedicated actions, not by
        # arbitrary product writes (spec §5.2, §6.3).
        read_only_fields = [
            "id",
            "track_stock",
            "current_stock",
            "created_at",
            "updated_at",
        ]

    def validate_selling_price_cents(self, value):
        if value < 0:
            raise serializers.ValidationError("Must be >= 0.")
        return value

    def validate_cost_per_unit_cents(self, value):
        if value < 0:
            raise serializers.ValidationError("Must be >= 0.")
        return value


class EnableStockTrackingSerializer(serializers.Serializer):
    """Body for ``POST /api/products/{id}/enable-stock-tracking/`` (spec §6.3)."""

    opening_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0")
    )
    low_stock_threshold = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
    )
