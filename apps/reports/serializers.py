"""Report serializers (spec §6.8, §7.4)."""

from __future__ import annotations

from rest_framework import serializers


class ReportSummarySerializer(serializers.Serializer):
    revenue_cents = serializers.IntegerField()
    cost_of_goods_sold_cents = serializers.IntegerField()
    # Money recovered from inventory — equals COGS, NOT profit (§7.4).
    capital_returned_cents = serializers.IntegerField()
    gross_profit_cents = serializers.IntegerField()
    expenses_cents = serializers.IntegerField()
    # "Potentially available profit" — does NOT imply cash on hand, since
    # money may already be spent or reinvested (spec §7.4).
    net_profit_cents = serializers.IntegerField(
        help_text=(
            "Potentially available profit (gross_profit - expenses). Does not "
            "imply cash on hand; money may already be spent or reinvested."
        )
    )
    sale_count = serializers.IntegerField()
    quantity_sold = serializers.DecimalField(max_digits=16, decimal_places=3)
    average_sale_value_cents = serializers.IntegerField()
    gross_profit_margin_percent = serializers.FloatField()


class ProductStatSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity_sold = serializers.DecimalField(max_digits=16, decimal_places=3)
    revenue_cents = serializers.IntegerField()
    cost_cents = serializers.IntegerField()
    profit_cents = serializers.IntegerField()


class CategoryStatSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity_sold = serializers.DecimalField(max_digits=16, decimal_places=3)
    revenue_cents = serializers.IntegerField()
    cost_cents = serializers.IntegerField()
    profit_cents = serializers.IntegerField()


class ExpenseStatSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    name = serializers.CharField()
    total_cents = serializers.IntegerField()
    expense_count = serializers.IntegerField()
