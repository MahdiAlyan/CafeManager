from django.contrib import admin

from .models import AppSettings


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ["id", "shop_name", "currency_code", "currency_symbol"]

    def has_add_permission(self, request):
        # Singleton — never add a second row.
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
