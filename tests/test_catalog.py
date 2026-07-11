"""Catalog API (spec §6.2, §6.3, §8)."""

import pytest

from apps.catalog.models import Product

pytestmark = pytest.mark.django_db


def test_create_product(auth_client, category):
    resp = auth_client.post(
        "/api/products/",
        {
            "name": "Latte",
            "category": category.id,
            "selling_unit": "cup",
            "selling_price_cents": 300,
            "cost_per_unit_cents": 120,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["track_stock"] is False
    assert resp.data["current_stock"] == "0.000"


def test_negative_price_rejected(auth_client, category):
    resp = auth_client.post(
        "/api/products/",
        {
            "name": "Bad",
            "category": category.id,
            "selling_unit": "cup",
            "selling_price_cents": -1,
        },
        format="json",
    )
    assert resp.status_code == 400


def test_no_delete_endpoint(auth_client, product):
    assert auth_client.delete(f"/api/products/{product.id}/").status_code == 405


def test_archive_and_restore(auth_client, product):
    resp = auth_client.post(f"/api/products/{product.id}/archive/")
    assert resp.status_code == 200
    assert resp.data["is_active"] is False

    resp = auth_client.post(f"/api/products/{product.id}/restore/")
    assert resp.status_code == 200
    assert resp.data["is_active"] is True


def test_list_excludes_inactive_by_default(auth_client, product):
    Product.objects.filter(id=product.id).update(is_active=False)
    resp = auth_client.get("/api/products/")
    ids = [p["id"] for p in resp.data["results"]]
    assert product.id not in ids

    resp = auth_client.get("/api/products/?include_inactive=true")
    ids = [p["id"] for p in resp.data["results"]]
    assert product.id in ids


def test_search_and_category_filter(auth_client, category, make_product):
    a = make_product(name="Cappuccino")
    make_product(name="Water")
    resp = auth_client.get("/api/products/?search=capp")
    ids = [p["id"] for p in resp.data["results"]]
    assert a.id in ids and len(ids) == 1


def test_enable_stock_tracking(auth_client, product):
    resp = auth_client.post(
        f"/api/products/{product.id}/enable-stock-tracking/",
        {"opening_quantity": "10", "low_stock_threshold": "5"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["track_stock"] is True
    assert resp.data["current_stock"] == "10.000"


def test_delete_category_in_use_returns_400(auth_client, product):
    # product references its category (PROTECT) -> clean 400, not a 500.
    resp = auth_client.delete(f"/api/categories/{product.category_id}/")
    assert resp.status_code == 400


def test_delete_unused_category_ok(auth_client, category):
    resp = auth_client.delete(f"/api/categories/{category.id}/")
    assert resp.status_code == 204
