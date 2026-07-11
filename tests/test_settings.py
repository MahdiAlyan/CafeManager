"""Settings singleton API + create_owner command (spec §4, §6.9)."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.shop_config.models import AppSettings

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_settings_get(auth_client):
    resp = auth_client.get("/api/settings/")
    assert resp.status_code == 200
    assert resp.data["shop_name"] == "My Coffee Shop"


def test_settings_patch(auth_client):
    resp = auth_client.patch(
        "/api/settings/",
        {"shop_name": "Radwan Cafe", "currency_code": "LBP"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["shop_name"] == "Radwan Cafe"
    AppSettings.load().refresh_from_db()
    assert AppSettings.load().shop_name == "Radwan Cafe"


def test_appsettings_is_singleton():
    a = AppSettings.load()
    a.shop_name = "One"
    a.save()
    b = AppSettings(shop_name="Two")
    b.save()
    assert b.pk == 1
    assert AppSettings.objects.count() == 1


def test_create_owner_command():
    out = StringIO()
    call_command("create_owner", username="boss", password="pw123456", stdout=out)
    assert User.objects.filter(username="boss").exists()
    assert "created" in out.getvalue()


def test_create_owner_refuses_second_owner():
    call_command("create_owner", username="boss", password="pw123456")
    with pytest.raises(CommandError):
        call_command("create_owner", username="other", password="pw123456")
