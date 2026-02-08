"""
URL patterns for the beneficiaries app.
All URLs are scoped under /beneficiaries/<company_pk>/...
"""

from django.urls import path

from . import views

app_name = "beneficiaries"

urlpatterns = [
    path(
        "<uuid:company_pk>/",
        views.BeneficiaryListView.as_view(),
        name="list",
    ),
    path(
        "<uuid:company_pk>/create/",
        views.BeneficiaryCreateView.as_view(),
        name="create",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/",
        views.BeneficiaryDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/edit/",
        views.BeneficiaryUpdateView.as_view(),
        name="update",
    ),
]

