"""
Celery tasks for month-end processing.

These tasks handle background processing of month-end runs:
- process_month_end_run_async: Create vesting events for approved runs
- submit_tax_directives_async: Submit tax directives to SARS
- submit_month_end_payments_async: Submit payments to banking API

Security notes:
- All tasks run with tenant context from the run's company.
- Audit logging included for all operations.
- Idempotency: tasks check run status before processing.
- Failed tasks do not automatically retry (manual intervention required).
"""

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from celery import shared_task
from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="month_end.process_run",
    max_retries=0,  # No auto-retry; requires manual intervention
    acks_late=True,
)
def process_month_end_run_async(
    self,
    run_id: str,
    user_id: str,
    share_price: str,
    tax_rate: str = "0.35",
) -> dict:
    """
    Process a month-end run asynchronously.
    
    Creates vesting events for all eligible beneficiaries.
    The run must be in APPROVED status.
    
    Args:
        run_id: UUID of the MonthEndRun to process.
        user_id: UUID of the user initiating the process.
        share_price: Share price as string (converted to Decimal).
        tax_rate: Tax rate as string (default 35%).
        
    Returns:
        dict with processing results.
    """
    from apps.accounts.models import User
    from apps.month_end.models import MonthEndRun, MonthEndRunStatus
    from apps.month_end.services import process_run, InvalidStateTransition
    
    logger.info("Starting async month-end run processing: %s", run_id)
    
    try:
        run = MonthEndRun.objects.select_for_update().get(pk=run_id)
        user = User.objects.get(pk=user_id)
    except MonthEndRun.DoesNotExist:
        logger.error("MonthEndRun not found: %s", run_id)
        return {"status": "error", "message": f"Run {run_id} not found"}
    except User.DoesNotExist:
        logger.error("User not found: %s", user_id)
        return {"status": "error", "message": f"User {user_id} not found"}
    
    # Idempotency: if already completed, return success
    if run.status == MonthEndRunStatus.COMPLETED:
        logger.info("Run %s already completed, skipping", run_id)
        return {
            "status": "skipped",
            "message": "Run already completed",
            "vesting_event_count": run.vesting_event_count,
        }
    
    # If not in approved status, cannot process
    if run.status != MonthEndRunStatus.APPROVED:
        logger.warning("Run %s is in %s status, cannot process", run_id, run.status)
        return {
            "status": "error",
            "message": f"Cannot process run in {run.get_status_display()} status",
        }
    
    try:
        run = process_run(
            run,
            user=user,
            share_price=Decimal(share_price),
            tax_rate=Decimal(tax_rate),
        )
        logger.info(
            "Month-end run %s processed: %d events, net R%s",
            run_id, run.vesting_event_count, run.total_net_proceeds,
        )
        return {
            "status": "success",
            "vesting_event_count": run.vesting_event_count,
            "total_net_proceeds": str(run.total_net_proceeds),
        }
    except InvalidStateTransition as e:
        logger.warning("Invalid state transition for run %s: %s", run_id, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception("Failed to process month-end run %s: %s", run_id, e)
        return {"status": "error", "message": str(e)}


@shared_task(
    bind=True,
    name="month_end.submit_tax_directives",
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
)
def submit_tax_directives_async(
    self,
    run_id: str,
    user_id: str,
) -> dict:
    """
    Submit tax directives to SARS for all beneficiaries in a month-end run.
    
    Creates TaxDirective records and submits them to SARS API.
    
    Args:
        run_id: UUID of the completed MonthEndRun.
        user_id: UUID of the user initiating submission.
        
    Returns:
        dict with submission results.
    """
    from apps.accounts.models import User
    from apps.audit.models import AuditAction
    from apps.audit.services import log_audit
    from apps.month_end.models import (
        MonthEndRun,
        MonthEndRunStatus,
        TaxDirective,
        TaxDirectiveStatus,
        VestingEvent,
    )
    from apps.month_end.services import create_tax_directive
    from apps.integrations.sars import SARSClient, TaxDirectiveRequest
    
    logger.info("Starting tax directive submission for run: %s", run_id)
    
    try:
        run = MonthEndRun.objects.get(pk=run_id)
        user = User.objects.get(pk=user_id)
    except MonthEndRun.DoesNotExist:
        return {"status": "error", "message": f"Run {run_id} not found"}
    except User.DoesNotExist:
        return {"status": "error", "message": f"User {user_id} not found"}
    
    if run.status != MonthEndRunStatus.COMPLETED:
        return {
            "status": "error",
            "message": f"Run must be completed to submit directives",
        }
    
    client = SARSClient(company=run.company, user=user)
    events = run.vesting_events.select_related("beneficiary")
    
    submitted = 0
    failed = 0
    requests_list = []
    
    for event in events:
        ben = event.beneficiary
        # Check if directive already exists
        existing = TaxDirective.objects.filter(
            company=run.company,
            beneficiary=ben,
            run=run,
        ).first()
        
        if existing:
            logger.info("Directive already exists for %s, skipping", ben.pk)
            continue
        
        # Create local directive record
        directive = create_tax_directive(
            beneficiary=ben,
            tax_year=run.period_year,
            taxable_amount=event.gross_amount,
            run=run,
            user=user,
        )
        
        # Prepare SARS request
        requests_list.append(TaxDirectiveRequest(
            beneficiary_id=str(ben.pk),
            id_number=ben.id_number or "",
            tax_number=ben.tax_number or "",
            gross_amount=event.gross_amount,
            tax_year=run.period_year,
        ))
        submitted += 1
    
    # Bulk submit to SARS
    if requests_list:
        try:
            responses = client.bulk_submit_directives(requests_list)
            logger.info("Submitted %d directives to SARS", len(responses))
        except Exception as e:
            logger.exception("SARS bulk submission failed: %s", e)
            failed = len(requests_list)
    
    log_audit(
        action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
        user=user,
        company=run.company,
        target_model="MonthEndRun",
        target_id=str(run.pk),
        details={
            "sub_action": "tax_directives_submitted",
            "submitted": submitted,
            "failed": failed,
        },
    )
    
    return {
        "status": "success" if failed == 0 else "partial",
        "submitted": submitted,
        "failed": failed,
    }


@shared_task(
    bind=True,
    name="month_end.submit_payments",
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
)
def submit_month_end_payments_async(
    self,
    run_id: str,
    user_id: str,
) -> dict:
    """
    Submit month-end payments to banking API.

    Iterates over all PENDING vesting events and submits EFT payments.

    Args:
        run_id: UUID of the completed MonthEndRun.
        user_id: UUID of the user initiating payments.

    Returns:
        dict with payment submission results.
    """
    from apps.accounts.models import User
    from apps.audit.models import AuditAction
    from apps.audit.services import log_audit
    from apps.month_end.models import (
        MonthEndRun,
        MonthEndRunStatus,
        VestingEvent,
        VestingEventStatus,
    )
    from apps.integrations.banking import BankingClient, PaymentRequest

    logger.info("Starting month-end payment submission for run: %s", run_id)

    try:
        run = MonthEndRun.objects.get(pk=run_id)
        user = User.objects.get(pk=user_id)
    except MonthEndRun.DoesNotExist:
        return {"status": "error", "message": f"Run {run_id} not found"}
    except User.DoesNotExist:
        return {"status": "error", "message": f"User {user_id} not found"}

    if run.status != MonthEndRunStatus.COMPLETED:
        return {
            "status": "error",
            "message": f"Cannot submit payments for run in {run.get_status_display()} status",
        }

    client = BankingClient(company=run.company, user=user)
    pending = run.vesting_events.filter(
        status=VestingEventStatus.PENDING,
        net_amount__gt=0,
    ).select_related("beneficiary")

    submitted = 0
    failed = 0

    for event in pending:
        ben = event.beneficiary
        try:
            request = PaymentRequest(
                beneficiary_id=str(ben.pk),
                amount=event.net_amount,
                bank_account=ben.account_number or "",
                bank_code=ben.branch_code or "",
                reference=f"ME-{run.pk}-{event.pk}",
            )
            response = client.submit_eft_payment(
                request,
                idempotency_key=f"me-{run.pk}-{event.pk}",
            )
            event.status = VestingEventStatus.PROCESSED
            event.notes = f"Payment ref: {response.payment_reference}"
            event.save(update_fields=["status", "notes", "updated_at"])
            submitted += 1
        except Exception as e:
            logger.error("Payment failed for vesting event %s: %s", event.pk, e)
            event.status = VestingEventStatus.FAILED
            event.notes = f"Payment failed: {e}"
            event.save(update_fields=["status", "notes", "updated_at"])
            failed += 1

    log_audit(
        action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
        user=user,
        company=run.company,
        target_model="MonthEndRun",
        target_id=str(run.pk),
        details={
            "sub_action": "payments_submitted",
            "submitted": submitted,
            "failed": failed,
        },
    )

    return {
        "status": "success" if failed == 0 else "partial",
        "submitted": submitted,
        "failed": failed,
    }

