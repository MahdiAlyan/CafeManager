"""Sale serializers (spec §5.3, §5.4, §6.4)."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .models import Sale, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_name_snapshot",
            "unit_snapshot",
            "quantity",
            "selling_price_cents_snapshot",
            "cost_per_unit_cents_snapshot",
            "line_revenue_cents",
            "line_cost_cents",
            "line_profit_cents",
        ]
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "created_at",
            "total_revenue_cents",
            "total_cost_cents",
            "total_profit_cents",
            "status",
            "voided_at",
            "void_reason",
            "items",
        ]
        read_only_fields = fields


class SaleLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )


class SaleCreateSerializer(serializers.Serializer):
    """Body for ``POST /api/sales/`` — server computes all prices (spec §7.1)."""

    items = SaleLineInputSerializer(many=True, allow_empty=False)


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
