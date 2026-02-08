"""
Admin configuration for month-end runs (read-only).
"""

from django.contrib import admin

from .models import MonthEndRun, TaxDirective, VestingEvent


@admin.register(MonthEndRun)
class MonthEndRunAdmin(admin.ModelAdmin):
    """Read-only admin for month-end runs."""

    list_display = [
        "title",
        "company",
        "period_year",
        "period_month",
        "status",
        "vesting_event_count",
        "total_net_proceeds",
        "created_at",
    ]
    list_filter = ["status", "period_year", "company"]
    search_fields = ["title", "idempotency_key"]
    readonly_fields = [
        "id",
        "company",
        "title",
        "description",
        "period_year",
        "period_month",
        "status",
        "idempotency_key",
        "created_by",
        "approved_by",
        "approved_at",
        "completed_at",
        "failure_reason",
        "total_shares_vested",
        "total_shares_sold",
        "total_gross_proceeds",
        "total_tax",
        "total_net_proceeds",
        "vesting_event_count",
        "termination_count",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VestingEvent)
class VestingEventAdmin(admin.ModelAdmin):
    """Read-only admin for vesting events."""

    list_display = [
        "beneficiary",
        "event_type",
        "shares_affected",
        "net_amount",
        "status",
        "event_date",
    ]
    list_filter = ["event_type", "status", "run"]
    search_fields = ["beneficiary__last_name", "beneficiary__first_name"]
    readonly_fields = [
        "id",
        "company",
        "run",
        "beneficiary",
        "event_type",
        "event_date",
        "shares_affected",
        "shares_before",
        "shares_after",
        "share_price",
        "gross_amount",
        "tax_amount",
        "net_amount",
        "status",
        "notes",
        "created_at",
        "updated_at",
    ]
    ordering = ["-event_date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TaxDirective)
class TaxDirectiveAdmin(admin.ModelAdmin):
    """Read-only admin for tax directives."""

    list_display = [
        "beneficiary",
        "tax_year",
        "directive_number",
        "status",
        "taxable_amount",
        "calculated_tax",
        "request_date",
    ]
    list_filter = ["status", "tax_year"]
    search_fields = ["beneficiary__last_name", "directive_number"]
    readonly_fields = [
        "id",
        "company",
        "run",
        "beneficiary",
        "directive_number",
        "tax_year",
        "request_date",
        "response_date",
        "taxable_amount",
        "directive_rate",
        "calculated_tax",
        "status",
        "decline_reason",
        "notes",
        "created_at",
        "updated_at",
    ]
    ordering = ["-request_date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

