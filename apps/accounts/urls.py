"""
Authentication URL patterns.
All auth endpoints live under /accounts/.
"""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("mfa/verify/", views.MFAVerifyView.as_view(), name="mfa-verify"),
]

