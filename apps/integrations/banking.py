"""
Banking integration client (STUB).

Provides stub implementations for:
- EFT (Electronic Funds Transfer) payments
- NAEDO (Non-Authenticated Early Debit Order) payments
- Transaction status queries
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from apps.integrations.base import BaseIntegrationClient
from apps.integrations.models import IntegrationStatus, IntegrationSystem


class PaymentStatus(str, Enum):
    """Status of a bank payment."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class PaymentType(str, Enum):
    """Type of bank payment."""
    EFT = "eft"
    NAEDO = "naedo"
    RTGS = "rtgs"  # Real-Time Gross Settlement


@dataclass
class PaymentRequest:
    """Request to submit a bank payment."""
    beneficiary_id: str
    amount: Decimal
    bank_account: str  # Will be redacted in logs
    bank_code: str
    reference: str
    payment_type: PaymentType = PaymentType.EFT


@dataclass
class PaymentResponse:
    """Response from payment submission."""
    payment_reference: str
    status: PaymentStatus
    submitted_at: Optional[datetime] = None
    message: str = ""


@dataclass
class BulkPaymentRequest:
    """Request for bulk payment file upload."""
    payments: List[PaymentRequest]
    batch_reference: str
    payment_date: date


class BankingClient(BaseIntegrationClient):
    """
    Banking client (STUB implementation).
    
    In production, this would connect to bank APIs (e.g., Standard Bank, Nedbank).
    For now, returns mock data and logs all calls.
    """

    system = IntegrationSystem.BANKING

    def health_check(self) -> bool:
        """Check if banking API is reachable."""
        log = self._create_log("health_check", {})
        self._complete_log(log, status=IntegrationStatus.SUCCESS, response_code=200)
        return True

    def submit_eft_payment(
        self,
        request: PaymentRequest,
        *,
        idempotency_key: str = "",
    ) -> PaymentResponse:
        """
        Submit an EFT payment.
        
        STUB: Returns mock pending response.
        """
        log = self._create_log(
            "submit_eft_payment",
            {
                "beneficiary_id": request.beneficiary_id,
                "amount": str(request.amount),
                "bank_code": request.bank_code,
                "reference": request.reference,
                "bank_account": request.bank_account,  # Will be redacted by _sanitise_request
            },
            reference_model="beneficiaries.Beneficiary",
            reference_id=request.beneficiary_id,
            idempotency_key=idempotency_key,
        )
        
        # STUB: Generate mock payment reference
        mock_ref = f"EFT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        response = PaymentResponse(
            payment_reference=mock_ref,
            status=PaymentStatus.PENDING,
            submitted_at=datetime.now(),
            message="Payment submitted (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "payment_reference": response.payment_reference,
                "status": response.status.value,
            },
            response_code=200,
        )
        return response

    def submit_naedo_payment(
        self,
        request: PaymentRequest,
        *,
        idempotency_key: str = "",
    ) -> PaymentResponse:
        """
        Submit a NAEDO payment.
        
        STUB: Returns mock pending response.
        """
        log = self._create_log(
            "submit_naedo_payment",
            {
                "beneficiary_id": request.beneficiary_id,
                "amount": str(request.amount),
                "bank_code": request.bank_code,
                "reference": request.reference,
            },
            reference_model="beneficiaries.Beneficiary",
            reference_id=request.beneficiary_id,
            idempotency_key=idempotency_key,
        )
        
        mock_ref = f"NAEDO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        response = PaymentResponse(
            payment_reference=mock_ref,
            status=PaymentStatus.PENDING,
            submitted_at=datetime.now(),
            message="NAEDO payment submitted (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "payment_reference": response.payment_reference,
                "status": response.status.value,
            },
            response_code=200,
        )
        return response

    def get_payment_status(self, payment_reference: str) -> PaymentResponse:
        """
        Check status of a submitted payment.
        
        STUB: Returns completed status.
        """
        log = self._create_log(
            "get_payment_status",
            {"payment_reference": payment_reference},
        )
        
        response = PaymentResponse(
            payment_reference=payment_reference,
            status=PaymentStatus.COMPLETED,
            message="Payment completed (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "payment_reference": response.payment_reference,
                "status": response.status.value,
            },
            response_code=200,
        )
        return response

