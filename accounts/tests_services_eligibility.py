"""Tests for :mod:`accounts.services.eligibility`.

Locks in the externally-observable behaviour of the loan-eligibility pre-check
engine so future phases (REST endpoint, "Eligibility check" live panel, MCP
``is_loan_approvable``) cannot silently regress the public surface.

Each test sets up a *deliberately clean* baseline (verified member, active
loan-type config, active FinancialPeriod) and then breaks exactly the rule
under test — so the FULL list of reasons surfaces only the targeted failure.
"""

from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    FinancialPeriod,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    LoanTypeConfiguration,
    MemberKYC,
)
from accounts.services import eligibility as eligibility_service
from accounts.services.exceptions import NotFoundError

User = get_user_model()


class EligibilityServiceTests(TestCase):
    """Behavioural lock-ins for :mod:`accounts.services.eligibility`."""

    def setUp(self):
        """Baseline: verified loan-eligible member, active FY, active loan type."""
        self.admin = User.objects.create_user(
            username="elig_admin",
            email="elig_admin@example.com",
            password="Pass1234!",
            first_name="Eve",
            last_name="Admin",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="elig_mem",
            email="elig_mem@example.com",
            password="Pass1234!",
            first_name="Mary",
            last_name="Member",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0001",
            eligible_for_loans=True,
        )
        self.kyc = MemberKYC.objects.create(user=self.member, kyc_status="verified")
        LoanTypeConfiguration.objects.create(
            loan_type="personal",
            interest_rate=Decimal("10.00"),
            is_active=True,
        )
        today = date.today()
        self.fy = FinancialPeriod.objects.create(
            label=f"FY{today.year}",
            start_date=date(today.year, 4, 1) if today.month >= 4 else date(today.year - 1, 4, 1),
            end_date=date(today.year + 1, 3, 31) if today.month >= 4 else date(today.year, 3, 31),
            status="open",
            is_active=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call(self, **overrides):
        """Default kwargs for the eligibility service; overridden per test."""
        kwargs = dict(
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("10000"),
        )
        kwargs.update(overrides)
        return eligibility_service.check_loan_eligibility(**kwargs)

    def _make_overdue_loan_for_member(self):
        """Persist a LoanAccount + a past-due unpaid LoanRepayment for self.member."""
        app = LoanApplication.objects.create(
            application_number="LA-9999-00001",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("5000"),
            interest_rate=Decimal("10.00"),
            interest_type="reducing",
            tenure_months=6,
            application_date=date.today() - timedelta(days=120),
            status="approved",
        )
        loan = LoanAccount.objects.create(
            loan_number="LN-9999-00001",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("5000"),
            interest_rate=Decimal("10.00"),
            interest_type="reducing",
            tenure_months=6,
            emi_amount=Decimal("900.00"),
            total_payable=Decimal("5400.00"),
            outstanding_balance=Decimal("5000.00"),
            total_emis=6,
            disbursement_date=date.today() - timedelta(days=90),
            first_emi_date=date.today() - timedelta(days=60),
        )
        LoanRepayment.objects.create(
            loan_account=loan,
            installment_number=1,
            due_date=date.today() - timedelta(days=30),
            amount_due=Decimal("900.00"),
            principal_component=Decimal("800.00"),
            interest_component=Decimal("100.00"),
            balance_after=Decimal("4200.00"),
            payment_status="overdue",
        )
        return loan

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_check_loan_eligibility_happy_path_returns_approvable_true(self):
        """A perfectly clean member with all configuration in place is approvable."""
        result = self._call()
        self.assertTrue(result["approvable"])
        self.assertEqual(result["reasons"], [])
        self.assertIn("exposure", result)

    # ------------------------------------------------------------------
    # Individual failure modes
    # ------------------------------------------------------------------

    def test_check_loan_eligibility_blocked_when_not_a_member(self):
        """Passing a non-member user (e.g. staff) surfaces the not-a-member reason."""
        result = self._call(user=self.admin)
        self.assertFalse(result["approvable"])
        self.assertIn("Selected user is not a member.", result["reasons"])

    def test_check_loan_eligibility_blocked_when_ineligible_flag(self):
        """``user.eligible_for_loans=False`` blocks approval."""
        self.member.eligible_for_loans = False
        self.member.save(update_fields=["eligible_for_loans"])
        result = self._call()
        self.assertFalse(result["approvable"])
        self.assertIn("Member is marked as ineligible for loans.", result["reasons"])

    def test_check_loan_eligibility_blocked_when_kyc_not_verified(self):
        """``MemberKYC.kyc_status != 'verified'`` blocks approval."""
        self.kyc.kyc_status = "pending"
        self.kyc.save(update_fields=["kyc_status"])
        result = self._call()
        self.assertFalse(result["approvable"])
        self.assertIn("KYC is not verified.", result["reasons"])

    def test_check_loan_eligibility_blocked_when_overdue_emi(self):
        """An existing overdue LoanRepayment for the member blocks approval."""
        self._make_overdue_loan_for_member()
        result = self._call()
        self.assertFalse(result["approvable"])
        self.assertIn("Member has overdue EMI on an existing loan.", result["reasons"])

    def test_check_loan_eligibility_blocked_when_loan_type_disabled(self):
        """A loan_type without an active LoanTypeConfiguration row blocks approval."""
        result = self._call(loan_type="vehicle")
        self.assertFalse(result["approvable"])
        self.assertTrue(
            any("Loan type 'vehicle' is currently disabled." in r for r in result["reasons"]),
            result["reasons"],
        )

    def test_check_loan_eligibility_blocked_when_principal_zero(self):
        """Principal of zero (or negative) is rejected with a positive-amount reason."""
        result = self._call(principal_amount=Decimal("0"))
        self.assertFalse(result["approvable"])
        self.assertIn("Principal must be greater than zero.", result["reasons"])

    def test_check_loan_eligibility_blocked_when_no_active_fy(self):
        """No FinancialPeriod with is_active=True blocks approval."""
        FinancialPeriod.objects.update(is_active=False)
        result = self._call()
        self.assertFalse(result["approvable"])
        self.assertTrue(
            any("No active financial period" in r for r in result["reasons"]),
            result["reasons"],
        )

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def test_check_loan_eligibility_returns_multiple_reasons_when_multiple_fail(self):
        """Breaking three rules surfaces three distinct reasons in one call."""
        # 1. KYC not verified, 2. ineligible_for_loans, 3. loan_type disabled.
        self.kyc.kyc_status = "pending"
        self.kyc.save(update_fields=["kyc_status"])
        self.member.eligible_for_loans = False
        self.member.save(update_fields=["eligible_for_loans"])

        result = self._call(loan_type="vehicle")
        self.assertFalse(result["approvable"])
        self.assertEqual(len(result["reasons"]), 3, result["reasons"])
        self.assertIn("Member is marked as ineligible for loans.", result["reasons"])
        self.assertIn("KYC is not verified.", result["reasons"])
        self.assertTrue(
            any("Loan type 'vehicle' is currently disabled." in r for r in result["reasons"]),
            result["reasons"],
        )

    # ------------------------------------------------------------------
    # by-id lookup helper
    # ------------------------------------------------------------------

    def test_check_loan_eligibility_by_id_unknown_raises_not_found(self):
        """Unknown user_id raises NotFoundError (the *only* exception the service raises)."""
        with self.assertRaises(NotFoundError):
            eligibility_service.check_loan_eligibility_by_id(
                user_id=99999999,
                loan_type="personal",
                principal_amount=Decimal("10000"),
            )

    # ------------------------------------------------------------------
    # Exposure check — optional, conditional on the exposure service shipping.
    # ------------------------------------------------------------------

    def test_check_loan_eligibility_blocked_by_exposure_ceiling(self):
        """Projected outstanding above the ceiling blocks approval.

        Skipped when ``accounts.services.exposure`` is not yet in the tree
        (the module is being built concurrently in another agent).
        """
        try:
            import_module("accounts.services.exposure")
        except ImportError:
            self.skipTest("exposure service not yet in tree")

        from unittest.mock import patch

        exposure_snapshot = {
            "loan_outstanding": Decimal("4900000"),
            "share_capital": Decimal("1000"),
            "deposits": Decimal("1000"),
        }

        with patch(
            "accounts.services.eligibility._load_exposure_snapshot",
            return_value=exposure_snapshot,
        ):
            result = self._call(principal_amount=Decimal("500000"))

        self.assertFalse(result["approvable"])
        self.assertTrue(
            any("exposure ceiling" in r for r in result["reasons"]),
            result["reasons"],
        )
