"""API app configuration."""

from django.apps import AppConfig


class APIConfig(AppConfig):
    """Configuration for the REST API app."""
    
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    verbose_name = "REST API"

