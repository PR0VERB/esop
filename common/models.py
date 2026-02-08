"""
Base model classes for the ESOP platform.
All tenant-owned models inherit from TenantScopedModel.
"""

import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Abstract base for all models.
    Provides UUID pk, created/updated timestamps.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class TenantScopedManager(models.Manager):
    """
    Manager that can filter by company_id.
    Views/services MUST call .for_tenant(company) to scope queries.
    This is a safety net, not a substitute for explicit checks.
    """

    def for_tenant(self, company):
        return self.get_queryset().filter(company=company)


class TenantScopedModel(BaseModel):
    """
    Abstract base for all tenant-owned models.
    Every row belongs to exactly one company.
    """

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    objects = TenantScopedManager()

    class Meta(BaseModel.Meta):
        abstract = True

