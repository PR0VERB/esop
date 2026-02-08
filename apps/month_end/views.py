"""
Month-end run CRUD + state-change views with tenant isolation.

Security notes:
- All views scoped to company via MonthEndCompanyMixin.
- Only SchemeAdmins can access month-end views.
- State changes go through the service layer (never direct model mutation).
- Audit logging on every state change and CRUD operation.
"""

import logging
from decimal import Decimal

from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from apps.tenants.models import Company
from common.middleware import get_client_ip
from common.permissions import SchemeAdminRequiredMixin

from .forms import MonthEndRunForm, ProcessRunForm
from .models import MonthEndRun, MonthEndRunStatus
from .services import InvalidStateTransition, approve_run, process_run, reset_to_draft

logger = logging.getLogger(__name__)


class MonthEndCompanyMixin:
    """Resolve company from URL and scope querysets to tenant."""

    def get_company(self):
        if not hasattr(self, "_company"):
            self._company = get_object_or_404(
                Company, pk=self.kwargs["company_pk"], is_active=True
            )
        return self._company

    def get_queryset(self):
        return MonthEndRun.objects.for_tenant(self.get_company())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["company"] = self.get_company()
        return ctx


class MonthEndRunListView(
    SchemeAdminRequiredMixin, MonthEndCompanyMixin, ListView
):
    """List all month-end runs for a company."""

    model = MonthEndRun
    template_name = "month_end/list.html"
    context_object_name = "runs"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                models.Q(title__icontains=q)
                | models.Q(idempotency_key__icontains=q)
            )
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        return qs


class MonthEndRunDetailView(
    SchemeAdminRequiredMixin, MonthEndCompanyMixin, DetailView
):
    """View a single month-end run with its vesting events."""

    model = MonthEndRun
    template_name = "month_end/detail.html"
    context_object_name = "run"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vesting_events"] = self.object.vesting_events.select_related(
            "beneficiary"
        ).order_by("beneficiary__last_name", "beneficiary__first_name")
        ctx["tax_directives"] = self.object.tax_directives.select_related(
            "beneficiary"
        ).order_by("beneficiary__last_name")
        ctx["process_form"] = ProcessRunForm()
        return ctx


class MonthEndRunCreateView(
    SchemeAdminRequiredMixin, MonthEndCompanyMixin, CreateView
):
    """Create a new DRAFT month-end run."""

    model = MonthEndRun
    form_class = MonthEndRunForm
    template_name = "month_end/form.html"

    def form_valid(self, form):
        form.instance.company = self.get_company()
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        log_audit(
            action=AuditAction.MONTH_END_RUN_CREATE,
            user=self.request.user,
            ip_address=get_client_ip(self.request),
            company=self.get_company(),
            target_model="MonthEndRun",
            target_id=str(self.object.pk),
            details={"title": self.object.title, "period": self.object.period_display},
        )
        messages.success(self.request, f"Month-end run '{self.object.title}' created.")
        return response

    def get_success_url(self):
        return reverse_lazy(
            "month_end:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": self.object.pk},
        )


class MonthEndRunUpdateView(
    SchemeAdminRequiredMixin, MonthEndCompanyMixin, UpdateView
):
    """Edit a DRAFT month-end run."""

    model = MonthEndRun
    form_class = MonthEndRunForm
    template_name = "month_end/form.html"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return super().get_queryset().filter(status=MonthEndRunStatus.DRAFT)

    def get_success_url(self):
        return reverse_lazy(
            "month_end:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": self.object.pk},
        )


class _StateChangeView(SchemeAdminRequiredMixin, MonthEndCompanyMixin, View):
    """Base class for POST-only state-change views."""

    http_method_names = ["post"]

    def _get_run(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def _detail_url(self, run):
        return reverse_lazy(
            "month_end:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": run.pk},
        )


class MonthEndRunApproveView(_StateChangeView):
    """Approve a DRAFT run (four-eyes: approver ≠ creator)."""

    def post(self, request, *args, **kwargs):
        run = self._get_run()
        try:
            approve_run(
                run, user=request.user, ip_address=get_client_ip(request),
            )
            messages.success(request, f"Month-end run '{run.title}' approved.")
        except InvalidStateTransition as exc:
            messages.error(request, str(exc))
        return redirect(self._detail_url(run))


class MonthEndRunProcessView(_StateChangeView):
    """Process an APPROVED run — creates vesting events."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        run = self._get_run()
        form = ProcessRunForm(request.POST)

        if not form.is_valid():
            messages.error(request, "Invalid share price or tax rate.")
            return redirect(self._detail_url(run))

        try:
            process_run(
                run,
                user=request.user,
                share_price=form.cleaned_data["share_price"],
                tax_rate=form.cleaned_data["tax_rate"],
                ip_address=get_client_ip(request),
            )
            messages.success(
                request,
                f"Month-end run '{run.title}' processed — "
                f"{run.vesting_event_count} events created.",
            )
        except InvalidStateTransition as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(
                request,
                f"Month-end run '{run.title}' failed. See details for more info.",
            )
        return redirect(self._detail_url(run))


class MonthEndRunResetView(_StateChangeView):
    """Reset a FAILED or APPROVED run back to DRAFT."""

    def post(self, request, *args, **kwargs):
        run = self._get_run()
        try:
            reset_to_draft(
                run, user=request.user, ip_address=get_client_ip(request),
            )
            messages.success(request, f"Month-end run '{run.title}' reset to draft.")
        except InvalidStateTransition as exc:
            messages.error(request, str(exc))
        return redirect(self._detail_url(run))

