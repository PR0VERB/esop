"""
Comprehensive tests for the integrations app.

Tests cover:
- IntegrationLog model
- Base integration client
- Payroll, SARS, Velocity Trade, Banking client stubs
- Tenant isolation
- Idempotency
- Error handling
"""

import pytest
from datetime import date
from decimal import Decimal

from apps.integrations.models import IntegrationLog, IntegrationSystem, IntegrationStatus
from apps.integrations.base import BaseIntegrationClient
from apps.integrations.payroll import PayrollClient, EmployeeData
from apps.integrations.sars import SARSClient, TaxDirectiveRequest, DirectiveStatus
from apps.integrations.velocity import VelocityTradeClient, TradeRequest, TradeStatus
from apps.integrations.banking import BankingClient, PaymentRequest, PaymentStatus, PaymentType
from apps.tenants.models import Company
from apps.accounts.models import User


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def company(db):
    """Create a test company."""
    return Company.objects.create(
        name="Test Company",
        registration_number="2025/000001/07",
    )


@pytest.fixture
def other_company(db):
    """Create another company for isolation tests."""
    return Company.objects.create(
        name="Other Company",
        registration_number="2025/000002/07",
    )


@pytest.fixture
def user(db, company):
    """Create a test user."""
    return User.objects.create_user(
        username="admin_integration",
        password="SecurePass123!",
        company=company,
        role="scheme_admin",
    )


# -----------------------------------------------------------------------------
# IntegrationLog Model Tests
# -----------------------------------------------------------------------------

