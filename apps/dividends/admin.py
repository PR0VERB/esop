"""
Django admin for Dividend models.
Read-only for financial data; state changes go through views + service layer.
"""

from django.contrib import admin

from .models import DividendAllocation, DividendRun


class DividendAllocationInline(admin.TabularInline):
    model = DividendAllocation
    extra = 0
    readonly_fields = [
        "beneficiary",
        "shares_at_record_date",
        "gross_amount",
        "tax_amount",
        "net_amount",
        "status",
        "payment_reference",
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DividendRun)
class DividendRunAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "status",
        "company",
        "total_amount",
        "dividend_per_share",
        "record_date",
        "payment_date",
        "allocation_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["status", "company"]
    search_fields = ["title", "idempotency_key"]
    readonly_fields = [
        "id",
        "idempotency_key",
        "status",
        "created_by",
        "approved_by",
        "approved_at",
        "completed_at",
        "failure_reason",
        "total_gross",
        "total_tax",
        "total_net",
        "allocation_count",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["company", "created_by", "approved_by"]
    inlines = [DividendAllocationInline]

    def has_delete_permission(self, request, obj=None):
        """Prevent hard deletion from admin."""
        return False


@admin.register(DividendAllocation)
class DividendAllocationAdmin(admin.ModelAdmin):
    list_display = [
        "beneficiary",
        "run",
        "shares_at_record_date",
        "gross_amount",
        "tax_amount",
        "net_amount",
        "status",
    ]
    list_filter = ["status", "run__company"]
    search_fields = ["beneficiary__first_name", "beneficiary__last_name"]
    readonly_fields = [
        "id",
        "run",
        "beneficiary",
        "shares_at_record_date",
        "gross_amount",
        "tax_amount",
        "net_amount",
        "status",
        "payment_reference",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["company", "run", "beneficiary"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

