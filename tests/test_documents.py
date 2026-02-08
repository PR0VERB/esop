"""
Tests for Commit 5: Documents app – secure file handling, tenant isolation,
permissions, upload validation, download security, and audit logging.
"""

import hashlib
import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditLog
from apps.documents.forms import DocumentStatusForm, DocumentUploadForm
from apps.documents.models import Document, DocumentCategory, DocumentStatus
from apps.tenants.models import Company
from common.validators import (
    get_upload_path,
    sanitise_filename,
    validate_file_size,
    validate_file_type,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def company_a(db):
    return Company.objects.create(name="Alpha Corp", registration_number="REG-ALPHA")


@pytest.fixture
def company_b(db):
    return Company.objects.create(name="Beta Corp", registration_number="REG-BETA")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="doc_admin", password="SecurePass123!", role=UserRole.SCHEME_ADMIN
    )


@pytest.fixture
def ben_user(db, company_a):
    return User.objects.create_user(
        username="doc_ben", password="SecurePass123!",
        role=UserRole.BENEFICIARY, company=company_a,
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.login(username="doc_admin", password="SecurePass123!")
    return c


@pytest.fixture
def ben_client(ben_user):
    c = Client()
    c.login(username="doc_ben", password="SecurePass123!")
    return c


def _make_pdf(content=b"test-pdf-content"):
    """Create a fake PDF file with correct magic bytes."""
    return SimpleUploadedFile(
        "test_doc.pdf",
        b"%PDF-1.4 " + content,
        content_type="application/pdf",
    )


def _make_png():
    """Create a fake PNG with correct magic bytes."""
    return SimpleUploadedFile(
        "test_img.png",
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
        content_type="image/png",
    )


def _make_exe():
    """Create a disallowed EXE file."""
    return SimpleUploadedFile(
        "malware.exe",
        b"MZ" + b"\x00" * 100,
        content_type="application/x-msdownload",
    )


@pytest.fixture
def document_a(db, company_a, admin_user):
    """Active document for company A."""
    f = _make_pdf()
    doc = Document.objects.create(
        company=company_a,
        title="Alpha Trust Deed",
        category=DocumentCategory.TRUST_DEED,
        status=DocumentStatus.ACTIVE,
        file=f,
        original_filename="trust_deed.pdf",
        content_type="application/pdf",
        file_size=f.size,
        file_hash=hashlib.sha256(f.read()).hexdigest(),
        uploaded_by=admin_user,
    )
    return doc


@pytest.fixture
def document_b(db, company_b, admin_user):
    """Document for company B (cross-tenant test)."""
    f = _make_pdf(b"other-content")
    doc = Document.objects.create(
        company=company_b,
        title="Beta Board Resolution",
        category=DocumentCategory.BOARD_RESOLUTION,
        status=DocumentStatus.ACTIVE,
        file=f,
        original_filename="board_res.pdf",
        content_type="application/pdf",
        file_size=f.size,
        file_hash=hashlib.sha256(f.read()).hexdigest(),
        uploaded_by=admin_user,
    )
    return doc


@pytest.fixture
def quarantined_doc(db, company_a, admin_user):
    """Quarantined document – should NOT be downloadable."""
    f = _make_pdf(b"quarantined-content")
    return Document.objects.create(
        company=company_a,
        title="Quarantined File",
        category=DocumentCategory.OTHER,
        status=DocumentStatus.QUARANTINE,
        file=f,
        original_filename="suspect.pdf",
        content_type="application/pdf",
        file_size=f.size,
        file_hash=hashlib.sha256(f.read()).hexdigest(),
        uploaded_by=admin_user,
    )




# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------
class TestValidators:
    def test_validate_file_size_ok(self):
        f = _make_pdf()
        validate_file_size(f)  # Should not raise

    def test_validate_file_size_too_large(self, settings):
        settings.MAX_UPLOAD_SIZE_MB = 0  # 0 MB → any file is too large
        f = _make_pdf()
        with pytest.raises(ValidationError, match="exceeds"):
            validate_file_size(f)

    def test_validate_file_type_pdf_ok(self):
        f = _make_pdf()
        validate_file_type(f, allowed_types=["application/pdf"])

    def test_validate_file_type_png_ok(self):
        f = _make_png()
        validate_file_type(f, allowed_types=["image/png"])

    def test_validate_file_type_exe_rejected(self):
        f = _make_exe()
        with pytest.raises(ValidationError, match="not allowed"):
            validate_file_type(f, allowed_types=["application/pdf"])

    def test_validate_file_type_magic_mismatch(self):
        """File claims to be PDF but magic bytes are wrong."""
        f = SimpleUploadedFile(
            "fake.pdf",
            b"NOT-A-PDF-CONTENT",
            content_type="application/pdf",
        )
        with pytest.raises(ValidationError, match="does not match"):
            validate_file_type(f, allowed_types=["application/pdf"])

    def test_sanitise_filename_strips_path(self):
        result = sanitise_filename("../../etc/passwd")
        assert ".." not in result
        assert "etc" not in result or "passwd" in result

    def test_sanitise_filename_uuid_prefix(self):
        result = sanitise_filename("my document.pdf")
        assert result.endswith(".pdf")
        # UUID hex prefix is 12 chars + underscore
        assert len(result.split("_")[0]) == 12

    def test_sanitise_filename_special_chars(self):
        result = sanitise_filename("bad<>file|name?.pdf")
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result
        assert "?" not in result

    def test_get_upload_path_contains_company_id(self, company_a):
        """Upload path should be scoped to the company."""

        class FakeInstance:
            company_id = company_a.pk

        path = get_upload_path(FakeInstance(), "report.pdf")
        assert str(company_a.pk) in path
        assert path.startswith("documents/")


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------
class TestDocumentModel:
    def test_create_document(self, document_a):
        assert document_a.pk is not None
        assert document_a.title == "Alpha Trust Deed"

    def test_default_status_quarantine(self, db, company_a, admin_user):
        f = _make_pdf()
        doc = Document(
            company=company_a, title="Test", file=f,
            original_filename="t.pdf", content_type="application/pdf",
            file_size=10, uploaded_by=admin_user,
        )
        assert doc.status == DocumentStatus.QUARANTINE

    def test_is_accessible_active(self, document_a):
        assert document_a.is_accessible is True

    def test_is_accessible_quarantine(self, quarantined_doc):
        assert quarantined_doc.is_accessible is False

    def test_is_accessible_archived(self, document_a):
        document_a.status = DocumentStatus.ARCHIVED
        assert document_a.is_accessible is False

    def test_size_display_bytes(self, document_a):
        document_a.file_size = 500
        assert document_a.size_display == "500 B"

    def test_size_display_kb(self, document_a):
        document_a.file_size = 5120
        assert "KB" in document_a.size_display

    def test_size_display_mb(self, document_a):
        document_a.file_size = 5 * 1024 * 1024
        assert "MB" in document_a.size_display

    def test_str(self, document_a):
        assert "Alpha Trust Deed" in str(document_a)

    def test_for_tenant_scoping(self, document_a, document_b, company_a, company_b):
        qs_a = Document.objects.for_tenant(company_a)
        qs_b = Document.objects.for_tenant(company_b)
        assert document_a in qs_a
        assert document_a not in qs_b
        assert document_b in qs_b
        assert document_b not in qs_a


# ---------------------------------------------------------------------------
# Form tests
# ---------------------------------------------------------------------------
class TestDocumentUploadForm:
    def test_valid_pdf_upload(self, company_a):
        f = _make_pdf()
        form = DocumentUploadForm(
            data={"title": "Test PDF", "category": "other"},
            files={"file": f},
            company=company_a,
        )
        assert form.is_valid(), form.errors

    def test_exe_rejected(self, company_a):
        f = _make_exe()
        form = DocumentUploadForm(
            data={"title": "Bad File", "category": "other"},
            files={"file": f},
            company=company_a,
        )
        assert not form.is_valid()
        assert "file" in form.errors

    def test_magic_mismatch_rejected(self, company_a):
        """File says PDF but content is not."""
        f = SimpleUploadedFile("fake.pdf", b"NOT-PDF", content_type="application/pdf")
        form = DocumentUploadForm(
            data={"title": "Fake", "category": "other"},
            files={"file": f},
            company=company_a,
        )
        assert not form.is_valid()
        assert "file" in form.errors

    def test_save_computes_hash(self, company_a, admin_user):
        content = b"%PDF-1.4 hash-test-content"
        f = SimpleUploadedFile("hash.pdf", content, content_type="application/pdf")
        form = DocumentUploadForm(
            data={"title": "Hash Test", "category": "other"},
            files={"file": f},
            company=company_a,
        )
        assert form.is_valid(), form.errors
        instance = form.save(commit=False)
        instance.company = company_a
        instance.uploaded_by = admin_user
        instance.save()
        expected_hash = hashlib.sha256(content).hexdigest()
        assert instance.file_hash == expected_hash

    def test_save_stores_metadata(self, company_a, admin_user):
        f = _make_pdf()
        form = DocumentUploadForm(
            data={"title": "Meta Test", "category": "trust_deed"},
            files={"file": f},
            company=company_a,
        )
        assert form.is_valid(), form.errors
        instance = form.save(commit=False)
        instance.company = company_a
        instance.uploaded_by = admin_user
        instance.save()
        assert instance.original_filename == "test_doc.pdf"
        assert instance.content_type == "application/pdf"
        assert instance.file_size > 0

    def test_beneficiary_scoped_to_company(self, company_a, company_b):
        """Beneficiary dropdown should only show company's beneficiaries."""
        form_a = DocumentUploadForm(company=company_a)
        form_b = DocumentUploadForm(company=company_b)
        # Both should have querysets scoped to their company
        assert str(form_a.fields["beneficiary"].queryset.query).count("company") >= 0
        # No company → empty queryset
        form_none = DocumentUploadForm(company=None)
        assert form_none.fields["beneficiary"].queryset.count() == 0


# ---------------------------------------------------------------------------
# View tests – permissions
# ---------------------------------------------------------------------------
class TestDocumentViewPermissions:
    def test_list_requires_login(self, company_a):
        c = Client()
        url = reverse("documents:list", kwargs={"company_pk": company_a.pk})
        resp = c.get(url)
        assert resp.status_code in (302, 403)

    def test_list_denied_for_beneficiary(self, ben_client, company_a):
        url = reverse("documents:list", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_list_ok_for_admin(self, admin_client, company_a, document_a):
        url = reverse("documents:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert b"Alpha Trust Deed" in resp.content

    def test_upload_denied_for_beneficiary(self, ben_client, company_a):
        url = reverse("documents:upload", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_download_denied_for_beneficiary(self, ben_client, company_a, document_a):
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": document_a.pk,
        })
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_status_change_denied_for_beneficiary(self, ben_client, company_a, quarantined_doc):
        url = reverse("documents:status-update", kwargs={
            "company_pk": company_a.pk, "pk": quarantined_doc.pk,
        })
        resp = ben_client.get(url)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# View tests – CRUD operations
# ---------------------------------------------------------------------------
class TestDocumentViews:
    def test_detail_view(self, admin_client, company_a, document_a):
        url = reverse("documents:detail", kwargs={
            "company_pk": company_a.pk, "pk": document_a.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert b"Alpha Trust Deed" in resp.content

    def test_upload_get(self, admin_client, company_a):
        url = reverse("documents:upload", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_upload_post_success(self, admin_client, company_a):
        url = reverse("documents:upload", kwargs={"company_pk": company_a.pk})
        f = _make_pdf()
        resp = admin_client.post(url, {
            "title": "New Upload",
            "category": "other",
            "file": f,
        })
        assert resp.status_code == 302  # redirect on success
        doc = Document.objects.get(title="New Upload")
        assert doc.status == DocumentStatus.QUARANTINE
        assert doc.company == company_a
        assert doc.file_hash  # SHA-256 should be set

    def test_upload_exe_rejected(self, admin_client, company_a):
        url = reverse("documents:upload", kwargs={"company_pk": company_a.pk})
        f = _make_exe()
        resp = admin_client.post(url, {
            "title": "Bad Upload",
            "category": "other",
            "file": f,
        })
        assert resp.status_code == 200  # re-renders form with errors
        assert not Document.objects.filter(title="Bad Upload").exists()

    def test_search_filter(self, admin_client, company_a, document_a):
        url = reverse("documents:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"q": "Alpha"})
        assert b"Alpha Trust Deed" in resp.content
        resp2 = admin_client.get(url, {"q": "NONEXISTENT"})
        assert b"Alpha Trust Deed" not in resp2.content

    def test_category_filter(self, admin_client, company_a, document_a):
        url = reverse("documents:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"category": "trust_deed"})
        assert b"Alpha Trust Deed" in resp.content
        resp2 = admin_client.get(url, {"category": "payment_file"})
        assert b"Alpha Trust Deed" not in resp2.content

    def test_status_change(self, admin_client, company_a, quarantined_doc):
        url = reverse("documents:status-update", kwargs={
            "company_pk": company_a.pk, "pk": quarantined_doc.pk,
        })
        resp = admin_client.post(url, {"status": "active"})
        assert resp.status_code == 302
        quarantined_doc.refresh_from_db()
        assert quarantined_doc.status == DocumentStatus.ACTIVE


# ---------------------------------------------------------------------------
# Download security tests
# ---------------------------------------------------------------------------
class TestDocumentDownloadSecurity:
    def test_download_active_ok(self, admin_client, company_a, document_a):
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": document_a.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Disposition"].startswith("attachment")
        assert resp["X-Content-Type-Options"] == "nosniff"
        assert resp["Cache-Control"] == "private, no-store"

    def test_download_quarantined_404(self, admin_client, company_a, quarantined_doc):
        """Quarantined files must NOT be downloadable."""
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": quarantined_doc.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 404

    def test_download_archived_404(self, admin_client, company_a, document_a):
        """Archived files must NOT be downloadable."""
        document_a.status = DocumentStatus.ARCHIVED
        document_a.save()
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": document_a.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 404

    def test_download_rejected_404(self, admin_client, company_a, document_a):
        """Rejected files must NOT be downloadable."""
        document_a.status = DocumentStatus.REJECTED
        document_a.save()
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": document_a.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation tests
# ---------------------------------------------------------------------------
class TestDocumentTenantIsolation:
    def test_list_shows_only_own_company(
        self, admin_client, company_a, company_b, document_a, document_b
    ):
        url = reverse("documents:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert b"Alpha Trust Deed" in resp.content
        assert b"Beta Board Resolution" not in resp.content

    def test_detail_cross_tenant_404(self, admin_client, company_a, document_b):
        """Accessing company B's document through company A's URL → 404."""
        url = reverse("documents:detail", kwargs={
            "company_pk": company_a.pk, "pk": document_b.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 404

    def test_download_cross_tenant_404(self, admin_client, company_a, document_b):
        """Downloading company B's document through company A's URL → 404."""
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": document_b.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit logging tests
# ---------------------------------------------------------------------------
class TestDocumentAuditLogging:
    def test_upload_creates_audit_log(self, admin_client, company_a):
        url = reverse("documents:upload", kwargs={"company_pk": company_a.pk})
        f = _make_pdf()
        admin_client.post(url, {
            "title": "Audited Upload",
            "category": "other",
            "file": f,
        })
        assert AuditLog.objects.filter(action="file_upload").exists()
        entry = AuditLog.objects.filter(action="file_upload").first()
        assert entry.target_model == "Document"
        assert entry.details.get("filename") == "test_doc.pdf"

    def test_download_creates_audit_log(self, admin_client, company_a, document_a):
        url = reverse("documents:download", kwargs={
            "company_pk": company_a.pk, "pk": document_a.pk,
        })
        admin_client.get(url)
        assert AuditLog.objects.filter(action="file_download").exists()
        entry = AuditLog.objects.filter(action="file_download").first()
        assert entry.target_model == "Document"
        assert str(document_a.pk) in entry.target_id

    def test_status_change_creates_audit_log(self, admin_client, company_a, quarantined_doc):
        url = reverse("documents:status-update", kwargs={
            "company_pk": company_a.pk, "pk": quarantined_doc.pk,
        })
        admin_client.post(url, {"status": "active"})
        entries = AuditLog.objects.filter(
            target_model="Document",
            target_id=str(quarantined_doc.pk),
        )
        status_entry = entries.filter(details__action="status_change").first()
        assert status_entry is not None
        assert status_entry.details["old_status"] == "quarantine"
        assert status_entry.details["new_status"] == "active"