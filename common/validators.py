"""
Secure file upload validators.

Security notes:
- Allowlist-only approach: reject anything not explicitly permitted.
- Magic byte checking prevents MIME spoofing (e.g. .exe renamed to .pdf).
- Filename sanitisation strips path traversal and special characters.
- Size limit enforced before file is fully read into memory.
"""

import os
import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError


# Magic bytes for allowed file types
MAGIC_BYTES = {
    "application/pdf": [b"%PDF"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "text/csv": [],  # CSV has no reliable magic bytes; rely on extension + MIME
}


def validate_file_size(file):
    """Reject files exceeding MAX_UPLOAD_SIZE_MB."""
    max_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10) * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            f"File size {file.size / (1024 * 1024):.1f} MB exceeds "
            f"the {settings.MAX_UPLOAD_SIZE_MB} MB limit."
        )


def validate_file_type(file, *, allowed_types=None):
    """
    Validate file MIME type against an allowlist.
    Uses both the declared content_type and magic byte verification.
    """
    if allowed_types is None:
        allowed_types = getattr(settings, "ALLOWED_UPLOAD_TYPES", [])

    content_type = getattr(file, "content_type", "")
    if content_type not in allowed_types:
        raise ValidationError(
            f"File type '{content_type}' is not allowed. "
            f"Permitted types: {', '.join(allowed_types)}."
        )

    # Magic byte verification (skip for types without reliable magic bytes)
    expected_magic = MAGIC_BYTES.get(content_type, [])
    if expected_magic:
        file.seek(0)
        header = file.read(16)
        file.seek(0)
        if not any(header.startswith(magic) for magic in expected_magic):
            raise ValidationError(
                "File content does not match its declared type. "
                "The file may be corrupted or mislabelled."
            )


def sanitise_filename(filename: str) -> str:
    """
    Sanitise an uploaded filename:
    - Strip directory components (path traversal defence).
    - Remove special characters.
    - Prepend a UUID to prevent collisions and enumeration.
    - Truncate to a safe length.
    """
    # Strip any directory path
    filename = os.path.basename(filename)

    # Extract extension
    name, ext = os.path.splitext(filename)

    # Remove non-alphanumeric characters (keep hyphens and underscores)
    name = re.sub(r"[^\w\-]", "_", name)

    # Truncate the name portion
    name = name[:80]

    # Prepend UUID for uniqueness and anti-enumeration
    safe_name = f"{uuid.uuid4().hex[:12]}_{name}{ext.lower()}"
    return safe_name


def get_upload_path(instance, filename: str) -> str:
    """
    Generate a tenant-scoped upload path.
    Structure: documents/<company_id>/<sanitised_filename>
    This prevents cross-tenant file access at the filesystem level.
    """
    safe_name = sanitise_filename(filename)
    company_id = str(instance.company_id) if instance.company_id else "orphan"
    return f"documents/{company_id}/{safe_name}"

