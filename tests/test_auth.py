"""
Tests for Commit 3: Authentication, lockout, rate limiting, MFA stub, audit trail.
"""

import pytest
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditLog, AuditAction
from common.decorators import clear_rate_limit_store


@pytest.fixture
def company(db):
    from apps.tenants.models import Company
    return Company.objects.create(
        name="Test Corp",
        registration_number="REG-TEST-001",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin1",
        password="SecurePass123!",
        role=UserRole.SCHEME_ADMIN,
    )


@pytest.fixture
def beneficiary_user(db, company):
    return User.objects.create_user(
        username="ben1",
        password="SecurePass123!",
        role=UserRole.BENEFICIARY,
        company=company,
    )


@pytest.fixture
def client():
    return Client()


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear rate limit store before each test."""
    clear_rate_limit_store()
    yield
    clear_rate_limit_store()


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------
class TestLogin:
    def test_login_page_renders(self, client, db):
        resp = client.get(reverse("accounts:login"))
        assert resp.status_code == 200
        assert b"Sign In" in resp.content

    def test_successful_login(self, client, admin_user):
        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        assert resp.status_code == 302  # Redirect on success

    def test_failed_login_bad_password(self, client, admin_user):
        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "wrongpassword"},
        )
        assert resp.status_code == 200  # Re-renders form
        assert b"Invalid credentials" in resp.content

    def test_failed_login_nonexistent_user(self, client, db):
        resp = client.post(
            reverse("accounts:login"),
            {"username": "nobody", "password": "doesntmatter"},
        )
        assert resp.status_code == 200
        assert b"Invalid credentials" in resp.content

    def test_login_redirects_authenticated_user(self, client, admin_user):
        client.login(username="admin1", password="SecurePass123!")
        resp = client.get(reverse("accounts:login"))
        assert resp.status_code == 302  # Redirect away from login

    def test_login_csrf_required(self, client, admin_user):
        """POST without CSRF token must fail."""
        from django.test import Client as RawClient
        csrf_client = RawClient(enforce_csrf_checks=True)
        resp = csrf_client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        assert resp.status_code == 403  # CSRF failure


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------
class TestLogout:
    def test_logout_post(self, client, admin_user):
        client.login(username="admin1", password="SecurePass123!")
        resp = client.post(reverse("accounts:logout"))
        assert resp.status_code == 302
        # Verify session is cleared
        resp2 = client.get(reverse("accounts:login"))
        assert resp2.status_code == 200  # Not redirected (not authenticated)

    def test_logout_creates_audit_entry(self, client, admin_user):
        client.login(username="admin1", password="SecurePass123!")
        AuditLog.objects.all().delete()  # Clear login audit
        client.post(reverse("accounts:logout"))
        assert AuditLog.objects.filter(action=AuditAction.LOGOUT).exists()


# ---------------------------------------------------------------------------
# Lockout tests
# ---------------------------------------------------------------------------
class TestLockout:
    def test_account_locks_after_max_attempts(self, client, admin_user):
        """After 5 failed attempts, account should be locked."""
        for i in range(5):
            client.post(
                reverse("accounts:login"),
                {"username": "admin1", "password": "wrongpass"},
            )
        admin_user.refresh_from_db()
        assert admin_user.failed_login_attempts >= 5
        assert admin_user.locked_until is not None
        assert admin_user.locked_until > timezone.now()

    def test_locked_account_rejects_correct_password(self, client, admin_user):
        """Even with correct password, locked account can't log in."""
        # Lock the account
        admin_user.locked_until = timezone.now() + timezone.timedelta(minutes=15)
        admin_user.failed_login_attempts = 5
        admin_user.save()

        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        assert resp.status_code == 200  # Login fails
        assert b"Invalid credentials" in resp.content

    def test_lockout_expires_and_login_succeeds(self, client, admin_user):
        """After lockout expires, user can log in again."""
        # Set lockout in the past
        admin_user.locked_until = timezone.now() - timezone.timedelta(minutes=1)
        admin_user.failed_login_attempts = 5
        admin_user.save()

        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        assert resp.status_code == 302  # Login succeeds

    def test_successful_login_resets_lockout_counter(self, client, admin_user):
        """Successful login resets failed_login_attempts."""
        admin_user.failed_login_attempts = 3
        admin_user.save()

        client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        admin_user.refresh_from_db()
        assert admin_user.failed_login_attempts == 0
        assert admin_user.locked_until is None


# ---------------------------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------------------------
class TestRateLimiting:
    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limit_on_login(self, client, admin_user):
        """After 5 rapid requests, the 6th should get 429."""
        for i in range(5):
            client.post(
                reverse("accounts:login"),
                {"username": "admin1", "password": "wrong"},
            )
        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "wrong"},
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Audit trail for auth events
# ---------------------------------------------------------------------------
class TestAuthAudit:
    def test_successful_login_creates_audit_entry(self, client, admin_user):
        AuditLog.objects.all().delete()
        client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        assert AuditLog.objects.filter(action=AuditAction.LOGIN_SUCCESS).exists()

    def test_failed_login_creates_audit_entry(self, client, admin_user):
        AuditLog.objects.all().delete()
        client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "wrongpass"},
        )
        assert AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists()

    def test_nonexistent_user_login_creates_audit_entry(self, client, db):
        AuditLog.objects.all().delete()
        client.post(
            reverse("accounts:login"),
            {"username": "ghost", "password": "doesntmatter"},
        )
        assert AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists()
        entry = AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).first()
        assert entry.details["username"] == "ghost"


# ---------------------------------------------------------------------------
# MFA stub tests
# ---------------------------------------------------------------------------
class TestMFAStub:
    def test_mfa_verify_redirects_without_session(self, client, db):
        """MFA verify should redirect to login if no mfa_user_id in session."""
        resp = client.get(reverse("accounts:mfa-verify"))
        assert resp.status_code == 302
        assert "login" in resp.url

    @override_settings(MFA_ENABLED=True)
    def test_mfa_user_redirected_to_mfa_verify(self, client, admin_user):
        """When MFA is enabled and user has mfa_enabled, redirect to MFA."""
        admin_user.mfa_enabled = True
        admin_user.mfa_secret = "TESTSECRETBASE32"
        admin_user.save()

        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        assert resp.status_code == 302
        assert "mfa" in resp.url

    @override_settings(MFA_ENABLED=True)
    def test_mfa_verify_with_valid_token(self, client, admin_user):
        """Valid 6-digit token should complete login (stub accepts any 6 digits)."""
        admin_user.mfa_enabled = True
        admin_user.mfa_secret = "TESTSECRETBASE32"
        admin_user.save()

        # Step 1: Login (password OK, redirect to MFA)
        client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )

        # Step 2: Submit MFA token
        resp = client.post(
            reverse("accounts:mfa-verify"),
            {"token": "123456"},
        )
        assert resp.status_code == 302  # Redirect to home

    @override_settings(MFA_ENABLED=False)
    def test_mfa_disabled_skips_mfa_step(self, client, admin_user):
        """When MFA_ENABLED is False, even users with mfa_enabled skip MFA."""
        admin_user.mfa_enabled = True
        admin_user.mfa_secret = "TESTSECRETBASE32"
        admin_user.save()

        resp = client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "SecurePass123!"},
        )
        # Should go directly to redirect, not MFA
        assert resp.status_code == 302
        assert "mfa" not in resp.url

