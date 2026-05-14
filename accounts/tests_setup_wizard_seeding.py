"""Tests for setup-wizard statutory seeding (Phase B6).

The first-run wizard's ``accounts.views._finalize_setup`` step creates
the primary admin user, society configuration, KYC, and account/loan
type configurations. Phase B6 extends that same step to additionally
seed:

- the first ``FinancialPeriod`` for the current Indian fiscal year,
- five statutory ``FundAccount`` rows, and
- five ``annual_profit`` ``FundAllocationRule`` rows wiring those funds
  to the surplus distribution flow.

These are statutory defaults; operators can edit / replace them later
from the Funds and Allocation-Rules screens. The contract pinned here:
finalize must be idempotent (re-running must not duplicate or
overwrite operator edits).
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import FinancialPeriod, FundAccount, FundAllocationRule
from accounts.views import _finalize_setup

User = get_user_model()


def _build_valid_payload():
    """Build the minimal setup payload that ``_finalize_setup`` accepts.

    Mirrors the shape produced by the 7-step wizard's session state
    (see ``setup_wizard_view`` in ``accounts/views.py``).
    """
    return {
        "admin": {
            "full_name": "Setup Admin",
            "username": "setupadmin",
            "email": "setup.admin@example.com",
            "mobile_primary": "9876543210",
            "password": "AdminPass123!",
        },
        "kyc": {
            "aadhaar_number": "234567890123",
            "pan_number": "ABCDE1234F",
        },
        "society": {"society_name": "Test Cooperative Society Ltd."},
        "penalty": {"late_payment_penalty_per_day": "5.00"},
        "account_configs": [{"type": "Savings", "interest_rate": "4.00"}],
        "loan_configs": [{"type": "Personal", "interest_rate": "10.00"}],
    }


class SetupWizardSeedingTests(TestCase):
    """Phase B6: statutory FY / funds / allocation-rule seeding."""

    def setUp(self):
        self.payload = _build_valid_payload()
        today = timezone.localdate()
        self.fy_start_year = today.year if today.month >= 4 else today.year - 1
        self.expected_label = f"FY {self.fy_start_year}-{str(self.fy_start_year + 1)[-2:]}"
        self.expected_start = date(self.fy_start_year, 4, 1)
        self.expected_end = date(self.fy_start_year + 1, 3, 31)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _finalize(self):
        ok, err = _finalize_setup(self.payload)
        self.assertTrue(ok, msg=err)

    # ------------------------------------------------------------------
    # FinancialPeriod
    # ------------------------------------------------------------------

    def test_finalize_seeds_first_financial_period(self):
        """Finalize creates one FY row with April-March bounds and active=open."""
        self._finalize()
        fp = FinancialPeriod.objects.get(
            start_date=self.expected_start,
            end_date=self.expected_end,
        )
        self.assertEqual(fp.label, self.expected_label)
        self.assertEqual(fp.status, "open")
        self.assertTrue(fp.is_active)
        self.assertEqual(fp.start_date.month, 4)
        self.assertEqual(fp.start_date.day, 1)
        self.assertEqual(fp.end_date.month, 3)
        self.assertEqual(fp.end_date.day, 31)

        admin = User.objects.get(username="setupadmin")
        self.assertEqual(fp.created_by_id, admin.id)
        self.assertEqual(FinancialPeriod.objects.count(), 1)

    # ------------------------------------------------------------------
    # FundAccount × 5
    # ------------------------------------------------------------------

    def test_finalize_seeds_five_statutory_fund_accounts(self):
        """Five statutory FundAccount rows are created with the right shapes."""
        self._finalize()
        admin = User.objects.get(username="setupadmin")

        funds = FundAccount.objects.all()
        self.assertEqual(funds.count(), 5)

        by_name = {f.name: f for f in funds}
        expected = {
            "Statutory Reserve Fund": "statutory",
            "Education Fund": "education",
            "Build / Service Fund": "welfare",
            "Bad-debt Provision Fund": "reserve",
            "Dividend Fund": "dividend",
        }
        self.assertEqual(set(by_name), set(expected))
        for name, fund_type in expected.items():
            fund = by_name[name]
            self.assertEqual(fund.fund_type, fund_type, msg=name)
            self.assertEqual(fund.balance, Decimal("0"), msg=name)
            self.assertTrue(fund.is_active, msg=name)
            self.assertEqual(fund.created_by_id, admin.id, msg=name)
            self.assertTrue(
                fund.account_number.startswith(f"FND-{self.fy_start_year}-"),
                msg=f"{name}: unexpected account_number {fund.account_number!r}",
            )

        # account_numbers must be unique across the 5 rows
        account_numbers = {f.account_number for f in funds}
        self.assertEqual(len(account_numbers), 5)

    # ------------------------------------------------------------------
    # FundAllocationRule × 5
    # ------------------------------------------------------------------

    def test_finalize_seeds_five_annual_profit_allocation_rules(self):
        """Five annual_profit rules totalling 100% with ascending priorities."""
        self._finalize()

        rules = list(FundAllocationRule.objects.filter(trigger_event="annual_profit").order_by("priority_order"))
        self.assertEqual(len(rules), 5)
        self.assertEqual(FundAllocationRule.objects.count(), 5)

        for rule in rules:
            self.assertEqual(rule.trigger_event, "annual_profit")
            self.assertEqual(rule.allocation_type, "percentage")
            self.assertTrue(rule.is_active)

        priorities = [r.priority_order for r in rules]
        self.assertEqual(priorities, sorted(priorities))
        self.assertEqual(len(set(priorities)), 5, msg="priority_order must be unique")

        total = sum((r.percentage for r in rules), Decimal("0"))
        self.assertEqual(total, Decimal("100.00"))

        by_fund_name = {r.fund.name: r for r in rules}
        self.assertEqual(by_fund_name["Statutory Reserve Fund"].percentage, Decimal("25.00"))
        self.assertEqual(by_fund_name["Education Fund"].percentage, Decimal("1.50"))
        self.assertEqual(by_fund_name["Build / Service Fund"].percentage, Decimal("10.00"))
        self.assertEqual(by_fund_name["Bad-debt Provision Fund"].percentage, Decimal("2.00"))
        self.assertEqual(by_fund_name["Dividend Fund"].percentage, Decimal("61.50"))

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_finalize_is_idempotent(self):
        """Calling _finalize_setup twice must not duplicate seeded rows."""
        self._finalize()
        fp_before = FinancialPeriod.objects.count()
        fund_before = FundAccount.objects.count()
        rule_before = FundAllocationRule.objects.count()

        self._finalize()
        self.assertEqual(FinancialPeriod.objects.count(), fp_before)
        self.assertEqual(FundAccount.objects.count(), fund_before)
        self.assertEqual(FundAllocationRule.objects.count(), rule_before)

    # ------------------------------------------------------------------
    # Respect pre-existing operator edits
    # ------------------------------------------------------------------

    def test_finalize_respects_existing_fund_account(self):
        """An operator-created fund (and its rule) is not overwritten on finalize."""
        account_number = f"FND-{self.fy_start_year}-SR001"
        existing_fund = FundAccount.objects.create(
            name="Custom Reserve",
            fund_type="other",
            account_number=account_number,
            balance=Decimal("100.00"),
            is_active=True,
        )
        existing_rule = FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=existing_fund,
            allocation_type="percentage",
            percentage=Decimal("12.34"),
            priority_order=999,
            is_active=True,
        )

        self._finalize()

        existing_fund.refresh_from_db()
        self.assertEqual(existing_fund.name, "Custom Reserve")
        self.assertEqual(existing_fund.fund_type, "other")
        self.assertEqual(existing_fund.balance, Decimal("100.00"))

        existing_rule.refresh_from_db()
        self.assertEqual(existing_rule.percentage, Decimal("12.34"))
        self.assertEqual(existing_rule.priority_order, 999)
        self.assertEqual(existing_rule.allocation_type, "percentage")

        # The wizard still seeds the other 4 funds + rules around the
        # operator's pre-existing one, so totals remain 5 / 5.
        self.assertEqual(FundAccount.objects.count(), 5)
        self.assertEqual(
            FundAllocationRule.objects.filter(trigger_event="annual_profit").count(),
            5,
        )
