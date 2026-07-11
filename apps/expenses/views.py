"""Expenses API (spec §6.6)."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets

from common.date_range import apply_date_range

from .models import Expense, ExpenseCategory
from .serializers import ExpenseCategorySerializer, ExpenseSerializer


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """Expense categories. DELETE is 400 if any expense references it (§8)."""

    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


class ExpenseViewSet(viewsets.ModelViewSet):
    """Full CRUD — expenses CAN be deleted, unlike sales (§6.6)."""

    queryset = Expense.objects.select_related("category").all()
    serializer_class = ExpenseSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Expense.objects.select_related("category").all()
        qs = apply_date_range(qs, self.request, "occurred_at")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str),
            OpenApiParameter("to", str),
            OpenApiParameter("category", int),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
