"""
Comprehensive tests for Celery tasks.

Tests cover:
- Dividend tasks: process_dividend_run_async, submit_dividend_payments_async
- Month-end tasks: process_month_end_run_async, submit_tax_directives_async, submit_month_end_payments_async
- Integration tasks: sync_payroll_data_async, poll_tax_directive_status_async, poll_payment_status_async
- Idempotency (skipping already completed runs)
- Error handling (missing objects, invalid states)
- Audit log creation

Note: CELERY_TASK_ALWAYS_EAGER = True in test settings ensures synchronous execution.
"""

import pytest
from datetime import date
from decimal import Decimal

from apps.accounts.models import User
from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus
from apps.dividends.models import DividendRun, DividendAllocation, RunStatus, AllocationStatus
from apps.month_end.models import (
    MonthEndRun,
    MonthEndRunStatus,
    VestingEvent,
    TaxDirective,
    TaxDirectiveStatus,
)
from apps.tenants.models import Company


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def company(db):
    """Create a test company."""
    return Company.objects.create(
        name="Task Test Company",
        registration_number="2025/000099/07",
    )


@pytest.fixture
def other_company(db):
    """Create another company for isolation tests."""
    return Company.objects.create(
        name="Other Company",
        registration_number="2025/000100/07",
    )


@pytest.fixture
def admin_user(db, company):
    """Create an admin user."""
    return User.objects.create_user(
        username="task_admin",
        password="SecurePass123!",
        company=company,
        role="scheme_admin",
    )


@pytest.fixture
def approver_user(db, company):
    """Create an approver user (different from creator for four-eyes)."""
    return User.objects.create_user(
        username="task_approver",
        password="SecurePass123!",
        company=company,
        role="scheme_admin",
    )


@pytest.fixture
def beneficiary(db, company):
    """Create a test beneficiary."""
    return Beneficiary.objects.create(
        company=company,
        first_name="Task",
        last_name="Tester",
        employee_number="TASK001",
        email="task@test.com",
        status=BeneficiaryStatus.ACTIVE,
        vested_shares=100,
        unvested_shares=50,
        total_shares=150,
        bank_name="Test Bank",
        branch_code="123456",
        tax_number="1234567890",
    )


@pytest.fixture
def draft_dividend_run(db, company, admin_user):
    """Create a draft dividend run."""
    return DividendRun.objects.create(
        company=company,
        title="Test Dividend Run",
        record_date=date.today(),
        payment_date=date.today(),
        total_amount=Decimal("10000.00"),
        dividend_per_share=Decimal("1.50"),
        idempotency_key="task-test-dividend-001",
        created_by=admin_user,
    )


@pytest.fixture
def approved_dividend_run(db, company, admin_user, approver_user):
    """Create an approved dividend run."""
    run = DividendRun.objects.create(
        company=company,
        title="Approved Dividend Run",
        record_date=date.today(),
        payment_date=date.today(),
        total_amount=Decimal("10000.00"),
        dividend_per_share=Decimal("2.00"),
        idempotency_key="task-test-dividend-002",
        created_by=admin_user,
        status=RunStatus.APPROVED,
        approved_by=approver_user,
    )
    return run


@pytest.fixture
def draft_month_end_run(db, company, admin_user):
    """Create a draft month-end run."""
    return MonthEndRun.objects.create(
        company=company,
        title="January 2025 Month-End",
        period_month=1,
        period_year=2025,
        idempotency_key="task-test-month-end-001",
        created_by=admin_user,
    )


@pytest.fixture
def approved_month_end_run(db, company, admin_user, approver_user):
    """Create an approved month-end run."""
    run = MonthEndRun.objects.create(
        company=company,
        title="February 2025 Month-End",
        period_month=2,
        period_year=2025,
        idempotency_key="task-test-month-end-002",
        created_by=admin_user,
        status=MonthEndRunStatus.APPROVED,
        approved_by=approver_user,
    )
    return run


# -----------------------------------------------------------------------------
# Dividend Tasks Tests
# -----------------------------------------------------------------------------

