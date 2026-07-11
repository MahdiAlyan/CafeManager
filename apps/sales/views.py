"""Sales API (spec §6.4). Sales are immutable — no update/destroy."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.date_range import apply_date_range

from . import services
from .models import Sale
from .serializers import SaleCreateSerializer, SaleSerializer, VoidSerializer


class SaleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Sales are created and read but never edited or deleted (§5.3); the only
    post-creation transition is ``void`` (§7.2).
    """

    queryset = Sale.objects.prefetch_related("items").all()
    serializer_class = SaleSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Sale.objects.prefetch_related("items").all()
        qs = apply_date_range(qs, self.request, "created_at")
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str),
            OpenApiParameter("to", str),
            OpenApiParameter("status", str, enum=["completed", "voided"]),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=SaleCreateSerializer, responses=SaleSerializer)
    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = services.complete_sale(serializer.validated_data["items"])
        return Response(SaleSerializer(sale).data, status=201)

    @extend_schema(request=VoidSerializer, responses=SaleSerializer)
    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = services.void_sale(
            sale_id=self.get_object().pk,
            reason=serializer.validated_data.get("reason"),
        )
        return Response(SaleSerializer(sale).data)
