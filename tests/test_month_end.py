"""
Tests for Commit 7: Month-End app – state machine, vesting events,
tax directives, four-eyes principle, tenant isolation, permissions, audit logging.
"""

import uuid
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditAction, AuditLog
from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus
from apps.month_end.forms import MonthEndRunForm, ProcessRunForm
from apps.month_end.models import (
    MonthEndRun,
    MonthEndRunStatus,
    TaxDirective,
    TaxDirectiveStatus,
    VALID_TRANSITIONS,
    VestingEvent,
    VestingEventStatus,
    VestingEventType,
)
from apps.month_end.services import (
    InvalidStateTransition,
    approve_run,
    create_tax_directive,
    process_run,
    reset_to_draft,
    update_tax_directive_status,
)
from apps.tenants.models import Company


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def company_a(db):
    return Company.objects.create(name="Alpha Corp", registration_number="REG-ME-A")


@pytest.fixture
def company_b(db):
    return Company.objects.create(name="Beta Corp", registration_number="REG-ME-B")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="me_admin", password="SecurePass123!", role=UserRole.SCHEME_ADMIN,
    )


@pytest.fixture
def admin_user_2(db):
    """Second admin for four-eyes principle tests."""
    return User.objects.create_user(
        username="me_admin2", password="SecurePass123!", role=UserRole.SCHEME_ADMIN,
    )


