"""Seed default product categories (spec §5.1)."""

from django.db import migrations

DEFAULT_CATEGORIES = [
    "Beverages",
    "Snacks",
    "Coffee",
    "Tobacco",
    "Cakes",
    "Other",
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    for name in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={"is_default": True})


def unseed_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Category.objects.filter(name__in=DEFAULT_CATEGORIES, is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
