from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    can_delete = False
    readonly_fields = [f.name for f in SaleItem._meta.fields]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "created_at",
        "status",
        "total_revenue_cents",
        "total_profit_cents",
    ]
    list_filter = ["status"]
    inlines = [SaleItemInline]