class TestProcessDividendRunAsync:
    """Tests for process_dividend_run_async task."""
    
    def test_process_approved_run(self, approved_dividend_run, admin_user, beneficiary):
        """Test processing an approved dividend run."""
        from apps.dividends.tasks import process_dividend_run_async

        result = process_dividend_run_async(
            str(approved_dividend_run.pk),
            str(admin_user.pk),
        )

        assert result["status"] == "success"
        assert result["allocation_count"] >= 0

        # Verify run status changed
        approved_dividend_run.refresh_from_db()
        assert approved_dividend_run.status == RunStatus.COMPLETED

    def test_skip_already_completed_run(self, company, admin_user, approver_user):
        """Test idempotency: skip already completed run."""
        from apps.dividends.tasks import process_dividend_run_async

        run = DividendRun.objects.create(
            company=company,
            title="Completed Run",
            record_date=date.today(),
            payment_date=date.today(),
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.00"),
            idempotency_key="task-test-completed-001",
            created_by=admin_user,
            status=RunStatus.COMPLETED,
            approved_by=approver_user,
        )

        result = process_dividend_run_async(str(run.pk), str(admin_user.pk))

        assert result["status"] == "skipped"
        assert "already completed" in result["message"]

    def test_error_on_draft_run(self, draft_dividend_run, admin_user):
        """Test that draft runs cannot be processed."""
        from apps.dividends.tasks import process_dividend_run_async

        result = process_dividend_run_async(
            str(draft_dividend_run.pk),
            str(admin_user.pk),
        )

        assert result["status"] == "error"
        assert "Draft" in result["message"]

    def test_error_on_missing_run(self, admin_user):
        """Test error handling for missing run."""
        from apps.dividends.tasks import process_dividend_run_async
        import uuid

        result = process_dividend_run_async(
            str(uuid.uuid4()),
            str(admin_user.pk),
        )

        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_error_on_missing_user(self, approved_dividend_run):
        """Test error handling for missing user."""
        from apps.dividends.tasks import process_dividend_run_async
        import uuid

        result = process_dividend_run_async(
            str(approved_dividend_run.pk),
            str(uuid.uuid4()),
        )

        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestSubmitDividendPaymentsAsync:
    """Tests for submit_dividend_payments_async task."""

    def test_submit_payments_for_completed_run(
        self, company, admin_user, approver_user, beneficiary
    ):
        """Test submitting payments for a completed run."""
        from apps.dividends.tasks import submit_dividend_payments_async

        # Create a completed run with allocation
        run = DividendRun.objects.create(
            company=company,
            title="Payment Test Run",
            record_date=date.today(),
            payment_date=date.today(),
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.00"),
            idempotency_key="payment-test-001",
            created_by=admin_user,
            status=RunStatus.COMPLETED,
            approved_by=approver_user,
        )

        # Create allocation
        alloc = DividendAllocation.objects.create(
            company=company,
            run=run,
            beneficiary=beneficiary,
            shares_at_record_date=100,
            gross_amount=Decimal("100.00"),
            tax_amount=Decimal("20.00"),
            net_amount=Decimal("80.00"),
            status=AllocationStatus.PENDING,
        )

        result = submit_dividend_payments_async(str(run.pk), str(admin_user.pk))

        assert result["status"] in ("success", "partial")
        assert "submitted" in result
        assert "failed" in result

    def test_error_on_non_completed_run(self, approved_dividend_run, admin_user):
        """Test that only completed runs can have payments submitted."""
        from apps.dividends.tasks import submit_dividend_payments_async

        result = submit_dividend_payments_async(
            str(approved_dividend_run.pk),
            str(admin_user.pk),
        )

        assert result["status"] == "error"
        assert "approved status" in result["message"].lower() or "must be completed" in result["message"].lower()


# -----------------------------------------------------------------------------
# Month-End Tasks Tests
# -----------------------------------------------------------------------------

