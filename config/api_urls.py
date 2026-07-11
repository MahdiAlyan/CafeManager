"""
Root API router. Every path here is mounted under ``/api/`` (see
``config/urls.py``) and the resulting URL surface must match spec §6
exactly.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import CategoryViewSet, ProductViewSet
from apps.expenses.views import ExpenseCategoryViewSet, ExpenseViewSet
from apps.purchases.views import PurchaseViewSet
from apps.sales.views import SaleViewSet
from apps.stock.views import StockViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("sales", SaleViewSet, basename="sale")
router.register("purchases", PurchaseViewSet, basename="purchase")
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("stock", StockViewSet, basename="stock")

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.shop_config.urls")),
    path("", include("apps.reports.urls")),
    path("", include(router.urls)),
]
