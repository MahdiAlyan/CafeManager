"""Report URLs (spec §6.8)."""

from django.urls import path

from . import views

urlpatterns = [
    path("reports/summary/", views.summary, name="reports-summary"),
    path("reports/products/", views.products, name="reports-products"),
    path("reports/categories/", views.categories, name="reports-categories"),
    path("reports/expenses/", views.expenses, name="reports-expenses"),
    path(
        "reports/export/sales.csv",
        views.export_sales_csv,
        name="reports-export-sales",
    ),
    path(
        "reports/export/purchases.csv",
        views.export_purchases_csv,
        name="reports-export-purchases",
    ),
    path(
        "reports/export/expenses.csv",
        views.export_expenses_csv,
        name="reports-export-expenses",
    ),
]
