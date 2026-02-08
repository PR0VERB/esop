"""
Document upload form with security validation.

Security notes:
- File type validated against allowlist (MIME + magic bytes).
- File size validated against MAX_UPLOAD_SIZE_MB.
- Original filename preserved for display but never used for storage.
- SHA-256 hash computed for integrity verification.
"""

import hashlib

from django import forms
from django.conf import settings

from apps.beneficiaries.models import Beneficiary
from common.validators import validate_file_size, validate_file_type

from .models import Document, DocumentCategory


class DocumentUploadForm(forms.ModelForm):
    """Form for uploading a new document."""

    class Meta:
        model = Document
        fields = ["title", "description", "category", "beneficiary", "file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._company = company
        # Scope beneficiary choices to the current company
        if company:
            self.fields["beneficiary"].queryset = (
                Beneficiary.objects.for_tenant(company)
            )
        else:
            self.fields["beneficiary"].queryset = Beneficiary.objects.none()
        self.fields["beneficiary"].required = False
        self.fields["file"].help_text = (
            f"Allowed: PDF, PNG, JPEG. Max size: {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    def clean_file(self):
        """Validate uploaded file type and size."""
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            raise forms.ValidationError("No file was uploaded.")

        # Size check
        validate_file_size(uploaded)

        # Type check (MIME + magic bytes)
        validate_file_type(uploaded)

        return uploaded

    def save(self, commit=True):
        instance = super().save(commit=False)

        uploaded = self.cleaned_data["file"]

        # Store metadata
        instance.original_filename = uploaded.name
        instance.content_type = uploaded.content_type
        instance.file_size = uploaded.size

        # Compute SHA-256 hash for integrity
        sha256 = hashlib.sha256()
        uploaded.seek(0)
        for chunk in uploaded.chunks():
            sha256.update(chunk)
        instance.file_hash = sha256.hexdigest()
        uploaded.seek(0)

        if commit:
            instance.save()
        return instance


class DocumentStatusForm(forms.ModelForm):
    """
    Admin-only form for changing document status.
    Used to approve (quarantine → active) or reject documents.
    """

    class Meta:
        model = Document
        fields = ["status"]

