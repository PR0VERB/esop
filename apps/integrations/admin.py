"""Admin interface for integration logs."""

from django.contrib import admin

from apps.integrations.models import IntegrationLog, JSECompany


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    """Read-only admin for integration logs."""

    list_display = [
        "id",
        "company",
        "system",
        "operation",
        "status",
        "response_code",
        "started_at",
        "completed_at",
        "initiated_by",
    ]
    list_filter = [
        "system",
        "status",
        "started_at",
        "company",
    ]
    search_fields = [
        "operation",
        "idempotency_key",
        "reference_id",
        "error_message",
    ]
    readonly_fields = [
        "id",
        "company",
        "system",
        "operation",
        "status",
        "request_data",
        "response_data",
        "response_code",
        "error_message",
        "retry_count",
        "max_retries",
        "started_at",
        "completed_at",
        "initiated_by",
        "reference_model",
        "reference_id",
        "idempotency_key",
        "created_at",
        "updated_at",
    ]
    ordering = ["-started_at"]
    date_hierarchy = "started_at"

    def has_add_permission(self, request):
        """Prevent manual creation - logs are created by clients."""
        return False

    def has_change_permission(self, request, obj=None):
        """Logs are immutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit trail."""
        return False


@admin.register(JSECompany)
class JSECompanyAdmin(admin.ModelAdmin):
    list_display = ("ticker", "company_name", "sector", "market_cap_category", "share_price", "is_active")
    list_filter = ("sector", "market_cap_category", "is_active")
    search_fields = ("ticker", "company_name", "isin")
    readonly_fields = ("last_enriched_at", "share_price", "market_cap")

