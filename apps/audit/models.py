"""
Immutable audit log for all sensitive actions.
AuditLog entries are append-only: no update, no delete (except retention pruning).
"""

import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    # Authentication
    LOGIN_SUCCESS = "login_success", "Login Success"
    LOGIN_FAILED = "login_failed", "Login Failed"
    LOGOUT = "logout", "Logout"
    PASSWORD_CHANGE = "password_change", "Password Change"
    MFA_ENABLED = "mfa_enabled", "MFA Enabled"
    MFA_DISABLED = "mfa_disabled", "MFA Disabled"

    # Beneficiary data
    BENEFICIARY_CREATE = "beneficiary_create", "Beneficiary Created"
    BENEFICIARY_UPDATE = "beneficiary_update", "Beneficiary Updated"
    BENEFICIARY_DELETE = "beneficiary_delete", "Beneficiary Deleted"
    BANK_DETAIL_CHANGE = "bank_detail_change", "Bank Detail Changed"

    # Dividend runs
    DIVIDEND_RUN_CREATE = "dividend_run_create", "Dividend Run Created"
    DIVIDEND_RUN_STATE_CHANGE = "dividend_run_state_change", "Dividend Run State Change"
    DIVIDEND_ALLOCATION_APPLY = "dividend_allocation_apply", "Dividend Allocation Applied"

    # Month-end runs
    MONTH_END_RUN_CREATE = "month_end_run_create", "Month-End Run Created"
    MONTH_END_RUN_STATE_CHANGE = "month_end_run_state_change", "Month-End Run State Change"

    # Files
    FILE_UPLOAD = "file_upload", "File Uploaded"
    FILE_DOWNLOAD = "file_download", "File Downloaded"
    PAYMENT_FILE_GENERATED = "payment_file_generated", "Payment File Generated"

    # Manual overrides
    MANUAL_OVERRIDE = "manual_override", "Manual Override"

    # Integration
    INTEGRATION_CALL = "integration_call", "Integration Call"
    INTEGRATION_RESPONSE = "integration_response", "Integration Response"


class AuditLog(models.Model):
    """
    Immutable audit trail. No update or delete operations allowed
    except via the retention management command.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Who
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # What
    action = models.CharField(max_length=50, choices=AuditAction.choices, db_index=True)

    # Context
    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    target_model = models.CharField(max_length=100, blank=True, db_index=True)
    target_id = models.CharField(max_length=100, blank=True)

    # Details (flexible JSON payload)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["company", "action", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["target_model", "target_id"]),
        ]
        # Prevent accidental updates at the Django level
        # (DB-level trigger recommended for production)

    def __str__(self):
        return f"[{self.timestamp}] {self.action} by {self.user}"

    def save(self, *args, **kwargs):
        """Only allow creation, not updates."""
        if not kwargs.get("force_insert", False) and self._state.adding is False:
            raise ValueError("AuditLog entries are immutable. Cannot update.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Block manual deletion. Use management command for retention."""
        raise ValueError("AuditLog entries cannot be deleted directly. Use prune_audit_logs command.")

