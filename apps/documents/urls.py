"""
URL patterns for the documents app.
All routes scoped under <uuid:company_pk>/.
"""

from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path(
        "<uuid:company_pk>/",
        views.DocumentListView.as_view(),
        name="list",
    ),
    path(
        "<uuid:company_pk>/upload/",
        views.DocumentUploadView.as_view(),
        name="upload",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/",
        views.DocumentDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/download/",
        views.DocumentDownloadView.as_view(),
        name="download",
    ),
    path(
        "<uuid:company_pk>/<uuid:pk>/status/",
        views.DocumentStatusUpdateView.as_view(),
        name="status-update",
    ),
]

