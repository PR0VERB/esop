"""
API URL routing with versioned endpoints.

All API endpoints are prefixed with /api/v1/.
Uses Django REST Framework's DefaultRouter for automatic URL generation.
"""

from django.urls import include, path
from rest_framework.authtoken import views as authtoken_views
from rest_framework.routers import DefaultRouter

from . import views

app_name = "api"

# Create router and register viewsets
router = DefaultRouter()
router.register(r"beneficiaries", views.BeneficiaryViewSet, basename="beneficiary")
router.register(r"dividend-runs", views.DividendRunViewSet, basename="dividend-run")
router.register(r"dividend-allocations", views.DividendAllocationViewSet, basename="dividend-allocation")
router.register(r"month-end-runs", views.MonthEndRunViewSet, basename="month-end-run")
router.register(r"vesting-events", views.VestingEventViewSet, basename="vesting-event")
router.register(r"tax-directives", views.TaxDirectiveViewSet, basename="tax-directive")
router.register(r"jse-companies", views.JSECompanySearchViewSet, basename="jse-company")

urlpatterns = [
    # Token authentication endpoint
    path("auth/token/", authtoken_views.obtain_auth_token, name="api-token-auth"),
    
    # API endpoints from router
    path("", include(router.urls)),
]

