"""URL patterns for month-end runs, scoped by company."""

from django.urls import path

from . import views

app_name = "month_end"

urlpatterns = [
    # Company-scoped month-end run URLs
    path(
        "<uuid:company_pk>/",
        views.MonthEndRunListView.as_view(),
        name="list",
    ),
    path(
        "<uuid:company_pk>/create/",
        views.MonthEndRunCreateView.as_view(),
        name="create",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/",
        views.MonthEndRunDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/edit/",
        views.MonthEndRunUpdateView.as_view(),
        name="update",
    ),
    # State change endpoints (POST-only)
    path(
        "<uuid:company_pk>/<uuid:pk>/approve/",
        views.MonthEndRunApproveView.as_view(),
        name="approve",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/process/",
        views.MonthEndRunProcessView.as_view(),
        name="process",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/reset/",
        views.MonthEndRunResetView.as_view(),
        name="reset",
    ),
]

