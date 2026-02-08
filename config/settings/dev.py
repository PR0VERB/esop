"""
Development settings – NEVER use in production.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Relax secure cookies for local HTTP dev
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Use console email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Celery: run tasks synchronously in dev
CELERY_TASK_ALWAYS_EAGER = True

# Disable HSTS in dev
SECURE_HSTS_SECONDS = 0
SECURE_SSL_REDIRECT = False

# Allow sqlite for quick local testing (Postgres preferred)
import environ  # noqa: E402

env = environ.Env()
if not env("DATABASE_URL", default=""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
            "ATOMIC_REQUESTS": True,
        }
    }

# Logging: show DEBUG in dev
LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # noqa: F405

