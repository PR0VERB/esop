"""
URL configuration for ESOP Administration Platform.
"""

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import include, path


def health_check(request):
    """Unauthenticated health check for load balancers."""
    return JsonResponse({"status": "ok"})


@login_required
def demo_home(request):
    """Temporary demo navigator — nicely-formatted links to every demo URL."""
    return render(request, "demo/home.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("accounts/", include("apps.accounts.urls")),
    path("companies/", include("apps.tenants.urls")),
    path("beneficiaries/", include("apps.beneficiaries.urls")),
    path("documents/", include("apps.documents.urls")),
    path("dividends/", include("apps.dividends.urls")),
    path("month-end/", include("apps.month_end.urls")),
    # REST API (versioned)
    path("api/v1/", include("apps.api.urls")),
    # Temporary demo navigator
    path("temphomedemo", demo_home, name="demo-home"),
    # App URLs added in later commits:
    # path("integrations/", include("apps.integrations.urls")),
]
