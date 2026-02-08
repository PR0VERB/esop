"""
Tests for Commit 6: Dividends app – state machine, allocation calculations,
idempotency, four-eyes principle, tenant isolation, permissions, audit logging.
"""

import uuid
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditAction, AuditLog
from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus
from apps.dividends.forms import DividendRunForm
from apps.dividends.models import (
    AllocationStatus,
    DEFAULT_DWT_RATE,
    DividendAllocation,
    DividendRun,
    RunStatus,
    VALID_TRANSITIONS,
)
from apps.dividends.services import (
    InvalidStateTransition,
    approve_run,
    process_run,
    reset_to_draft,
)
from apps.tenants.models import Company


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def company_a(db):
    return Company.objects.create(name="Alpha Corp", registration_number="REG-DIV-A")


@pytest.fixture
def company_b(db):
    return Company.objects.create(name="Beta Corp", registration_number="REG-DIV-B")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="div_admin", password="SecurePass123!", role=UserRole.SCHEME_ADMIN,
    )


@pytest.fixture
def admin_user_2(db):
    """Second admin for four-eyes principle tests."""
    return User.objects.create_user(
        username="div_admin2", password="SecurePass123!", role=UserRole.SCHEME_ADMIN,
    )


@pytest.fixture
def ben_user(db, company_a):
    return User.objects.create_user(
        username="div_ben", password="SecurePass123!",
        role=UserRole.BENEFICIARY, company=company_a,
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.login(username="div_admin", password="SecurePass123!")
    return c


@pytest.fixture
def admin2_client(admin_user_2):
    c = Client()
    c.login(username="div_admin2", password="SecurePass123!")
    return c


@pytest.fixture
def ben_client(ben_user):
    c = Client()
    c.login(username="div_ben", password="SecurePass123!")
    return c


@pytest.fixture
def draft_run(company_a, admin_user):
    return DividendRun.objects.create(
        company=company_a,
        title="FY2025 Final Dividend",
        total_amount=Decimal("100000.00"),
        dividend_per_share=Decimal("1.500000"),
        dwt_rate=DEFAULT_DWT_RATE,
        record_date="2025-06-30",
        payment_date="2025-07-15",
        idempotency_key="ALPHA-FY2025-FINAL",
        created_by=admin_user,
    )


@pytest.fixture
def beneficiary_active(company_a):
    return Beneficiary.objects.create(
        company=company_a,
        employee_number="EMP001",
        first_name="John",
        last_name="Doe",
        total_shares=1000,
        vested_shares=800,
        unvested_shares=200,
        status=BeneficiaryStatus.ACTIVE,
    )


@pytest.fixture
def beneficiary_active_2(company_a):
    return Beneficiary.objects.create(
        company=company_a,
        employee_number="EMP002",
        first_name="Jane",
        last_name="Smith",
        total_shares=500,
        vested_shares=300,
        unvested_shares=200,
        status=BeneficiaryStatus.ACTIVE,
    )


@pytest.fixture
def beneficiary_inactive(company_a):
    return Beneficiary.objects.create(
        company=company_a,
        employee_number="EMP003",
        first_name="Bob",
        last_name="Inactive",
        total_shares=200,
        vested_shares=200,
        unvested_shares=0,
        status=BeneficiaryStatus.INACTIVE,
    )


@pytest.fixture
def beneficiary_zero_vested(company_a):
    return Beneficiary.objects.create(
        company=company_a,
        employee_number="EMP004",
        first_name="Alice",
        last_name="Unvested",
        total_shares=100,
        vested_shares=0,
        unvested_shares=100,
        status=BeneficiaryStatus.ACTIVE,
    )


# ===========================================================================
# Model tests
# ===========================================================================
class TestDividendRunModel:
    def test_create_draft_run(self, draft_run):
        assert draft_run.status == RunStatus.DRAFT
        assert draft_run.is_editable is True
        assert draft_run.can_approve is True
        assert draft_run.can_process is False

    def test_str_representation(self, draft_run):
        assert "FY2025 Final Dividend" in str(draft_run)
        assert "Draft" in str(draft_run)

    def test_idempotency_key_unique(self, company_a, admin_user):
        """Duplicate idempotency key must raise IntegrityError."""
        from django.db import IntegrityError

        DividendRun.objects.create(
            company=company_a,
            title="Run 1",
            total_amount=Decimal("1000.00"),
            dividend_per_share=Decimal("1.000000"),
            record_date="2025-06-30",
            payment_date="2025-07-15",
            idempotency_key="UNIQUE-KEY-1",
            created_by=admin_user,
        )
        with pytest.raises(IntegrityError):
            DividendRun.objects.create(
                company=company_a,
                title="Run 2",
                total_amount=Decimal("2000.00"),
                dividend_per_share=Decimal("2.000000"),
                record_date="2025-06-30",
                payment_date="2025-07-15",
                idempotency_key="UNIQUE-KEY-1",
                created_by=admin_user,
            )

    def test_default_dwt_rate(self, draft_run):
        assert draft_run.dwt_rate == Decimal("0.20")

    def test_default_totals_zero(self, draft_run):
        assert draft_run.total_gross == Decimal("0.00")
        assert draft_run.total_tax == Decimal("0.00")
        assert draft_run.total_net == Decimal("0.00")
        assert draft_run.allocation_count == 0


class TestDividendAllocationModel:
    def test_unique_constraint(self, draft_run, beneficiary_active):
        """One allocation per beneficiary per run."""
        from django.db import IntegrityError

        DividendAllocation.objects.create(
            company=draft_run.company,
            run=draft_run,
            beneficiary=beneficiary_active,
            shares_at_record_date=800,
            gross_amount=Decimal("1200.00"),
            tax_amount=Decimal("240.00"),
            net_amount=Decimal("960.00"),
        )
        with pytest.raises(IntegrityError):
            DividendAllocation.objects.create(
                company=draft_run.company,
                run=draft_run,
                beneficiary=beneficiary_active,
                shares_at_record_date=800,
                gross_amount=Decimal("1200.00"),
                tax_amount=Decimal("240.00"),
                net_amount=Decimal("960.00"),
            )


class TestValidTransitions:
    def test_draft_can_go_to_approved(self):
        assert RunStatus.APPROVED in VALID_TRANSITIONS[RunStatus.DRAFT]

    def test_draft_cannot_go_to_processing(self):
        assert RunStatus.PROCESSING not in VALID_TRANSITIONS[RunStatus.DRAFT]

    def test_approved_can_go_to_processing(self):
        assert RunStatus.PROCESSING in VALID_TRANSITIONS[RunStatus.APPROVED]

    def test_approved_can_go_back_to_draft(self):
        assert RunStatus.DRAFT in VALID_TRANSITIONS[RunStatus.APPROVED]

    def test_completed_is_terminal(self):
        assert VALID_TRANSITIONS[RunStatus.COMPLETED] == []

    def test_failed_can_go_to_draft(self):
        assert RunStatus.DRAFT in VALID_TRANSITIONS[RunStatus.FAILED]


# ===========================================================================
# Service layer tests
# ===========================================================================
class TestApproveRun:
    def test_approve_draft_run(self, draft_run, admin_user_2):
        run = approve_run(draft_run, user=admin_user_2)
        assert run.status == RunStatus.APPROVED
        assert run.approved_by == admin_user_2
        assert run.approved_at is not None

    def test_four_eyes_principle(self, draft_run, admin_user):
        """Creator cannot approve their own run."""
        with pytest.raises(InvalidStateTransition, match="four-eyes"):
            approve_run(draft_run, user=admin_user)

    def test_approve_non_draft_fails(self, draft_run, admin_user, admin_user_2):
        approve_run(draft_run, user=admin_user_2)
        with pytest.raises(InvalidStateTransition):
            approve_run(draft_run, user=admin_user)

    def test_approve_creates_audit_log(self, draft_run, admin_user_2):
        approve_run(draft_run, user=admin_user_2)
        logs = AuditLog.objects.filter(
            action=AuditAction.DIVIDEND_RUN_STATE_CHANGE,
            target_id=str(draft_run.pk),
        )
        assert logs.exists()
        log = logs.first()
        assert log.details["old_status"] == RunStatus.DRAFT
        assert log.details["new_status"] == RunStatus.APPROVED


class TestProcessRun:
    def test_process_creates_allocations(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_active_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        run = process_run(draft_run, user=admin_user)

        assert run.status == RunStatus.COMPLETED
        assert run.allocation_count == 2
        assert run.completed_at is not None

    def test_allocation_amounts_correct(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        """gross = shares × dps, tax = gross × dwt, net = gross - tax."""
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)

        alloc = DividendAllocation.objects.get(
            run=draft_run, beneficiary=beneficiary_active,
        )
        expected_gross = Decimal("800") * Decimal("1.500000")  # 1200.00
        expected_tax = expected_gross * Decimal("0.20")  # 240.00
        expected_net = expected_gross - expected_tax  # 960.00

        assert alloc.shares_at_record_date == 800
        assert alloc.gross_amount == expected_gross.quantize(Decimal("0.01"))
        assert alloc.tax_amount == expected_tax.quantize(Decimal("0.01"))
        assert alloc.net_amount == expected_net.quantize(Decimal("0.01"))
        assert alloc.status == AllocationStatus.PENDING

    def test_inactive_beneficiaries_excluded(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_inactive,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)

        assert draft_run.allocation_count == 1
        assert not DividendAllocation.objects.filter(
            beneficiary=beneficiary_inactive,
        ).exists()

    def test_zero_vested_excluded(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_zero_vested,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)

        assert draft_run.allocation_count == 1
        assert not DividendAllocation.objects.filter(
            beneficiary=beneficiary_zero_vested,
        ).exists()

    def test_totals_computed(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_active_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)

        # Ben1: 800 × 1.5 = 1200, tax 240, net 960
        # Ben2: 300 × 1.5 = 450, tax 90, net 360
        assert draft_run.total_gross == Decimal("1650.00")
        assert draft_run.total_tax == Decimal("330.00")
        assert draft_run.total_net == Decimal("1320.00")

    def test_process_non_approved_fails(self, draft_run, admin_user):
        with pytest.raises(InvalidStateTransition):
            process_run(draft_run, user=admin_user)

    def test_process_creates_audit_logs(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)

        # Should have: DRAFT→APPROVED, APPROVED→PROCESSING, allocation, PROCESSING→COMPLETED
        state_logs = AuditLog.objects.filter(
            action=AuditAction.DIVIDEND_RUN_STATE_CHANGE,
            target_id=str(draft_run.pk),
        )
        assert state_logs.count() >= 3

        alloc_logs = AuditLog.objects.filter(
            action=AuditAction.DIVIDEND_ALLOCATION_APPLY,
            target_id=str(draft_run.pk),
        )
        assert alloc_logs.count() == 1


class TestResetToDraft:
    def test_reset_approved_to_draft(self, draft_run, admin_user, admin_user_2):
        approve_run(draft_run, user=admin_user_2)
        run = reset_to_draft(draft_run, user=admin_user)
        assert run.status == RunStatus.DRAFT
        assert run.approved_by is None
        assert run.approved_at is None

    def test_reset_failed_to_draft(self, draft_run, admin_user, admin_user_2, beneficiary_active):
        approve_run(draft_run, user=admin_user_2)
        # Force to FAILED state
        draft_run.status = RunStatus.FAILED
        draft_run.failure_reason = "Test failure"
        draft_run.save(update_fields=["status", "failure_reason", "updated_at"])

        run = reset_to_draft(draft_run, user=admin_user)
        assert run.status == RunStatus.DRAFT
        assert run.failure_reason == ""

    def test_reset_deletes_allocations(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)
        assert draft_run.allocations.count() > 0

        # Force back to FAILED so we can reset
        draft_run.status = RunStatus.FAILED
        draft_run.save(update_fields=["status", "updated_at"])

        reset_to_draft(draft_run, user=admin_user)
        assert draft_run.allocations.count() == 0
        assert draft_run.allocation_count == 0
        assert draft_run.total_gross == Decimal("0.00")

    def test_reset_completed_fails(self, draft_run, admin_user, admin_user_2, beneficiary_active):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)
        assert draft_run.status == RunStatus.COMPLETED

        with pytest.raises(InvalidStateTransition):
            reset_to_draft(draft_run, user=admin_user)

    def test_reset_draft_fails(self, draft_run, admin_user):
        """Cannot reset a run that is already DRAFT."""
        with pytest.raises(InvalidStateTransition):
            reset_to_draft(draft_run, user=admin_user)

# ===========================================================================
# Form tests
# ===========================================================================
@pytest.mark.django_db
class TestDividendRunForm:
    def test_valid_form(self):
        data = {
            "title": "Test Run",
            "total_amount": "50000.00",
            "dividend_per_share": "1.250000",
            "dwt_rate": "0.2000",
            "record_date": "2025-06-30",
            "payment_date": "2025-07-15",
            "idempotency_key": str(uuid.uuid4()),
        }
        form = DividendRunForm(data=data)
        assert form.is_valid(), form.errors

    def test_record_date_must_be_before_payment_date(self):
        data = {
            "title": "Test Run",
            "total_amount": "50000.00",
            "dividend_per_share": "1.250000",
            "dwt_rate": "0.2000",
            "record_date": "2025-07-15",
            "payment_date": "2025-06-30",
            "idempotency_key": str(uuid.uuid4()),
        }
        form = DividendRunForm(data=data)
        assert not form.is_valid()
        assert "Record date must be before payment date" in str(form.errors)

    def test_same_dates_rejected(self):
        data = {
            "title": "Test Run",
            "total_amount": "50000.00",
            "dividend_per_share": "1.250000",
            "dwt_rate": "0.2000",
            "record_date": "2025-07-15",
            "payment_date": "2025-07-15",
            "idempotency_key": str(uuid.uuid4()),
        }
        form = DividendRunForm(data=data)
        assert not form.is_valid()

    def test_idempotency_key_auto_generated(self):
        form = DividendRunForm()
        assert form.fields["idempotency_key"].initial is not None


# ===========================================================================
# View tests
# ===========================================================================
class TestDividendRunListView:
    def test_list_requires_login(self, company_a):
        c = Client()
        url = reverse("dividends:list", kwargs={"company_pk": company_a.pk})
        resp = c.get(url)
        assert resp.status_code == 302  # redirect to login

    def test_beneficiary_cannot_access(self, ben_client, company_a):
        url = reverse("dividends:list", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_admin_can_list(self, admin_client, company_a, draft_run):
        url = reverse("dividends:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "FY2025 Final Dividend" in resp.content.decode()

    def test_search_filter(self, admin_client, company_a, draft_run):
        url = reverse("dividends:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"q": "FY2025"})
        assert resp.status_code == 200
        assert "FY2025 Final Dividend" in resp.content.decode()

    def test_status_filter(self, admin_client, company_a, draft_run):
        url = reverse("dividends:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"status": "draft"})
        assert resp.status_code == 200
        assert "FY2025 Final Dividend" in resp.content.decode()

        resp = admin_client.get(url, {"status": "completed"})
        assert "FY2025 Final Dividend" not in resp.content.decode()


class TestDividendRunDetailView:
    def test_detail_requires_login(self, company_a, draft_run):
        c = Client()
        url = reverse("dividends:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = c.get(url)
        assert resp.status_code == 302

    def test_beneficiary_cannot_access(self, ben_client, company_a, draft_run):
        url = reverse("dividends:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_admin_can_view_detail(self, admin_client, company_a, draft_run):
        url = reverse("dividends:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "FY2025 Final Dividend" in resp.content.decode()

    def test_detail_shows_allocations(
        self, admin_client, company_a, draft_run,
        admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)
        url = reverse("dividends:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "John" in resp.content.decode()


class TestDividendRunCreateView:
    def test_create_requires_login(self, company_a):
        c = Client()
        url = reverse("dividends:create", kwargs={"company_pk": company_a.pk})
        resp = c.get(url)
        assert resp.status_code == 302

    def test_beneficiary_cannot_create(self, ben_client, company_a):
        url = reverse("dividends:create", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_admin_can_get_create_form(self, admin_client, company_a):
        url = reverse("dividends:create", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_admin_can_create_run(self, admin_client, company_a):
        url = reverse("dividends:create", kwargs={"company_pk": company_a.pk})
        data = {
            "title": "New Dividend Run",
            "total_amount": "50000.00",
            "dividend_per_share": "1.250000",
            "dwt_rate": "0.2000",
            "record_date": "2025-06-30",
            "payment_date": "2025-07-15",
            "idempotency_key": str(uuid.uuid4()),
        }
        resp = admin_client.post(url, data)
        assert resp.status_code == 302  # redirect on success
        assert DividendRun.objects.filter(title="New Dividend Run").exists()

    def test_create_generates_audit_log(self, admin_client, company_a):
        url = reverse("dividends:create", kwargs={"company_pk": company_a.pk})
        data = {
            "title": "Audited Run",
            "total_amount": "10000.00",
            "dividend_per_share": "0.500000",
            "dwt_rate": "0.2000",
            "record_date": "2025-06-30",
            "payment_date": "2025-07-15",
            "idempotency_key": str(uuid.uuid4()),
        }
        admin_client.post(url, data)
        assert AuditLog.objects.filter(
            action=AuditAction.DIVIDEND_RUN_CREATE,
        ).exists()


class TestDividendRunUpdateView:
    def test_can_update_draft_run(self, admin_client, company_a, draft_run):
        url = reverse("dividends:update", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_cannot_update_approved_run(
        self, admin_client, company_a, draft_run, admin_user_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("dividends:update", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 404  # filtered out by queryset


class TestDividendRunApproveView:
    def test_approve_via_post(self, admin2_client, company_a, draft_run):
        url = reverse("dividends:approve", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin2_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == RunStatus.APPROVED

    def test_approve_get_not_allowed(self, admin2_client, company_a, draft_run):
        url = reverse("dividends:approve", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin2_client.get(url)
        assert resp.status_code == 405  # method not allowed

    def test_creator_cannot_approve_via_view(self, admin_client, company_a, draft_run):
        url = reverse("dividends:approve", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302  # redirect back with error message
        draft_run.refresh_from_db()
        assert draft_run.status == RunStatus.DRAFT  # still draft


class TestDividendRunProcessView:
    def test_process_via_post(
        self, admin_client, company_a, draft_run,
        admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("dividends:process", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == RunStatus.COMPLETED

    def test_process_draft_fails(self, admin_client, company_a, draft_run):
        url = reverse("dividends:process", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == RunStatus.DRAFT  # unchanged


class TestDividendRunResetView:
    def test_reset_approved_via_post(
        self, admin_client, company_a, draft_run, admin_user_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("dividends:reset", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == RunStatus.DRAFT

    def test_reset_completed_fails(
        self, admin_client, company_a, draft_run,
        admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user)
        url = reverse("dividends:reset", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == RunStatus.COMPLETED  # unchanged


# ===========================================================================
# Tenant isolation tests
# ===========================================================================
class TestTenantIsolation:
    def test_list_only_shows_own_company_runs(
        self, admin_client, company_a, company_b, admin_user,
    ):
        """Runs from company_b must not appear in company_a listing."""
        # Create runs for both companies
        DividendRun.objects.create(
            company=company_a,
            title="Alpha Run",
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.000000"),
            record_date="2025-06-30",
            payment_date="2025-07-15",
            idempotency_key="ALPHA-ISO-1",
            created_by=admin_user,
        )
        DividendRun.objects.create(
            company=company_b,
            title="Beta Run",
            total_amount=Decimal("20000.00"),
            dividend_per_share=Decimal("2.000000"),
            record_date="2025-06-30",
            payment_date="2025-07-15",
            idempotency_key="BETA-ISO-1",
            created_by=admin_user,
        )

        url = reverse("dividends:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        content = resp.content.decode()
        assert "Alpha Run" in content
        assert "Beta Run" not in content

    def test_cannot_access_other_company_detail(
        self, admin_client, company_b, admin_user,
    ):
        """Accessing a run via wrong company_pk returns 404."""
        run = DividendRun.objects.create(
            company=company_b,
            title="Beta Only",
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.000000"),
            record_date="2025-06-30",
            payment_date="2025-07-15",
            idempotency_key="BETA-ISO-2",
            created_by=admin_user,
        )
        # Try to access beta run via alpha company URL — should 404
        url = reverse("dividends:detail", kwargs={"company_pk": company_b.pk, "pk": run.pk})
        resp = admin_client.get(url)
        # Admin can access company_b since SchemeAdmin has cross-tenant access
        # But the queryset scopes to company_pk, so direct access works
        # The key test: accessing via WRONG company_pk
        from apps.tenants.models import Company
        other_company = Company.objects.create(
            name="Ghost Corp", registration_number="REG-GHOST"
        )
        url_wrong = reverse("dividends:detail", kwargs={"company_pk": other_company.pk, "pk": run.pk})
        resp = admin_client.get(url_wrong)
        assert resp.status_code == 404

    def test_allocations_scoped_to_run_company(
        self, company_a, company_b, admin_user, admin_user_2,
    ):
        """Allocations must only include beneficiaries from the run's company."""
        # Ben in company_a
        Beneficiary.objects.create(
            company=company_a, employee_number="EMP-A1",
            first_name="InA", last_name="User",
            total_shares=100, vested_shares=100, unvested_shares=0,
            status=BeneficiaryStatus.ACTIVE,
        )
        # Ben in company_b
        Beneficiary.objects.create(
            company=company_b, employee_number="EMP-B1",
            first_name="InB", last_name="User",
            total_shares=200, vested_shares=200, unvested_shares=0,
            status=BeneficiaryStatus.ACTIVE,
        )

        run = DividendRun.objects.create(
            company=company_a,
            title="Scoped Run",
            total_amount=Decimal("10000.00"),
            dividend_per_share=Decimal("1.000000"),
            record_date="2025-06-30",
            payment_date="2025-07-15",
            idempotency_key="SCOPE-TEST-1",
            created_by=admin_user,
        )
        approve_run(run, user=admin_user_2)
        process_run(run, user=admin_user)

        # Only company_a beneficiary should have an allocation
        assert run.allocation_count == 1
        alloc = run.allocations.first()
        assert alloc.beneficiary.company == company_a
