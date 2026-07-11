"""Catalog API: Category and Product ViewSets (spec §6.2, §6.3)."""

from __future__ import annotations

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    EnableStockTrackingSerializer,
    ProductSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    """CRUD for categories. DELETE is 400 if any product references it."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


class ProductViewSet(viewsets.ModelViewSet):
    """
    Products. No ``destroy`` — products referenced by historical sales must
    never be hard-deleted (spec §6.3); use ``archive``/``restore`` instead.
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Product.objects.all()
        # Filters apply to the list only — detail routes (retrieve, archive,
        # restore, enable-stock-tracking) must resolve archived products too.
        if self.action != "list":
            return qs
        params = self.request.query_params

        category = params.get("category")
        if category:
            qs = qs.filter(category_id=category)

        search = params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(barcode__icontains=search))

        include_inactive = params.get("include_inactive", "false").lower() == "true"
        if not include_inactive:
            qs = qs.filter(is_active=True)

        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("category", int),
            OpenApiParameter("search", str),
            OpenApiParameter("include_inactive", bool),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=None, responses=ProductSerializer)
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        product = services.archive_product(self.get_object())
        return Response(ProductSerializer(product).data)

    @extend_schema(request=None, responses=ProductSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        product = services.restore_product(self.get_object())
        return Response(ProductSerializer(product).data)

    @extend_schema(
        request=EnableStockTrackingSerializer, responses=ProductSerializer
    )
    @action(detail=True, methods=["post"], url_path="enable-stock-tracking")
    def enable_stock_tracking(self, request, pk=None):
        serializer = EnableStockTrackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.enable_stock_tracking(
            product_id=self.get_object().pk,
            opening_quantity=serializer.validated_data["opening_quantity"],
            low_stock_threshold=serializer.validated_data.get("low_stock_threshold"),
        )
        return Response(
            ProductSerializer(product).data, status=status.HTTP_200_OK
        )
