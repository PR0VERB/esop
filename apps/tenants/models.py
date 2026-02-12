"""
Tenant (Company) model.
Every client of the ESOP platform is a Company.
All tenant-owned data is scoped by company_id.
"""

from common.models import BaseModel
from django.db import models


class Company(BaseModel):
    """
    A client company that uses the ESOP platform.
    This is the tenant boundary.
    """

    name = models.CharField(max_length=255)
    registration_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Company registration number (e.g. CIPC number).",
    )
    tax_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Company tax reference number.",
    )
    is_active = models.BooleanField(default=True)

    # ESOP scheme details
    scheme_name = models.CharField(max_length=255, blank=True)
    trust_name = models.CharField(max_length=255, blank=True)
    trust_bank_account = models.CharField(
        max_length=50,
        blank=True,
        help_text="Trust bank account number for dividend distributions.",
    )

    # JSE listing details (optional — only for JSE-listed companies)
    jse_ticker = models.CharField(
        max_length=10,
        blank=True,
        help_text="JSE ticker symbol if the company is listed.",
    )
    jse_isin = models.CharField(
        max_length=12,
        blank=True,
        help_text="ISIN code for the company's listed shares.",
    )
    sector = models.CharField(
        max_length=100,
        blank=True,
        help_text="Industry sector (e.g. 'Mining', 'Technology').",
    )

    class Meta(BaseModel.Meta):
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self):
        return self.name

