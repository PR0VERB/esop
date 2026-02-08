"""
Dividend distribution models with state-machine workflow.

State machine for DividendRun:
    DRAFT → APPROVED → PROCESSING → COMPLETED
                                  → FAILED

Security notes:
- All models are tenant-scoped via TenantScopedModel.
- State transitions enforced in the service layer (not in views).
- Idempotency key prevents duplicate runs.
- Amounts stored as DecimalField(max_digits=16, decimal_places=2) for ZAR precision.
- Tax calculations use SA dividend withholding tax rate (20%).
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from common.models import TenantScopedModel


class RunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


# Valid state transitions: {current_state: [allowed_next_states]}
VALID_TRANSITIONS = {
    RunStatus.DRAFT: [RunStatus.APPROVED],
    RunStatus.APPROVED: [RunStatus.PROCESSING, RunStatus.DRAFT],
    RunStatus.PROCESSING: [RunStatus.COMPLETED, RunStatus.FAILED],
    RunStatus.COMPLETED: [],
    RunStatus.FAILED: [RunStatus.DRAFT],
}

# SA Dividend Withholding Tax rate (20% as of 2024/2025)
DEFAULT_DWT_RATE = Decimal("0.20")


class DividendRun(TenantScopedModel):
    """
    A single dividend distribution run for a company.
    Contains the total amount and metadata; individual allocations
    are in DividendAllocation.
    """

    # Descriptive
    title = models.CharField(
        max_length=255,
        help_text="e.g. 'FY2025 Final Dividend'",
    )
    description = models.TextField(blank=True)

    # Financial
    total_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Total dividend pool in ZAR.",
    )
    dividend_per_share = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0.000001"))],
        help_text="Dividend amount per share (ZAR).",
    )
    dwt_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=DEFAULT_DWT_RATE,
        help_text="Dividend Withholding Tax rate (e.g. 0.2000 = 20%).",
    )

    # Dates
    record_date = models.DateField(
        help_text="Date on which share register is frozen for this dividend.",
    )
    ldt_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last Date to Trade. Beneficiaries active on LDT qualify for dividend.",
    )
    payment_date = models.DateField(
        help_text="Date on which payments will be made.",
    )
    declaration_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the dividend was declared by the board.",
    )

    # State machine
    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.DRAFT,
        db_index=True,
    )

    # Idempotency
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique key to prevent duplicate runs (e.g. 'COMPANY-FY2025-FINAL').",
    )

    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dividend_runs_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dividend_runs_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    # Computed totals (populated after processing)
    total_gross = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    total_tax = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    total_net = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
    )
    allocation_count = models.PositiveIntegerField(default=0)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "record_date"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_editable(self) -> bool:
        """Only DRAFT runs can be edited."""
        return self.status == RunStatus.DRAFT

    @property
    def can_approve(self) -> bool:
        return RunStatus.APPROVED in VALID_TRANSITIONS.get(self.status, [])

    @property
    def can_process(self) -> bool:
        return RunStatus.PROCESSING in VALID_TRANSITIONS.get(self.status, [])


class AllocationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"


class DividendAllocation(TenantScopedModel):
    """
    Per-beneficiary allocation within a dividend run.
    Created during the PROCESSING phase.
    Amounts are calculated: gross = shares × dividend_per_share,
    tax = gross × dwt_rate, net = gross − tax.
    """

    run = models.ForeignKey(
        DividendRun,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    beneficiary = models.ForeignKey(
        "beneficiaries.Beneficiary",
        on_delete=models.PROTECT,
        related_name="dividend_allocations",
    )

    # Snapshot of share count at record_date (immutable after creation)
    shares_at_record_date = models.PositiveIntegerField(
        help_text="Number of vested shares held on the record date.",
    )

    # Calculated amounts
    gross_amount = models.DecimalField(max_digits=16, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=16, decimal_places=2)
    net_amount = models.DecimalField(max_digits=16, decimal_places=2)

    # Payment tracking
    status = models.CharField(
        max_length=20,
        choices=AllocationStatus.choices,
        default=AllocationStatus.PENDING,
        db_index=True,
    )
    payment_reference = models.CharField(max_length=100, blank=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["beneficiary__last_name", "beneficiary__first_name"]
        indexes = [
            models.Index(fields=["run", "status"]),
            models.Index(fields=["beneficiary", "run"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "beneficiary"],
                name="unique_allocation_per_beneficiary_per_run",
            ),
        ]

    def __str__(self):
        return (
            f"{self.beneficiary} – R{self.net_amount} "
            f"({self.get_status_display()})"
        )

