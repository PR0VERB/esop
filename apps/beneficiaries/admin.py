"""
Django admin for Beneficiary model.
Read-only encrypted fields; all changes go through views + audit log.
"""

from django.contrib import admin

from .models import Beneficiary


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = [
        "employee_number",
        "first_name",
        "last_name",
        "company",
        "status",
        "total_shares",
        "created_at",
    ]
    list_filter = ["status", "company"]
    search_fields = ["first_name", "last_name", "employee_number", "email"]
    readonly_fields = [
        "id",
        "id_number_encrypted",
        "account_number_encrypted",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["user", "company"]

    def has_delete_permission(self, request, obj=None):
        """Prevent hard deletion from admin. Use status change instead."""
        return False

