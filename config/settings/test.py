"""
Test settings – fast, isolated, deterministic.
"""

from .base import *  # noqa: F401, F403

DEBUG = False

# Use in-memory sqlite for speed in CI
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "ATOMIC_REQUESTS": True,
    }
}

# Fast password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Celery: synchronous
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable rate limiting in tests
RATELIMIT_ENABLE = False

# Disable DRF throttling in tests
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [],  # Disable throttling in tests
    "DEFAULT_THROTTLE_RATES": {},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "EXCEPTION_HANDLER": "apps.api.exceptions.custom_exception_handler",
}

# Email
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Session cookies don't need to be secure in tests
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

SECRET_KEY = "test-secret-key-not-for-production-use-only-testing"
FIELD_ENCRYPTION_KEY = "dGVzdC1lbmNyeXB0aW9uLWtleS1ub3QtZm9yLXByb2Q="  # test only

# Use in-memory file storage for tests (no filesystem writes)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

