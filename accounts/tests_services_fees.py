"""Tests for accounts.services.fees — Phase B4.

Locks in the externally-observable behaviour of the fee service so future
phases cannot silently regress the public surface:

    resolve_active_fee_schedule, compute_fee_amount,
    apply_processing_fee, apply_membership_fee,
    apply_late_payment_fees, apply_annual_maintenance_fees.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    AuditLog,
    FeeCharge,
    FeeSchedule,
    FinancialPeriod,
    LoanRepayment,
    LoanTypeConfiguration,
    MemberAccount,
    SocietyConfiguration,
)
from accounts.services import fees as fee_service
from accounts.services import loans as loan_service

User = get_user_model()


class FeeScheduleResolutionTests(TestCase):
    """Tests for resolve_active_fee_schedule and compute_fee_amount."""

    def setUp(self):
        self.schedule_flat = FeeSchedule.objects.create(
            fee_type="processing",
            name="Processing Fee (flat)",
            amount=Decimal("500.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        self.schedule_pct = FeeSchedule.objects.create(
            fee_type="processing",
            name="Processing Fee (pct)",
            percentage=Decimal("1.50"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2026, 4, 1),
        )
        self.schedule_inactive = FeeSchedule.objects.create(
            fee_type="processing",
            name="Processing Fee (inactive)",
            amount=Decimal("999.00"),
            applies_to="loan",
            is_active=False,
            effective_date=date(2026, 4, 1),
        )

    def test_resolve_picks_most_recent_active(self):
        """Should pick the schedule with the latest effective_date <= as_of."""
        result = fee_service.resolve_active_fee_schedule("processing", "loan", as_of=date(2026, 5, 1))
        self.assertEqual(result.id, self.schedule_pct.id)

    def test_resolve_falls_back_to_older_when_newer_not_yet_effective(self):
        """Before the newer schedule's effective_date, the older one is returned."""
        result = fee_service.resolve_active_fee_schedule("processing", "loan", as_of=date(2025, 12, 1))
        self.assertEqual(result.id, self.schedule_flat.id)

    def test_resolve_returns_none_when_no_match(self):
        """No active schedule for the given fee_type/applies_to → None."""
        result = fee_service.resolve_active_fee_schedule("late_payment", "loan")
        self.assertIsNone(result)

    def test_resolve_skips_inactive(self):
        """Inactive schedules are never returned."""
        FeeSchedule.objects.filter(id=self.schedule_pct.id).update(is_active=False)
        result = fee_service.resolve_active_fee_schedule("processing", "loan", as_of=date(2026, 5, 1))
        self.assertEqual(result.id, self.schedule_flat.id)

    def test_compute_fee_amount_flat(self):
        """Flat amount takes precedence over percentage."""
        amount = fee_service.compute_fee_amount(self.schedule_flat, base=Decimal("100000"))
        self.assertEqual(amount, Decimal("500.00"))

    def test_compute_fee_amount_percentage(self):
        """Percentage of base when amount is None."""
        amount = fee_service.compute_fee_amount(self.schedule_pct, base=Decimal("100000"))
        self.assertEqual(amount, Decimal("1500.00"))

    def test_compute_fee_amount_none_schedule(self):
        """None schedule → ZERO."""
        self.assertEqual(fee_service.compute_fee_amount(None), Decimal("0.00"))

    def test_compute_fee_amount_no_base_for_pct(self):
        """Percentage schedule with no base → ZERO."""
        amount = fee_service.compute_fee_amount(self.schedule_pct, base=None)
        self.assertEqual(amount, Decimal("0.00"))


