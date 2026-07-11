"""Expense serializers (spec §5.6, §5.7, §6.6)."""

from __future__ import annotations

from rest_framework import serializers

from .models import Expense, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_default", "created_at"]
        read_only_fields = ["id", "is_default", "created_at"]


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "id",
            "title",
            "category",
            "amount_cents",
            "occurred_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_amount_cents(self, value):
        if value < 0:
            raise serializers.ValidationError("Must be >= 0.")
        return value
