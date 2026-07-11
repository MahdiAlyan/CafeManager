"""Seed default expense categories (spec §5.6)."""

from django.db import migrations

DEFAULT_EXPENSE_CATEGORIES = [
    "Electricity",
    "Rent",
    "Delivery",
    "Maintenance",
    "Broken items",
    "Expired items",
    "Free items",
    "Personal use",
    "Cleaning",
    "Equipment",
    "Other",
]


def seed_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")
    for name in DEFAULT_EXPENSE_CATEGORIES:
        ExpenseCategory.objects.get_or_create(
            name=name, defaults={"is_default": True}
        )


def unseed_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")
    ExpenseCategory.objects.filter(
        name__in=DEFAULT_EXPENSE_CATEGORIES, is_default=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("expenses", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