class ProcessingFeeTests(TestCase):
    """Tests for apply_processing_fee."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_fee",
            email="admin_fee@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="Fee",
            is_staff=True,
            role="admin",
        )
        self.approver = User.objects.create_user(
            username="approver_fee",
            email="approver_fee@example.com",
            password="Pass1234!",
            first_name="Approver",
            last_name="Fee",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem_fee",
            email="mem_fee@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Fee",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0001",
        )
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00001",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("50000.00"),
        )
        LoanTypeConfiguration.objects.create(
            loan_type="personal",
            interest_rate=Decimal("10.00"),
            is_active=True,
        )
        self.schedule = FeeSchedule.objects.create(
            fee_type="processing",
            name="Loan Processing Fee",
            percentage=Decimal("1.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )

    def _create_and_approve_loan(self, processing_fee=None):
        """Helper: create + approve a loan, returning the LoanAccount."""
        app = loan_service.create_loan_application(
            user_id=self.member.id,
            loan_type="personal",
            principal_amount="100000",
            interest_rate="10",
            tenure_months=12,
            actor=self.admin,
        )
        return loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today(),
            disbursement_account_id=self.account.id,
            processing_fee=processing_fee,
            actor=self.approver,
        )

    def test_processing_fee_posted_on_approval(self):
        """Loan approval auto-posts a processing FeeCharge + debit Transaction."""
        loan_ac = self._create_and_approve_loan(processing_fee="1000")
        charge = FeeCharge.objects.get(loan_account=loan_ac, fee_schedule__fee_type="processing")
        self.assertEqual(charge.amount, Decimal("1000.00"))
        self.assertEqual(charge.status, "charged")
        self.assertIsNotNone(charge.transaction)
        self.assertEqual(charge.transaction.transaction_type, "debit")
        self.assertEqual(charge.transaction.amount, Decimal("1000.00"))
        self.assertIn("Processing fee", charge.transaction.description)

    def test_processing_fee_uses_schedule_percentage_when_no_explicit_fee(self):
        """When processing_fee is not passed, the schedule percentage is used."""
        loan_ac = self._create_and_approve_loan(processing_fee=None)
        charge = FeeCharge.objects.get(loan_account=loan_ac, fee_schedule__fee_type="processing")
        # 1% of 100000 = 1000
        self.assertEqual(charge.amount, Decimal("1000.00"))

    def test_processing_fee_idempotent(self):
        """Calling apply_processing_fee again on the same loan is a no-op."""
        loan_ac = self._create_and_approve_loan(processing_fee="500")
        result = fee_service.apply_processing_fee(loan_ac, actor=self.approver)
        self.assertIsNone(result)
        self.assertEqual(FeeCharge.objects.filter(loan_account=loan_ac).count(), 1)

    def test_processing_fee_no_schedule_is_noop(self):
        """If no active processing FeeSchedule exists, no fee is posted."""
        self.schedule.is_active = False
        self.schedule.save()
        loan_ac = self._create_and_approve_loan(processing_fee=None)
        self.assertFalse(FeeCharge.objects.filter(loan_account=loan_ac).exists())

    def test_processing_fee_audit_log(self):
        """Processing fee posts an audit log with entity_type='fee'."""
        loan_ac = self._create_and_approve_loan(processing_fee="500")
        charge = FeeCharge.objects.get(loan_account=loan_ac)
        audit = AuditLog.objects.filter(entity_type="fee", entity_id=charge.id).first()
        self.assertIsNotNone(audit)
        self.assertIn("Processing fee", audit.description)

    def test_processing_fee_balance_deducted(self):
        """The debit Transaction reduces the member account balance."""
        initial_balance = self.account.balance
        self._create_and_approve_loan(processing_fee="500")
        self.account.refresh_from_db()
        # Balance = initial + 100000 (disbursement credit) - 500 (fee debit)
        expected = initial_balance + Decimal("100000") - Decimal("500")
        self.assertEqual(self.account.balance, expected)


class MembershipFeeTests(TestCase):
    """Tests for apply_membership_fee."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_mf",
            email="admin_mf@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="MF",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem_mf",
            email="mem_mf@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="MF",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0010",
        )
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
        )
        self.schedule = FeeSchedule.objects.create(
            fee_type="membership",
            name="Annual Membership",
            amount=Decimal("300.00"),
            applies_to="membership",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )

    def test_membership_fee_posted_on_first_account(self):
        """First account creation for a member posts a membership fee."""
        account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00010",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
        )
        charge = fee_service.apply_membership_fee(
            self.member,
            member_account=account,
            actor=self.admin,
            financial_period=self.fp,
        )
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, Decimal("300.00"))
        self.assertEqual(charge.status, "charged")
        self.assertEqual(charge.financial_period, self.fp)
        self.assertIsNotNone(charge.transaction)

    def test_membership_fee_idempotent_per_fy(self):
        """Second call for same user + FY is a no-op."""
        account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00011",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
        )
        fee_service.apply_membership_fee(
            self.member, member_account=account, actor=self.admin, financial_period=self.fp
        )
        result = fee_service.apply_membership_fee(
            self.member, member_account=account, actor=self.admin, financial_period=self.fp
        )
        self.assertIsNone(result)
        self.assertEqual(FeeCharge.objects.filter(user=self.member, fee_schedule__fee_type="membership").count(), 1)

    def test_membership_fee_no_schedule_is_noop(self):
        """No active membership schedule → no fee."""
        self.schedule.is_active = False
        self.schedule.save()
        account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00012",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
        )
        result = fee_service.apply_membership_fee(self.member, member_account=account, actor=self.admin)
        self.assertIsNone(result)

    def test_membership_fee_pending_when_no_account(self):
        """If the member has no active account, fee is stored as pending."""
        charge = fee_service.apply_membership_fee(
            self.member,
            member_account=None,
            actor=self.admin,
            financial_period=self.fp,
        )
        self.assertIsNotNone(charge)
        self.assertEqual(charge.status, "pending")
        self.assertIsNone(charge.transaction)


