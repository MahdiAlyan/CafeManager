"""Shared pytest fixtures."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product
from apps.expenses.models import ExpenseCategory
from common.enums import ProductUnit

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", password="pw-secret-123")


@pytest.fixture
def api_client():
    """Unauthenticated client."""
    return APIClient()


@pytest.fixture
def auth_client(owner):
    """Client carrying the owner's token."""
    token, _ = Token.objects.get_or_create(user=owner)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def category(db):
    return Category.objects.create(name="Test Beverages")


@pytest.fixture
def expense_category(db):
    return ExpenseCategory.objects.create(name="Test Rent")


@pytest.fixture
def product(category):
    """A simple non-tracked product: sells for 250c, costs 100c."""
    return Product.objects.create(
        name="Espresso",
        category=category,
        selling_unit=ProductUnit.CUP,
        selling_price_cents=250,
        cost_per_unit_cents=100,
    )


@pytest.fixture
def make_product(category):
    def _make(**kwargs):
        defaults = dict(
            name="Widget",
            category=category,
            selling_unit=ProductUnit.PIECE,
            selling_price_cents=100,
            cost_per_unit_cents=60,
        )
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    return _make


@pytest.fixture
def tracked_product(category):
    """A stock-tracked product starting with 100 units."""
    from apps.catalog.services import enable_stock_tracking

    p = Product.objects.create(
        name="Cola Can",
        category=category,
        selling_unit=ProductUnit.CAN,
        selling_price_cents=150,
        cost_per_unit_cents=50,
    )
    enable_stock_tracking(p.pk, Decimal("100"), Decimal("10"))
    p.refresh_from_db()
    return p