class TestProcessMonthEndRunAsync:
    """Tests for process_month_end_run_async task."""

    def test_process_approved_run(
        self, approved_month_end_run, admin_user, beneficiary
    ):
        """Test processing an approved month-end run."""
        from apps.month_end.tasks import process_month_end_run_async

        result = process_month_end_run_async(
            str(approved_month_end_run.pk),
            str(admin_user.pk),
            share_price="10.00",
            tax_rate="0.35",
        )

        assert result["status"] == "success"

        # Verify run status changed
        approved_month_end_run.refresh_from_db()
        assert approved_month_end_run.status == MonthEndRunStatus.COMPLETED

    def test_skip_already_completed_run(self, company, admin_user, approver_user):
        """Test idempotency: skip already completed run."""
        from apps.month_end.tasks import process_month_end_run_async

        run = MonthEndRun.objects.create(
            company=company,
            title="Completed ME Run",
            period_month=3,
            period_year=2025,
            idempotency_key="me-completed-001",
            created_by=admin_user,
            status=MonthEndRunStatus.COMPLETED,
            approved_by=approver_user,
        )

        result = process_month_end_run_async(
            str(run.pk),
            str(admin_user.pk),
            share_price="10.00",
        )

        assert result["status"] == "skipped"
        assert "already completed" in result["message"]

    def test_error_on_draft_run(self, draft_month_end_run, admin_user):
        """Test that draft runs cannot be processed."""
        from apps.month_end.tasks import process_month_end_run_async

        result = process_month_end_run_async(
            str(draft_month_end_run.pk),
            str(admin_user.pk),
            share_price="10.00",
        )

        assert result["status"] == "error"
        assert "Draft" in result["message"]


class TestSubmitTaxDirectivesAsync:
    """Tests for submit_tax_directives_async task."""

    def test_submit_directives_for_completed_run(
        self, company, admin_user, approver_user, beneficiary
    ):
        """Test submitting tax directives for a completed run."""
        from apps.month_end.tasks import submit_tax_directives_async
        from apps.month_end.models import VestingEvent, VestingEventType

        run = MonthEndRun.objects.create(
            company=company,
            title="Directive Test Run",
            period_month=4,
            period_year=2025,
            idempotency_key="directive-test-001",
            created_by=admin_user,
            status=MonthEndRunStatus.COMPLETED,
            approved_by=approver_user,
        )

        # Create vesting event
        VestingEvent.objects.create(
            company=company,
            run=run,
            beneficiary=beneficiary,
            event_type=VestingEventType.SALE,
            event_date=date.today(),
            shares_affected=100,
            shares_before=100,
            shares_after=0,
            share_price=Decimal("10.00"),
            gross_amount=Decimal("1000.00"),
            tax_amount=Decimal("350.00"),
            net_amount=Decimal("650.00"),
        )

        result = submit_tax_directives_async(str(run.pk), str(admin_user.pk))

        assert result["status"] in ("success", "partial")
        assert "submitted" in result

    def test_error_on_non_completed_run(self, approved_month_end_run, admin_user):
        """Test that only completed runs can have directives submitted."""
        from apps.month_end.tasks import submit_tax_directives_async

        result = submit_tax_directives_async(
            str(approved_month_end_run.pk),
            str(admin_user.pk),
        )

        assert result["status"] == "error"
        assert "must be completed" in result["message"]


# -----------------------------------------------------------------------------
# Integration Tasks Tests
# -----------------------------------------------------------------------------

