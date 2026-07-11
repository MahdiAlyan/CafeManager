from rest_framework import serializers

from .models import AppSettings


class AppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSettings
        fields = [
            "id",
            "shop_name",
            "currency_code",
            "currency_symbol",
            "currency_decimal_digits",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
