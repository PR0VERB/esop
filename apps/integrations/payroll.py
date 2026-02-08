"""
Payroll API integration client (STUB).

Provides stub implementations for:
- Syncing employee/beneficiary data
- Retrieving new hires, terminations, promotions
- Updating IRP5 information
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from apps.integrations.base import BaseIntegrationClient
from apps.integrations.models import IntegrationStatus, IntegrationSystem


@dataclass
class EmployeeData:
    """Employee data from payroll system."""
    employee_id: str
    id_number: str
    first_name: str
    last_name: str
    email: str
    department: str
    job_title: str
    start_date: date
    termination_date: Optional[date] = None
    tax_number: str = ""


class PayrollClient(BaseIntegrationClient):
    """
    Payroll API client (STUB implementation).
    
    In production, this would connect to the actual payroll system API.
    For now, returns mock data and logs all calls.
    """

    system = IntegrationSystem.PAYROLL

    def health_check(self) -> bool:
        """Check if payroll API is reachable."""
        log = self._create_log("health_check", {})
        # STUB: Always return True
        self._complete_log(log, status=IntegrationStatus.SUCCESS, response_code=200)
        return True

    def get_active_employees(self) -> List[EmployeeData]:
        """
        Retrieve all active employees from payroll.
        
        STUB: Returns empty list. In production, would call payroll API.
        """
        log = self._create_log("get_active_employees", {})
        
        # STUB: Return empty list (no mock data by default)
        result = []
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={"count": len(result)},
            response_code=200,
        )
        return result

    def get_employee_updates(self, since_date: date) -> dict:
        """
        Get employee changes since a given date.
        
        Returns dict with keys: new_hires, terminations, promotions
        
        STUB: Returns empty lists. In production, would call payroll API.
        """
        log = self._create_log(
            "get_employee_updates",
            {"since_date": since_date.isoformat()},
        )
        
        # STUB: Return empty changes
        result = {
            "new_hires": [],
            "terminations": [],
            "promotions": [],
        }
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data=result,
            response_code=200,
        )
        return result

    def get_terminations(self, since_date: date) -> List[dict]:
        """
        Get terminated employees since a given date.
        
        STUB: Returns empty list.
        """
        log = self._create_log(
            "get_terminations",
            {"since_date": since_date.isoformat()},
        )
        
        result = []
        
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={"count": len(result)},
            response_code=200,
        )
        return result

    def upload_irp5_data(self, beneficiary_id: str, tax_year: int, data: dict) -> bool:
        """
        Upload IRP5 data for a beneficiary to payroll system.
        
        STUB: Returns True, logs the request.
        """
        log = self._create_log(
            "upload_irp5_data",
            {
                "beneficiary_id": beneficiary_id,
                "tax_year": tax_year,
                "data_keys": list(data.keys()),
            },
            reference_model="beneficiaries.Beneficiary",
            reference_id=beneficiary_id,
        )
        
        # STUB: Always succeed
        self._complete_log(
            log,
            status=IntegrationStatus.SUCCESS,
            response_data={"uploaded": True},
            response_code=200,
        )
        return True

