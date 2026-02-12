"""URL patterns for the tenants (company management) app."""

from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("", views.CompanyListView.as_view(), name="list"),
    path("create/", views.CompanyCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.CompanyDetailView.as_view(), name="detail"),
]
