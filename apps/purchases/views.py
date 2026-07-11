"""Purchases API (spec §6.5)."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from common.date_range import apply_date_range

from . import services
from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer


class PurchaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """List/retrieve purchases and record new ones (server computes unit cost)."""

    queryset = Purchase.objects.select_related("product").all()
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        qs = Purchase.objects.select_related("product").all()
        qs = apply_date_range(qs, self.request, "purchase_date")
        product = self.request.query_params.get("product")
        if product:
            qs = qs.filter(product_id=product)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str),
            OpenApiParameter("to", str),
            OpenApiParameter("product", int),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=PurchaseCreateSerializer, responses=PurchaseSerializer)
    def create(self, request, *args, **kwargs):
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = services.record_purchase(**serializer.validated_data)
        return Response(PurchaseSerializer(purchase).data, status=201)
