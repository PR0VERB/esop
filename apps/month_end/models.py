"""
Month-end processing models with state-machine workflow.

State machine for MonthEndRun:
    DRAFT → APPROVED → PROCESSING → COMPLETED
                                  → FAILED

Security notes:
- All models are tenant-scoped via TenantScopedModel.
- State transitions enforced in the service layer (not in views).
- Idempotency key prevents duplicate runs.
- Amounts stored as DecimalField(max_digits=16, decimal_places=2) for ZAR precision.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from common.models import TenantScopedModel


class MonthEndRunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


# Valid state transitions: {current_state: [allowed_next_states]}
VALID_TRANSITIONS = {
    MonthEndRunStatus.DRAFT: [MonthEndRunStatus.APPROVED],
    MonthEndRunStatus.APPROVED: [MonthEndRunStatus.PROCESSING, MonthEndRunStatus.DRAFT],
    MonthEndRunStatus.PROCESSING: [MonthEndRunStatus.COMPLETED, MonthEndRunStatus.FAILED],
    MonthEndRunStatus.COMPLETED: [],
    MonthEndRunStatus.FAILED: [MonthEndRunStatus.DRAFT],
}


class MonthEndRun(TenantScopedModel):
    """
    A month-end processing run for a company.
    Covers vesting events, share sales, tax directives, and payments.
    """

    # Period covered
    period_year = models.PositiveSmallIntegerField(
        help_text="Year of the period (e.g. 2025).",
    )
    period_month = models.PositiveSmallIntegerField(
        help_text="Month of the period (1-12).",
        validators=[MinValueValidator(1)],
    )
    title = models.CharField(
        max_length=255,
        help_text="e.g. 'January 2025 Month-End'",
    )
    description = models.TextField(blank=True)

    # State machine
    status = models.CharField(
        max_length=20,
        choices=MonthEndRunStatus.choices,
        default=MonthEndRunStatus.DRAFT,
        db_index=True,
    )

    # Idempotency
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique key to prevent duplicate runs (e.g. 'COMPANY-2025-01').",
    )

    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="month_end_runs_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="month_end_runs_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    # Computed totals (populated after processing)
    total_shares_vested = models.PositiveIntegerField(default=0)
    total_shares_sold = models.PositiveIntegerField(default=0)
    total_gross_proceeds = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    total_tax = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    total_net_proceeds = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    vesting_event_count = models.PositiveIntegerField(default=0)
    termination_count = models.PositiveIntegerField(default=0)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-period_year", "-period_month"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "period_year", "period_month"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(period_month__gte=1, period_month__lte=12),
                name="valid_period_month",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_editable(self) -> bool:
        """Only DRAFT runs can be edited."""
        return self.status == MonthEndRunStatus.DRAFT

    @property
    def can_approve(self) -> bool:
        return MonthEndRunStatus.APPROVED in VALID_TRANSITIONS.get(self.status, [])

    @property
    def can_process(self) -> bool:
        return MonthEndRunStatus.PROCESSING in VALID_TRANSITIONS.get(self.status, [])

    @property
    def period_display(self) -> str:
        """Human-readable period string."""
        import calendar
        return f"{calendar.month_name[self.period_month]} {self.period_year}"


class VestingEventType(models.TextChoices):
    """Types of vesting events during month-end processing."""
    SCHEDULED = "scheduled", "Scheduled Vesting"
    SALE = "sale", "Share Sale"
    FORFEITURE = "forfeiture", "Forfeiture (Termination)"
    TRANSFER = "transfer", "Transfer"


class VestingEventStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class VestingEvent(TenantScopedModel):
    """
    Per-beneficiary vesting event within a month-end run.
    Tracks share movement: vesting, sales, forfeitures.
    """

    run = models.ForeignKey(
        MonthEndRun,
        on_delete=models.PROTECT,
        related_name="vesting_events",
    )
    beneficiary = models.ForeignKey(
        "beneficiaries.Beneficiary",
        on_delete=models.PROTECT,
        related_name="vesting_events",
    )

    event_type = models.CharField(
        max_length=20,
        choices=VestingEventType.choices,
        db_index=True,
    )
    event_date = models.DateField(
        help_text="Date when the event occurred or is scheduled.",
    )

    # Share counts
    shares_affected = models.PositiveIntegerField(
        help_text="Number of shares affected by this event.",
    )
    shares_before = models.PositiveIntegerField(
        help_text="Vested shares before this event.",
    )
    shares_after = models.PositiveIntegerField(
        help_text="Vested shares after this event.",
    )

    # Financial (for sales)
    share_price = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Price per share at sale (ZAR).",
    )
    gross_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    tax_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    net_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=VestingEventStatus.choices,
        default=VestingEventStatus.PENDING,
        db_index=True,
    )
    notes = models.TextField(blank=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-event_date", "beneficiary__last_name"]
        indexes = [
            models.Index(fields=["run", "event_type"]),
            models.Index(fields=["beneficiary", "event_date"]),
        ]

    def __str__(self):
        return (
            f"{self.beneficiary} – {self.get_event_type_display()} "
            f"({self.shares_affected} shares)"
        )


class TaxDirectiveStatus(models.TextChoices):
    """Status of SARS tax directive request."""
    PENDING = "pending", "Pending"
    REQUESTED = "requested", "Requested from SARS"
    RECEIVED = "received", "Received"
    DECLINED = "declined", "Declined by SARS"
    NOT_REQUIRED = "not_required", "Not Required"


class TaxDirective(TenantScopedModel):
    """
    Tax directive for a beneficiary's share transaction.
    Required by SARS for certain share disposals.
    """

    run = models.ForeignKey(
        MonthEndRun,
        on_delete=models.PROTECT,
        related_name="tax_directives",
        null=True,
        blank=True,
        help_text="Associated month-end run (optional).",
    )
    beneficiary = models.ForeignKey(
        "beneficiaries.Beneficiary",
        on_delete=models.PROTECT,
        related_name="tax_directives",
    )

    # SARS reference
    directive_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="SARS tax directive number once received.",
    )
    tax_year = models.PositiveSmallIntegerField(
        help_text="Tax year (e.g. 2025 for 2024/2025 tax year).",
    )

    # Request details
    request_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date directive was requested from SARS.",
    )
    response_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date response was received from SARS.",
    )

    # Tax calculation
    taxable_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
        help_text="Taxable amount as per SARS directive.",
    )
    directive_rate = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="Tax rate specified in directive (e.g. 0.3500 = 35%).",
    )
    calculated_tax = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
        help_text="Tax calculated per directive.",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=TaxDirectiveStatus.choices,
        default=TaxDirectiveStatus.PENDING,
        db_index=True,
    )
    decline_reason = models.TextField(
        blank=True,
        help_text="Reason if directive was declined by SARS.",
    )
    notes = models.TextField(blank=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-request_date", "beneficiary__last_name"]
        indexes = [
            models.Index(fields=["beneficiary", "tax_year"]),
            models.Index(fields=["status", "request_date"]),
        ]

    def __str__(self):
        return (
            f"{self.beneficiary} – Tax Directive {self.tax_year} "
            f"({self.get_status_display()})"
        )

