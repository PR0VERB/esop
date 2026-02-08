"""
URL patterns for the dividends app.
All URLs are scoped under /dividends/<company_pk>/...
"""

from django.urls import path

from . import views

app_name = "dividends"

urlpatterns = [
    path(
        "<uuid:company_pk>/",
        views.DividendRunListView.as_view(),
        name="list",
    ),
    path(
        "<uuid:company_pk>/create/",
        views.DividendRunCreateView.as_view(),
        name="create",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/",
        views.DividendRunDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/edit/",
        views.DividendRunUpdateView.as_view(),
        name="update",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/approve/",
        views.DividendRunApproveView.as_view(),
        name="approve",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/process/",
        views.DividendRunProcessView.as_view(),
        name="process",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/reset/",
        views.DividendRunResetView.as_view(),
        name="reset",
    ),
]

