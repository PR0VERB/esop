"""
Month-end run service layer – all business logic lives here.

Security notes:
- State transitions are validated before execution.
- All mutations are wrapped in atomic transactions.
- Idempotency: duplicate processing of the same run is a no-op.
- Audit logging on every state change.
- Financial calculations use Decimal for precision (no floats).
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus

from .models import (
    MonthEndRun,
    MonthEndRunStatus,
    TaxDirective,
    TaxDirectiveStatus,
    VALID_TRANSITIONS,
    VestingEvent,
    VestingEventStatus,
    VestingEventType,
)

logger = logging.getLogger(__name__)


class InvalidStateTransition(Exception):
    """Raised when a state transition is not allowed."""
    pass


def _validate_transition(run: MonthEndRun, new_status: str) -> None:
    """Check that the transition is allowed by the state machine."""
    allowed = VALID_TRANSITIONS.get(run.status, [])
    if new_status not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition from '{run.get_status_display()}' "
            f"to '{MonthEndRunStatus(new_status).label}'. "
            f"Allowed: {[MonthEndRunStatus(s).label for s in allowed]}"
        )


def _change_status(
    run: MonthEndRun,
    new_status: str,
    *,
    user,
    ip_address: str | None = None,
    details: dict | None = None,
) -> MonthEndRun:
    """
    Transition a run to a new status with audit logging.
    Caller must already be inside an atomic block.
    """
    _validate_transition(run, new_status)
    old_status = run.status
    run.status = new_status
    run.save(update_fields=["status", "updated_at"])

    log_audit(
        action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
        user=user,
        ip_address=ip_address,
        company=run.company,
        target_model="MonthEndRun",
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
    run: MonthEndRun,
    *,
    user,
    ip_address: str | None = None,
) -> MonthEndRun:
    """
    Move a DRAFT run to APPROVED.
    Requires a different user than the creator (four-eyes principle).
    """
    if user == run.created_by:
        raise InvalidStateTransition(
            "The approver must be different from the creator (four-eyes principle)."
        )

    run = _change_status(
        run, MonthEndRunStatus.APPROVED, user=user, ip_address=ip_address,
    )
    run.approved_by = user
    run.approved_at = timezone.now()
    run.save(update_fields=["approved_by", "approved_at", "updated_at"])
    return run


@transaction.atomic
def process_run(
    run: MonthEndRun,
    *,
    user,
    share_price: Decimal,
    tax_rate: Decimal = Decimal("0.35"),
    ip_address: str | None = None,
) -> MonthEndRun:
    """
    Move an APPROVED run to PROCESSING, then create vesting events
    for all active beneficiaries with vested shares > 0.

    Idempotent: if vesting events already exist, skip creation.
    On success → COMPLETED. On error → FAILED.
    """
    run = _change_status(
        run, MonthEndRunStatus.PROCESSING, user=user, ip_address=ip_address,
    )

    try:
        _create_vesting_events(
            run,
            share_price=share_price,
            tax_rate=tax_rate,
            user=user,
            ip_address=ip_address,
        )

        # Update run totals
        run.completed_at = timezone.now()
        run.save(update_fields=["completed_at", "updated_at"])

        run = _change_status(
            run, MonthEndRunStatus.COMPLETED, user=user, ip_address=ip_address,
            details={
                "vesting_event_count": run.vesting_event_count,
                "total_shares_sold": run.total_shares_sold,
                "total_net_proceeds": str(run.total_net_proceeds),
            },
        )
    except Exception as exc:
        logger.exception("Month-end run %s failed: %s", run.pk, exc)
        run.failure_reason = str(exc)
        run.status = MonthEndRunStatus.FAILED
        run.save(update_fields=["status", "failure_reason", "updated_at"])
        raise

    return run


def _create_vesting_events(
    run: MonthEndRun,
    *,
    share_price: Decimal,
    tax_rate: Decimal,
    user,
    ip_address: str | None = None,
) -> int:
    """
    Create VestingEvent rows for every eligible beneficiary.
    Deem all vested shares as sold (per ESOP process).
    Idempotent: skips if events already exist for this run.
    Returns the number of events created.
    """
    # Idempotency guard
    if run.vesting_events.exists():
        logger.info("Vesting events already exist for run %s – skipping.", run.pk)
        return 0

    from datetime import date

    eligible = Beneficiary.objects.for_tenant(run.company).filter(
        status=BeneficiaryStatus.ACTIVE,
        vested_shares__gt=0,
    )

    events = []
    total_shares = 0
    total_gross = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_net = Decimal("0.00")

    event_date = date(run.period_year, run.period_month, 1)

    for ben in eligible:
        shares = ben.vested_shares
        gross = (Decimal(shares) * share_price).quantize(Decimal("0.01"))
        tax = (gross * tax_rate).quantize(Decimal("0.01"))
        net = gross - tax

        events.append(
            VestingEvent(
                company=run.company,
                run=run,
                beneficiary=ben,
                event_type=VestingEventType.SALE,
                event_date=event_date,
                shares_affected=shares,
                shares_before=shares,
                shares_after=0,
                share_price=share_price,
                gross_amount=gross,
                tax_amount=tax,
                net_amount=net,
                status=VestingEventStatus.PENDING,
            )
        )

        total_shares += shares
        total_gross += gross
        total_tax += tax
        total_net += net

    if events:
        VestingEvent.objects.bulk_create(events)

    # Update run totals
    run.vesting_event_count = len(events)
    run.total_shares_sold = total_shares
    run.total_shares_vested = total_shares
    run.total_gross_proceeds = total_gross
    run.total_tax = total_tax
    run.total_net_proceeds = total_net
    run.save(update_fields=[
        "vesting_event_count", "total_shares_sold", "total_shares_vested",
        "total_gross_proceeds", "total_tax", "total_net_proceeds", "updated_at",
    ])

    log_audit(
        action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
        user=user,
        ip_address=ip_address,
        company=run.company,
        target_model="MonthEndRun",
        target_id=str(run.pk),
        details={
            "sub_action": "vesting_events_created",
            "beneficiaries_processed": len(events),
            "total_shares": total_shares,
            "share_price": str(share_price),
        },
    )

    return len(events)


@transaction.atomic
def reset_to_draft(
    run: MonthEndRun,
    *,
    user,
    ip_address: str | None = None,
) -> MonthEndRun:
    """
    Reset a FAILED or APPROVED run back to DRAFT.
    Deletes any existing vesting events.
    """
    run = _change_status(
        run, MonthEndRunStatus.DRAFT, user=user, ip_address=ip_address,
    )
    deleted_count = run.vesting_events.all().delete()[0]
    run.approved_by = None
    run.approved_at = None
    run.completed_at = None
    run.failure_reason = ""
    run.total_shares_vested = 0
    run.total_shares_sold = 0
    run.total_gross_proceeds = Decimal("0.00")
    run.total_tax = Decimal("0.00")
    run.total_net_proceeds = Decimal("0.00")
    run.vesting_event_count = 0
    run.termination_count = 0
    run.save(update_fields=[
        "approved_by", "approved_at", "completed_at", "failure_reason",
        "total_shares_vested", "total_shares_sold", "total_gross_proceeds",
        "total_tax", "total_net_proceeds", "vesting_event_count",
        "termination_count", "updated_at",
    ])
    logger.info("Run %s reset to DRAFT, %d events deleted.", run.pk, deleted_count)
    return run


@transaction.atomic
def create_tax_directive(
    beneficiary: Beneficiary,
    *,
    tax_year: int,
    taxable_amount: Decimal,
    run: MonthEndRun | None = None,
    user,
    ip_address: str | None = None,
) -> TaxDirective:
    """
    Create a tax directive request for a beneficiary.
    """
    directive = TaxDirective.objects.create(
        company=beneficiary.company,
        run=run,
        beneficiary=beneficiary,
        tax_year=tax_year,
        taxable_amount=taxable_amount,
        status=TaxDirectiveStatus.PENDING,
    )

    log_audit(
        action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
        user=user,
        ip_address=ip_address,
        company=beneficiary.company,
        target_model="TaxDirective",
        target_id=str(directive.pk),
        details={
            "sub_action": "tax_directive_created",
            "beneficiary_id": str(beneficiary.pk),
            "tax_year": tax_year,
            "taxable_amount": str(taxable_amount),
        },
    )

    return directive


@transaction.atomic
def update_tax_directive_status(
    directive: TaxDirective,
    *,
    new_status: str,
    directive_number: str = "",
    directive_rate: Decimal | None = None,
    decline_reason: str = "",
    user,
    ip_address: str | None = None,
) -> TaxDirective:
    """
    Update the status of a tax directive after SARS response.
    """
    old_status = directive.status
    directive.status = new_status
    directive.response_date = timezone.now().date()

    if directive_number:
        directive.directive_number = directive_number
    if directive_rate is not None:
        directive.directive_rate = directive_rate
        directive.calculated_tax = (
            directive.taxable_amount * directive_rate
        ).quantize(Decimal("0.01"))
    if decline_reason:
        directive.decline_reason = decline_reason

    directive.save()

    log_audit(
        action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
        user=user,
        ip_address=ip_address,
        company=directive.company,
        target_model="TaxDirective",
        target_id=str(directive.pk),
        details={
            "sub_action": "tax_directive_status_change",
            "old_status": old_status,
            "new_status": new_status,
            "directive_number": directive_number,
        },
    )

    return directive

