"""Tests for accounts.services.interest_engine (Phase B1).

Locks in the externally-observable behaviour of the unified interest engine
so future phases (B2 cron, B3 EMI reconciliation, B5 society live aggregates)
cannot silently regress the public surface:

    accrue_deposits, accrue_loans, run_full_engine.

The engine writes through the transactions service for deposit credits, so
these tests double as integration tests for the
``payment_mode="internal"`` path and confirm that no ``Instrument`` row is
created for system-generated interest postings.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    AuditLog,
    FinancialPeriod,
    Instrument,
    InterestPayout,
    InterestReceivable,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    Transaction,
)
from accounts.services import interest_engine

User = get_user_model()


class InterestEngineDepositTests(TestCase):
    """``accrue_deposits`` behavioural contract."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin1",
            email="admin1@example.com",
            password="Pass1234!",
            first_name="Alpha",
            last_name="Admin",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem1",
            email="mem1@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="One",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0001",
        )
        # 100 days ago so interest is non-trivial.
        self.opening = date.today() - timedelta(days=100)
        self.fp = FinancialPeriod.objects.create(
            label="FY2025-26",
            start_date=date(date.today().year, 4, 1),
            end_date=date(date.today().year + 1, 3, 31),
            status="open",
            is_active=True,
        )

    def _make_account(self, *, acc_type="fd", rate="6.00", balance="100000", status="active", interest_rate=None):
        rate_value = Decimal(rate) if interest_rate is None else Decimal(str(interest_rate))
        return MemberAccount.objects.create(
            user=self.member,
            account_number=f"AC{acc_type.upper()}{MemberAccount.objects.count() + 1:04d}",
            account_type=acc_type,
            opening_date=self.opening,
            balance=Decimal(balance),
            interest_rate=rate_value,
            status=status,
        )

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_credits_eligible_deposit_account(self):
        """FD account: posts Transaction(interest, internal), InterestPayout, balance bumps, no Instrument."""
        acct = self._make_account(acc_type="fd", rate="6.00", balance="100000")
        as_of = date.today()

        result = interest_engine.accrue_deposits(
            as_of=as_of,
            financial_period=self.fp,
            actor=self.admin,
            audit_via="test",
        )

        self.assertEqual(result["accounts_updated"], 1)
        self.assertGreater(result["total_posted"], Decimal("0"))
        self.assertEqual(result["period_end"], as_of)
        self.assertEqual(len(result["payouts"]), 1)

        txn = Transaction.objects.get(member_account=acct, transaction_type="interest")
        self.assertEqual(txn.payment_mode, "internal")
        self.assertEqual(txn.amount, result["total_posted"])
        self.assertIsNone(txn.instrument, "Internal interest postings must not create an Instrument row.")
        self.assertEqual(txn.transaction_date, as_of)

        payout = result["payouts"][0]
        self.assertEqual(payout.transaction_id, txn.id)
        self.assertEqual(payout.status, "credited")
        self.assertEqual(payout.financial_period_id, self.fp.id)
        self.assertEqual(payout.period_start, self.opening)
        self.assertEqual(payout.period_end, as_of)

        acct.refresh_from_db()
        self.assertEqual(acct.balance, Decimal("100000") + result["total_posted"])
        self.assertEqual(acct.accrued_interest, result["total_posted"])
        self.assertEqual(acct.last_interest_calc_date, as_of)
        # No Instrument was created anywhere.
        self.assertEqual(Instrument.objects.count(), 0)

    def test_engine_writes_summary_audit_row(self):
        """A single aggregated AuditLog row is written per run, not one per account."""
        self._make_account(acc_type="fd", rate="6.00", balance="100000")
        self._make_account(acc_type="cd", rate="5.50", balance="50000")
        before = AuditLog.objects.count()

        result = interest_engine.accrue_deposits(
            as_of=date.today(), financial_period=self.fp, actor=self.admin, audit_via="panel"
        )
        self.assertEqual(result["accounts_updated"], 2)

        new_rows = AuditLog.objects.filter(id__gt=before).filter(entity_type="system")
        self.assertEqual(new_rows.count(), 1, "Expected exactly one summary audit row from the engine.")
        self.assertIn("Interest engine (panel)", new_rows.first().description)

    # ------------------------------------------------------------------
    # Eligibility filters
    # ------------------------------------------------------------------

    def test_excludes_share_and_od_account_types(self):
        """Share earns dividend (Phase B9, not interest); OD is debit-balance — both skipped."""
        self._make_account(acc_type="share", rate="6.00", balance="100000")
        self._make_account(acc_type="od", rate="12.00", balance="100000")

        result = interest_engine.accrue_deposits(as_of=date.today())
        self.assertEqual(result["accounts_updated"], 0)
        self.assertEqual(result["total_posted"], Decimal("0.00"))
        self.assertFalse(Transaction.objects.filter(transaction_type="interest").exists())

    def test_skips_zero_rate_account(self):
        """``interest_rate=0`` accounts are not eligible."""
        self._make_account(acc_type="fd", rate="0.00", balance="100000")
        result = interest_engine.accrue_deposits(as_of=date.today())
        self.assertEqual(result["accounts_updated"], 0)

    def test_skips_non_active_and_soft_deleted_accounts(self):
        frozen = self._make_account(acc_type="fd", rate="6.00", balance="100000", status="frozen")
        soft_del = self._make_account(acc_type="fd", rate="6.00", balance="100000")
        soft_del.is_deleted = True
        soft_del.save(update_fields=["is_deleted"])

        result = interest_engine.accrue_deposits(as_of=date.today())
        self.assertEqual(result["accounts_updated"], 0)
        frozen.refresh_from_db()
        soft_del.refresh_from_db()
        self.assertIsNone(frozen.last_interest_calc_date)
        self.assertIsNone(soft_del.last_interest_calc_date)

    def test_skips_account_with_zero_balance(self):
        """``daily_simple_interest`` returns 0 for a zero balance; nothing posts."""
        self._make_account(acc_type="fd", rate="6.00", balance="0")
        result = interest_engine.accrue_deposits(as_of=date.today())
        self.assertEqual(result["accounts_updated"], 0)
        self.assertFalse(Transaction.objects.exists())

    # ------------------------------------------------------------------
    # Window / idempotency
    # ------------------------------------------------------------------

    def test_uses_last_interest_calc_date_as_window_start(self):
        """Once last_interest_calc_date is set, the window starts from there, not opening_date."""
        acct = self._make_account(acc_type="fd", rate="6.00", balance="100000")
        first_as_of = date.today() - timedelta(days=30)
        interest_engine.accrue_deposits(as_of=first_as_of, financial_period=self.fp)

        acct.refresh_from_db()
        self.assertEqual(acct.last_interest_calc_date, first_as_of)
        balance_after_first = acct.balance

        # Second run: window is only the last 30 days, so interest must be strictly
        # less than what would be posted from `opening` to today.
        second_as_of = date.today()
        result = interest_engine.accrue_deposits(as_of=second_as_of, financial_period=self.fp)
        self.assertEqual(result["accounts_updated"], 1)
        acct.refresh_from_db()
        self.assertEqual(acct.last_interest_calc_date, second_as_of)
        self.assertGreater(acct.balance, balance_after_first)

    def test_idempotent_same_as_of(self):
        """A second run on the same ``as_of`` date is a no-op."""
        self._make_account(acc_type="fd", rate="6.00", balance="100000")
        as_of = date.today()
        first = interest_engine.accrue_deposits(as_of=as_of, financial_period=self.fp)
        second = interest_engine.accrue_deposits(as_of=as_of, financial_period=self.fp)

        self.assertEqual(first["accounts_updated"], 1)
        self.assertEqual(second["accounts_updated"], 0)
        self.assertEqual(second["total_posted"], Decimal("0.00"))
        self.assertEqual(InterestPayout.objects.count(), 1)
        self.assertEqual(Transaction.objects.filter(transaction_type="interest").count(), 1)


