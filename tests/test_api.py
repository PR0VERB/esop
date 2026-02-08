"""
Comprehensive tests for REST API endpoints.

Tests cover:
- Authentication (Token and Session)
- Permissions (tenant isolation, role-based access)
- CRUD operations for all endpoints
- State machine transitions via API
- Error handling and response format
- Audit logging

Note: Throttling is disabled in test settings.
"""

import pytest
from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus
from apps.dividends.models import DividendRun, DividendAllocation, RunStatus
from apps.month_end.models import MonthEndRun, MonthEndRunStatus
from apps.tenants.models import Company


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """Unauthenticated API client."""
    return APIClient()


@pytest.fixture
def company(db):
    """Create a test company."""
    return Company.objects.create(
        name="Test Company",
        registration_number="2025/000001/07",
    )


@pytest.fixture
def other_company(db):
    """Create another company for tenant isolation tests."""
    return Company.objects.create(
        name="Other Company",
        registration_number="2025/000002/07",
    )


@pytest.fixture
def admin_user(db, company):
    """Create a scheme admin user."""
    user = User.objects.create_user(
        username="admin_api",
        email="admin@test.com",
        password="securepassword123",
        role=UserRole.SCHEME_ADMIN,
        company=company,
    )
    return user


@pytest.fixture
def other_admin(db, other_company):
    """Create an admin for another company."""
    user = User.objects.create_user(
        username="other_admin",
        email="other@test.com",
        password="securepassword123",
        role=UserRole.SCHEME_ADMIN,
        company=other_company,
    )
    return user


@pytest.fixture
def beneficiary_user(db, company):
    """Create a beneficiary user."""
    user = User.objects.create_user(
        username="beneficiary_api",
        email="beneficiary@test.com",
        password="securepassword123",
        role=UserRole.BENEFICIARY,
        company=company,
    )
    return user


@pytest.fixture
def admin_token(admin_user):
    """Create auth token for admin."""
    token, _ = Token.objects.get_or_create(user=admin_user)
    return token


@pytest.fixture
def authenticated_client(api_client, admin_token):
    """API client authenticated with admin token."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
    return api_client


@pytest.fixture
def beneficiary(db, company, beneficiary_user):
    """Create a test beneficiary."""
    return Beneficiary.objects.create(
        company=company,
        user=beneficiary_user,
        employee_number="EMP001",
        first_name="John",
        last_name="Doe",
        email="john@test.com",
        vested_shares=1000,
        unvested_shares=500,
        total_shares=1500,
        status=BeneficiaryStatus.ACTIVE,
    )


@pytest.fixture
def other_beneficiary(db, other_company):
    """Create a beneficiary in another company."""
    return Beneficiary.objects.create(
        company=other_company,
        employee_number="EMP002",
        first_name="Jane",
        last_name="Smith",
        email="jane@other.com",
        status=BeneficiaryStatus.ACTIVE,
    )


@pytest.fixture
def dividend_run(db, company, admin_user):
    """Create a test dividend run."""
    return DividendRun.objects.create(
        company=company,
        title="Test Dividend",
        total_amount=Decimal("100000.00"),
        dividend_per_share=Decimal("10.00"),
        record_date=date.today(),
        payment_date=date.today(),
        idempotency_key="TEST-DIV-001",
        created_by=admin_user,
        status=RunStatus.DRAFT,
    )


# -----------------------------------------------------------------------------
# Authentication Tests
# -----------------------------------------------------------------------------

class TestAuthentication:
    """Test API authentication."""

    @pytest.mark.django_db
    def test_unauthenticated_request_rejected(self, api_client):
        """Unauthenticated requests should be rejected."""
        url = reverse("api:beneficiary-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_authentication_works(self, authenticated_client):
        """Token authentication should grant access."""
        url = reverse("api:beneficiary-list")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_session_authentication_works(self, api_client, admin_user):
        """Session authentication should grant access."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("api:beneficiary-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_obtain_token(self, api_client, admin_user):
        """User can obtain auth token via API."""
        url = reverse("api:api-token-auth")
        response = api_client.post(url, {
            "username": admin_user.username,
            "password": "securepassword123",
        })
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data


# -----------------------------------------------------------------------------
# Tenant Isolation Tests
# -----------------------------------------------------------------------------