@pytest.fixture
def ben_user(db, company_a):
    return User.objects.create_user(
        username="me_ben", password="SecurePass123!",
        role=UserRole.BENEFICIARY, company=company_a,
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.login(username="me_admin", password="SecurePass123!")
    return c


@pytest.fixture
def admin2_client(admin_user_2):
    c = Client()
    c.login(username="me_admin2", password="SecurePass123!")
    return c


@pytest.fixture
def ben_client(ben_user):
    c = Client()
    c.login(username="me_ben", password="SecurePass123!")
    return c


@pytest.fixture
def draft_run(company_a, admin_user):
    return MonthEndRun.objects.create(
        company=company_a,
        title="January 2025 Month-End",
        period_year=2025,
        period_month=1,
        idempotency_key="ALPHA-2025-01",
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
class TestMonthEndRunModel:
    def test_create_draft_run(self, draft_run):
        assert draft_run.status == MonthEndRunStatus.DRAFT
        assert draft_run.is_editable is True
        assert draft_run.can_approve is True
        assert draft_run.can_process is False

    def test_str_representation(self, draft_run):
        assert "January 2025 Month-End" in str(draft_run)
        assert "Draft" in str(draft_run)

    def test_period_display(self, draft_run):
        assert draft_run.period_display == "January 2025"

    def test_idempotency_key_unique(self, company_a, admin_user):
        """Duplicate idempotency key must raise IntegrityError."""
        from django.db import IntegrityError

        MonthEndRun.objects.create(
            company=company_a,
            title="Run 1",
            period_year=2025,
            period_month=1,
            idempotency_key="UNIQUE-KEY-1",
            created_by=admin_user,
        )
        with pytest.raises(IntegrityError):
            MonthEndRun.objects.create(
                company=company_a,
                title="Run 2",
                period_year=2025,
                period_month=2,
                idempotency_key="UNIQUE-KEY-1",
                created_by=admin_user,
            )

    def test_default_totals_zero(self, draft_run):
        assert draft_run.total_gross_proceeds == Decimal("0.00")
        assert draft_run.total_tax == Decimal("0.00")
        assert draft_run.total_net_proceeds == Decimal("0.00")
        assert draft_run.vesting_event_count == 0


class TestVestingEventModel:
    def test_create_event(self, draft_run, beneficiary_active):
        event = VestingEvent.objects.create(
            company=draft_run.company,
            run=draft_run,
            beneficiary=beneficiary_active,
            event_type=VestingEventType.SALE,
            event_date="2025-01-31",
            shares_affected=800,
            shares_before=800,
            shares_after=0,
            share_price=Decimal("10.0000"),
            gross_amount=Decimal("8000.00"),
            tax_amount=Decimal("2800.00"),
            net_amount=Decimal("5200.00"),
        )
        assert event.status == VestingEventStatus.PENDING
        assert str(event.beneficiary) in str(event)


class TestTaxDirectiveModel:
    def test_create_directive(self, draft_run, beneficiary_active):
        directive = TaxDirective.objects.create(
            company=draft_run.company,
            beneficiary=beneficiary_active,
            tax_year=2025,
            taxable_amount=Decimal("8000.00"),
        )
        assert directive.status == TaxDirectiveStatus.PENDING


class TestValidTransitions:
    def test_draft_can_go_to_approved(self):
        assert MonthEndRunStatus.APPROVED in VALID_TRANSITIONS[MonthEndRunStatus.DRAFT]

    def test_draft_cannot_go_to_processing(self):
        assert MonthEndRunStatus.PROCESSING not in VALID_TRANSITIONS[MonthEndRunStatus.DRAFT]

    def test_approved_can_go_to_processing(self):
        assert MonthEndRunStatus.PROCESSING in VALID_TRANSITIONS[MonthEndRunStatus.APPROVED]

    def test_approved_can_go_back_to_draft(self):
        assert MonthEndRunStatus.DRAFT in VALID_TRANSITIONS[MonthEndRunStatus.APPROVED]

    def test_completed_is_terminal(self):
        assert VALID_TRANSITIONS[MonthEndRunStatus.COMPLETED] == []

    def test_failed_can_go_to_draft(self):
        assert MonthEndRunStatus.DRAFT in VALID_TRANSITIONS[MonthEndRunStatus.FAILED]


# ===========================================================================
# Service layer tests
# ===========================================================================
class TestApproveRun:
    def test_approve_draft_run(self, draft_run, admin_user_2):
        run = approve_run(draft_run, user=admin_user_2)
        assert run.status == MonthEndRunStatus.APPROVED
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
            action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
            target_id=str(draft_run.pk),
        )
        assert logs.exists()
        log = logs.first()
        assert log.details["old_status"] == MonthEndRunStatus.DRAFT
        assert log.details["new_status"] == MonthEndRunStatus.APPROVED


class TestProcessRun:
    def test_process_creates_vesting_events(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_active_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        run = process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
            tax_rate=Decimal("0.35"),
        )

        assert run.status == MonthEndRunStatus.COMPLETED
        assert run.vesting_event_count == 2
        assert run.completed_at is not None

    def test_vesting_event_amounts_correct(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        """gross = shares × price, tax = gross × rate, net = gross - tax."""
        approve_run(draft_run, user=admin_user_2)
        process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
            tax_rate=Decimal("0.35"),
        )

        event = VestingEvent.objects.get(
            run=draft_run, beneficiary=beneficiary_active,
        )
        expected_gross = Decimal("800") * Decimal("10.0000")  # 8000.00
        expected_tax = expected_gross * Decimal("0.35")  # 2800.00
        expected_net = expected_gross - expected_tax  # 5200.00

        assert event.shares_affected == 800
        assert event.shares_before == 800
        assert event.shares_after == 0
        assert event.gross_amount == expected_gross.quantize(Decimal("0.01"))
        assert event.tax_amount == expected_tax.quantize(Decimal("0.01"))
        assert event.net_amount == expected_net.quantize(Decimal("0.01"))
        assert event.status == VestingEventStatus.PENDING

    def test_inactive_beneficiaries_excluded(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_inactive,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
        )

        assert draft_run.vesting_event_count == 1
        assert not VestingEvent.objects.filter(
            beneficiary=beneficiary_inactive,
        ).exists()

    def test_zero_vested_excluded(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_zero_vested,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
        )

        assert draft_run.vesting_event_count == 1
        assert not VestingEvent.objects.filter(
            beneficiary=beneficiary_zero_vested,
        ).exists()

    def test_totals_computed(
        self, draft_run, admin_user, admin_user_2,
        beneficiary_active, beneficiary_active_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
            tax_rate=Decimal("0.35"),
        )

        # Ben1: 800 × 10 = 8000, tax 2800, net 5200
        # Ben2: 300 × 10 = 3000, tax 1050, net 1950
        assert draft_run.total_gross_proceeds == Decimal("11000.00")
        assert draft_run.total_tax == Decimal("3850.00")
        assert draft_run.total_net_proceeds == Decimal("7150.00")

    def test_process_non_approved_fails(self, draft_run, admin_user):
        with pytest.raises(InvalidStateTransition):
            process_run(
                draft_run, user=admin_user,
                share_price=Decimal("10.0000"),
            )

    def test_process_creates_audit_logs(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
        )

        # Should have: DRAFT→APPROVED, APPROVED→PROCESSING, vesting events, PROCESSING→COMPLETED
        state_logs = AuditLog.objects.filter(
            action=AuditAction.MONTH_END_RUN_STATE_CHANGE,
            target_id=str(draft_run.pk),
        )
        assert state_logs.count() >= 3

    def test_idempotency_skip_duplicate_events(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        """Vesting events should not be recreated if they already exist."""
        approve_run(draft_run, user=admin_user_2)

        # First, create a vesting event manually
        VestingEvent.objects.create(
            company=draft_run.company,
            run=draft_run,
            beneficiary=beneficiary_active,
            event_type=VestingEventType.SALE,
            event_date="2025-01-01",
            shares_affected=800,
            shares_before=800,
            shares_after=0,
        )

        # Processing should skip since events already exist
        process_run(
            draft_run, user=admin_user,
            share_price=Decimal("10.0000"),
        )

        # Should still be exactly 1 event (no duplicates)
        assert VestingEvent.objects.filter(run=draft_run).count() == 1


class TestResetToDraft:
    def test_reset_approved_to_draft(self, draft_run, admin_user, admin_user_2):
        approve_run(draft_run, user=admin_user_2)
        run = reset_to_draft(draft_run, user=admin_user)
        assert run.status == MonthEndRunStatus.DRAFT
        assert run.approved_by is None
        assert run.approved_at is None

    def test_reset_failed_to_draft(self, draft_run, admin_user, admin_user_2, beneficiary_active):
        approve_run(draft_run, user=admin_user_2)
        # Force to FAILED state
        draft_run.status = MonthEndRunStatus.FAILED
        draft_run.failure_reason = "Test failure"
        draft_run.save(update_fields=["status", "failure_reason", "updated_at"])

        run = reset_to_draft(draft_run, user=admin_user)
        assert run.status == MonthEndRunStatus.DRAFT
        assert run.failure_reason == ""

    def test_reset_deletes_vesting_events(
        self, draft_run, admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user, share_price=Decimal("10.0000"))
        assert draft_run.vesting_events.count() > 0

        # Force back to FAILED so we can reset
        draft_run.status = MonthEndRunStatus.FAILED
        draft_run.save(update_fields=["status", "updated_at"])

        reset_to_draft(draft_run, user=admin_user)
        assert draft_run.vesting_events.count() == 0
        assert draft_run.vesting_event_count == 0
        assert draft_run.total_gross_proceeds == Decimal("0.00")

    def test_reset_completed_fails(self, draft_run, admin_user, admin_user_2, beneficiary_active):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user, share_price=Decimal("10.0000"))
        assert draft_run.status == MonthEndRunStatus.COMPLETED

        with pytest.raises(InvalidStateTransition):
            reset_to_draft(draft_run, user=admin_user)

    def test_reset_draft_fails(self, draft_run, admin_user):
        """Cannot reset a run that is already DRAFT."""
        with pytest.raises(InvalidStateTransition):
            reset_to_draft(draft_run, user=admin_user)


class TestTaxDirectiveServices:
    def test_create_tax_directive(self, beneficiary_active, admin_user):
        directive = create_tax_directive(
            beneficiary_active,
            tax_year=2025,
            taxable_amount=Decimal("8000.00"),
            user=admin_user,
        )
        assert directive.status == TaxDirectiveStatus.PENDING
        assert directive.taxable_amount == Decimal("8000.00")

    def test_update_directive_status_received(self, beneficiary_active, admin_user):
        directive = create_tax_directive(
            beneficiary_active,
            tax_year=2025,
            taxable_amount=Decimal("8000.00"),
            user=admin_user,
        )
        updated = update_tax_directive_status(
            directive,
            new_status=TaxDirectiveStatus.RECEIVED,
            directive_number="TD-123456",
            directive_rate=Decimal("0.3000"),
            user=admin_user,
        )
        assert updated.status == TaxDirectiveStatus.RECEIVED
        assert updated.directive_number == "TD-123456"
        assert updated.directive_rate == Decimal("0.3000")
        assert updated.calculated_tax == Decimal("2400.00")  # 8000 × 0.30
        assert updated.response_date is not None

    def test_update_directive_status_declined(self, beneficiary_active, admin_user):
        directive = create_tax_directive(
            beneficiary_active,
            tax_year=2025,
            taxable_amount=Decimal("8000.00"),
            user=admin_user,
        )
        updated = update_tax_directive_status(
            directive,
            new_status=TaxDirectiveStatus.DECLINED,
            decline_reason="Invalid ID number",
            user=admin_user,
        )
        assert updated.status == TaxDirectiveStatus.DECLINED
        assert updated.decline_reason == "Invalid ID number"


# ===========================================================================
# Form tests
# ===========================================================================
@pytest.mark.django_db
class TestMonthEndRunForm:
    def test_valid_form(self):
        data = {
            "title": "Test Month-End",
            "period_year": 2025,
            "period_month": 6,
            "idempotency_key": str(uuid.uuid4()),
        }
        form = MonthEndRunForm(data=data)
        assert form.is_valid(), form.errors

    def test_invalid_month(self):
        data = {
            "title": "Test Month-End",
            "period_year": 2025,
            "period_month": 13,  # Invalid
            "idempotency_key": str(uuid.uuid4()),
        }
        form = MonthEndRunForm(data=data)
        assert not form.is_valid()
        assert "period_month" in form.errors

    def test_idempotency_key_auto_generated(self):
        form = MonthEndRunForm()
        assert form.initial.get("idempotency_key") is not None
        assert form.initial["idempotency_key"].startswith("ME-")

    def test_auto_generate_title(self):
        data = {
            "title": "",  # Empty
            "period_year": 2025,
            "period_month": 6,
            "idempotency_key": str(uuid.uuid4()),
        }
        form = MonthEndRunForm(data=data)
        assert form.is_valid()
        assert "June 2025" in form.cleaned_data["title"]


class TestProcessRunForm:
    def test_valid_form(self):
        data = {
            "share_price": "10.0000",
            "tax_rate": "0.3500",
        }
        form = ProcessRunForm(data=data)
        assert form.is_valid()

    def test_invalid_share_price(self):
        data = {
            "share_price": "0",  # Invalid - must be > 0
            "tax_rate": "0.3500",
        }
        form = ProcessRunForm(data=data)
        assert not form.is_valid()

    def test_tax_rate_bounds(self):
        data = {
            "share_price": "10.0000",
            "tax_rate": "1.5",  # Invalid - > 1
        }
        form = ProcessRunForm(data=data)
        assert not form.is_valid()


# ===========================================================================
# View tests
# ===========================================================================
class TestMonthEndRunListView:
    def test_list_requires_login(self, company_a):
        c = Client()
        url = reverse("month_end:list", kwargs={"company_pk": company_a.pk})
        resp = c.get(url)
        assert resp.status_code == 302  # redirect to login

    def test_beneficiary_cannot_access(self, ben_client, company_a):
        url = reverse("month_end:list", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_admin_can_list(self, admin_client, company_a, draft_run):
        url = reverse("month_end:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "January 2025 Month-End" in resp.content.decode()

    def test_search_filter(self, admin_client, company_a, draft_run):
        url = reverse("month_end:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"q": "January"})
        assert resp.status_code == 200
        assert "January 2025 Month-End" in resp.content.decode()

    def test_status_filter(self, admin_client, company_a, draft_run):
        url = reverse("month_end:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url, {"status": "draft"})
        assert resp.status_code == 200
        assert "January 2025 Month-End" in resp.content.decode()

        resp = admin_client.get(url, {"status": "completed"})
        assert "January 2025 Month-End" not in resp.content.decode()


class TestMonthEndRunDetailView:
    def test_detail_requires_login(self, company_a, draft_run):
        c = Client()
        url = reverse("month_end:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = c.get(url)
        assert resp.status_code == 302

    def test_beneficiary_cannot_access(self, ben_client, company_a, draft_run):
        url = reverse("month_end:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_admin_can_view_detail(self, admin_client, company_a, draft_run):
        url = reverse("month_end:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "January 2025 Month-End" in resp.content.decode()

    def test_detail_shows_vesting_events(
        self, admin_client, company_a, draft_run,
        admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user, share_price=Decimal("10.0000"))
        url = reverse("month_end:detail", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "John" in resp.content.decode()


class TestMonthEndRunCreateView:
    def test_create_requires_login(self, company_a):
        c = Client()
        url = reverse("month_end:create", kwargs={"company_pk": company_a.pk})
        resp = c.get(url)
        assert resp.status_code == 302

    def test_beneficiary_cannot_create(self, ben_client, company_a):
        url = reverse("month_end:create", kwargs={"company_pk": company_a.pk})
        resp = ben_client.get(url)
        assert resp.status_code == 403

    def test_admin_can_get_create_form(self, admin_client, company_a):
        url = reverse("month_end:create", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_admin_can_create_run(self, admin_client, company_a):
        url = reverse("month_end:create", kwargs={"company_pk": company_a.pk})
        data = {
            "title": "New Month-End Run",
            "period_year": 2025,
            "period_month": 6,
            "idempotency_key": str(uuid.uuid4()),
        }
        resp = admin_client.post(url, data)
        assert resp.status_code == 302  # redirect on success
        assert MonthEndRun.objects.filter(title="New Month-End Run").exists()

    def test_create_generates_audit_log(self, admin_client, company_a):
        url = reverse("month_end:create", kwargs={"company_pk": company_a.pk})
        data = {
            "title": "Audited Run",
            "period_year": 2025,
            "period_month": 7,
            "idempotency_key": str(uuid.uuid4()),
        }
        admin_client.post(url, data)
        assert AuditLog.objects.filter(
            action=AuditAction.MONTH_END_RUN_CREATE,
        ).exists()


class TestMonthEndRunUpdateView:
    def test_can_update_draft_run(self, admin_client, company_a, draft_run):
        url = reverse("month_end:update", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_cannot_update_approved_run(
        self, admin_client, company_a, draft_run, admin_user_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("month_end:update", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 404  # filtered out by queryset


class TestMonthEndRunApproveView:
    def test_approve_via_post(self, admin2_client, company_a, draft_run):
        url = reverse("month_end:approve", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin2_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.APPROVED

    def test_approve_get_not_allowed(self, admin2_client, company_a, draft_run):
        url = reverse("month_end:approve", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin2_client.get(url)
        assert resp.status_code == 405  # method not allowed

    def test_creator_cannot_approve_via_view(self, admin_client, company_a, draft_run):
        url = reverse("month_end:approve", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302  # redirect back with error message
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.DRAFT  # still draft


class TestMonthEndRunProcessView:
    def test_process_via_post(
        self, admin_client, company_a, draft_run,
        admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("month_end:process", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url, {"share_price": "10.0000", "tax_rate": "0.35"})
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.COMPLETED

    def test_process_draft_fails(self, admin_client, company_a, draft_run):
        url = reverse("month_end:process", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url, {"share_price": "10.0000", "tax_rate": "0.35"})
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.DRAFT  # unchanged

    def test_process_requires_share_price(
        self, admin_client, company_a, draft_run, admin_user_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("month_end:process", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url, {})  # Missing share_price
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.APPROVED  # unchanged


class TestMonthEndRunResetView:
    def test_reset_approved_via_post(
        self, admin_client, company_a, draft_run, admin_user_2,
    ):
        approve_run(draft_run, user=admin_user_2)
        url = reverse("month_end:reset", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.DRAFT

    def test_reset_completed_fails(
        self, admin_client, company_a, draft_run,
        admin_user, admin_user_2, beneficiary_active,
    ):
        approve_run(draft_run, user=admin_user_2)
        process_run(draft_run, user=admin_user, share_price=Decimal("10.0000"))
        url = reverse("month_end:reset", kwargs={"company_pk": company_a.pk, "pk": draft_run.pk})
        resp = admin_client.post(url)
        assert resp.status_code == 302
        draft_run.refresh_from_db()
        assert draft_run.status == MonthEndRunStatus.COMPLETED  # unchanged


# ===========================================================================
# Tenant isolation tests
# ===========================================================================
class TestTenantIsolation:
    def test_list_only_shows_own_company_runs(
        self, admin_client, company_a, company_b, admin_user,
    ):
        """Runs from company_b must not appear in company_a listing."""
        MonthEndRun.objects.create(
            company=company_a,
            title="Alpha Run",
            period_year=2025,
            period_month=1,
            idempotency_key="ALPHA-ISO-1",
            created_by=admin_user,
        )
        MonthEndRun.objects.create(
            company=company_b,
            title="Beta Run",
            period_year=2025,
            period_month=2,
            idempotency_key="BETA-ISO-1",
            created_by=admin_user,
        )

        url = reverse("month_end:list", kwargs={"company_pk": company_a.pk})
        resp = admin_client.get(url)
        content = resp.content.decode()
        assert "Alpha Run" in content
        assert "Beta Run" not in content

    def test_cannot_access_other_company_detail(
        self, admin_client, company_b, admin_user,
    ):
        """Accessing a run via wrong company_pk returns 404."""
        run = MonthEndRun.objects.create(
            company=company_b,
            title="Beta Only",
            period_year=2025,
            period_month=3,
            idempotency_key="BETA-ISO-2",
            created_by=admin_user,
        )
        # Create another company to test wrong company access
        other_company = Company.objects.create(
            name="Ghost Corp", registration_number="REG-GHOST"
        )
        url_wrong = reverse("month_end:detail", kwargs={"company_pk": other_company.pk, "pk": run.pk})
        resp = admin_client.get(url_wrong)
        assert resp.status_code == 404

    def test_vesting_events_scoped_to_run_company(
        self, company_a, company_b, admin_user, admin_user_2,
    ):
        """Vesting events must only include beneficiaries from the run's company."""
        Beneficiary.objects.create(
            company=company_a, employee_number="EMP-A1",
            first_name="InA", last_name="User",
            total_shares=100, vested_shares=100, unvested_shares=0,
            status=BeneficiaryStatus.ACTIVE,
        )
        Beneficiary.objects.create(
            company=company_b, employee_number="EMP-B1",
            first_name="InB", last_name="User",
            total_shares=200, vested_shares=200, unvested_shares=0,
            status=BeneficiaryStatus.ACTIVE,
        )

        run = MonthEndRun.objects.create(
            company=company_a,
            title="Scoped Run",
            period_year=2025,
            period_month=4,
            idempotency_key="SCOPE-TEST-1",
            created_by=admin_user,
        )
        approve_run(run, user=admin_user_2)
        process_run(run, user=admin_user, share_price=Decimal("10.0000"))

        # Only company_a beneficiary should have a vesting event
        assert run.vesting_event_count == 1
        event = run.vesting_events.first()
        assert event.beneficiary.company == company_a

