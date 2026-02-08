"""
REST API app for external system integration.

Provides:
- Token-based authentication with tenant scoping
- CRUD endpoints for beneficiaries, dividend runs, allocations
- Read-only endpoints for month-end runs and vesting events
- Webhook endpoints for external system callbacks

Security notes:
- All endpoints require authentication (Token or Session)
- All querysets are tenant-scoped
- Rate limiting applied to all endpoints
- Audit logging for all write operations
"""

default_app_config = "apps.api.apps.APIConfig"

