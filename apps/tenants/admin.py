from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "registration_number", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "registration_number")
    readonly_fields = ("id", "created_at", "updated_at")

