"""Auth serializers (spec §4, §6.1)."""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.authtoken.serializers import AuthTokenSerializer


class LoginSerializer(AuthTokenSerializer):
    """Username/password login. Reuses DRF's credential validation."""


class LoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    shop_name = serializers.CharField()
