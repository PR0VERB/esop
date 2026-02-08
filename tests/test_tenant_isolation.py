"""
Tests for Commit 2: Tenant isolation, user model, audit log.
"""

import pytest
from django.test import RequestFactory

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditLog
from apps.audit.services import log_audit, log_login_success, log_login_failed
from apps.tenants.models import Company
from common.models import TenantScopedManager


@pytest.fixture
def company_a(db):
    return Company.objects.create(
        name="Company A",
        registration_number="REG-A-001",
    )


@pytest.fixture
def company_b(db):
    return Company.objects.create(
        name="Company B",
        registration_number="REG-B-001",
    )


@pytest.fixture
def admin_user(db, company_a):
    return User.objects.create_user(
        username="admin1",
        password="testpass12345!",
        role=UserRole.SCHEME_ADMIN,
        company=None,  # Admins can access all
    )


@pytest.fixture
def beneficiary_user_a(db, company_a):
    return User.objects.create_user(
        username="ben_a",
        password="testpass12345!",
        role=UserRole.BENEFICIARY,
        company=company_a,
    )


@pytest.fixture
def beneficiary_user_b(db, company_b):
    return User.objects.create_user(
        username="ben_b",
        password="testpass12345!",
        role=UserRole.BENEFICIARY,
        company=company_b,
    )


class TestUserModel:
    def test_admin_can_access_any_company(self, admin_user, company_a, company_b):
        assert admin_user.can_access_company(company_a) is True
        assert admin_user.can_access_company(company_b) is True

    def test_beneficiary_can_access_own_company(self, beneficiary_user_a, company_a):
        assert beneficiary_user_a.can_access_company(company_a) is True

    def test_beneficiary_cannot_access_other_company(self, beneficiary_user_a, company_b):
        assert beneficiary_user_a.can_access_company(company_b) is False

    def test_user_roles(self, admin_user, beneficiary_user_a):
        assert admin_user.is_scheme_admin is True
        assert admin_user.is_beneficiary is False
        assert beneficiary_user_a.is_scheme_admin is False
        assert beneficiary_user_a.is_beneficiary is True


class TestCompanyModel:
    def test_company_creation(self, company_a):
        assert company_a.name == "Company A"
        assert company_a.registration_number == "REG-A-001"
        assert company_a.is_active is True

    def test_unique_registration_number(self, company_a, db):
        with pytest.raises(Exception):  # IntegrityError
            Company.objects.create(
                name="Duplicate",
                registration_number="REG-A-001",
            )


class TestAuditLog:
    def test_audit_log_creation(self, admin_user, company_a):
        entry = log_audit(
            action="login_success",
            user=admin_user,
            company=company_a,
            details={"test": True},
        )
        assert entry.pk is not None
        assert entry.action == "login_success"
        assert entry.user == admin_user

    def test_audit_log_immutable(self, admin_user):
        entry = log_audit(action="login_success", user=admin_user)
        entry.details = {"modified": True}
        with pytest.raises(ValueError, match="immutable"):
            entry.save()

    def test_audit_log_no_delete(self, admin_user):
        entry = log_audit(action="login_success", user=admin_user)
        with pytest.raises(ValueError, match="cannot be deleted"):
            entry.delete()

    def test_log_login_success(self, admin_user):
        entry = log_login_success(admin_user, ip_address="127.0.0.1")
        assert entry.action == "login_success"
        assert entry.ip_address == "127.0.0.1"

    def test_log_login_failed(self, db):
        entry = log_login_failed("unknown_user", ip_address="10.0.0.1")
        assert entry.action == "login_failed"
        assert entry.details["username"] == "unknown_user"

    def test_audit_log_count(self, admin_user, company_a):
        for i in range(5):
            log_audit(action="login_success", user=admin_user, company=company_a)
        assert AuditLog.objects.count() == 5


class TestTenantIsolation:
    """Verify that tenant scoping works correctly."""

    def test_company_a_user_cannot_see_company_b(
        self, beneficiary_user_a, beneficiary_user_b, company_a, company_b
    ):
        """Cross-tenant access must be denied at the model level."""
        assert beneficiary_user_a.can_access_company(company_b) is False
        assert beneficiary_user_b.can_access_company(company_a) is False

    def test_admin_users_see_all(self, admin_user, company_a, company_b):
        assert admin_user.can_access_company(company_a) is True
        assert admin_user.can_access_company(company_b) is True

