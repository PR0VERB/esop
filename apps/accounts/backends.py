"""
Custom authentication backend with progressive lockout.

Security features:
- Check if account is locked before attempting auth
- Increment failed_login_attempts on bad credentials
- Lock account after MAX_FAILED_LOGIN_ATTEMPTS
- Reset counter on successful login
- Audit log every auth attempt
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

from apps.audit.services import log_login_failed, log_login_success
from common.middleware import get_client_ip

User = get_user_model()

# Defaults – overridable in settings
MAX_FAILED_ATTEMPTS = getattr(settings, "MAX_FAILED_LOGIN_ATTEMPTS", 5)
LOCKOUT_DURATION_MINUTES = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 15)


class LockoutBackend(ModelBackend):
    """
    Authenticates against accounts.User with progressive lockout.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        ip_address = get_client_ip(request) if request else None

        # Look up the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Don't reveal whether user exists – log and return
            log_login_failed(username, ip_address=ip_address)
            return None

        # Check lockout
        if user.locked_until and user.locked_until > timezone.now():
            log_login_failed(username, ip_address=ip_address)
            return None

        # If lock has expired, reset
        if user.locked_until and user.locked_until <= timezone.now():
            user.failed_login_attempts = 0
            user.locked_until = None
            user.save(update_fields=["failed_login_attempts", "locked_until"])

        # Verify password
        if not user.check_password(password):
            user.failed_login_attempts += 1
            update_fields = ["failed_login_attempts"]

            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = timezone.now() + timezone.timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                update_fields.append("locked_until")

            user.save(update_fields=update_fields)
            log_login_failed(username, ip_address=ip_address)
            return None

        # Check if user is allowed to log in (active, etc.)
        if not self.user_can_authenticate(user):
            log_login_failed(username, ip_address=ip_address)
            return None

        # Success – reset lockout counters
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_ip = ip_address
        user.save(update_fields=["failed_login_attempts", "locked_until", "last_login_ip"])

        log_login_success(user, ip_address=ip_address)
        return user

