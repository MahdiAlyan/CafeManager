from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "product",
        "type",
        "quantity_change",
        "resulting_stock",
        "created_at",
    ]
    list_filter = ["type"]
