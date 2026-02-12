"""
Company (tenant) management views.

Only scheme admins can create, list, or view companies.
Company creation is not tenant-scoped (it creates a NEW tenant).
"""

import logging

from django.contrib import messages
from django.db import models
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from common.middleware import get_client_ip
from common.permissions import SchemeAdminRequiredMixin

from .forms import CompanyCreateForm
from .models import Company

logger = logging.getLogger(__name__)


class CompanyListView(SchemeAdminRequiredMixin, ListView):
    """List all companies. Scheme admins only."""

    model = Company
    template_name = "tenants/company_list.html"
    context_object_name = "companies"
    paginate_by = 25

    def get_queryset(self):
        qs = Company.objects.all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                models.Q(name__icontains=q)
                | models.Q(registration_number__icontains=q)
                | models.Q(jse_ticker__icontains=q)
            )
        return qs


class CompanyDetailView(SchemeAdminRequiredMixin, DetailView):
    """View a single company. Scheme admins only."""

    model = Company
    template_name = "tenants/company_detail.html"
    context_object_name = "company"


class CompanyCreateView(SchemeAdminRequiredMixin, CreateView):
    """
    Create a new Company tenant with optional JSE search autofill.
    Scheme admins only.
    """

    model = Company
    form_class = CompanyCreateForm
    template_name = "tenants/company_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)

        log_audit(
            action=AuditAction.COMPANY_CREATE,
            user=self.request.user,
            ip_address=get_client_ip(self.request),
            company=self.object,
            target_model="Company",
            target_id=str(self.object.pk),
            details={
                "name": self.object.name,
                "registration_number": self.object.registration_number,
                "jse_ticker": self.object.jse_ticker,
            },
        )
        messages.success(
            self.request,
            f"Company '{self.object.name}' created successfully.",
        )
        return response

    def get_success_url(self):
        return reverse_lazy("tenants:detail", kwargs={"pk": self.object.pk})
