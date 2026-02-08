"""
Default-deny permission mixins for views.
All views MUST use one of these mixins.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class SchemeAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow scheme admin users."""

    def test_func(self):
        return self.request.user.is_scheme_admin


class BeneficiaryRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow beneficiary users."""

    def test_func(self):
        return self.request.user.is_beneficiary


class TenantAccessMixin(LoginRequiredMixin):
    """
    Ensure the user can access the requested tenant's data.
    Views using this mixin must implement get_company().
    """

    def get_company(self):
        raise NotImplementedError("Subclasses must implement get_company()")

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        company = self.get_company()
        if company and not request.user.can_access_company(company):
            raise PermissionDenied("You do not have access to this company's data.")
        return response


class ObjectOwnerMixin:
    """
    For beneficiary views: ensure they can only see their own objects.
    The queryset must be filtered to the user's records.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_beneficiary:
            # Beneficiaries only see their own records
            # Subclass must define the filter field
            filter_field = getattr(self, "owner_filter_field", "user")
            qs = qs.filter(**{filter_field: user})
        elif user.is_scheme_admin and hasattr(user, "company") and user.company:
            # If admin is scoped to a company, filter by it
            qs = qs.filter(company=user.company)
        return qs

