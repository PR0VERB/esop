"""
Beneficiary model – tenant-scoped, with encrypted PII fields.

Security notes:
- id_number and account_number are stored encrypted at rest (Fernet).
- All queries MUST be scoped via .for_tenant(company) or permission mixins.
- Status transitions are enforced in the service layer.
"""

from django.conf import settings
from django.db import models

from common.encryption import decrypt_value, encrypt_value
from common.models import TenantScopedModel


class BeneficiaryStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    SUSPENDED = "suspended", "Suspended"
    TERMINATED = "terminated", "Terminated"


class LeaverType(models.TextChoices):
    """
    Classification for terminated beneficiaries.
    Good Leavers: retirement, retrenchment, death, disability.
    Bad Leavers: resignation, dismissal for cause.
    """
    GOOD = "good", "Good Leaver"
    BAD = "bad", "Bad Leaver"


class BankAccountType(models.TextChoices):
    SAVINGS = "savings", "Savings"
    CHEQUE = "cheque", "Cheque / Current"
    TRANSMISSION = "transmission", "Transmission"


class Beneficiary(TenantScopedModel):
    """
    A beneficiary in the ESOP scheme.
    Belongs to exactly one company (tenant).
    Optionally linked to a User account for portal access.
    """

    # Link to user account (optional – not all beneficiaries have portal access)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficiary_profile",
        help_text="Portal user account. NULL if beneficiary has no login.",
    )

    # Personal information
    employee_number = models.CharField(max_length=50, blank=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    id_number_encrypted = models.TextField(
        blank=True,
        help_text="SA ID number – stored encrypted.",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    tax_number = models.CharField(max_length=20, blank=True)

    # Bank details (encrypted fields)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number_encrypted = models.TextField(
        blank=True,
        help_text="Bank account number – stored encrypted.",
    )
    account_type = models.CharField(
        max_length=20,
        choices=BankAccountType.choices,
        blank=True,
    )
    branch_code = models.CharField(max_length=10, blank=True)

    # Share allocation
    total_shares = models.PositiveIntegerField(default=0)
    vested_shares = models.PositiveIntegerField(default=0)
    unvested_shares = models.PositiveIntegerField(default=0)

    # Status
    status = models.CharField(
        max_length=20,
        choices=BeneficiaryStatus.choices,
        default=BeneficiaryStatus.ACTIVE,
        db_index=True,
    )
    leaver_type = models.CharField(
        max_length=10,
        choices=LeaverType.choices,
        blank=True,
        help_text="Set when status is TERMINATED. Good/Bad leaver affects dividend treatment.",
    )

    # Important dates
    employment_date = models.DateField(null=True, blank=True)
    scheme_join_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        verbose_name_plural = "beneficiaries"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "last_name", "first_name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_number"],
                name="unique_employee_per_company",
                condition=models.Q(employee_number__gt=""),
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_number})"

    # -----------------------------------------------------------------------
    # Encrypted field helpers
    # -----------------------------------------------------------------------
    @property
    def id_number(self) -> str:
        """Decrypt and return the SA ID number."""
        return decrypt_value(self.id_number_encrypted)

    @id_number.setter
    def id_number(self, value: str):
        """Encrypt and store the SA ID number."""
        self.id_number_encrypted = encrypt_value(value) if value else ""

    @property
    def account_number(self) -> str:
        """Decrypt and return the bank account number."""
        return decrypt_value(self.account_number_encrypted)

    @account_number.setter
    def account_number(self, value: str):
        """Encrypt and store the bank account number."""
        self.account_number_encrypted = encrypt_value(value) if value else ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        return self.status == BeneficiaryStatus.ACTIVE

    def clean(self):
        """Model-level validation."""
        super().clean()
        if self.vested_shares + self.unvested_shares != self.total_shares:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                "vested_shares + unvested_shares must equal total_shares."
            )

