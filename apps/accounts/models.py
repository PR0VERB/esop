"""
Custom user model for the ESOP platform.
Roles: SCHEME_ADMIN (internal staff) and BENEFICIARY (external portal user).
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    SCHEME_ADMIN = "scheme_admin", "Scheme Admin"
    BENEFICIARY = "beneficiary", "Beneficiary"


class User(AbstractUser):
    """
    Custom user with tenant association and role.
    - Scheme Admins: internal staff, can access all clients.
    - Beneficiaries: external, can only see their own data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.BENEFICIARY,
        db_index=True,
    )

    # Tenant association: NULL for scheme admins who can access all companies
    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        help_text="Company this user belongs to. NULL for internal admin staff.",
    )

    # MFA fields (behind feature flag)
    mfa_secret = models.CharField(max_length=64, blank=True)
    mfa_enabled = models.BooleanField(default=False)

    # Security tracking
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_scheme_admin(self):
        return self.role == UserRole.SCHEME_ADMIN

    @property
    def is_beneficiary(self):
        return self.role == UserRole.BENEFICIARY

    def can_access_company(self, company):
        """
        Scheme admins can access all companies.
        Beneficiaries can only access their own company.
        """
        if self.is_scheme_admin:
            return True
        return self.company_id == company.id

