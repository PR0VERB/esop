from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "user", "company", "target_model", "target_id")
    list_filter = ("action", "company")
    search_fields = ("user__username", "target_model", "target_id")
    readonly_fields = (
        "id",
        "timestamp",
        "user",
        "ip_address",
        "action",
        "company",
        "target_model",
        "target_id",
        "details",
    )
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False  # Audit logs created only via service

    def has_change_permission(self, request, obj=None):
        return False  # Immutable

    def has_delete_permission(self, request, obj=None):
        return False  # Use management command

