"""
Celery tasks for dividend distribution processing.

These tasks handle background processing of dividend runs:
- process_dividend_run_async: Process allocations for approved runs
- submit_dividend_payments_async: Submit payments to banking API

Security notes:
- All tasks run with tenant context from the run's company.
- Audit logging included for all operations.
- Idempotency: tasks check run status before processing.
- Failed tasks do not automatically retry (manual intervention required).
"""

import logging
from typing import TYPE_CHECKING

from celery import shared_task
from django.db import transaction

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="dividends.process_run",
    max_retries=0,  # No auto-retry; requires manual intervention
    acks_late=True,  # Acknowledge after processing (at-least-once)
)
def process_dividend_run_async(self, run_id: str, user_id: str) -> dict:
    """
    Process a dividend run asynchronously.
    
    Creates dividend allocations for all eligible beneficiaries.
    The run must be in APPROVED status.
    
    Args:
        run_id: UUID of the DividendRun to process.
        user_id: UUID of the user initiating the process.
        
    Returns:
        dict with processing results.
    """
    from apps.accounts.models import User
    from apps.dividends.models import DividendRun, RunStatus
    from apps.dividends.services import process_run, InvalidStateTransition
    
    logger.info("Starting async dividend run processing: %s", run_id)
    
    try:
        run = DividendRun.objects.select_for_update().get(pk=run_id)
        user = User.objects.get(pk=user_id)
    except DividendRun.DoesNotExist:
        logger.error("DividendRun not found: %s", run_id)
        return {"status": "error", "message": f"Run {run_id} not found"}
    except User.DoesNotExist:
        logger.error("User not found: %s", user_id)
        return {"status": "error", "message": f"User {user_id} not found"}
    
    # Idempotency: if already completed, return success
    if run.status == RunStatus.COMPLETED:
        logger.info("Run %s already completed, skipping", run_id)
        return {
            "status": "skipped",
            "message": "Run already completed",
            "allocation_count": run.allocation_count,
        }
    
    # If not in approved status, cannot process
    if run.status != RunStatus.APPROVED:
        logger.warning("Run %s is in %s status, cannot process", run_id, run.status)
        return {
            "status": "error",
            "message": f"Cannot process run in {run.get_status_display()} status",
        }
    
    try:
        run = process_run(run, user=user)
        logger.info(
            "Dividend run %s processed: %d allocations, net R%s",
            run_id, run.allocation_count, run.total_net,
        )
        return {
            "status": "success",
            "allocation_count": run.allocation_count,
            "total_net": str(run.total_net),
        }
    except InvalidStateTransition as e:
        logger.warning("Invalid state transition for run %s: %s", run_id, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception("Failed to process dividend run %s: %s", run_id, e)
        return {"status": "error", "message": str(e)}


@shared_task(
    bind=True,
    name="dividends.submit_payments",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    acks_late=True,
)
def submit_dividend_payments_async(
    self,
    run_id: str,
    user_id: str,
) -> dict:
    """
    Submit dividend payments to banking API.
    
    Iterates over all PENDING allocations and submits EFT payments.
    
    Args:
        run_id: UUID of the completed DividendRun.
        user_id: UUID of the user initiating payments.
        
    Returns:
        dict with payment submission results.
    """
    from decimal import Decimal
    from apps.accounts.models import User
    from apps.audit.models import AuditAction
    from apps.audit.services import log_audit
    from apps.dividends.models import AllocationStatus, DividendRun, RunStatus
    from apps.integrations.banking import BankingClient, PaymentRequest
    
    logger.info("Starting dividend payment submission for run: %s", run_id)
    
    try:
        run = DividendRun.objects.get(pk=run_id)
        user = User.objects.get(pk=user_id)
    except DividendRun.DoesNotExist:
        return {"status": "error", "message": f"Run {run_id} not found"}
    except User.DoesNotExist:
        return {"status": "error", "message": f"User {user_id} not found"}
    
    # Run must be completed before payments
    if run.status != RunStatus.COMPLETED:
        return {
            "status": "error",
            "message": f"Cannot submit payments for run in {run.get_status_display()} status",
        }
    
    client = BankingClient(company=run.company, user=user)
    pending = run.allocations.filter(status=AllocationStatus.PENDING)
    
    submitted = 0
    failed = 0
    
    for alloc in pending:
        ben = alloc.beneficiary
        try:
            request = PaymentRequest(
                beneficiary_id=str(ben.pk),
                amount=alloc.net_amount,
                bank_account=ben.account_number or "",
                bank_code=ben.branch_code or "",
                reference=f"DIV-{run.pk}-{ben.pk}",
            )
            response = client.submit_eft_payment(
                request,
                idempotency_key=f"div-{run.pk}-{alloc.pk}",
            )
            alloc.payment_reference = response.payment_reference
            alloc.status = AllocationStatus.PAID
            alloc.save(update_fields=["status", "payment_reference", "updated_at"])
            submitted += 1
        except Exception as e:
            logger.error("Payment failed for allocation %s: %s", alloc.pk, e)
            alloc.status = AllocationStatus.FAILED
            alloc.save(update_fields=["status", "updated_at"])
            failed += 1
    
    log_audit(
        action=AuditAction.DIVIDEND_ALLOCATION_APPLY,
        user=user,
        company=run.company,
        target_model="DividendRun",
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

