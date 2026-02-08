"""
Document CRUD views with tenant isolation and secure file serving.

Security notes:
- All views scoped to company via DocumentCompanyMixin.
- Files are NEVER served via MEDIA_URL. Downloads go through
  DocumentDownloadView which checks permissions and streams the file.
- Upload audit logged. Download audit logged.
- Status change (quarantine → active) audit logged.
- SchemeAdminRequiredMixin on all views.
"""

import logging
import mimetypes

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.audit.models import AuditAction
from apps.audit.services import log_audit
from apps.tenants.models import Company
from common.middleware import get_client_ip
from common.permissions import SchemeAdminRequiredMixin

from .forms import DocumentStatusForm, DocumentUploadForm
from .models import Document, DocumentCategory, DocumentStatus

logger = logging.getLogger(__name__)


class DocumentCompanyMixin:
    """Resolve company from URL and scope querysets."""

    def get_company(self):
        if not hasattr(self, "_company"):
            self._company = get_object_or_404(
                Company, pk=self.kwargs["company_pk"], is_active=True
            )
        return self._company

    def get_queryset(self):
        return Document.objects.for_tenant(self.get_company())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["company"] = self.get_company()
        return ctx


class DocumentListView(SchemeAdminRequiredMixin, DocumentCompanyMixin, ListView):
    """List all documents for a company."""

    model = Document
    template_name = "documents/list.html"
    context_object_name = "documents"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(title__icontains=q)
        category = self.request.GET.get("category", "").strip()
        if category:
            qs = qs.filter(category=category)
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category_choices"] = DocumentCategory.choices
        return ctx


class DocumentDetailView(SchemeAdminRequiredMixin, DocumentCompanyMixin, DetailView):
    """View document metadata."""

    model = Document
    template_name = "documents/detail.html"
    context_object_name = "document"


class DocumentUploadView(SchemeAdminRequiredMixin, DocumentCompanyMixin, CreateView):
    """Upload a new document."""

    model = Document
    form_class = DocumentUploadForm
    template_name = "documents/upload.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs

    def form_valid(self, form):
        form.instance.company = self.get_company()
        form.instance.uploaded_by = self.request.user
        # New uploads start in quarantine
        form.instance.status = DocumentStatus.QUARANTINE
        response = super().form_valid(form)

        log_audit(
            action=AuditAction.FILE_UPLOAD,
            user=self.request.user,
            ip_address=get_client_ip(self.request),
            company=self.get_company(),
            target_model="Document",
            target_id=str(self.object.pk),
            details={
                "filename": self.object.original_filename,
                "content_type": self.object.content_type,
                "file_size": self.object.file_size,
                "file_hash": self.object.file_hash,
                "category": self.object.category,
            },
        )
        messages.success(
            self.request,
            f"Document '{self.object.title}' uploaded. Status: quarantine (pending review).",
        )
        return response

    def get_success_url(self):
        return reverse_lazy(
            "documents:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": self.object.pk},
        )


class DocumentDownloadView(SchemeAdminRequiredMixin, DocumentCompanyMixin, View):
    """
    Secure file download. Streams the file through Django instead of
    exposing the MEDIA_URL directly. This ensures:
    - Permission check on every download.
    - Audit trail of who downloaded what.
    - No direct filesystem path exposure.
    """

    def get(self, request, company_pk, pk):
        doc = get_object_or_404(self.get_queryset(), pk=pk)

        if not doc.is_accessible:
            raise Http404("This document is not available for download.")

        log_audit(
            action=AuditAction.FILE_DOWNLOAD,
            user=request.user,
            ip_address=get_client_ip(request),
            company=self.get_company(),
            target_model="Document",
            target_id=str(doc.pk),
            details={
                "filename": doc.original_filename,
                "file_hash": doc.file_hash,
            },
        )

        # Determine content type
        ct = doc.content_type or mimetypes.guess_type(doc.original_filename)[0] or "application/octet-stream"

        response = FileResponse(
            doc.file.open("rb"),
            content_type=ct,
        )
        # Force download with original filename
        response["Content-Disposition"] = (
            f'attachment; filename="{doc.original_filename}"'
        )
        # Security headers for downloads
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class DocumentStatusUpdateView(
    SchemeAdminRequiredMixin, DocumentCompanyMixin, UpdateView
):
    """
    Update document status (quarantine → active, or → rejected/archived).
    Scheme admins only. Audit logged.
    """

    model = Document
    form_class = DocumentStatusForm
    template_name = "documents/status_form.html"

    def form_valid(self, form):
        old_status = Document.objects.get(pk=self.object.pk).status
        response = super().form_valid(form)

        log_audit(
            action=AuditAction.FILE_UPLOAD,  # Re-use; details distinguish
            user=self.request.user,
            ip_address=get_client_ip(self.request),
            company=self.get_company(),
            target_model="Document",
            target_id=str(self.object.pk),
            details={
                "action": "status_change",
                "old_status": old_status,
                "new_status": self.object.status,
                "filename": self.object.original_filename,
            },
        )
        messages.success(
            self.request,
            f"Document status changed to {self.object.get_status_display()}.",
        )
        return response

    def get_success_url(self):
        return reverse_lazy(
            "documents:detail",
            kwargs={"company_pk": self.get_company().pk, "pk": self.object.pk},
        )

