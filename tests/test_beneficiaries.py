"""
Tests for Commit 4: Beneficiaries app – tenant isolation, permissions, CRUD,
encryption, form validation, and audit logging.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditLog
from apps.beneficiaries.forms import BeneficiaryForm
from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus
from apps.tenants.models import Company


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def company_a(db):
    return Company.objects.create(name="Alpha Corp", registration_number="REG-ALPHA")


@pytest.fixture
def company_b(db):
    return Company.objects.create(name="Beta Corp", registration_number="REG-BETA")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin_ben", password="SecurePass123!", role=UserRole.SCHEME_ADMIN
    )


@pytest.fixture
def ben_user(db, company_a):
    return User.objects.create_user(
        username="ben_portal", password="SecurePass123!",
        role=UserRole.BENEFICIARY, company=company_a,
    )


@pytest.fixture
def beneficiary_a(db, company_a):
    b = Beneficiary(
        company=company_a, first_name="Thabo", last_name="Mbeki",
        employee_number="EMP001", email="thabo@alpha.co.za",
        total_shares=100, vested_shares=60, unvested_shares=40,
    )
    b.id_number = "8501015009086"  # valid Luhn
    b.account_number = "1234567890"
    b.save()
    return b


@pytest.fixture
def beneficiary_b(db, company_b):
    b = Beneficiary(
        company=company_b, first_name="Sipho", last_name="Dlamini",
        employee_number="EMP002",
        total_shares=50, vested_shares=30, unvested_shares=20,
    )
    b.save()
    return b


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.login(username="admin_ben", password="SecurePass123!")
    return c


@pytest.fixture
def ben_client(ben_user):
    c = Client()
    c.login(username="ben_portal", password="SecurePass123!")
    return c


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------
class TestBeneficiaryModel:
    def test_create_beneficiary(self, beneficiary_a):
        assert beneficiary_a.pk is not None
        assert beneficiary_a.first_name == "Thabo"
        assert beneficiary_a.status == BeneficiaryStatus.ACTIVE

    def test_encrypted_id_number(self, beneficiary_a):
        """ID number should be encrypted at rest, decrypted via property."""
        assert beneficiary_a.id_number == "8501015009086"
        assert beneficiary_a.id_number_encrypted != "8501015009086"
        assert len(beneficiary_a.id_number_encrypted) > 20  # ciphertext is long

    def test_encrypted_account_number(self, beneficiary_a):
        assert beneficiary_a.account_number == "1234567890"
        assert beneficiary_a.account_number_encrypted != "1234567890"

    def test_full_name(self, beneficiary_a):
        assert beneficiary_a.full_name == "Thabo Mbeki"

    def test_is_active(self, beneficiary_a):
        assert beneficiary_a.is_active is True
        beneficiary_a.status = BeneficiaryStatus.TERMINATED
        assert beneficiary_a.is_active is False

    def test_str(self, beneficiary_a):
        assert "Thabo Mbeki" in str(beneficiary_a)

    def test_clean_share_mismatch(self, company_a):
        b = Beneficiary(
            company=company_a, first_name="X", last_name="Y",
            total_shares=100, vested_shares=50, unvested_shares=30,
        )
        from django.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="must equal total_shares"):
            b.clean()

    def test_for_tenant_scoping(self, beneficiary_a, beneficiary_b, company_a, company_b):
        qs_a = Beneficiary.objects.for_tenant(company_a)
        qs_b = Beneficiary.objects.for_tenant(company_b)
        assert beneficiary_a in qs_a
        assert beneficiary_a not in qs_b
        assert beneficiary_b in qs_b
        assert beneficiary_b not in qs_a


# ---------------------------------------------------------------------------
# Form validation tests
# ---------------------------------------------------------------------------
class TestBeneficiaryForm:
    def _base_data(self):
        return {
            "first_name": "Test", "last_name": "User",
            "employee_number": "EMP999",
            "total_shares": 100, "vested_shares": 60, "unvested_shares": 40,
            "status": "active",
        }

    def test_valid_form(self):
        data = {**self._base_data(), "id_number": "8501015009086", "account_number": "123456"}
        form = BeneficiaryForm(data=data)
        assert form.is_valid(), form.errors

    def test_id_number_wrong_length(self):
        data = {**self._base_data(), "id_number": "12345"}
        form = BeneficiaryForm(data=data)
        assert not form.is_valid()
        assert "id_number" in form.errors

    def test_id_number_bad_luhn(self):
        data = {**self._base_data(), "id_number": "8501015009087"}  # bad check digit
        form = BeneficiaryForm(data=data)
        assert not form.is_valid()
        assert "checksum" in str(form.errors["id_number"])

    def test_account_number_too_short(self):
        data = {**self._base_data(), "account_number": "123"}
        form = BeneficiaryForm(data=data)
        assert not form.is_valid()
        assert "account_number" in form.errors

    def test_share_allocation_mismatch(self):
        data = {**self._base_data(), "total_shares": 100, "vested_shares": 50, "unvested_shares": 30}
        form = BeneficiaryForm(data=data)
        assert not form.is_valid()
        assert "Vested shares" in str(form.errors)

    def test_form_encrypts_on_save(self, company_a):
        data = {**self._base_data(), "id_number": "8501015009086", "account_number": "9876543210"}
        form = BeneficiaryForm(data=data)
        assert form.is_valid(), form.errors
        instance = form.save(commit=False)
        instance.company = company_a
        instance.save()
        # Reload from DB
        instance.refresh_from_db()
        assert instance.id_number == "8501015009086"
        assert instance.id_number_encrypted != "8501015009086"
        assert instance.account_number == "9876543210"
        assert instance.account_number_encrypted != "9876543210"


# ---------------------------------------------------------------------------
# View tests – permissions, CRUD, audit logging
# ---------------------------------------------------------------------------
class TestBeneficiaryViews:
    def test_list_requires_login(self, company_a):
        c = Client()
        url = reverse("beneficiaries:list", kwargs={"company_pk": company_a.pk})
        resp = c.get(url)
        assert resp.status_code in (302, 403)

    def test_list_denied_for_beneficiary_role(self, ben_client, company_a):
        url = reverse("beneficiaries:list", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_list_ok_for_admin(self, admin_client, company_a, beneficiary_a):
        url = reverse("beneficiaries:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert b"Thabo" in resp.content

    def test_detail_ok(self, admin_client, company_a, beneficiary_a):
        url = reverse("beneficiaries:detail", kwargs={
            "company_pk": company_a.pk, "pk": beneficiary_a.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert b"Mbeki" in resp.content

    def test_create_view_get(self, admin_client, company_a):
        url = reverse("beneficiaries:create", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_create_view_post(self, admin_client, company_a):
        url = reverse("beneficiaries:create", kwargs={"company_pk": company_a.pk})
        data = {
            "first_name": "Naledi", "last_name": "Zulu",
            "employee_number": "EMP100", "email": "naledi@alpha.co.za",
            "total_shares": 200, "vested_shares": 100, "unvested_shares": 100,
            "status": "active", "id_number": "8501015009086",
            "account_number": "123456789",
        }
        resp = admin_client.post(url, data)
        assert resp.status_code == 302  # redirect on success
        assert Beneficiary.objects.filter(employee_number="EMP100").exists()

    def test_create_audit_log(self, admin_client, company_a):
        url = reverse("beneficiaries:create", kwargs={"company_pk": company_a.pk})
        data = {
            "first_name": "Audit", "last_name": "Test",
            "employee_number": "EMPAUDIT",
            "total_shares": 10, "vested_shares": 5, "unvested_shares": 5,
            "status": "active",
        }
        admin_client.post(url, data)
        assert AuditLog.objects.filter(action="beneficiary_create").exists()

    def test_search_filter(self, admin_client, company_a, beneficiary_a):
        url = reverse("beneficiaries:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"q": "Thabo"})
        assert resp.status_code == 200
        assert b"Thabo" in resp.content
        resp2 = admin_client.get(url, {"q": "NONEXISTENT"})
        assert b"Thabo" not in resp2.content

    def test_status_filter(self, admin_client, company_a, beneficiary_a):
        url = reverse("beneficiaries:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"status": "terminated"})
        assert b"Thabo" not in resp.content
        resp2 = admin_client.get(url, {"status": "active"})
        assert b"Thabo" in resp2.content


# ---------------------------------------------------------------------------
# Tenant isolation tests
# ---------------------------------------------------------------------------
class TestBeneficiaryTenantIsolation:
    def test_queryset_cross_tenant(self, beneficiary_a, beneficiary_b, company_a, company_b):
        """Beneficiaries from company A must not appear in company B queryset."""
        qs_a = Beneficiary.objects.for_tenant(company_a)
        qs_b = Beneficiary.objects.for_tenant(company_b)
        assert qs_a.count() == 1
        assert qs_b.count() == 1
        assert qs_a.first().pk == beneficiary_a.pk
        assert qs_b.first().pk == beneficiary_b.pk

    def test_view_returns_only_own_company(self, admin_client, company_a, company_b, beneficiary_a, beneficiary_b):
        """List view for company A must not show company B's beneficiaries."""
        url = reverse("beneficiaries:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert b"Thabo" in resp.content
        assert b"Sipho" not in resp.content

    def test_detail_cross_tenant_404(self, admin_client, company_a, beneficiary_b):
        """Accessing company B's beneficiary through company A's URL → 404."""
        url = reverse("beneficiaries:detail", kwargs={
            "company_pk": company_a.pk, "pk": beneficiary_b.pk,
        })
        resp = admin_client.get(url)
        assert resp.status_code == 404

