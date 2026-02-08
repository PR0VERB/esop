"""
URL configuration for ESOP Administration Platform.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    """Unauthenticated health check for load balancers."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("accounts/", include("apps.accounts.urls")),
    path("beneficiaries/", include("apps.beneficiaries.urls")),
    path("documents/", include("apps.documents.urls")),
    path("dividends/", include("apps.dividends.urls")),
    path("month-end/", include("apps.month_end.urls")),
    # REST API (versioned)
    path("api/v1/", include("apps.api.urls")),
    # App URLs added in later commits:
    # path("integrations/", include("apps.integrations.urls")),
]
