"""
Production settings – security hardened.
"""

from .base import *  # noqa: F401, F403

import environ  # noqa: E402

env = environ.Env()

DEBUG = False

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# HSTS – enforce HTTPS
# ---------------------------------------------------------------------------
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Cookies – already secure in base, but re-assert
# ---------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ---------------------------------------------------------------------------
# Additional production security
# ---------------------------------------------------------------------------
# Shorter sessions for admin (30 minutes)
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=1800)

# Email – configure for real SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# Logging level
LOGGING["root"]["level"] = "WARNING"  # noqa: F405

