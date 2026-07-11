"""Auth flow + enforcement (spec §4, §6.1)."""

import pytest
from rest_framework.authtoken.models import Token

pytestmark = pytest.mark.django_db


def test_login_returns_token_and_shop_name(api_client, owner):
    resp = api_client.post(
        "/api/auth/login/",
        {"username": "owner", "password": "pw-secret-123"},
        format="json",
    )
    assert resp.status_code == 200
    assert "token" in resp.data
    assert resp.data["shop_name"] == "My Coffee Shop"


def test_login_bad_credentials(api_client, owner):
    resp = api_client.post(
        "/api/auth/login/",
        {"username": "owner", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 400


def test_logout_deletes_token(auth_client, owner):
    assert Token.objects.filter(user=owner).exists()
    resp = auth_client.post("/api/auth/logout/")
    assert resp.status_code == 204
    assert not Token.objects.filter(user=owner).exists()


def test_endpoints_require_authentication(api_client):
    # No token -> 401 on a protected endpoint.
    assert api_client.get("/api/products/").status_code == 401
    assert api_client.get("/api/reports/summary/").status_code == 401
    assert api_client.get("/api/settings/").status_code == 401


def test_authenticated_access_ok(auth_client):
    assert auth_client.get("/api/products/").status_code == 200