class InterestEngineLoanTests(TestCase):
    """``accrue_loans`` behavioural contract."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin2",
            email="admin2@example.com",
            password="Pass1234!",
            first_name="Beta",
            last_name="Admin",
            is_staff=True,
            role="admin",
        )
        self.approver = User.objects.create_user(
            username="approver2",
            email="approver2@example.com",
            password="Pass1234!",
            first_name="Gamma",
            last_name="Approver",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem2",
            email="mem2@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Two",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0002",
        )
        self.fp = FinancialPeriod.objects.create(
            label="FY2025-26",
            start_date=date(date.today().year, 4, 1),
            end_date=date(date.today().year + 1, 3, 31),
            status="open",
            is_active=True,
        )

    def _make_loan_with_repayment(self, *, interest_component=Decimal("83.33"), payment_status="upcoming"):
        app = LoanApplication.objects.create(
            application_number=f"LA-2025-{LoanApplication.objects.count() + 1:05d}",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            application_date=date.today(),
            status="approved",
            approval_date=date.today(),
            created_by=self.admin,
            approved_by=self.approver,
        )
        loan = LoanAccount.objects.create(
            loan_number=f"LN-2025-{LoanAccount.objects.count() + 1:05d}",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            emi_amount=Decimal("879.16"),
            total_payable=Decimal("10550.00"),
            total_paid=Decimal("0"),
            outstanding_balance=Decimal("10000"),
            overdue_amount=Decimal("0"),
            disbursement_date=date.today() - timedelta(days=30),
            first_emi_date=date.today() - timedelta(days=30),
            total_emis=12,
            emis_paid=0,
            emis_overdue=0,
            created_by=self.admin,
        )
        repayment = LoanRepayment.objects.create(
            loan_account=loan,
            installment_number=1,
            due_date=date.today(),
            amount_due=Decimal("879.16"),
            principal_component=Decimal("795.83"),
            interest_component=interest_component,
            payment_status=payment_status,
        )
        return loan, repayment

    def test_creates_receivable_for_unpaid_due_emi(self):
        loan, rep = self._make_loan_with_repayment()
        result = interest_engine.accrue_loans(
            as_of=date.today(), financial_period=self.fp, actor=self.admin, audit_via="test"
        )
        self.assertEqual(result["rows_created"], 1)
        self.assertEqual(result["installments_considered"], 1)

        rec = InterestReceivable.objects.get(loan_account=loan, due_date=rep.due_date)
        self.assertEqual(rec.amount_accrued, rep.interest_component)
        self.assertEqual(rec.status, "accrued")
        self.assertEqual(rec.financial_period_id, self.fp.id)

    def test_idempotent_for_same_as_of(self):
        self._make_loan_with_repayment()
        first = interest_engine.accrue_loans(as_of=date.today(), financial_period=self.fp)
        second = interest_engine.accrue_loans(as_of=date.today(), financial_period=self.fp)
        self.assertEqual(first["rows_created"], 1)
        self.assertEqual(second["rows_created"], 0)
        self.assertEqual(second["rows_updated"], 0)
        self.assertEqual(InterestReceivable.objects.count(), 1)

    def test_skips_paid_repayments(self):
        loan, rep = self._make_loan_with_repayment(payment_status="paid")
        rep.amount_paid = rep.amount_due
        rep.paid_date = date.today()
        rep.save()
        result = interest_engine.accrue_loans(as_of=date.today(), financial_period=self.fp)
        self.assertEqual(result["installments_considered"], 0)
        self.assertFalse(InterestReceivable.objects.exists())

    def test_skips_future_due_repayments(self):
        loan = LoanApplication.objects.create(
            application_number="LA-2025-FUT01",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            application_date=date.today(),
            status="approved",
            approval_date=date.today(),
            created_by=self.admin,
            approved_by=self.approver,
        )
        loan_acct = LoanAccount.objects.create(
            loan_number="LN-2025-FUT01",
            application=loan,
            user=self.member,
            status="active",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            emi_amount=Decimal("879.16"),
            total_payable=Decimal("10550.00"),
            outstanding_balance=Decimal("10000"),
            disbursement_date=date.today(),
            first_emi_date=date.today() + timedelta(days=30),
            total_emis=12,
            created_by=self.admin,
        )
        LoanRepayment.objects.create(
            loan_account=loan_acct,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount_due=Decimal("879.16"),
            principal_component=Decimal("795.83"),
            interest_component=Decimal("83.33"),
            payment_status="upcoming",
        )
        result = interest_engine.accrue_loans(as_of=date.today(), financial_period=self.fp)
        self.assertEqual(result["installments_considered"], 0)
        self.assertFalse(InterestReceivable.objects.exists())

    def test_refreshes_amount_when_interest_component_changes(self):
        loan, rep = self._make_loan_with_repayment(interest_component=Decimal("83.33"))
        interest_engine.accrue_loans(as_of=date.today(), financial_period=self.fp)
        rec = InterestReceivable.objects.get(loan_account=loan, due_date=rep.due_date)
        self.assertEqual(rec.amount_accrued, Decimal("83.33"))

        rep.interest_component = Decimal("90.00")
        rep.save(update_fields=["interest_component"])
        result = interest_engine.accrue_loans(as_of=date.today(), financial_period=self.fp)
        self.assertEqual(result["rows_updated"], 1)
        rec.refresh_from_db()
        self.assertEqual(rec.amount_accrued, Decimal("90.00"))


class InterestEngineFullEngineTests(TestCase):
    """``run_full_engine`` runs both sides atomically."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin3",
            email="admin3@example.com",
            password="Pass1234!",
            first_name="Gamma",
            last_name="Admin",
            is_staff=True,
            role="admin",
        )
        self.approver = User.objects.create_user(
            username="approver3",
            email="approver3@example.com",
            password="Pass1234!",
            first_name="Delta",
            last_name="Approver",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem3",
            email="mem3@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Three",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0003",
        )
        self.opening = date.today() - timedelta(days=60)
        self.fp = FinancialPeriod.objects.create(
            label="FY2025-26",
            start_date=date(date.today().year, 4, 1),
            end_date=date(date.today().year + 1, 3, 31),
            status="open",
            is_active=True,
        )
        # One deposit account + one loan with a due unpaid EMI.
        self.acct = MemberAccount.objects.create(
            user=self.member,
            account_number="AC-COMBO-001",
            account_type="fd",
            opening_date=self.opening,
            balance=Decimal("50000"),
            interest_rate=Decimal("6.00"),
            status="active",
        )
        app = LoanApplication.objects.create(
            application_number="LA-COMBO-001",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            application_date=date.today(),
            status="approved",
            approval_date=date.today(),
            created_by=self.admin,
            approved_by=self.approver,
        )
        self.loan = LoanAccount.objects.create(
            loan_number="LN-COMBO-001",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            emi_amount=Decimal("879.16"),
            total_payable=Decimal("10550.00"),
            outstanding_balance=Decimal("10000"),
            disbursement_date=date.today() - timedelta(days=30),
            first_emi_date=date.today() - timedelta(days=30),
            total_emis=12,
            created_by=self.admin,
        )
        self.repayment = LoanRepayment.objects.create(
            loan_account=self.loan,
            installment_number=1,
            due_date=date.today(),
            amount_due=Decimal("879.16"),
            principal_component=Decimal("795.83"),
            interest_component=Decimal("83.33"),
            payment_status="upcoming",
        )

    def test_runs_both_sides(self):
        out = interest_engine.run_full_engine(
            as_of=date.today(), financial_period=self.fp, actor=self.admin, audit_via="test"
        )
        self.assertEqual(out["deposits"]["accounts_updated"], 1)
        self.assertGreater(out["deposits"]["total_posted"], Decimal("0"))
        self.assertEqual(out["loans"]["rows_created"], 1)
        self.assertEqual(out["loans"]["installments_considered"], 1)
        self.assertTrue(Transaction.objects.filter(transaction_type="interest").exists())
        self.assertTrue(InterestReceivable.objects.filter(loan_account=self.loan).exists())

    def test_full_engine_idempotent(self):
        """Running twice on the same as_of date posts deposits once, creates receivable once."""
        interest_engine.run_full_engine(as_of=date.today(), financial_period=self.fp)
        second = interest_engine.run_full_engine(as_of=date.today(), financial_period=self.fp)
        self.assertEqual(second["deposits"]["accounts_updated"], 0)
        self.assertEqual(second["loans"]["rows_created"], 0)
        self.assertEqual(InterestPayout.objects.count(), 1)
        self.assertEqual(InterestReceivable.objects.count(), 1)
