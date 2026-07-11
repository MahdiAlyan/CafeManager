"""Stock serializers (spec §6.7)."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product

from .models import StockMovement


class StockProductSerializer(serializers.ModelSerializer):
    """A tracked product with its current stock state (``GET /api/stock/``)."""

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "selling_unit",
            "current_stock",
            "low_stock_threshold",
            "track_stock",
        ]
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "type",
            "quantity_change",
            "resulting_stock",
            "related_sale",
            "related_purchase",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class StockAdjustSerializer(serializers.Serializer):
    """Body for ``POST /api/stock/{product_id}/adjust/`` (spec §6.7)."""

    type = serializers.CharField()
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