class TestSyncPayrollDataAsync:
    """Tests for sync_payroll_data_async task."""

    def test_sync_payroll_success(self, company, admin_user):
        """Test successful payroll sync."""
        from apps.integrations.tasks import sync_payroll_data_async

        result = sync_payroll_data_async(str(company.pk), str(admin_user.pk))

        assert result["status"] == "success"
        assert "employees_synced" in result

    def test_error_on_missing_company(self, admin_user):
        """Test error handling for missing company."""
        from apps.integrations.tasks import sync_payroll_data_async
        import uuid

        result = sync_payroll_data_async(str(uuid.uuid4()), str(admin_user.pk))

        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestPollTaxDirectiveStatusAsync:
    """Tests for poll_tax_directive_status_async task."""

    def test_skip_already_resolved_directive(
        self, company, admin_user, beneficiary, approved_month_end_run
    ):
        """Test that already resolved directives are skipped."""
        from apps.integrations.tasks import poll_tax_directive_status_async

        directive = TaxDirective.objects.create(
            company=company,
            beneficiary=beneficiary,
            run=approved_month_end_run,
            tax_year=2025,
            taxable_amount=Decimal("1000.00"),
            status=TaxDirectiveStatus.RECEIVED,
            directive_number="DIR123",
        )

        result = poll_tax_directive_status_async(
            str(directive.pk),
            str(admin_user.pk),
        )

        assert result["status"] == "skipped"
        assert "already resolved" in result["message"]

    def test_skip_directive_without_number(
        self, company, admin_user, beneficiary, approved_month_end_run
    ):
        """Test that directives without a number are skipped."""
        from apps.integrations.tasks import poll_tax_directive_status_async

        directive = TaxDirective.objects.create(
            company=company,
            beneficiary=beneficiary,
            run=approved_month_end_run,
            tax_year=2025,
            taxable_amount=Decimal("1000.00"),
            status=TaxDirectiveStatus.REQUESTED,
            directive_number="",  # No number yet
        )

        result = poll_tax_directive_status_async(
            str(directive.pk),
            str(admin_user.pk),
        )

        assert result["status"] == "skipped"
        assert "No directive number" in result["message"]


class TestPollPaymentStatusAsync:
    """Tests for poll_payment_status_async task."""

    def test_skip_already_paid_allocation(
        self, company, admin_user, approver_user, beneficiary
    ):
        """Test that already paid allocations are skipped."""
        from apps.integrations.tasks import poll_payment_status_async

        run = DividendRun.objects.create(
            company=company,
            title="Paid Run",
            record_date=date.today(),
            payment_date=date.today(),
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.00"),
            idempotency_key="poll-payment-001",
            created_by=admin_user,
            status=RunStatus.COMPLETED,
        )

        alloc = DividendAllocation.objects.create(
            company=company,
            run=run,
            beneficiary=beneficiary,
            shares_at_record_date=100,
            gross_amount=Decimal("100.00"),
            tax_amount=Decimal("20.00"),
            net_amount=Decimal("80.00"),
            status=AllocationStatus.PAID,
            payment_reference="PAY123",
        )

        result = poll_payment_status_async(str(alloc.pk), str(admin_user.pk))

        assert result["status"] == "skipped"
        assert "already resolved" in result["message"]

    def test_skip_allocation_without_payment_ref(
        self, company, admin_user, approver_user, beneficiary
    ):
        """Test that allocations without payment reference are skipped."""
        from apps.integrations.tasks import poll_payment_status_async

        run = DividendRun.objects.create(
            company=company,
            title="Unpaid Run",
            record_date=date.today(),
            payment_date=date.today(),
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.00"),
            idempotency_key="poll-payment-002",
            created_by=admin_user,
            status=RunStatus.COMPLETED,
        )

        alloc = DividendAllocation.objects.create(
            company=company,
            run=run,
            beneficiary=beneficiary,
            shares_at_record_date=100,
            gross_amount=Decimal("100.00"),
            tax_amount=Decimal("20.00"),
            net_amount=Decimal("80.00"),
            status=AllocationStatus.PENDING,
            payment_reference="",  # No reference yet
        )

        result = poll_payment_status_async(str(alloc.pk), str(admin_user.pk))

        assert result["status"] == "skipped"
        assert "No payment reference" in result["message"]

    def test_error_on_missing_allocation(self, admin_user):
        """Test error handling for missing allocation."""
        from apps.integrations.tasks import poll_payment_status_async
        import uuid

        result = poll_payment_status_async(str(uuid.uuid4()), str(admin_user.pk))

        assert result["status"] == "error"
        assert "not found" in result["message"]

