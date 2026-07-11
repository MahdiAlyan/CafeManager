"""AppSettings — a singleton row (pk=1) holding shop-wide configuration."""

from __future__ import annotations

from django.db import models


class AppSettings(models.Model):
    """
    Shop-wide settings. Enforced as a singleton at ``pk=1`` (spec §5.9):
    ``save`` always writes pk=1, and ``load`` returns (creating if needed)
    that single row.
    """

    id = models.IntegerField(primary_key=True, default=1, editable=False)
    shop_name = models.CharField(max_length=120, default="My Coffee Shop")
    currency_code = models.CharField(max_length=3, default="USD")
    currency_symbol = models.CharField(max_length=8, default="$")
    currency_decimal_digits = models.IntegerField(default=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "app settings"
        verbose_name_plural = "app settings"

    def __str__(self) -> str:
        return self.shop_name

    def save(self, *args, **kwargs):
        # Always the singleton row. If it already exists, coerce this write
        # into an UPDATE so constructing a fresh instance never collides.
        self.pk = 1
        if type(self).objects.filter(pk=1).exists():
            self._state.adding = False
            kwargs.pop("force_insert", None)
            kwargs["force_update"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - singleton guard
        # The singleton is never deleted.
        pass

    @classmethod
    def load(cls) -> "AppSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
