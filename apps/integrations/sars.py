"""
SARS e-Filing integration client (STUB).

Provides stub implementations for:
- Submitting tax directives
- Checking directive status
- Bulk directive submissions
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from apps.integrations.base import BaseIntegrationClient
from apps.integrations.models import IntegrationStatus, IntegrationSystem


class DirectiveStatus(str, Enum):
    """Status of a SARS tax directive."""
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"


@dataclass
class TaxDirectiveRequest:
    """Request to submit a tax directive to SARS."""
    beneficiary_id: str
    id_number: str
    tax_number: str
    gross_amount: Decimal
    tax_year: int
    directive_type: str = "IT88"  # Lump sum benefit


@dataclass
class TaxDirectiveResponse:
    """Response from SARS for a tax directive."""
    reference_number: str
    status: DirectiveStatus
    tax_rate: Optional[Decimal] = None
    message: str = ""


class SARSClient(BaseIntegrationClient):
    """
    SARS e-Filing client (STUB implementation).
    
    In production, this would connect to SARS e-Filing API.
    For now, returns mock data and logs all calls.
    """

    system = IntegrationSystem.SARS

    def health_check(self) -> bool:
        """Check if SARS API is reachable."""
        log = self._create_log("health_check", {})
        # STUB: Always return True
        self._complete_log(log, status=IntegrationStatus.SUCCESS, response_code=200)
        return True

    def submit_tax_directive(
        self,
        request: TaxDirectiveRequest,
        *,
        idempotency_key: str = "",
    ) -> TaxDirectiveResponse:
        """
        Submit a tax directive request to SARS.
        
        STUB: Returns a mock pending response.
        """
        log = self._create_log(
            "submit_tax_directive",
            {
                "beneficiary_id": request.beneficiary_id,
                "gross_amount": str(request.gross_amount),
                "tax_year": request.tax_year,
                "directive_type": request.directive_type,
            },
            reference_model="beneficiaries.Beneficiary",
            reference_id=request.beneficiary_id,
            idempotency_key=idempotency_key,
        )
        
        # STUB: Generate mock reference number
        mock_ref = f"SARS-{request.tax_year}-{request.beneficiary_id[:8]}"
        
        response = TaxDirectiveResponse(
            reference_number=mock_ref,
            status=DirectiveStatus.PENDING,
            message="Directive submitted successfully (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "reference_number": response.reference_number,
                "status": response.status.value,
            },
            response_code=200,
        )
        return response

    def get_directive_status(self, reference_number: str) -> TaxDirectiveResponse:
        """
        Check status of a previously submitted directive.
        
        STUB: Returns approved status with default tax rate.
        """
        log = self._create_log(
            "get_directive_status",
            {"reference_number": reference_number},
        )
        
        # STUB: Return approved with 35% rate
        response = TaxDirectiveResponse(
            reference_number=reference_number,
            status=DirectiveStatus.APPROVED,
            tax_rate=Decimal("0.35"),
            message="Directive approved (STUB)",
        )
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={
                "reference_number": response.reference_number,
                "status": response.status.value,
                "tax_rate": str(response.tax_rate),
            },
            response_code=200,
        )
        return response

    def bulk_submit_directives(
        self,
        requests: List[TaxDirectiveRequest],
    ) -> List[TaxDirectiveResponse]:
        """
        Submit multiple tax directives in bulk.
        
        STUB: Returns mock responses for each request.
        """
        log = self._create_log(
            "bulk_submit_directives",
            {"count": len(requests)},
        )
        
        responses = []
        for req in requests:
            mock_ref = f"SARS-{req.tax_year}-{req.beneficiary_id[:8]}"
            responses.append(TaxDirectiveResponse(
                reference_number=mock_ref,
                status=DirectiveStatus.PENDING,
                message="Directive submitted (STUB)",
            ))
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={"submitted_count": len(responses)},
            response_code=200,
        )
        return responses

