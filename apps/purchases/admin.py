from django.contrib import admin

from .models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "product",
        "purchase_date",
        "quantity_purchased",
        "total_cost_cents",
        "calculated_unit_cost_cents",
        "product_cost_updated",
    ]
    list_filter = ["product_cost_updated"]
    search_fields = ["supplier"]
