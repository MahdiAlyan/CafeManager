"""Settings endpoint — always operates on the singleton AppSettings (spec §6.9)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AppSettings
from .serializers import AppSettingsSerializer


class SettingsView(APIView):
    """``GET``/``PATCH`` ``/api/settings/`` — no id in the URL (pk=1 singleton)."""

    @extend_schema(responses=AppSettingsSerializer)
    def get(self, request):
        return Response(AppSettingsSerializer(AppSettings.load()).data)

    @extend_schema(request=AppSettingsSerializer, responses=AppSettingsSerializer)
    def patch(self, request):
        settings_obj = AppSettings.load()
        serializer = AppSettingsSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
