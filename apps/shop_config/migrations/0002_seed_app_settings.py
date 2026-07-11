"""Seed the singleton AppSettings row (spec §5.9, override 5)."""

from django.db import migrations


def seed_settings(apps, schema_editor):
    AppSettings = apps.get_model("shop_config", "AppSettings")
    AppSettings.objects.get_or_create(
        pk=1,
        defaults={
            "shop_name": "My Coffee Shop",
            "currency_code": "USD",
            "currency_symbol": "$",
            "currency_decimal_digits": 2,
        },
    )


def unseed_settings(apps, schema_editor):
    AppSettings = apps.get_model("shop_config", "AppSettings")
    AppSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shop_config", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_settings, unseed_settings),
    ]
