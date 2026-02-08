from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "company", "is_active", "mfa_enabled")
    list_filter = ("role", "is_active", "mfa_enabled")
    search_fields = ("username", "email", "first_name", "last_name")
    readonly_fields = ("id", "failed_login_attempts", "locked_until", "last_login_ip")

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "ESOP",
            {
                "fields": (
                    "role",
                    "company",
                    "mfa_enabled",
                    "mfa_secret",
                    "failed_login_attempts",
                    "locked_until",
                    "last_login_ip",
                )
            },
        ),
    )

