"""
Document model – tenant-scoped, secure file storage.

Security notes:
- Files are NEVER served directly via MEDIA_URL. All downloads go through
  a view that checks permissions and streams the file.
- Upload path is tenant-scoped: documents/<company_id>/<sanitised_name>.
- Content type and magic bytes are validated on upload.
- Quarantine status allows a malware-scan step before files are accessible.
- Soft-delete via status; no hard deletion from the application layer.
"""

from django.conf import settings
from django.db import models

from common.models import TenantScopedModel
from common.validators import get_upload_path


class DocumentCategory(models.TextChoices):
    """Categories for organising documents."""
    TRUST_DEED = "trust_deed", "Trust Deed"
    SCHEME_RULES = "scheme_rules", "Scheme Rules"
    TAX_CERTIFICATE = "tax_certificate", "Tax Certificate"
    PAYMENT_FILE = "payment_file", "Payment File"
    BOARD_RESOLUTION = "board_resolution", "Board Resolution"
    BENEFICIARY_ID = "beneficiary_id", "Beneficiary ID Document"
    BENEFICIARY_PROOF = "beneficiary_proof", "Beneficiary Proof of Banking"
    DIVIDEND_REPORT = "dividend_report", "Dividend Report"
    MONTH_END_REPORT = "month_end_report", "Month-End Report"
    SARS_SUBMISSION = "sars_submission", "SARS Submission"
    OTHER = "other", "Other"


class DocumentStatus(models.TextChoices):
    """Lifecycle status of a document."""
    QUARANTINE = "quarantine", "Quarantine (pending scan)"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"
    REJECTED = "rejected", "Rejected (failed scan)"


class Document(TenantScopedModel):
    """
    A file uploaded to the platform, scoped to a company.
    Optionally linked to a specific beneficiary.
    """

    # Ownership
    beneficiary = models.ForeignKey(
        "beneficiaries.Beneficiary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        help_text="Beneficiary this document relates to (optional).",
    )

    # File storage
    file = models.FileField(
        upload_to=get_upload_path,
        max_length=500,
        help_text="Uploaded file. Served only through authenticated download view.",
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename as uploaded by the user.",
    )
    content_type = models.CharField(
        max_length=100,
        help_text="MIME type of the uploaded file.",
    )
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes.",
    )
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of file contents for integrity verification.",
    )

    # Metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=DocumentCategory.choices,
        default=DocumentCategory.OTHER,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.QUARANTINE,
        db_index=True,
    )

    # Who uploaded
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
    )

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "category"]),
            models.Index(fields=["company", "status"]),
            models.Index(fields=["beneficiary", "category"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

    @property
    def is_accessible(self) -> bool:
        """Only active documents can be downloaded."""
        return self.status == DocumentStatus.ACTIVE

    @property
    def size_display(self) -> str:
        """Human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        return f"{self.file_size / (1024 * 1024):.1f} MB"

