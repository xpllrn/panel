"""Tests for the ``run_interest_engine`` management command (Phase B2).

The command is a thin wrapper around
``accounts.services.interest_engine.run_full_engine`` (and the two halves
for the --deposits-only / --loans-only flags). These tests focus on the
*wrapper's* contract:

- argparse validation (mutually-exclusive flags, bad date, bad period id),
- correct delegation to the engine,
- stdout summary lines for cron logs.

The engine's own behaviour is covered by
``accounts/tests_services_interest_engine.py``.
"""

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import (
    FinancialPeriod,
    InterestPayout,
    InterestReceivable,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    Transaction,
)

User = get_user_model()


class RunInterestEngineCommandTests(TestCase):
    """Behavioural contract for ``python manage.py run_interest_engine``."""

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
        self.opening = date.today() - timedelta(days=60)
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="ACFD0001",
            account_type="fd",
            opening_date=self.opening,
            balance=Decimal("100000"),
            interest_rate=Decimal("6.00"),
            status="active",
        )
        app = LoanApplication.objects.create(
            application_number="LA-2025-CMD01",
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
            loan_number="LN-2025-CMD01",
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
        LoanRepayment.objects.create(
            loan_account=self.loan,
            installment_number=1,
            due_date=date.today(),
            amount_due=Decimal("879.16"),
            principal_component=Decimal("795.83"),
            interest_component=Decimal("83.33"),
            payment_status="upcoming",
        )

    def _run(self, *args):
        out = StringIO()
        err = StringIO()
        call_command("run_interest_engine", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    # ------------------------------------------------------------------
    # Happy path — default: runs both sides
    # ------------------------------------------------------------------

    def test_default_invocation_runs_both_sides(self):
        out, _ = self._run()
        self.assertEqual(Transaction.objects.filter(transaction_type="interest").count(), 1)
        self.assertEqual(InterestPayout.objects.count(), 1)
        self.assertEqual(InterestReceivable.objects.count(), 1)
        self.assertIn("[deposits]", out)
        self.assertIn("[loans]", out)

    # ------------------------------------------------------------------
    # Flag handling
    # ------------------------------------------------------------------

    def test_deposits_only_skips_loan_side(self):
        out, _ = self._run("--deposits-only")
        self.assertTrue(Transaction.objects.filter(transaction_type="interest").exists())
        self.assertFalse(InterestReceivable.objects.exists())
        self.assertIn("[deposits]", out)
        self.assertNotIn("[loans]", out)

    def test_loans_only_skips_deposit_side(self):
        out, _ = self._run("--loans-only")
        self.assertFalse(Transaction.objects.filter(transaction_type="interest").exists())
        self.assertEqual(InterestReceivable.objects.count(), 1)
        self.assertIn("[loans]", out)
        self.assertNotIn("[deposits]", out)

    def test_deposits_only_and_loans_only_are_mutually_exclusive(self):
        with self.assertRaises(CommandError):
            self._run("--deposits-only", "--loans-only")

    # ------------------------------------------------------------------
    # --as-of parsing
    # ------------------------------------------------------------------

    def test_as_of_in_past_runs_engine_with_that_date(self):
        past = date.today() - timedelta(days=10)
        # Make sure the loan repayment due date is on/before the past anchor.
        LoanRepayment.objects.filter(loan_account=self.loan).update(due_date=past)
        self._run("--as-of", past.isoformat())
        self.account.refresh_from_db()
        self.assertEqual(self.account.last_interest_calc_date, past)
        rec = InterestReceivable.objects.get(loan_account=self.loan)
        self.assertEqual(rec.due_date, past)

    def test_bad_as_of_format_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run("--as-of", "31/03/2026")

    # ------------------------------------------------------------------
    # --period resolution
    # ------------------------------------------------------------------

    def test_explicit_period_id_is_attributed_to_payouts(self):
        other_fp = FinancialPeriod.objects.create(
            label="FY2024-25",
            start_date=date(date.today().year - 1, 4, 1),
            end_date=date(date.today().year, 3, 31),
            status="closed",
            is_active=False,
        )
        self._run("--period", str(other_fp.id))
        payout = InterestPayout.objects.get()
        self.assertEqual(payout.financial_period_id, other_fp.id)

    def test_missing_period_id_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run("--period", "999999")

    # ------------------------------------------------------------------
    # Idempotency at the command level
    # ------------------------------------------------------------------

    def test_running_twice_on_same_as_of_is_safe(self):
        self._run()
        self._run()
        self.assertEqual(Transaction.objects.filter(transaction_type="interest").count(), 1)
        self.assertEqual(InterestPayout.objects.count(), 1)
        self.assertEqual(InterestReceivable.objects.count(), 1)
