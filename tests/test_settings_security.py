"""
Tests for Commit 1: Settings and security baseline.
Verifies that security settings are correctly configured.
"""

import pytest
from django.conf import settings
from django.test import RequestFactory


class TestSecuritySettings:
    """Verify security-critical settings are not accidentally weakened."""

    def test_debug_is_false_in_test(self):
        assert settings.DEBUG is False

    def test_session_cookie_httponly(self):
        assert settings.SESSION_COOKIE_HTTPONLY is True

    def test_csrf_cookie_httponly(self):
        assert settings.CSRF_COOKIE_HTTPONLY is True

    def test_csrf_cookie_samesite(self):
        assert settings.CSRF_COOKIE_SAMESITE == "Lax"

    def test_session_cookie_samesite(self):
        assert settings.SESSION_COOKIE_SAMESITE == "Lax"

    def test_x_frame_options_deny(self):
        assert settings.X_FRAME_OPTIONS == "DENY"

    def test_secure_content_type_nosniff(self):
        assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True

    def test_password_min_length(self):
        """Password must be at least 12 characters."""
        min_length_validator = None
        for v in settings.AUTH_PASSWORD_VALIDATORS:
            if "MinimumLengthValidator" in v["NAME"]:
                min_length_validator = v
                break
        assert min_length_validator is not None
        assert min_length_validator.get("OPTIONS", {}).get("min_length", 8) >= 12

    def test_session_expire_at_browser_close(self):
        assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True

    def test_atomic_requests_enabled(self):
        assert settings.DATABASES["default"]["ATOMIC_REQUESTS"] is True

    def test_secret_key_not_default_insecure(self):
        assert "insecure" not in settings.SECRET_KEY
        assert len(settings.SECRET_KEY) >= 20

    def test_allowed_upload_types_restricted(self):
        """Only safe file types allowed."""
        allowed = settings.ALLOWED_UPLOAD_TYPES
        assert "application/pdf" in allowed
        assert "image/png" in allowed
        assert "image/jpeg" in allowed
        # Dangerous types must NOT be in the list
        assert "application/javascript" not in allowed
        assert "text/html" not in allowed
        assert "application/x-executable" not in allowed

    def test_max_upload_size_has_limit(self):
        assert settings.MAX_UPLOAD_SIZE_MB <= 50  # Reasonable cap

    def test_timezone_is_south_africa(self):
        assert settings.TIME_ZONE == "Africa/Johannesburg"


@pytest.mark.django_db
class TestHealthEndpoint:
    """Health check endpoint must be unauthenticated and safe."""

    def test_health_returns_200(self, client):
        response = client.get("/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_no_auth_required(self, client):
        """Health check must work without login."""
        response = client.get("/health/")
        assert response.status_code == 200


class TestCSPHeaders:
    """Content Security Policy must be present."""

    def test_csp_config_exists(self):
        assert hasattr(settings, "CONTENT_SECURITY_POLICY")
        csp = settings.CONTENT_SECURITY_POLICY
        assert "DIRECTIVES" in csp
        directives = csp["DIRECTIVES"]
        assert "default-src" in directives
        assert "'self'" in directives["default-src"]
        assert "frame-ancestors" in directives
        assert "'none'" in directives["frame-ancestors"]

