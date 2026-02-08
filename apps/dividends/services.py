"""
Dividend run service layer – all business logic lives here.

Security notes:
- State transitions are validated before execution.
- All mutations are wrapped in atomic transactions.
- Idempotency: duplicate processing of the same run is a no-op.
- Audit logging on every state change.
- Tax calculations use Decimal for precision (no floats).
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from apps.beneficiaries.models import BeneficiaryStatus

from .models import (
    AllocationStatus,
    DividendAllocation,
    DividendRun,
    RunStatus,
    VALID_TRANSITIONS,
)

logger = logging.getLogger(__name__)


class InvalidStateTransition(Exception):
    """Raised when a state transition is not allowed."""
    pass


def _validate_transition(run: DividendRun, new_status: str) -> None:
    """Check that the transition is allowed by the state machine."""
    allowed = VALID_TRANSITIONS.get(run.status, [])
    if new_status not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition from '{run.get_status_display()}' "
            f"to '{RunStatus(new_status).label}'. "
            f"Allowed: {[RunStatus(s).label for s in allowed]}"
        )


def _change_status(
    run: DividendRun,
    new_status: str,
    *,
    user,
    ip_address: str | None = None,
    details: dict | None = None,
) -> DividendRun:
    """
    Transition a run to a new status with audit logging.
    Caller must already be inside an atomic block.
    """
    _validate_transition(run, new_status)
    old_status = run.status
    run.status = new_status
    run.save(update_fields=["status", "updated_at"])

    log_audit(
        action=AuditAction.DIVIDEND_RUN_STATE_CHANGE,
        user=user,
        ip_address=ip_address,
        company=run.company,
        target_model="DividendRun",
        target_id=str(run.pk),
        details={
            "old_status": old_status,
            "new_status": new_status,
            **(details or {}),
        },
    )
    return run


@transaction.atomic
def approve_run(
    run: DividendRun,
    *,
    user,
    ip_address: str | None = None,
) -> DividendRun:
    """
    Move a DRAFT run to APPROVED.
    Requires a different user than the creator (four-eyes principle).
    """
    if user == run.created_by:
        raise InvalidStateTransition(
            "The approver must be different from the creator (four-eyes principle)."
        )

    run = _change_status(
        run, RunStatus.APPROVED, user=user, ip_address=ip_address,
    )
    run.approved_by = user
    run.approved_at = timezone.now()
    run.save(update_fields=["approved_by", "approved_at", "updated_at"])
    return run


@transaction.atomic
def process_run(
    run: DividendRun,
    *,
    user,
    ip_address: str | None = None,
) -> DividendRun:
    """
    Move an APPROVED run to PROCESSING, then create allocations
    for every active beneficiary with vested shares > 0.

    Idempotent: if allocations already exist, skip creation.
    On success → COMPLETED. On error → FAILED.
    """
    run = _change_status(
        run, RunStatus.PROCESSING, user=user, ip_address=ip_address,
    )

    try:
        _create_allocations(run, user=user, ip_address=ip_address)

        # Compute totals
        run.total_gross = sum_field(run, "gross_amount")
        run.total_tax = sum_field(run, "tax_amount")
        run.total_net = sum_field(run, "net_amount")
        run.allocation_count = run.allocations.count()
        run.completed_at = timezone.now()
        run.save(update_fields=[
            "total_gross", "total_tax", "total_net",
            "allocation_count", "completed_at", "updated_at",
        ])

        run = _change_status(
            run, RunStatus.COMPLETED, user=user, ip_address=ip_address,
            details={
                "allocation_count": run.allocation_count,
                "total_net": str(run.total_net),
            },
        )
    except Exception as exc:
        logger.exception("Dividend run %s failed: %s", run.pk, exc)
        run.failure_reason = str(exc)
        run.status = RunStatus.FAILED
        run.save(update_fields=["status", "failure_reason", "updated_at"])
        log_audit(
            action=AuditAction.DIVIDEND_RUN_STATE_CHANGE,
            user=user,
            ip_address=ip_address,
            company=run.company,
            target_model="DividendRun",
            target_id=str(run.pk),
            details={"old_status": RunStatus.PROCESSING, "new_status": RunStatus.FAILED, "error": str(exc)},
        )
        raise

    return run


def _create_allocations(
    run: DividendRun,
    *,
    user,
    ip_address: str | None = None,
) -> int:
    """
    Create DividendAllocation rows for every eligible beneficiary.
    Idempotent: skips if allocations already exist for this run.
    Returns the number of allocations created.
    """
    # Idempotency guard
    if run.allocations.exists():
        logger.info("Allocations already exist for run %s – skipping.", run.pk)
        return 0

    from apps.beneficiaries.models import Beneficiary

    eligible = Beneficiary.objects.for_tenant(run.company).filter(
        status=BeneficiaryStatus.ACTIVE,
        vested_shares__gt=0,
    )

    allocations = []
    for ben in eligible:
        gross = (Decimal(ben.vested_shares) * run.dividend_per_share).quantize(
            Decimal("0.01")
        )
        tax = (gross * run.dwt_rate).quantize(Decimal("0.01"))
        net = gross - tax

        allocations.append(
            DividendAllocation(
                company=run.company,
                run=run,
                beneficiary=ben,
                shares_at_record_date=ben.vested_shares,
                gross_amount=gross,
                tax_amount=tax,
                net_amount=net,
                status=AllocationStatus.PENDING,
            )
        )

    if allocations:
        DividendAllocation.objects.bulk_create(allocations)

    log_audit(
        action=AuditAction.DIVIDEND_ALLOCATION_APPLY,
        user=user,
        ip_address=ip_address,
        company=run.company,
        target_model="DividendRun",
        target_id=str(run.pk),
        details={
            "beneficiaries_allocated": len(allocations),
            "dividend_per_share": str(run.dividend_per_share),
        },
    )

    return len(allocations)


def sum_field(run: DividendRun, field: str) -> Decimal:
    """Sum a decimal field across all allocations for a run."""
    from django.db.models import Sum

    result = run.allocations.aggregate(total=Sum(field))["total"]
    return result or Decimal("0.00")


@transaction.atomic
def reset_to_draft(
    run: DividendRun,
    *,
    user,
    ip_address: str | None = None,
) -> DividendRun:
    """
    Reset a FAILED or APPROVED run back to DRAFT.
    Deletes any existing allocations.
    """
    run = _change_status(
        run, RunStatus.DRAFT, user=user, ip_address=ip_address,
    )
    deleted_count = run.allocations.all().delete()[0]
    run.approved_by = None
    run.approved_at = None
    run.completed_at = None
    run.failure_reason = ""
    run.total_gross = Decimal("0.00")
    run.total_tax = Decimal("0.00")
    run.total_net = Decimal("0.00")
    run.allocation_count = 0
    run.save(update_fields=[
        "approved_by", "approved_at", "completed_at", "failure_reason",
        "total_gross", "total_tax", "total_net", "allocation_count",
        "updated_at",
    ])
    logger.info("Run %s reset to DRAFT, %d allocations deleted.", run.pk, deleted_count)
    return run