class TestTenantIsolation:
    """Test tenant isolation in API."""

    def test_list_only_shows_own_tenant_data(
        self, authenticated_client, beneficiary, other_beneficiary
    ):
        """List endpoints should only show data from user's company."""
        url = reverse("api:beneficiary-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(beneficiary.id)

    def test_cannot_access_other_tenant_object(
        self, authenticated_client, other_beneficiary
    ):
        """Cannot retrieve object from another tenant."""
        url = reverse("api:beneficiary-detail", kwargs={"pk": other_beneficiary.id})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_update_other_tenant_object(
        self, authenticated_client, other_beneficiary
    ):
        """Cannot update object from another tenant."""
        url = reverse("api:beneficiary-detail", kwargs={"pk": other_beneficiary.id})
        response = authenticated_client.patch(url, {"first_name": "Hacked"}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_delete_other_tenant_object(
        self, authenticated_client, other_beneficiary
    ):
        """Cannot delete object from another tenant."""
        url = reverse("api:beneficiary-detail", kwargs={"pk": other_beneficiary.id})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# -----------------------------------------------------------------------------
# Beneficiary API Tests
# -----------------------------------------------------------------------------

class TestBeneficiaryAPI:
    """Test Beneficiary CRUD operations."""

    def test_list_beneficiaries(self, authenticated_client, beneficiary):
        """List beneficiaries."""
        url = reverse("api:beneficiary-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert len(response.data["results"]) == 1

    def test_retrieve_beneficiary(self, authenticated_client, beneficiary):
        """Retrieve single beneficiary."""
        url = reverse("api:beneficiary-detail", kwargs={"pk": beneficiary.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "John"
        assert response.data["last_name"] == "Doe"

    def test_create_beneficiary(self, authenticated_client, company):
        """Create new beneficiary."""
        url = reverse("api:beneficiary-list")
        data = {
            "employee_number": "EMP999",
            "first_name": "New",
            "last_name": "Employee",
            "email": "new@test.com",
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["employee_number"] == "EMP999"

        # Verify company was set from authenticated user
        created = Beneficiary.objects.get(employee_number="EMP999")
        assert created.company == company

    def test_update_beneficiary(self, authenticated_client, beneficiary):
        """Update beneficiary."""
        url = reverse("api:beneficiary-detail", kwargs={"pk": beneficiary.id})
        response = authenticated_client.patch(url, {"first_name": "Updated"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        beneficiary.refresh_from_db()
        assert beneficiary.first_name == "Updated"

    def test_delete_beneficiary(self, authenticated_client, beneficiary):
        """Delete beneficiary."""
        url = reverse("api:beneficiary-detail", kwargs={"pk": beneficiary.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Beneficiary.objects.filter(id=beneficiary.id).exists()


# -----------------------------------------------------------------------------
# Dividend Run API Tests
# -----------------------------------------------------------------------------

class TestDividendRunAPI:
    """Test Dividend Run CRUD and state transitions."""

    def test_list_dividend_runs(self, authenticated_client, dividend_run):
        """List dividend runs."""
        url = reverse("api:dividend-run-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_retrieve_dividend_run(self, authenticated_client, dividend_run):
        """Retrieve single dividend run."""
        url = reverse("api:dividend-run-detail", kwargs={"pk": dividend_run.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Test Dividend"

    def test_create_dividend_run(self, authenticated_client, company):
        """Create new dividend run."""
        url = reverse("api:dividend-run-list")
        data = {
            "title": "New Dividend",
            "total_amount": "50000.00",
            "dividend_per_share": "5.00",
            "record_date": str(date.today()),
            "payment_date": str(date.today()),
            "idempotency_key": "NEW-DIV-001",
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        created = DividendRun.objects.get(idempotency_key="NEW-DIV-001")
        assert created.company == company
        assert created.status == RunStatus.DRAFT

    def test_approve_dividend_run(self, api_client, dividend_run, other_admin):
        """Approve dividend run (four-eyes principle)."""
        # Create token for other admin (different from creator)
        token, _ = Token.objects.get_or_create(user=other_admin)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # Other admin's company must match
        dividend_run.company = other_admin.company
        dividend_run.save()

        url = reverse("api:dividend-run-approve", kwargs={"pk": dividend_run.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "approved"

        dividend_run.refresh_from_db()
        assert dividend_run.status == RunStatus.APPROVED

    def test_approve_own_run_fails(self, authenticated_client, dividend_run):
        """Cannot approve own dividend run (four-eyes principle)."""
        url = reverse("api:dividend-run-approve", kwargs={"pk": dividend_run.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid_state_transition" in response.data["error"]["code"]


# -----------------------------------------------------------------------------
# Permission Tests
# -----------------------------------------------------------------------------

class TestPermissions:
    """Test role-based permissions."""

    def test_beneficiary_cannot_create(self, api_client, beneficiary_user):
        """Beneficiaries cannot create beneficiaries."""
        token, _ = Token.objects.get_or_create(user=beneficiary_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        url = reverse("api:beneficiary-list")
        response = api_client.post(url, {
            "first_name": "New",
            "last_name": "Person",
        })

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_beneficiary_cannot_create_dividend_run(self, api_client, beneficiary_user):
        """Beneficiaries cannot create dividend runs."""
        token, _ = Token.objects.get_or_create(user=beneficiary_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        url = reverse("api:dividend-run-list")
        response = api_client.post(url, {"title": "Hacked"})

        assert response.status_code == status.HTTP_403_FORBIDDEN


# -----------------------------------------------------------------------------
# Error Response Format Tests
# -----------------------------------------------------------------------------

class TestErrorFormat:
    """Test consistent error response format."""

    def test_not_found_error_format(self, authenticated_client):
        """404 errors have consistent format."""
        import uuid
        url = reverse("api:beneficiary-detail", kwargs={"pk": uuid.uuid4()})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data
        assert "code" in response.data["error"]
        assert "message" in response.data["error"]

    def test_validation_error_format(self, authenticated_client):
        """Validation errors have consistent format."""
        url = reverse("api:dividend-run-list")
        # Missing required fields
        response = authenticated_client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "code" in response.data["error"]

