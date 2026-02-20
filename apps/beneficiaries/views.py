"""
Beneficiary CRUD views with tenant isolation and role-based permissions.

Security notes:
- All list/detail views scoped to the user's company via get_queryset().
- Create/update restricted to Scheme Admins.
- Company is set server-side on create (never from client input).
- Audit log on every create/update.
"""

import logging

from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from apps.tenants.models import Company
from common.middleware import get_client_ip
from common.permissions import SchemeAdminRequiredMixin

from .forms import BeneficiaryForm
from .models import Beneficiary

logger = logging.getLogger(__name__)


class BeneficiaryCompanyMixin:
    """
    Mixin that resolves the current company from the URL and enforces
    tenant-scoped querysets. All beneficiary views use this.
    """

    def get_company(self):
        if not hasattr(self, "_company"):
            self._company = get_object_or_404(
                Company, pk=self.kwargs["company_pk"], is_active=True
            )
        return self._company

    def get_queryset(self):
        return Beneficiary.objects.for_tenant(self.get_company())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["company"] = self.get_company()
        return ctx


class BeneficiaryListView(SchemeAdminRequiredMixin, BeneficiaryCompanyMixin, ListView):
    """List all beneficiaries for a company. Scheme admins only."""

    model = Beneficiary
    template_name = "beneficiaries/list.html"
    context_object_name = "beneficiaries"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        # Optional search filter
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                models.Q(first_name__icontains=q)
                | models.Q(last_name__icontains=q)
                | models.Q(employee_number__icontains=q)
                | models.Q(email__icontains=q)
            )
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        return qs


class BeneficiaryDetailView(
    SchemeAdminRequiredMixin, BeneficiaryCompanyMixin, DetailView
):
    """View a single beneficiary. Scheme admins only."""

    model = Beneficiary
    template_name = "beneficiaries/detail.html"
    context_object_name = "beneficiary"
    pk_url_kwarg = "pk"


class BeneficiaryCreateView(
    SchemeAdminRequiredMixin, BeneficiaryCompanyMixin, CreateView
):
    """Create a new beneficiary. Scheme admins only."""

    model = Beneficiary
    form_class = BeneficiaryForm
    template_name = "beneficiaries/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs

    def form_valid(self, form):
        # Set company server-side (never trust client input)
        form.instance.company = self.get_company()
        response = super().form_valid(form)

        log_audit(
            action=AuditAction.BENEFICIARY_CREATE,
            user=self.request.user,
            ip_address=get_client_ip(self.request),
            company=self.get_company(),
            target_model="Beneficiary",
            target_id=str(self.object.pk),
            details={
                "employee_number": self.object.employee_number,
                "name": self.object.full_name,
            },
        )
        messages.success(self.request, f"Beneficiary {self.object.full_name} created.")
        return response

    def get_success_url(self):
        return reverse_lazy(
            "beneficiaries:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": self.object.pk},
        )


class BeneficiaryUpdateView(
    SchemeAdminRequiredMixin, BeneficiaryCompanyMixin, UpdateView
):
    """Update an existing beneficiary. Scheme admins only."""

    model = Beneficiary
    form_class = BeneficiaryForm
    template_name = "beneficiaries/form.html"
    pk_url_kwarg = "pk"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs

    def form_valid(self, form):
        # Capture old values for audit trail (before save)
        old_obj = Beneficiary.objects.get(pk=self.object.pk)
        old_values = {
            "employee_number": old_obj.employee_number,
            "name": old_obj.full_name,
            "status": old_obj.status,
            "total_shares": old_obj.total_shares,
        }

        # Check if bank details changed BEFORE super().form_valid() (which saves)
        account_changed = self._account_changed(form, old_obj)

        response = super().form_valid(form)

        log_audit(
            action=AuditAction.BENEFICIARY_UPDATE,
            user=self.request.user,
            ip_address=get_client_ip(self.request),
            company=self.get_company(),
            target_model="Beneficiary",
            target_id=str(self.object.pk),
            details={
                "old": old_values,
                "new": {
                    "employee_number": self.object.employee_number,
                    "name": self.object.full_name,
                    "status": self.object.status,
                    "total_shares": self.object.total_shares,
                },
            },
        )

        if account_changed:
            log_audit(
                action=AuditAction.BANK_DETAIL_CHANGE,
                user=self.request.user,
                ip_address=get_client_ip(self.request),
                company=self.get_company(),
                target_model="Beneficiary",
                target_id=str(self.object.pk),
                details={"employee_number": self.object.employee_number},
            )

        messages.success(self.request, f"Beneficiary {self.object.full_name} updated.")
        return response

    @staticmethod
    def _account_changed(form, old_obj):
        """Check if bank details were changed (uses the already-validated form)."""
        new_account = form.cleaned_data.get("account_number", "")
        old_account = old_obj.account_number
        return new_account != old_account

    def get_success_url(self):
        return reverse_lazy(
            "beneficiaries:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": self.object.pk},
        )

