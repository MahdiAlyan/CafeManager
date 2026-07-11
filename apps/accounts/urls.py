"""Auth URLs (spec §6.1)."""

from django.urls import path

from .views import LoginView, LogoutView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
]
