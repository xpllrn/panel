"""Tests for Phase B3 — EMI ↔ Receivable reconciliation.

Locks in the engine-aware reconciliation contract in
``accounts.services.interest_engine.reconcile_emi_to_receivable`` and
proves that both EMI-settlement paths exercise it:

- ``accounts.services.loans.record_emi_payment`` (the explicit "Record EMI
  payment" admin flow), AND
- ``accounts.services.transactions._settle_loan_repayment`` (used by
  ``post_transaction(loan_repayment_id=...)`` — the "post a Transaction
  against an installment" flow).

Also confirms that the legacy
``accounts.utils.mark_interest_receivable_collected_for_repayment`` shim
delegates to the engine.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    FinancialPeriod,
    InterestReceivable,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    Transaction,
)
from accounts.services import interest_engine
from accounts.services import loans as loan_service
from accounts.services import transactions as txn_service
from accounts.utils import mark_interest_receivable_collected_for_repayment

User = get_user_model()


class _Mixin:
    """Common fixtures: admin/approver/member + active FY + an active loan
    with one upcoming installment due today."""

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
        self.approver = User.objects.create_user(
            username="approver1",
            email="approver1@example.com",
            password="Pass1234!",
            first_name="Beta",
            last_name="Approver",
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
        self.fp = FinancialPeriod.objects.create(
            label="FY2025-26",
            start_date=date(date.today().year, 4, 1),
            end_date=date(date.today().year + 1, 3, 31),
            status="open",
            is_active=True,
        )
        self.disbursement_account = MemberAccount.objects.create(
            user=self.member,
            account_number="ACOD0001",
            account_type="cd",
            opening_date=date.today() - timedelta(days=60),
            balance=Decimal("50000"),
            interest_rate=Decimal("0.00"),
            status="active",
        )
        app = LoanApplication.objects.create(
            application_number="LA-2025-B3001",
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
            loan_number="LN-2025-B3001",
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
            disbursement_account=self.disbursement_account,
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


class ReconcileEmiToReceivableUnitTests(_Mixin, TestCase):
    """Direct unit tests on the engine helper."""

    def _mark_repayment_paid(self):
        self.repayment.payment_status = "paid"
        self.repayment.amount_paid = self.repayment.amount_due
        self.repayment.paid_date = date.today()
        self.repayment.save()

    def test_flips_existing_accrued_to_collected(self):
        rec = InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("0"),
            status="accrued",
            due_date=self.repayment.due_date,
        )
        self._mark_repayment_paid()

        changed = interest_engine.reconcile_emi_to_receivable(self.repayment)
        self.assertEqual(changed, 1)
        rec.refresh_from_db()
        self.assertEqual(rec.status, "collected")
        self.assertEqual(rec.amount_collected, rec.amount_accrued)
        self.assertEqual(rec.collected_date, self.repayment.paid_date)

    def test_creates_collected_row_when_no_prior_accrual(self):
        """Paying before the engine has had a chance to materialise the
        receivable still leaves a complete record on the loan side."""
        self._mark_repayment_paid()

        changed = interest_engine.reconcile_emi_to_receivable(self.repayment)
        self.assertEqual(changed, 1)
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.status, "collected")
        self.assertEqual(rec.amount_accrued, Decimal("83.33"))
        self.assertEqual(rec.amount_collected, Decimal("83.33"))
        self.assertEqual(rec.collected_date, self.repayment.paid_date)
        self.assertEqual(rec.financial_period_id, self.fp.id)

    def test_links_transaction_when_provided(self):
        InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("0"),
            status="accrued",
            due_date=self.repayment.due_date,
        )
        self._mark_repayment_paid()
        txn = Transaction.objects.create(
            transaction_number="TXN-RECT-001",
            user=self.member,
            member_account=self.disbursement_account,
            transaction_type="credit",
            amount=Decimal("879.16"),
            balance_after=Decimal("50879.16"),
            payment_mode="cash",
            description="EMI test",
        )
        interest_engine.reconcile_emi_to_receivable(self.repayment, transaction=txn)
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.transaction_id, txn.id)

    def test_idempotent_when_already_collected(self):
        rec = InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("83.33"),
            status="collected",
            collected_date=date.today() - timedelta(days=1),
            due_date=self.repayment.due_date,
        )
        original_collected_date = rec.collected_date
        self._mark_repayment_paid()
        changed = interest_engine.reconcile_emi_to_receivable(self.repayment)
        self.assertEqual(changed, 0)
        rec.refresh_from_db()
        self.assertEqual(rec.collected_date, original_collected_date)

    def test_collected_row_picks_up_transaction_on_late_link(self):
        """If the receivable was collected without a transaction link earlier,
        a later call with `transaction=<txn>` fills it in (1 = changed)."""
        rec = InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("83.33"),
            status="collected",
            collected_date=date.today(),
            due_date=self.repayment.due_date,
        )
        self._mark_repayment_paid()
        txn = Transaction.objects.create(
            transaction_number="TXN-RECT-002",
            user=self.member,
            member_account=self.disbursement_account,
            transaction_type="credit",
            amount=Decimal("879.16"),
            balance_after=Decimal("50879.16"),
            payment_mode="cash",
        )
        changed = interest_engine.reconcile_emi_to_receivable(self.repayment, transaction=txn)
        self.assertEqual(changed, 1)
        rec.refresh_from_db()
        self.assertEqual(rec.transaction_id, txn.id)

    def test_does_not_touch_written_off_rows(self):
        InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("0"),
            status="written_off",
            due_date=self.repayment.due_date,
        )
        self._mark_repayment_paid()
        changed = interest_engine.reconcile_emi_to_receivable(self.repayment)
        self.assertEqual(changed, 0)
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.status, "written_off")

    def test_partial_payment_is_noop(self):
        self.repayment.payment_status = "partial"
        self.repayment.amount_paid = Decimal("500")
        self.repayment.paid_date = date.today()
        self.repayment.save()
        changed = interest_engine.reconcile_emi_to_receivable(self.repayment)
        self.assertEqual(changed, 0)
        self.assertFalse(InterestReceivable.objects.exists())

    def test_zero_interest_component_is_noop(self):
        self.repayment.interest_component = Decimal("0")
        self._mark_repayment_paid()
        changed = interest_engine.reconcile_emi_to_receivable(self.repayment)
        self.assertEqual(changed, 0)
        self.assertFalse(InterestReceivable.objects.exists())


class RecordEmiPaymentReconcilesTests(_Mixin, TestCase):
    """The high-level `record_emi_payment` service settles the receivable."""

    def test_full_emi_payment_creates_collected_receivable(self):
        result = loan_service.record_emi_payment(
            loan_account_id=self.loan.id,
            installment_number=1,
            amount_paid=Decimal("879.16"),
            payment_mode="cash",
            actor=self.admin,
            audit_via="test",
        )
        self.assertEqual(result["repayment"].payment_status, "paid")
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.status, "collected")
        self.assertEqual(rec.amount_accrued, Decimal("83.33"))
        self.assertEqual(rec.amount_collected, Decimal("83.33"))
        self.assertEqual(rec.transaction_id, result["transaction"].id)

    def test_full_emi_flips_pre_existing_accrued_row(self):
        InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("0"),
            status="accrued",
            due_date=self.repayment.due_date,
        )
        result = loan_service.record_emi_payment(
            loan_account_id=self.loan.id,
            installment_number=1,
            amount_paid=Decimal("879.16"),
            payment_mode="cash",
            actor=self.admin,
            audit_via="test",
        )
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.status, "collected")
        self.assertEqual(rec.transaction_id, result["transaction"].id)
        self.assertEqual(InterestReceivable.objects.count(), 1)

    def test_partial_emi_does_not_create_receivable(self):
        loan_service.record_emi_payment(
            loan_account_id=self.loan.id,
            installment_number=1,
            amount_paid=Decimal("500"),
            payment_mode="cash",
            actor=self.admin,
            audit_via="test",
        )
        self.repayment.refresh_from_db()
        self.assertEqual(self.repayment.payment_status, "partial")
        self.assertFalse(InterestReceivable.objects.exists())


class PostTransactionLoanRepaymentReconcilesTests(_Mixin, TestCase):
    """`post_transaction(loan_repayment_id=...)` also reconciles when the
    installment ends up `paid` (Phase B3 closes the parity gap with
    `record_emi_payment`)."""

    def test_full_payment_via_post_transaction_collects_receivable(self):
        txn = txn_service.post_transaction(
            member_account_id=self.disbursement_account.id,
            transaction_type="credit",
            amount=Decimal("879.16"),
            description="EMI #1",
            payment_mode="cash",
            loan_repayment_id=self.repayment.id,
            actor=self.admin,
        )
        self.repayment.refresh_from_db()
        self.assertEqual(self.repayment.payment_status, "paid")
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.status, "collected")
        self.assertEqual(rec.transaction_id, txn.id)
        self.assertEqual(rec.amount_collected, Decimal("83.33"))

    def test_partial_payment_via_post_transaction_no_receivable(self):
        txn_service.post_transaction(
            member_account_id=self.disbursement_account.id,
            transaction_type="credit",
            amount=Decimal("500"),
            description="EMI #1 partial",
            payment_mode="cash",
            loan_repayment_id=self.repayment.id,
            actor=self.admin,
        )
        self.repayment.refresh_from_db()
        self.assertEqual(self.repayment.payment_status, "partial")
        self.assertFalse(InterestReceivable.objects.exists())


class LegacyUtilsShimTests(_Mixin, TestCase):
    """`accounts.utils.mark_interest_receivable_collected_for_repayment` is
    kept as a thin shim — assert it now routes through the engine."""

    def test_shim_creates_row_when_missing_just_like_engine(self):
        self.repayment.payment_status = "paid"
        self.repayment.amount_paid = self.repayment.amount_due
        self.repayment.paid_date = date.today()
        self.repayment.save()

        changed = mark_interest_receivable_collected_for_repayment(self.repayment)
        self.assertEqual(changed, 1)
        rec = InterestReceivable.objects.get(loan_account=self.loan, due_date=self.repayment.due_date)
        self.assertEqual(rec.status, "collected")

    def test_shim_idempotent_on_collected(self):
        InterestReceivable.objects.create(
            loan_account=self.loan,
            financial_period=self.fp,
            amount_accrued=Decimal("83.33"),
            amount_collected=Decimal("83.33"),
            status="collected",
            collected_date=date.today(),
            due_date=self.repayment.due_date,
        )
        self.repayment.payment_status = "paid"
        self.repayment.amount_paid = self.repayment.amount_due
        self.repayment.paid_date = date.today()
        self.repayment.save()

        self.assertEqual(mark_interest_receivable_collected_for_repayment(self.repayment), 0)
