"""Integration-style tests for Phase A6 (profit distribution from locked P&L)."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import FinancialPeriod, FundAccount, FundAllocationRule, ProfitAndLoss

User = get_user_model()


class DistributeProfitLockedPLTests(TestCase):
    """Panel distribute-profit uses locked ProfitAndLoss.net_surplus (ROADMAP A6)."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="pladmin",
            email="pladmin@example.com",
            password="AdminPass123!",
            role="admin",
            is_staff=True,
        )
        self.fund = FundAccount.objects.create(
            name="Reserve Test Fund",
            fund_type="other",
            account_number="FND-PL-001",
            balance=Decimal("0"),
            created_by=self.admin,
        )
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund,
            allocation_type="percentage",
            percentage=Decimal("100"),
            created_by=self.admin,
        )
        y = 2090
        self.fp = FinancialPeriod.objects.create(
            label=f"FY{y}",
            start_date=date(y, 4, 1),
            end_date=date(y + 1, 3, 31),
            status="open",
            is_active=True,
            created_by=self.admin,
        )
        self.pl = ProfitAndLoss.objects.create(
            financial_period=self.fp,
            net_surplus=Decimal("5000"),
            calculation_date=timezone.now(),
            is_locked=False,
            calculated_by=self.admin,
        )
        self.client.login(username="pladmin", password="AdminPass123!")

    def test_distribute_rejects_unlocked_pl(self):
        """Unlocked P&L returns a clear error (no fund movements)."""
        r = self.client.post(reverse("distribute_profit"), {"financial_period_id": self.fp.id})
        data = r.json()
        self.assertFalse(data["success"])
        self.assertIn("not locked", data["error"].lower())

    def test_distribute_uses_locked_net_surplus(self):
        """Locked P&L with positive net_surplus runs allocation rules."""
        self.pl.is_locked = True
        self.pl.save(update_fields=["is_locked"])
        r = self.client.post(reverse("distribute_profit"), {"financial_period_id": self.fp.id})
        data = r.json()
        self.assertTrue(data["success"], msg=data)
        self.fund.refresh_from_db()
        self.assertGreater(self.fund.balance, Decimal("0"))
