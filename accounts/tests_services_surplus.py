"""Tests for accounts.services.surplus — Phase B9.

Locks in the externally-observable behaviour of the surplus distribution
service:

    compute_allocations, distribute_surplus.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import (
    AuditLog,
    FinancialPeriod,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    ProfitAndLoss,
)
from accounts.services import surplus as surplus_service
from accounts.services.exceptions import NotFoundError, ValidationError

User = get_user_model()


class ComputeAllocationsTests(TestCase):
    """Tests for compute_allocations (pure computation, no side effects)."""

    def setUp(self):
        self.fund_statutory = FundAccount.objects.create(
            name="Statutory Reserve",
            fund_type="statutory",
            account_number="FND-TEST-SR001",
            balance=Decimal("0"),
        )
        self.fund_education = FundAccount.objects.create(
            name="Education Fund",
            fund_type="education",
            account_number="FND-TEST-ED001",
            balance=Decimal("0"),
        )
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_statutory,
            allocation_type="percentage",
            percentage=Decimal("25.00"),
            is_active=True,
            priority_order=1,
        )
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_education,
            allocation_type="percentage",
            percentage=Decimal("10.00"),
            is_active=True,
            priority_order=2,
        )

    def test_percentage_allocations(self):
        """Percentage rules compute correctly."""
        allocs = surplus_service.compute_allocations(Decimal("10000"))
        self.assertEqual(len(allocs), 2)
        self.assertEqual(allocs[0]["amount"], Decimal("2500.00"))
        self.assertEqual(allocs[1]["amount"], Decimal("1000.00"))

    def test_zero_surplus_returns_empty(self):
        """Zero or negative surplus → no allocations."""
        self.assertEqual(surplus_service.compute_allocations(Decimal("0")), [])
        self.assertEqual(surplus_service.compute_allocations(Decimal("-100")), [])

    def test_fixed_amount_rule(self):
        """Fixed-amount rules return the fixed amount."""
        FundAllocationRule.objects.all().delete()
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_statutory,
            allocation_type="fixed",
            amount=Decimal("500.00"),
            is_active=True,
        )
        allocs = surplus_service.compute_allocations(Decimal("10000"))
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs[0]["amount"], Decimal("500.00"))

    def test_max_cap_respected(self):
        """Allocation is capped at max_cap."""
        FundAllocationRule.objects.all().delete()
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_statutory,
            allocation_type="percentage",
            percentage=Decimal("50.00"),
            max_cap=Decimal("1000.00"),
            is_active=True,
        )
        allocs = surplus_service.compute_allocations(Decimal("10000"))
        self.assertEqual(allocs[0]["amount"], Decimal("1000.00"))

    def test_min_threshold_skips_rule(self):
        """Rule with min_threshold above surplus is skipped."""
        FundAllocationRule.objects.all().delete()
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_statutory,
            allocation_type="percentage",
            percentage=Decimal("25.00"),
            min_threshold=Decimal("50000.00"),
            is_active=True,
        )
        allocs = surplus_service.compute_allocations(Decimal("10000"))
        self.assertEqual(len(allocs), 0)

    def test_inactive_rules_excluded(self):
        """Inactive rules are not included."""
        FundAllocationRule.objects.update(is_active=False)
        allocs = surplus_service.compute_allocations(Decimal("10000"))
        self.assertEqual(len(allocs), 0)


class DistributeSurplusTests(TestCase):
    """Tests for distribute_surplus."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_surplus",
            email="admin_surplus@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="Surplus",
            is_staff=True,
            role="admin",
        )
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="closed",
            is_active=False,
        )
        self.pl = ProfitAndLoss.objects.create(
            financial_period=self.fp,
            net_surplus=Decimal("10000.00"),
            calculation_date=timezone.now(),
            is_locked=True,
            calculated_by=self.admin,
        )
        self.fund_statutory = FundAccount.objects.create(
            name="Statutory Reserve",
            fund_type="statutory",
            account_number="FND-2025-SR001",
            balance=Decimal("0"),
        )
        self.fund_education = FundAccount.objects.create(
            name="Education Fund",
            fund_type="education",
            account_number="FND-2025-ED001",
            balance=Decimal("0"),
        )
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_statutory,
            allocation_type="percentage",
            percentage=Decimal("25.00"),
            is_active=True,
            priority_order=1,
        )
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_education,
            allocation_type="percentage",
            percentage=Decimal("10.00"),
            is_active=True,
            priority_order=2,
        )

    def test_distribute_credits_funds(self):
        """Surplus distribution credits fund accounts correctly."""
        result = surplus_service.distribute_surplus(self.fp, actor=self.admin)
        self.assertFalse(result["already_distributed"])
        self.assertEqual(result["net_surplus"], Decimal("10000.00"))
        self.assertEqual(result["total_allocated"], Decimal("3500.00"))
        self.assertEqual(len(result["allocations"]), 2)

        self.fund_statutory.refresh_from_db()
        self.fund_education.refresh_from_db()
        self.assertEqual(self.fund_statutory.balance, Decimal("2500.00"))
        self.assertEqual(self.fund_education.balance, Decimal("1000.00"))

    def test_distribute_idempotent(self):
        """Running distribute_surplus again returns existing allocations."""
        surplus_service.distribute_surplus(self.fp, actor=self.admin)
        result = surplus_service.distribute_surplus(self.fp, actor=self.admin)
        self.assertTrue(result["already_distributed"])
        self.assertEqual(result["total_allocated"], Decimal("3500.00"))

        # Fund balances should NOT have doubled.
        self.fund_statutory.refresh_from_db()
        self.assertEqual(self.fund_statutory.balance, Decimal("2500.00"))

    def test_distribute_rejects_missing_pl(self):
        """No P&L snapshot → NotFoundError."""
        self.pl.delete()
        with self.assertRaises(NotFoundError):
            surplus_service.distribute_surplus(self.fp, actor=self.admin)

    def test_distribute_rejects_unlocked_pl(self):
        """Unlocked P&L → ValidationError."""
        self.pl.is_locked = False
        self.pl.save()
        with self.assertRaises(ValidationError):
            surplus_service.distribute_surplus(self.fp, actor=self.admin)

    def test_distribute_rejects_zero_surplus(self):
        """Zero net_surplus → ValidationError."""
        self.pl.net_surplus = Decimal("0")
        self.pl.save()
        with self.assertRaises(ValidationError):
            surplus_service.distribute_surplus(self.fp, actor=self.admin)

    def test_distribute_rejects_no_rules(self):
        """No active allocation rules → ValidationError."""
        FundAllocationRule.objects.update(is_active=False)
        with self.assertRaises(ValidationError):
            surplus_service.distribute_surplus(self.fp, actor=self.admin)

    def test_distribute_updates_pl_fund_allocations_total(self):
        """After distribution, P&L.fund_allocations_total is updated."""
        surplus_service.distribute_surplus(self.fp, actor=self.admin)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.fund_allocations_total, Decimal("3500.00"))

    def test_distribute_creates_fund_transactions(self):
        """FundTransaction rows are created with correct metadata."""
        surplus_service.distribute_surplus(self.fp, actor=self.admin)
        txns = FundTransaction.objects.filter(
            trigger_event="annual_profit",
            financial_period=self.fp,
        )
        self.assertEqual(txns.count(), 2)
        for txn in txns:
            self.assertEqual(txn.transaction_type, "credit")
            self.assertEqual(txn.payment_mode, "internal")
            self.assertIsNotNone(txn.allocation_rule)
            self.assertIn("Annual profit distribution", txn.description)

    def test_distribute_writes_audit_log(self):
        """Distribution writes an audit log entry."""
        surplus_service.distribute_surplus(self.fp, actor=self.admin)
        audit = AuditLog.objects.filter(
            entity_type="fund",
            description__contains="Distributed surplus",
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn("₹10000", audit.description)

    def test_distribute_via_api_audit_marker(self):
        """audit_via='api' includes 'via API:' in the audit description."""
        surplus_service.distribute_surplus(self.fp, actor=self.admin, audit_via="api")
        audit = AuditLog.objects.filter(
            entity_type="fund",
            description__contains="via API:",
        ).first()
        self.assertIsNotNone(audit)
