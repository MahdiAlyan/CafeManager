"""Expenses API (spec §6.6, §8)."""

import pytest

from apps.expenses.models import Expense

pytestmark = pytest.mark.django_db


def test_create_and_delete_expense(auth_client, expense_category):
    resp = auth_client.post(
        "/api/expenses/",
        {
            "title": "Electricity bill",
            "category": expense_category.id,
            "amount_cents": 5000,
        },
        format="json",
    )
    assert resp.status_code == 201
    expense_id = resp.data["id"]

    # Expenses CAN be deleted (unlike sales).
    resp = auth_client.delete(f"/api/expenses/{expense_id}/")
    assert resp.status_code == 204
    assert not Expense.objects.filter(id=expense_id).exists()


def test_negative_amount_rejected(auth_client, expense_category):
    resp = auth_client.post(
        "/api/expenses/",
        {"title": "x", "category": expense_category.id, "amount_cents": -1},
        format="json",
    )
    assert resp.status_code == 400


def test_expense_category_list_and_create(auth_client):
    resp = auth_client.post(
        "/api/expense-categories/", {"name": "Gas"}, format="json"
    )
    assert resp.status_code == 201
    resp = auth_client.get("/api/expense-categories/")
    assert resp.status_code == 200


def test_delete_expense_category_in_use_400(auth_client, expense_category):
    Expense.objects.create(
        title="x", category=expense_category, amount_cents=100
    )
    resp = auth_client.delete(f"/api/expense-categories/{expense_category.id}/")
    assert resp.status_code == 400
