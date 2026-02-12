"""
API ViewSets for ESOP models with tenant-scoped access.

Security notes:
- All querysets are filtered by tenant.
- Object-level permissions check tenant membership.
- Write operations create audit log entries.
- State transitions go through service layer, not direct model updates.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import models, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response


def _make_json_safe(data: dict) -> dict:
    """
    Convert non-JSON-serializable values in a dict to strings.

    This handles common types like Decimal, UUID, date, datetime that
    appear in serializer.validated_data but cannot be stored in JSONField.
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, (Decimal, UUID)):
            result[key] = str(value)
        elif isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = _make_json_safe(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [
                str(v) if isinstance(v, (Decimal, UUID)) else v.isoformat() if isinstance(v, (date, datetime)) else v
                for v in value
            ]
        else:
            result[key] = value
    return result

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from apps.beneficiaries.models import Beneficiary
from apps.integrations.models import JSECompany
from apps.dividends.models import DividendRun, DividendAllocation
from apps.dividends import services as dividend_services
from apps.dividends.services import InvalidStateTransition as DividendInvalidStateTransition
from apps.month_end.models import MonthEndRun, VestingEvent, TaxDirective
from apps.month_end import services as month_end_services
from apps.month_end.services import InvalidStateTransition as MonthEndInvalidStateTransition

from .exceptions import InvalidStateTransitionError, TenantMismatchError
from .permissions import IsSchemeAdmin, TenantScopedPermission, IsOwnerOrSchemeAdmin
from .serializers import (
    BeneficiaryListSerializer, BeneficiaryDetailSerializer,
    DividendRunListSerializer, DividendRunDetailSerializer, DividendRunCreateSerializer,
    DividendAllocationSerializer,
    MonthEndRunListSerializer, MonthEndRunDetailSerializer, MonthEndRunCreateSerializer,
    VestingEventSerializer, TaxDirectiveSerializer,
    JSECompanySearchSerializer,
)

logger = logging.getLogger(__name__)


class TenantScopedViewSetMixin:
    """Mixin to scope querysets to the authenticated user's tenant."""
    
    def get_queryset(self):
        """Filter queryset by user's company."""
        qs = super().get_queryset()
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return qs.none()
        
        # Scheme admins with a company see only that company's data
        # Scheme admins without a company see all data (superusers)
        if user.company:
            return qs.filter(company=user.company)
        
        return qs
    
    def perform_create(self, serializer):
        """Set company and created_by from authenticated user."""
        user = self.request.user
        extra_kwargs = {}
        
        # Set company if the model has it
        model = serializer.Meta.model
        if hasattr(model, "company"):
            if not user.company:
                raise TenantMismatchError("You must be associated with a company to create records.")
            extra_kwargs["company"] = user.company
        
        # Set created_by if the model has it
        if hasattr(model, "created_by"):
            extra_kwargs["created_by"] = user
        
        instance = serializer.save(**extra_kwargs)

        # Audit log - use model-specific action if available
        action_map = {
            "Beneficiary": AuditAction.BENEFICIARY_CREATE,
            "DividendRun": AuditAction.DIVIDEND_RUN_CREATE,
            "MonthEndRun": AuditAction.MONTH_END_RUN_CREATE,
        }
        audit_action = action_map.get(model.__name__, AuditAction.BENEFICIARY_CREATE)

        log_audit(
            action=audit_action,
            user=user,
            company=user.company,
            target_model=model.__name__,
            target_id=str(instance.pk),
            details=_make_json_safe(dict(serializer.validated_data)),
        )

        return instance


# -----------------------------------------------------------------------------
# Beneficiary ViewSet
# -----------------------------------------------------------------------------

class BeneficiaryViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint for beneficiaries.
    
    - list: GET /api/v1/beneficiaries/
    - retrieve: GET /api/v1/beneficiaries/{id}/
    - create: POST /api/v1/beneficiaries/
    - update: PUT /api/v1/beneficiaries/{id}/
    - partial_update: PATCH /api/v1/beneficiaries/{id}/
    - destroy: DELETE /api/v1/beneficiaries/{id}/
    """
    
    queryset = Beneficiary.objects.all()
    permission_classes = [TenantScopedPermission, IsSchemeAdmin]
    
    def get_serializer_class(self):
        if self.action == "list":
            return BeneficiaryListSerializer
        return BeneficiaryDetailSerializer
    
    def perform_destroy(self, instance):
        """Audit log before deletion."""
        user = self.request.user
        log_audit(
            action=AuditAction.BENEFICIARY_DELETE,
            user=user,
            company=instance.company,
            target_model="Beneficiary",
            target_id=str(instance.pk),
            details={"deleted": True},
        )
        instance.delete()


# -----------------------------------------------------------------------------
# Dividend ViewSets
# -----------------------------------------------------------------------------

class DividendRunViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint for dividend runs.
    
    Additional actions:
    - approve: POST /api/v1/dividend-runs/{id}/approve/
    - process: POST /api/v1/dividend-runs/{id}/process/
    - reset: POST /api/v1/dividend-runs/{id}/reset/
    """
    
    queryset = DividendRun.objects.all()
    permission_classes = [TenantScopedPermission, IsSchemeAdmin]
    
    def get_serializer_class(self):
        if self.action == "list":
            return DividendRunListSerializer
        elif self.action == "create":
            return DividendRunCreateSerializer
        return DividendRunDetailSerializer
    
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a dividend run (four-eyes principle)."""
        run = self.get_object()
        try:
            with transaction.atomic():
                dividend_services.approve_run(run=run, user=request.user)
            return Response({"status": "approved"})
        except (ValueError, DividendInvalidStateTransition) as e:
            raise InvalidStateTransitionError(str(e))

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        """Process an approved dividend run."""
        run = self.get_object()
        try:
            with transaction.atomic():
                dividend_services.process_run(run=run, user=request.user)
            return Response({"status": "processing"})
        except (ValueError, DividendInvalidStateTransition) as e:
            raise InvalidStateTransitionError(str(e))

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """Reset a dividend run to draft."""
        run = self.get_object()
        try:
            with transaction.atomic():
                dividend_services.reset_to_draft(run=run, user=request.user)
            return Response({"status": "reset"})
        except (ValueError, DividendInvalidStateTransition) as e:
            raise InvalidStateTransitionError(str(e))


class DividendAllocationViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoint for dividend allocations.

    Allocations are created by processing, not via API.
    Filter by run_id: GET /api/v1/dividend-allocations/?run={run_id}
    """

    queryset = DividendAllocation.objects.select_related("beneficiary", "run")
    permission_classes = [TenantScopedPermission, IsOwnerOrSchemeAdmin]
    serializer_class = DividendAllocationSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filter by run if specified
        run_id = self.request.query_params.get("run")
        if run_id:
            qs = qs.filter(run_id=run_id)

        # For beneficiaries, only show their allocations
        user = self.request.user
        if user.is_beneficiary and hasattr(user, "beneficiary_profile"):
            qs = qs.filter(beneficiary=user.beneficiary_profile)

        return qs


# -----------------------------------------------------------------------------
# Month-End ViewSets
# -----------------------------------------------------------------------------

class MonthEndRunViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """
    API endpoint for month-end runs.

    Additional actions:
    - approve: POST /api/v1/month-end-runs/{id}/approve/
    - process: POST /api/v1/month-end-runs/{id}/process/
    - reset: POST /api/v1/month-end-runs/{id}/reset/
    """

    queryset = MonthEndRun.objects.all()
    permission_classes = [TenantScopedPermission, IsSchemeAdmin]

    def get_serializer_class(self):
        if self.action == "list":
            return MonthEndRunListSerializer
        elif self.action == "create":
            return MonthEndRunCreateSerializer
        return MonthEndRunDetailSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a month-end run (four-eyes principle)."""
        run = self.get_object()
        try:
            with transaction.atomic():
                month_end_services.approve_run(run=run, user=request.user)
            return Response({"status": "approved"})
        except (ValueError, MonthEndInvalidStateTransition) as e:
            raise InvalidStateTransitionError(str(e))

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        """Process an approved month-end run."""
        run = self.get_object()
        share_price = request.data.get("share_price")
        tax_rate = request.data.get("tax_rate")

        if not share_price or not tax_rate:
            return Response(
                {"error": {"code": "missing_parameters", "message": "share_price and tax_rate are required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                month_end_services.process_run(
                    run=run,
                    user=request.user,
                    share_price=share_price,
                    tax_rate=tax_rate,
                )
            return Response({"status": "processing"})
        except (ValueError, MonthEndInvalidStateTransition) as e:
            raise InvalidStateTransitionError(str(e))

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """Reset a month-end run to draft."""
        run = self.get_object()
        try:
            with transaction.atomic():
                month_end_services.reset_to_draft(run=run, user=request.user)
            return Response({"status": "reset"})
        except (ValueError, MonthEndInvalidStateTransition) as e:
            raise InvalidStateTransitionError(str(e))


class VestingEventViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoint for vesting events.

    Events are created by processing, not via API.
    Filter by run_id: GET /api/v1/vesting-events/?run={run_id}
    """

    queryset = VestingEvent.objects.select_related("beneficiary", "run")
    permission_classes = [TenantScopedPermission, IsOwnerOrSchemeAdmin]
    serializer_class = VestingEventSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filter by run if specified
        run_id = self.request.query_params.get("run")
        if run_id:
            qs = qs.filter(run_id=run_id)

        # For beneficiaries, only show their events
        user = self.request.user
        if user.is_beneficiary and hasattr(user, "beneficiary_profile"):
            qs = qs.filter(beneficiary=user.beneficiary_profile)

        return qs


class TaxDirectiveViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoint for tax directives.

    Directives are created during month-end processing.
    """

    queryset = TaxDirective.objects.select_related("beneficiary", "run")
    permission_classes = [TenantScopedPermission, IsSchemeAdmin]
    serializer_class = TaxDirectiveSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filter by run if specified
        run_id = self.request.query_params.get("run")
        if run_id:
            qs = qs.filter(run_id=run_id)

        return qs


# -----------------------------------------------------------------------------
# JSE Company Search ViewSet
# -----------------------------------------------------------------------------

class JSECompanySearchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Search JSE-listed companies for autocomplete during company creation.

    GET /api/v1/jse-companies/?q=sasol
    GET /api/v1/jse-companies/{id}/

    Scheme admins only. Not tenant-scoped (this is reference data).
    """

    queryset = JSECompany.objects.filter(is_active=True)
    serializer_class = JSECompanySearchSerializer
    permission_classes = [IsSchemeAdmin]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(
                models.Q(company_name__icontains=q)
                | models.Q(ticker__icontains=q)
                | models.Q(isin__icontains=q)
            )
        else:
            qs = qs.none()
        return qs[:20]

    @action(detail=True, methods=["post"])
    def enrich(self, request, pk=None):
        """Trigger live data enrichment for a JSE company."""
        jse_company = self.get_object()
        from apps.integrations.tasks import enrich_jse_company_async

        enrich_jse_company_async.delay(
            jse_company_id=jse_company.pk,
            user_id=str(request.user.pk),
        )
        return Response({
            "status": "queued",
            "message": f"Enrichment queued for {jse_company.ticker}",
        })

