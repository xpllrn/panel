"""Tests for accounts.services.society — Phase B5.

Locks in the externally-observable behaviour of the society main account
service:

    compute_live_position, get_main_account.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    FeeCharge,
    FeeSchedule,
    FinancialPeriod,
    FundAccount,
    InterestReceivable,
    LoanAccount,
    LoanApplication,
    MemberAccount,
    SocietyAccount,
)
from accounts.services import society as society_service

User = get_user_model()


class ComputeLivePositionTests(TestCase):
    """Tests for compute_live_position."""

    def setUp(self):
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
        )
        self.member = User.objects.create_user(
            username="mem_soc",
            email="mem_soc@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Soc",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0100",
        )

    def test_empty_database_returns_zeros(self):
        """No accounts/loans/fees → all zeros."""
        pos = society_service.compute_live_position(financial_period=self.fp)
        for field in society_service.POSITION_FIELDS:
            self.assertEqual(pos[field], Decimal("0.00"), f"{field} should be zero")

    def test_deposits_aggregated(self):
        """Active deposit accounts (non-share, non-OD) are summed."""
        MemberAccount.objects.create(
            user=self.member,
            account_number="FD-2026-00100",
            account_type="fd",
            opening_date=date.today(),
            balance=Decimal("50000.00"),
            accrued_interest=Decimal("1200.00"),
        )
        MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00100",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("30000.00"),
            accrued_interest=Decimal("800.00"),
        )
        # Share account should be excluded.
        MemberAccount.objects.create(
            user=self.member,
            account_number="SHR-2026-00100",
            account_type="share",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
        )
        pos = society_service.compute_live_position(financial_period=self.fp)
        self.assertEqual(pos["total_member_deposits"], Decimal("80000.00"))
        self.assertEqual(pos["total_interest_payable"], Decimal("2000.00"))

    def test_loan_outstanding_aggregated(self):
        """Active loan outstanding balances are summed."""
        admin = User.objects.create_user(
            username="admin_soc", email="a@a.com", password="P", is_staff=True, role="admin"
        )
        app = LoanApplication.objects.create(
            application_number="LA-2026-00100",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("100000"),
            interest_rate=Decimal("10"),
            tenure_months=12,
            status="approved",
            created_by=admin,
        )
        LoanAccount.objects.create(
            loan_number="LN-2026-00100",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("100000"),
            interest_rate=Decimal("10"),
            tenure_months=12,
            outstanding_balance=Decimal("85000.00"),
        )
        pos = society_service.compute_live_position(financial_period=self.fp)
        self.assertEqual(pos["total_loan_outstanding"], Decimal("85000.00"))

    def test_interest_receivable_aggregated(self):
        """Accrued InterestReceivable rows (accrued - collected) are summed."""
        admin = User.objects.create_user(
            username="admin_soc2", email="a2@a.com", password="P", is_staff=True, role="admin"
        )
        app = LoanApplication.objects.create(
            application_number="LA-2026-00101",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("60000"),
            interest_rate=Decimal("10"),
            tenure_months=12,
            status="approved",
            created_by=admin,
        )
        loan_ac = LoanAccount.objects.create(
            loan_number="LN-2026-00101",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("60000"),
            interest_rate=Decimal("10"),
            tenure_months=12,
            outstanding_balance=Decimal("60000"),
        )
        InterestReceivable.objects.create(
            loan_account=loan_ac,
            amount_accrued=Decimal("500.00"),
            amount_collected=Decimal("0.00"),
            status="accrued",
            due_date=date(2026, 1, 1),
        )
        InterestReceivable.objects.create(
            loan_account=loan_ac,
            amount_accrued=Decimal("500.00"),
            amount_collected=Decimal("200.00"),
            status="accrued",
            due_date=date(2026, 2, 1),
        )
        pos = society_service.compute_live_position(financial_period=self.fp)
        # (500 - 0) + (500 - 200) = 800
        self.assertEqual(pos["total_interest_receivable"], Decimal("800.00"))

    def test_fees_collected_in_period(self):
        """Charged FeeCharge rows within the FY are summed."""
        schedule = FeeSchedule.objects.create(
            fee_type="processing",
            name="Processing",
            amount=Decimal("500"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        FeeCharge.objects.create(
            fee_schedule=schedule,
            user=self.member,
            amount=Decimal("500.00"),
            status="charged",
        )
        FeeCharge.objects.create(
            fee_schedule=schedule,
            user=self.member,
            amount=Decimal("300.00"),
            status="charged",
        )
        # Waived fee should NOT be counted.
        FeeCharge.objects.create(
            fee_schedule=schedule,
            user=self.member,
            amount=Decimal("200.00"),
            status="waived",
        )
        pos = society_service.compute_live_position(financial_period=self.fp)
        self.assertEqual(pos["total_fees_collected"], Decimal("800.00"))

    def test_fund_balance_aggregated(self):
        """All non-deleted FundAccount balances are summed."""
        FundAccount.objects.create(
            name="Statutory Reserve",
            fund_type="statutory",
            account_number="FND-2025-SR001",
            balance=Decimal("25000.00"),
        )
        FundAccount.objects.create(
            name="Education Fund",
            fund_type="education",
            account_number="FND-2025-ED001",
            balance=Decimal("5000.00"),
        )
        # Deleted fund should be excluded.
        FundAccount.objects.create(
            name="Deleted Fund",
            fund_type="other",
            account_number="FND-2025-XX001",
            balance=Decimal("9999.00"),
            is_deleted=True,
        )
        pos = society_service.compute_live_position(financial_period=self.fp)
        self.assertEqual(pos["total_fund_balance"], Decimal("30000.00"))


class GetMainAccountTests(TestCase):
    """Tests for get_main_account (live + snapshot + drift)."""

    def setUp(self):
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
        )
        self.member = User.objects.create_user(
            username="mem_main",
            email="mem_main@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Main",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0200",
        )

    def test_no_snapshot_returns_stale_true(self):
        """When no SocietyAccount exists, snapshot is None and stale is True."""
        result = society_service.get_main_account(financial_period=self.fp)
        self.assertIsNone(result["snapshot"])
        self.assertIsNone(result["drift"])
        self.assertTrue(result["snapshot_stale"])
        self.assertIsNotNone(result["live"])
        self.assertEqual(result["financial_period"]["id"], self.fp.id)

    def test_snapshot_matches_live_no_drift(self):
        """When snapshot matches live, drift is all zeros and stale is False."""
        # Create a snapshot that matches the live (empty) state.
        SocietyAccount.objects.create(
            financial_period=self.fp,
            total_member_deposits=Decimal("0"),
            total_loan_outstanding=Decimal("0"),
            total_interest_payable=Decimal("0"),
            total_interest_receivable=Decimal("0"),
            total_fees_collected=Decimal("0"),
            total_fund_balance=Decimal("0"),
            net_surplus=Decimal("0"),
        )
        result = society_service.get_main_account(financial_period=self.fp)
        self.assertFalse(result["snapshot_stale"])
        for field in society_service.POSITION_FIELDS:
            self.assertEqual(result["drift"][field], Decimal("0.00"))

    def test_drift_detected_when_live_differs(self):
        """When live differs from snapshot, drift shows the difference."""
        # Snapshot says deposits = 50000, but live has 80000.
        SocietyAccount.objects.create(
            financial_period=self.fp,
            total_member_deposits=Decimal("50000"),
            total_loan_outstanding=Decimal("0"),
            total_interest_payable=Decimal("0"),
            total_interest_receivable=Decimal("0"),
            total_fees_collected=Decimal("0"),
            total_fund_balance=Decimal("0"),
            net_surplus=Decimal("0"),
        )
        MemberAccount.objects.create(
            user=self.member,
            account_number="FD-2026-00200",
            account_type="fd",
            opening_date=date.today(),
            balance=Decimal("80000.00"),
        )
        result = society_service.get_main_account(financial_period=self.fp)
        self.assertTrue(result["snapshot_stale"])
        self.assertEqual(result["drift"]["total_member_deposits"], Decimal("30000.00"))

    def test_financial_period_data_included(self):
        """The response includes financial period metadata."""
        result = society_service.get_main_account(financial_period=self.fp)
        self.assertEqual(result["financial_period"]["label"], "FY 2025-26")
        self.assertEqual(result["financial_period"]["status"], "open")

    def test_no_active_period_returns_none_fp(self):
        """When no active FY and none passed, financial_period is None."""
        self.fp.is_active = False
        self.fp.save()
        result = society_service.get_main_account(financial_period=None)
        self.assertIsNone(result["financial_period"])
        self.assertIsNotNone(result["live"])