class LateFeeTests(TestCase):
    """Tests for apply_late_payment_fees."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_lf",
            email="admin_lf@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="LF",
            is_staff=True,
            role="admin",
        )
        self.approver = User.objects.create_user(
            username="approver_lf",
            email="approver_lf@example.com",
            password="Pass1234!",
            first_name="Approver",
            last_name="LF",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem_lf",
            email="mem_lf@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="LF",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0020",
        )
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00020",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("100000.00"),
        )
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
        )
        LoanTypeConfiguration.objects.create(
            loan_type="personal",
            interest_rate=Decimal("10.00"),
            is_active=True,
        )
        self.late_schedule = FeeSchedule.objects.create(
            fee_type="late_payment",
            name="Late Payment Fee",
            amount=Decimal("200.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        # Also need a processing schedule so loan approval doesn't fail
        FeeSchedule.objects.create(
            fee_type="processing",
            name="Processing Fee",
            amount=Decimal("0.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        SocietyConfiguration.objects.create(
            society_name="Test Society",
            late_fee_grace_days=7,
        )

    def _create_overdue_loan(self):
        """Create a loan with an overdue EMI."""
        app = loan_service.create_loan_application(
            user_id=self.member.id,
            loan_type="personal",
            principal_amount="120000",
            interest_rate="10",
            tenure_months=12,
            actor=self.admin,
        )
        loan_ac = loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today() - timedelta(days=60),
            disbursement_account_id=self.account.id,
            actor=self.approver,
        )
        # Mark first EMI as overdue (due 30 days ago).
        emi = LoanRepayment.objects.filter(loan_account=loan_ac, installment_number=1).first()
        emi.due_date = date.today() - timedelta(days=30)
        emi.payment_status = "overdue"
        emi.save()
        return loan_ac, emi

    def test_late_fee_posted_for_overdue_emi(self):
        """Overdue EMI past grace gets a late_payment FeeCharge."""
        loan_ac, emi = self._create_overdue_loan()
        result = fee_service.apply_late_payment_fees(
            as_of=date.today(),
            grace_days=7,
            financial_period=self.fp,
        )
        self.assertEqual(result["charges_created"], 1)
        charge = FeeCharge.objects.get(loan_repayment=emi, fee_schedule__fee_type="late_payment")
        self.assertEqual(charge.amount, Decimal("200.00"))
        self.assertEqual(charge.status, "charged")
        self.assertIsNotNone(charge.transaction)

    def test_late_fee_idempotent(self):
        """Running the sweep again does not double-charge."""
        loan_ac, emi = self._create_overdue_loan()
        fee_service.apply_late_payment_fees(as_of=date.today(), grace_days=7, financial_period=self.fp)
        result = fee_service.apply_late_payment_fees(as_of=date.today(), grace_days=7, financial_period=self.fp)
        self.assertEqual(result["charges_created"], 0)
        self.assertEqual(FeeCharge.objects.filter(loan_repayment=emi).count(), 1)

    def test_late_fee_respects_grace_period(self):
        """EMI overdue by fewer days than grace → no fee."""
        loan_ac, emi = self._create_overdue_loan()
        # EMI is 30 days overdue; set grace to 60 → should not trigger.
        result = fee_service.apply_late_payment_fees(as_of=date.today(), grace_days=60, financial_period=self.fp)
        self.assertEqual(result["charges_created"], 0)

    def test_late_fee_no_schedule_is_noop(self):
        """No active late_payment schedule → no fees posted."""
        self.late_schedule.is_active = False
        self.late_schedule.save()
        self._create_overdue_loan()
        result = fee_service.apply_late_payment_fees(as_of=date.today(), grace_days=0, financial_period=self.fp)
        self.assertEqual(result["charges_created"], 0)

    def test_late_fee_skips_paid_emis(self):
        """Paid EMIs are not charged a late fee."""
        loan_ac, emi = self._create_overdue_loan()
        emi.payment_status = "paid"
        emi.save()
        result = fee_service.apply_late_payment_fees(as_of=date.today(), grace_days=0, financial_period=self.fp)
        self.assertEqual(result["charges_created"], 0)

    def test_late_fee_audit_log(self):
        """Late fee sweep writes a summary audit log."""
        self._create_overdue_loan()
        fee_service.apply_late_payment_fees(as_of=date.today(), grace_days=7, financial_period=self.fp)
        audit = AuditLog.objects.filter(entity_type="fee", description__contains="late_payment").first()
        self.assertIsNotNone(audit)


class AnnualMaintenanceFeeTests(TestCase):
    """Tests for apply_annual_maintenance_fees."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_am",
            email="admin_am@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="AM",
            is_staff=True,
            role="admin",
        )
        self.member1 = User.objects.create_user(
            username="mem_am1",
            email="mem_am1@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="AM1",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0030",
        )
        self.member2 = User.objects.create_user(
            username="mem_am2",
            email="mem_am2@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="AM2",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0031",
        )
        self.account1 = MemberAccount.objects.create(
            user=self.member1,
            account_number="CD-2026-00030",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
        )
        self.account2 = MemberAccount.objects.create(
            user=self.member2,
            account_number="CD-2026-00031",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
        )
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
        )
        self.schedule = FeeSchedule.objects.create(
            fee_type="annual_maintenance",
            name="Annual Maintenance",
            amount=Decimal("100.00"),
            applies_to="membership",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )

    def test_annual_fee_posted_for_all_members(self):
        """All active members get an annual_maintenance fee."""
        result = fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        self.assertEqual(result["charges_created"], 2)
        self.assertEqual(FeeCharge.objects.filter(fee_schedule__fee_type="annual_maintenance").count(), 2)

    def test_annual_fee_idempotent(self):
        """Running again for the same FY does not double-charge."""
        fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        result = fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        self.assertEqual(result["charges_created"], 0)
        self.assertEqual(result["charges_skipped"], 2)

    def test_annual_fee_no_schedule_is_noop(self):
        """No active annual_maintenance schedule → no fees."""
        self.schedule.is_active = False
        self.schedule.save()
        result = fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        self.assertEqual(result["charges_created"], 0)

    def test_annual_fee_no_financial_period_is_noop(self):
        """No financial period → no fees."""
        self.fp.is_active = False
        self.fp.save()
        result = fee_service.apply_annual_maintenance_fees(financial_period=None, actor=self.admin)
        self.assertEqual(result["charges_created"], 0)

    def test_annual_fee_pending_when_no_account(self):
        """Member without an active account gets a pending fee."""
        self.account2.status = "closed"
        self.account2.save()
        result = fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        self.assertEqual(result["charges_created"], 2)
        charge = FeeCharge.objects.get(user=self.member2, fee_schedule__fee_type="annual_maintenance")
        self.assertEqual(charge.status, "pending")
        self.assertIsNone(charge.transaction)

    def test_annual_fee_balance_deducted(self):
        """The debit Transaction reduces the member account balance."""
        initial = self.account1.balance
        fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        self.account1.refresh_from_db()
        self.assertEqual(self.account1.balance, initial - Decimal("100.00"))

    def test_annual_fee_audit_log(self):
        """Annual sweep writes a summary audit log."""
        fee_service.apply_annual_maintenance_fees(financial_period=self.fp, actor=self.admin)
        audit = AuditLog.objects.filter(entity_type="fee", description__contains="annual_maintenance").first()
        self.assertIsNotNone(audit)
