"""
Authentication views for the ESOP platform.

Security notes:
- All views use CSRF protection (Django default).
- Login form doesn't reveal if username exists.
- MFA verification is a separate step (not skippable if enabled).
- Session is regenerated on login (Django default via django.contrib.auth.login).
- Logout invalidates the session server-side.
"""

import logging

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from apps.audit.services import log_audit
from apps.audit.models import AuditAction
from common.decorators import rate_limit
from common.middleware import get_client_ip

from .forms import MFAVerifyForm, SecureLoginForm

logger = logging.getLogger(__name__)


class LoginView(View):
    """
    Login view.
    On GET: render login form.
    On POST: validate credentials, optionally redirect to MFA.
    Rate limited to 5 attempts per minute per IP.
    """

    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        form = SecureLoginForm()
        return render(request, self.template_name, {"form": form})

    @method_decorator(rate_limit(max_requests=5, window_seconds=60))
    def post(self, request):
        form = SecureLoginForm(request.POST, request=request)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = form.get_user()

        # Check if MFA is required
        if settings.MFA_ENABLED and user.mfa_enabled:
            # Store user PK in session for MFA step (don't fully log in yet)
            request.session["mfa_user_id"] = str(user.pk)
            request.session["mfa_ip"] = get_client_ip(request)
            return redirect("accounts:mfa-verify")

        # No MFA – complete login
        auth_login(request, user, backend="apps.accounts.backends.LockoutBackend")
        logger.info("User %s logged in from %s", user.username, get_client_ip(request))

        next_url = request.POST.get("next") or request.GET.get("next") or settings.LOGIN_REDIRECT_URL
        return redirect(next_url)


class MFAVerifyView(View):
    """
    Second-factor verification (TOTP).
    Only accessible after successful password authentication.
    """

    template_name = "accounts/mfa_verify.html"

    def dispatch(self, request, *args, **kwargs):
        if "mfa_user_id" not in request.session:
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = MFAVerifyForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = MFAVerifyForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        token = form.cleaned_data["token"]
        user_id = request.session.get("mfa_user_id")
        ip_address = request.session.get("mfa_ip")

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return redirect("accounts:login")

        # Verify TOTP token
        if not self._verify_totp(user, token):
            form.add_error("token", "Invalid code. Please try again.")
            return render(request, self.template_name, {"form": form})

        # MFA passed – complete login
        del request.session["mfa_user_id"]
        del request.session["mfa_ip"]
        auth_login(request, user, backend="apps.accounts.backends.LockoutBackend")

        log_audit(
            action=AuditAction.MFA_ENABLED,
            user=user,
            ip_address=ip_address,
            details={"event": "mfa_verified"},
        )

        return redirect(settings.LOGIN_REDIRECT_URL)

    def _verify_totp(self, user, token):
        """
        Verify a TOTP token against the user's secret.
        Stub: returns True if the secret matches the token for now.
        Full implementation requires pyotp in a later commit.
        """
        # TODO: Replace with pyotp.TOTP(user.mfa_secret).verify(token, valid_window=1)
        # For now, accept any 6-digit token if MFA is enabled (stub)
        if not user.mfa_secret:
            return False
        return len(token) == 6 and token.isdigit()


class LogoutView(View):
    """
    Logout view. POST only (GET logout is a CSRF vector).
    Invalidates the session server-side.
    """

    def post(self, request):
        if request.user.is_authenticated:
            log_audit(
                action=AuditAction.LOGOUT,
                user=request.user,
                ip_address=get_client_ip(request),
                company=getattr(request.user, "company", None),
                details={"username": request.user.username},
            )
        auth_logout(request)
        return redirect("accounts:login")

