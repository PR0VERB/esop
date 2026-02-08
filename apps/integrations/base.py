"""
Base integration client with common functionality.

All integration clients inherit from this and implement
the abstract methods for their specific external system.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.integrations.models import IntegrationLog, IntegrationStatus, IntegrationSystem
from apps.tenants.models import Company

logger = logging.getLogger(__name__)


class BaseIntegrationClient(ABC):
    """
    Abstract base class for all integration clients.
    
    Provides common functionality:
    - Logging of all API calls
    - Error handling with retry support
    - Request/response sanitisation
    - Idempotency key support
    """

    # Subclasses must define these
    system: IntegrationSystem = None
    
    def __init__(self, company: Company, user=None):
        """
        Initialise the client.
        
        Args:
            company: The tenant company for scoping
            user: The user initiating the calls (optional)
        """
        if self.system is None:
            raise NotImplementedError("Subclass must define 'system' class attribute")
        self.company = company
        self.user = user

    def _create_log(
        self,
        operation: str,
        request_data: dict,
        *,
        reference_model: str = "",
        reference_id: str = "",
        idempotency_key: str = "",
    ) -> IntegrationLog:
        """Create an integration log entry for tracking the call."""
        sanitised = self._sanitise_request(request_data)
        return IntegrationLog.objects.create(
            company=self.company,
            system=self.system,
            operation=operation,
            status=IntegrationStatus.IN_PROGRESS,
            request_data=sanitised,
            initiated_by=self.user,
            reference_model=reference_model,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )

    def _complete_log(
        self,
        log: IntegrationLog,
        *,
        status: IntegrationStatus,
        response_data: dict = None,
        response_code: int = None,
        error_message: str = "",
    ) -> IntegrationLog:
        """Update log entry with response details."""
        log.status = status
        log.response_data = response_data or {}
        log.response_code = response_code
        log.error_message = error_message
        log.completed_at = timezone.now()
        log.save(update_fields=[
            "status", "response_data", "response_code",
            "error_message", "completed_at", "updated_at",
        ])
        return log

    def _sanitise_request(self, data: dict) -> dict:
        """Remove sensitive fields from request data before logging."""
        if not data:
            return {}
        sanitised = data.copy()
        sensitive_keys = {
            "password", "token", "secret", "api_key", "auth",
            "credential", "private_key", "access_token", "refresh_token",
            "id_number", "bank_account", "account_number",
        }
        for key in list(sanitised.keys()):
            if any(s in key.lower() for s in sensitive_keys):
                sanitised[key] = "***REDACTED***"
        return sanitised

    def _handle_error(
        self,
        log: IntegrationLog,
        error: Exception,
        *,
        allow_retry: bool = True,
    ) -> IntegrationLog:
        """Handle errors and update log accordingly."""
        error_msg = str(error)
        logger.error(f"Integration error [{self.system}]: {error_msg}")
        
        if allow_retry and log.can_retry:
            log.retry_count += 1
            log.status = IntegrationStatus.RETRYING
            log.error_message = error_msg
            log.save(update_fields=["retry_count", "status", "error_message", "updated_at"])
        else:
            self._complete_log(
                log,
                status=IntegrationStatus.FAILED,
                error_message=error_msg,
            )
        return log

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the external system is reachable."""
        pass

