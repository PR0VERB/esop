"""
Django admin for Document model.
Read-only file fields; all uploads go through views + audit log.
"""

from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "status",
        "company",
        "original_filename",
        "file_size",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["status", "category", "company"]
    search_fields = ["title", "original_filename", "description"]
    readonly_fields = [
        "id",
        "file",
        "original_filename",
        "content_type",
        "file_size",
        "file_hash",
        "uploaded_by",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["company", "beneficiary", "uploaded_by"]

    def has_delete_permission(self, request, obj=None):
        """Prevent hard deletion from admin. Use status change instead."""
        return False

