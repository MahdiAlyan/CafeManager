from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "is_default", "created_at"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "category",
        "selling_price_cents",
        "cost_per_unit_cents",
        "is_active",
        "track_stock",
        "current_stock",
    ]
    list_filter = ["is_active", "track_stock", "category"]
    search_fields = ["name", "barcode"]
