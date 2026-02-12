"""
Integration models for tracking external API calls and responses.
"""

import uuid

from django.conf import settings
from django.db import models

from common.models import TenantScopedModel


class IntegrationSystem(models.TextChoices):
    """External systems we integrate with."""
    PAYROLL = "payroll", "Payroll API"
    SARS = "sars", "SARS e-Filing"
    VELOCITY_TRADE = "velocity_trade", "Velocity Trade"
    BANKING = "banking", "Banking (EFT/NAEDO)"
    JSE = "jse", "JSE"
    SENS = "sens", "SENS"


class IntegrationStatus(models.TextChoices):
    """Status of an integration call."""
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In Progress"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    TIMEOUT = "timeout", "Timeout"
    RETRYING = "retrying", "Retrying"


class IntegrationLog(TenantScopedModel):
    """
    Log of all external API calls for audit and debugging.
    
    Each call to an external system creates a log entry.
    Responses update the same entry.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Which system
    system = models.CharField(
        max_length=20,
        choices=IntegrationSystem.choices,
        db_index=True,
    )

    # What operation
    operation = models.CharField(
        max_length=100,
        help_text="e.g., 'submit_tax_directive', 'sync_employees', 'execute_trade'",
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=IntegrationStatus.choices,
        default=IntegrationStatus.PENDING,
        db_index=True,
    )

    # Request details (sanitised - no secrets)
    request_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sanitised request payload (no secrets/tokens).",
    )

    # Response details
    response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Response payload from external system.",
    )
    response_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code or system-specific code.",
    )

    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Who initiated
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_logs",
    )

    # Reference to related object (e.g., TaxDirective, DividendRun)
    reference_model = models.CharField(max_length=100, blank=True)
    reference_id = models.CharField(max_length=100, blank=True)

    # Idempotency
    idempotency_key = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Unique key to prevent duplicate calls.",
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["company", "system", "status"]),
            models.Index(fields=["system", "operation", "started_at"]),
            models.Index(fields=["reference_model", "reference_id"]),
        ]

    def __str__(self):
        return f"{self.system}:{self.operation} [{self.status}]"

    @property
    def duration_seconds(self):
        """Calculate duration if completed."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def can_retry(self):
        """Check if retry is allowed."""
        return (
            self.status in [IntegrationStatus.FAILED, IntegrationStatus.TIMEOUT]
            and self.retry_count < self.max_retries
        )


class JSECompany(models.Model):
    """
    Static reference data: JSE-listed companies.
    Seeded via management command; enriched with live data from Yahoo Finance.
    NOT tenant-scoped -- this is shared reference data.
    """

    ticker = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        help_text="JSE ticker symbol (e.g. 'SOL', 'NPN', 'ANG').",
    )
    company_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Full registered company name.",
    )
    isin = models.CharField(
        max_length=12,
        blank=True,
        help_text="International Securities Identification Number.",
    )
    sector = models.CharField(
        max_length=100,
        blank=True,
        help_text="JSE sector classification (e.g. 'Mining', 'Financial Services').",
    )
    market_cap_category = models.CharField(
        max_length=20,
        blank=True,
        help_text="Large Cap, Mid Cap, Small Cap, etc.",
    )
    registration_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="CIPC registration number if known.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the listing is currently active on JSE.",
    )
    last_enriched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When live data was last fetched from Yahoo Finance.",
    )
    share_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Last fetched share price in ZAR.",
    )
    market_cap = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Market capitalisation in ZAR.",
    )

    class Meta:
        ordering = ["company_name"]
        verbose_name = "JSE Listed Company"
        verbose_name_plural = "JSE Listed Companies"
        indexes = [
            models.Index(fields=["ticker", "is_active"]),
            models.Index(fields=["company_name", "is_active"]),
        ]

    def __str__(self):
        return f"{self.ticker} - {self.company_name}"

    @property
    def yahoo_ticker(self):
        """Yahoo Finance ticker for JSE stocks uses .JO suffix."""
        return f"{self.ticker}.JO"

