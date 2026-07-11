"""Purchase serializers (spec §5.5, §6.5)."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .models import Purchase


class PurchaseSerializer(serializers.ModelSerializer):
    """Read representation of a recorded purchase."""

    class Meta:
        model = Purchase
        fields = [
            "id",
            "product",
            "purchase_date",
            "quantity_purchased",
            "purchase_unit",
            "units_per_purchase_unit",
            "total_cost_cents",
            "calculated_unit_cost_cents",
            "supplier",
            "notes",
            "product_cost_updated",
            "created_at",
        ]
        read_only_fields = fields


class PurchaseCreateSerializer(serializers.Serializer):
    """Body for ``POST /api/purchases/`` (spec §6.5)."""

    product_id = serializers.IntegerField()
    quantity_purchased = serializers.DecimalField(max_digits=12, decimal_places=3)
    purchase_unit = serializers.CharField(max_length=20)
    units_per_purchase_unit = serializers.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal("1")
    )
    total_cost_cents = serializers.IntegerField(min_value=0)
    purchase_date = serializers.DateTimeField(required=False)
    supplier = serializers.CharField(
        max_length=120, required=False, allow_blank=True, allow_null=True
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    update_product_cost = serializers.BooleanField(default=False)

    def validate_quantity_purchased(self, value):
        if value <= 0:
            raise serializers.ValidationError("Must be > 0.")
        return value

    def validate_units_per_purchase_unit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Must be > 0.")
        return value
