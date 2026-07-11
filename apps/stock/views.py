"""
Stock API (spec §6.7). Routed so the final URLs are exactly:

* ``GET  /api/stock/``                         — tracked products
* ``GET  /api/stock/{product_id}/movements/``  — a product's ledger
* ``POST /api/stock/{product_id}/adjust/``     — manual adjustment
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.models import Product

from . import services
from .models import StockMovement
from .serializers import (
    StockAdjustSerializer,
    StockMovementSerializer,
    StockProductSerializer,
)


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """Products with ``track_stock=True``; ``{pk}`` is the product id."""

    queryset = Product.objects.filter(track_stock=True)
    serializer_class = StockProductSerializer
    http_method_names = ["get", "post", "head", "options"]

    @extend_schema(responses=StockMovementSerializer(many=True))
    @action(detail=True, methods=["get"])
    def movements(self, request, pk=None):
        product = self.get_object()
        qs = StockMovement.objects.filter(product=product)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(StockMovementSerializer(qs, many=True).data)

    @extend_schema(request=StockAdjustSerializer, responses=StockMovementSerializer)
    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        product = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = services.adjust_stock(
            product_id=product.pk,
            movement_type=serializer.validated_data["type"],
            magnitude=serializer.validated_data["quantity"],
            note=serializer.validated_data.get("note"),
        )
        return Response(StockMovementSerializer(movement).data)