class TestIntegrationLogModel:
    """Tests for IntegrationLog model."""

    def test_create_integration_log(self, company, user):
        """Test creating an integration log entry."""
        log = IntegrationLog.objects.create(
            company=company,
            system=IntegrationSystem.PAYROLL,
            operation="sync_employees",
            status=IntegrationStatus.IN_PROGRESS,
            initiated_by=user,
        )
        assert log.id is not None
        assert log.company == company
        assert log.system == IntegrationSystem.PAYROLL
        assert log.status == IntegrationStatus.IN_PROGRESS

    def test_log_str_representation(self, company):
        """Test string representation of log."""
        log = IntegrationLog.objects.create(
            company=company,
            system=IntegrationSystem.SARS,
            operation="submit_directive",
            status=IntegrationStatus.SUCCESS,
        )
        assert "sars" in str(log).lower()
        assert "submit_directive" in str(log)

    def test_duration_seconds_when_completed(self, company):
        """Test duration calculation when completed."""
        from django.utils import timezone
        log = IntegrationLog.objects.create(
            company=company,
            system=IntegrationSystem.BANKING,
            operation="submit_payment",
        )
        log.completed_at = timezone.now()
        log.save()
        assert log.duration_seconds is not None
        assert log.duration_seconds >= 0

    def test_can_retry_when_failed(self, company):
        """Test can_retry property for failed logs."""
        log = IntegrationLog.objects.create(
            company=company,
            system=IntegrationSystem.VELOCITY_TRADE,
            operation="execute_trade",
            status=IntegrationStatus.FAILED,
            retry_count=0,
            max_retries=3,
        )
        assert log.can_retry is True

    def test_cannot_retry_when_max_reached(self, company):
        """Test can_retry is False when max retries reached."""
        log = IntegrationLog.objects.create(
            company=company,
            system=IntegrationSystem.VELOCITY_TRADE,
            operation="execute_trade",
            status=IntegrationStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        assert log.can_retry is False

    def test_tenant_scoping(self, company, other_company):
        """Test that logs are scoped by tenant."""
        IntegrationLog.objects.create(
            company=company,
            system=IntegrationSystem.PAYROLL,
            operation="test_op",
        )
        IntegrationLog.objects.create(
            company=other_company,
            system=IntegrationSystem.PAYROLL,
            operation="other_op",
        )
        
        company_logs = IntegrationLog.objects.for_tenant(company)
        assert company_logs.count() == 1
        assert company_logs.first().operation == "test_op"


# -----------------------------------------------------------------------------
# Base Client Tests
# -----------------------------------------------------------------------------

class TestBaseIntegrationClient:
    """Tests for BaseIntegrationClient."""

    def test_sanitise_request_redacts_sensitive_fields(self, company, user):
        """Test that sensitive fields are redacted."""
        client = PayrollClient(company, user)
        data = {
            "employee_id": "123",
            "password": "secret123",
            "api_key": "key123",
            "bank_account": "1234567890",
        }
        sanitised = client._sanitise_request(data)
        assert sanitised["employee_id"] == "123"
        assert sanitised["password"] == "***REDACTED***"
        assert sanitised["api_key"] == "***REDACTED***"
        assert sanitised["bank_account"] == "***REDACTED***"


# -----------------------------------------------------------------------------
# Payroll Client Tests
# -----------------------------------------------------------------------------

class TestPayrollClient:
    """Tests for PayrollClient stub."""

    def test_health_check(self, company, user):
        """Test health check returns True."""
        client = PayrollClient(company, user)
        result = client.health_check()
        assert result is True
        # Verify log was created
        log = IntegrationLog.objects.filter(
            system=IntegrationSystem.PAYROLL,
            operation="health_check",
        ).first()
        assert log is not None
        assert log.status == IntegrationStatus.SUCCESS

    def test_get_active_employees(self, company, user):
        """Test get_active_employees returns empty list (stub)."""
        client = PayrollClient(company, user)
        result = client.get_active_employees()
        assert result == []
        log = IntegrationLog.objects.filter(operation="get_active_employees").first()
        assert log.status == IntegrationStatus.SUCCESS

    def test_get_employee_updates(self, company, user):
        """Test get_employee_updates returns empty changes."""
        client = PayrollClient(company, user)
        result = client.get_employee_updates(date.today())
        assert "new_hires" in result
        assert "terminations" in result
        assert "promotions" in result

    def test_upload_irp5_data(self, company, user):
        """Test upload_irp5_data succeeds."""
        client = PayrollClient(company, user)
        result = client.upload_irp5_data("ben-123", 2025, {"taxable_income": 100000})
        assert result is True


# -----------------------------------------------------------------------------
# SARS Client Tests
# -----------------------------------------------------------------------------

class TestSARSClient:
    """Tests for SARSClient stub."""

    def test_health_check(self, company, user):
        """Test health check returns True."""
        client = SARSClient(company, user)
        result = client.health_check()
        assert result is True

    def test_submit_tax_directive(self, company, user):
        """Test submitting a tax directive."""
        client = SARSClient(company, user)
        request = TaxDirectiveRequest(
            beneficiary_id="ben-123",
            id_number="9001015009087",
            tax_number="1234567890",
            gross_amount=Decimal("50000.00"),
            tax_year=2025,
        )
        response = client.submit_tax_directive(request, idempotency_key="test-key-1")
        assert response.reference_number is not None
        assert response.status == DirectiveStatus.PENDING
        # Verify log has idempotency key
        log = IntegrationLog.objects.filter(idempotency_key="test-key-1").first()
        assert log is not None

    def test_get_directive_status(self, company, user):
        """Test getting directive status returns approved."""
        client = SARSClient(company, user)
        response = client.get_directive_status("SARS-2025-test")
        assert response.status == DirectiveStatus.APPROVED
        assert response.tax_rate == Decimal("0.35")

    def test_bulk_submit_directives(self, company, user):
        """Test bulk submission."""
        client = SARSClient(company, user)
        requests = [
            TaxDirectiveRequest("ben-1", "id1", "tax1", Decimal("1000"), 2025),
            TaxDirectiveRequest("ben-2", "id2", "tax2", Decimal("2000"), 2025),
        ]
        responses = client.bulk_submit_directives(requests)
        assert len(responses) == 2


# -----------------------------------------------------------------------------
# Velocity Trade Client Tests
# -----------------------------------------------------------------------------

class TestVelocityTradeClient:
    """Tests for VelocityTradeClient stub."""

    def test_health_check(self, company, user):
        """Test health check returns True."""
        client = VelocityTradeClient(company, user)
        assert client.health_check() is True

    def test_execute_trade(self, company, user):
        """Test executing a trade."""
        client = VelocityTradeClient(company, user)
        request = TradeRequest(
            beneficiary_id="ben-123",
            shares=100,
            trade_type="SELL",
        )
        response = client.execute_trade(request)
        assert response.trade_reference is not None
        assert response.status == TradeStatus.PENDING

    def test_get_trade_status(self, company, user):
        """Test getting trade status."""
        client = VelocityTradeClient(company, user)
        response = client.get_trade_status("VT-20250208-abc123")
        assert response.status == TradeStatus.EXECUTED
        assert response.executed_price is not None

    def test_get_contract_note(self, company, user):
        """Test getting contract note."""
        client = VelocityTradeClient(company, user)
        note = client.get_contract_note("VT-20250208-abc123")
        assert note is not None
        assert note.contract_number is not None
        assert note.net_value < note.gross_value  # Fees deducted


# -----------------------------------------------------------------------------
# Banking Client Tests
# -----------------------------------------------------------------------------

class TestBankingClient:
    """Tests for BankingClient stub."""

    def test_health_check(self, company, user):
        """Test health check returns True."""
        client = BankingClient(company, user)
        assert client.health_check() is True

    def test_submit_eft_payment(self, company, user):
        """Test submitting an EFT payment."""
        client = BankingClient(company, user)
        request = PaymentRequest(
            beneficiary_id="ben-123",
            amount=Decimal("5000.00"),
            bank_account="1234567890",
            bank_code="051001",
            reference="DIV-2025-001",
        )
        response = client.submit_eft_payment(request)
        assert response.payment_reference is not None
        assert response.status == PaymentStatus.PENDING
        # Verify bank_account was redacted in log
        log = IntegrationLog.objects.filter(operation="submit_eft_payment").first()
        assert log.request_data.get("bank_account") == "***REDACTED***"

    def test_submit_naedo_payment(self, company, user):
        """Test submitting a NAEDO payment."""
        client = BankingClient(company, user)
        request = PaymentRequest(
            beneficiary_id="ben-123",
            amount=Decimal("1000.00"),
            bank_account="1234567890",
            bank_code="051001",
            reference="TAX-2025-001",
            payment_type=PaymentType.NAEDO,
        )
        response = client.submit_naedo_payment(request)
        assert response.payment_reference.startswith("NAEDO-")

    def test_get_payment_status(self, company, user):
        """Test getting payment status."""
        client = BankingClient(company, user)
        response = client.get_payment_status("EFT-20250208123456")
        assert response.status == PaymentStatus.COMPLETED


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------

class TestIntegrationLogging:
    """Tests for integration logging across all clients."""

    def test_all_clients_create_logs(self, company, user):
        """Test that all client operations create logs."""
        PayrollClient(company, user).health_check()
        SARSClient(company, user).health_check()
        VelocityTradeClient(company, user).health_check()
        BankingClient(company, user).health_check()

        logs = IntegrationLog.objects.for_tenant(company)
        assert logs.count() == 4
        systems = set(log.system for log in logs)
        assert IntegrationSystem.PAYROLL in systems
        assert IntegrationSystem.SARS in systems
        assert IntegrationSystem.VELOCITY_TRADE in systems
        assert IntegrationSystem.BANKING in systems

    def test_logs_include_user(self, company, user):
        """Test that logs include the initiating user."""
        client = PayrollClient(company, user)
        client.health_check()
        log = IntegrationLog.objects.first()
        assert log.initiated_by == user

    def test_logs_without_user(self, company):
        """Test that logs work without a user."""
        client = PayrollClient(company)
        client.health_check()
        log = IntegrationLog.objects.first()
        assert log.initiated_by is None

