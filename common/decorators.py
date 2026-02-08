"""
Security decorators for the ESOP platform.
"""

import functools
import logging
import time
from collections import defaultdict

from django.conf import settings
from django.http import HttpResponse

from common.middleware import get_client_ip

logger = logging.getLogger(__name__)

# In-memory rate limit store. In production, use Redis via Celery/django-redis.
# This is intentionally simple and stateless across restarts.
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def rate_limit(*, max_requests: int = 5, window_seconds: int = 60):
    """
    Simple per-IP rate limiter decorator for views.
    Returns HTTP 429 if the limit is exceeded.

    Usage:
        @rate_limit(max_requests=5, window_seconds=60)
        def my_view(request): ...

    For class-based views, apply to dispatch():
        @method_decorator(rate_limit(max_requests=5, window_seconds=60))
        def dispatch(self, request, *args, **kwargs): ...
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            # Skip rate limiting if disabled in settings (e.g., tests)
            if getattr(settings, "RATELIMIT_ENABLE", True) is False:
                return view_func(request, *args, **kwargs)

            ip = get_client_ip(request) or "unknown"
            key = f"{view_func.__qualname__}:{ip}"
            now = time.time()
            cutoff = now - window_seconds

            # Clean old entries
            _rate_limit_store[key] = [
                t for t in _rate_limit_store[key] if t > cutoff
            ]

            if len(_rate_limit_store[key]) >= max_requests:
                logger.warning(
                    "Rate limit exceeded: ip=%s view=%s",
                    ip,
                    view_func.__qualname__,
                )
                return HttpResponse(
                    "Too many requests. Please try again later.",
                    status=429,
                    content_type="text/plain",
                )

            _rate_limit_store[key].append(now)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def clear_rate_limit_store():
    """Clear the rate limit store. Used in tests."""
    _rate_limit_store.clear()

