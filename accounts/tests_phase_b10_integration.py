"""Phase B10 — Cross-product engine + fee + surplus integration tests.

End-to-end lifecycle test that exercises the full cooperative banking cycle:

    1. Open FY → onboard member → open accounts (CD, FD, RD, Loan)
    2. Run interest engine → deposits accrue interest, loan receivables materialise
    3. Record EMI payment → receivable reconciled
    4. Auto-fees: processing fee on loan approval, late-payment sweep, annual maintenance
    5. FY close → P&L lock → surplus distribution → fund credits

All services are called directly (no HTTP layer) to prove the service layer
is the single source of truth and all adapters can rely on it.
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
    FundAccount,
    FundAllocationRule,
    InterestReceivable,
    LoanRepayment,
    LoanTypeConfiguration,
    MemberAccount,
    SocietyConfiguration,
    Transaction,
)
from accounts.services import fees as fee_service
from accounts.services import financial_period as fp_service
from accounts.services import interest_engine
from accounts.services import loans as loan_service
from accounts.services import society as society_service
from accounts.services import surplus as surplus_service
from accounts.utils import persist_financial_snapshots

User = get_user_model()


class FullLifecycleIntegrationTest(TestCase):
    """End-to-end lifecycle: FY open → accounts → engine → fees → close → distribute."""

    def setUp(self):
        """Set up a complete cooperative society scenario."""
        # Society configuration.
        SocietyConfiguration.objects.create(
            society_name="Test Cooperative Society",
            late_payment_penalty_per_day=Decimal("10.00"),
            late_fee_grace_days=7,
        )

        # Staff users.
        self.admin = User.objects.create_user(
            username="admin_b10",
            email="admin_b10@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="B10",
            is_staff=True,
            role="admin",
        )
        self.approver = User.objects.create_user(
            username="approver_b10",
            email="approver_b10@example.com",
            password="Pass1234!",
            first_name="Approver",
            last_name="B10",
            is_staff=True,
            role="admin",
        )

        # Member.
        self.member = User.objects.create_user(
            username="mem_b10",
            email="mem_b10@example.com",
            password="Pass1234!",
            first_name="Ravi",
            last_name="Kumar",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0500",
        )

        # Financial period (FY 2025-26).
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
            created_by=self.admin,
        )

        # Loan type configuration.
        LoanTypeConfiguration.objects.create(
            loan_type="personal",
            interest_rate=Decimal("12.00"),
            is_active=True,
        )

        # Fee schedules.
        FeeSchedule.objects.create(
            fee_type="processing",
            name="Loan Processing Fee",
            percentage=Decimal("1.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        FeeSchedule.objects.create(
            fee_type="membership",
            name="Annual Membership",
            amount=Decimal("200.00"),
            applies_to="membership",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        FeeSchedule.objects.create(
            fee_type="late_payment",
            name="Late Payment Fee",
            amount=Decimal("100.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        FeeSchedule.objects.create(
            fee_type="annual_maintenance",
            name="Annual Maintenance",
            amount=Decimal("50.00"),
            applies_to="membership",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )

        # Statutory funds + allocation rules (mirrors setup wizard seeding).
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
        self.fund_welfare = FundAccount.objects.create(
            name="Build/Service Fund",
            fund_type="welfare",
            account_number="FND-2025-BS001",
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
        FundAllocationRule.objects.create(
            trigger_event="annual_profit",
            fund=self.fund_welfare,
            allocation_type="percentage",
            percentage=Decimal("65.00"),
            is_active=True,
            priority_order=3,
        )

    # ------------------------------------------------------------------
    # Step 1: Open accounts
    # ------------------------------------------------------------------

    def _open_accounts(self):
        """Create CD, FD, RD accounts for the member."""
        self.cd_account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2025-00500",
            account_type="cd",
            opening_date=date(2025, 4, 15),
            balance=Decimal("100000.00"),
            principal_amount=Decimal("100000.00"),
            interest_rate=Decimal("7.00"),
            last_interest_calc_date=date(2025, 4, 15),
        )
        self.fd_account = MemberAccount.objects.create(
            user=self.member,
            account_number="FD-2025-00500",
            account_type="fd",
            opening_date=date(2025, 4, 15),
            balance=Decimal("50000.00"),
            principal_amount=Decimal("50000.00"),
            interest_rate=Decimal("8.50"),
            tenure_months=12,
            last_interest_calc_date=date(2025, 4, 15),
        )
        self.rd_account = MemberAccount.objects.create(
            user=self.member,
            account_number="RD-2025-00500",
            account_type="rd",
            opening_date=date(2025, 4, 15),
            balance=Decimal("12000.00"),
            principal_amount=Decimal("12000.00"),
            interest_rate=Decimal("7.50"),
            rd_monthly_amount=Decimal("1000.00"),
            rd_total_installments=12,
            last_interest_calc_date=date(2025, 4, 15),
        )

    # ------------------------------------------------------------------
    # Step 2: Approve a loan
    # ------------------------------------------------------------------

    def _approve_loan(self):
        """Create and approve a personal loan."""
        app = loan_service.create_loan_application(
            user_id=self.member.id,
            loan_type="personal",
            principal_amount="60000",
            interest_rate="12",
            tenure_months=12,
            actor=self.admin,
        )
        self.loan_account = loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date(2025, 5, 1),
            disbursement_account_id=self.cd_account.id,
            actor=self.approver,
        )

    # ------------------------------------------------------------------
    # The full lifecycle test
    # ------------------------------------------------------------------

    def test_full_lifecycle(self):
        """Complete lifecycle: accounts → loan → engine → fees → close → distribute."""
        # --- Step 1: Open accounts ---
        self._open_accounts()

        # Membership fee should be posted on first account (via adapter hook).
        # We simulate it here since we're calling models directly.
        fee_service.apply_membership_fee(
            self.member,
            member_account=self.cd_account,
            actor=self.admin,
            financial_period=self.fp,
        )
        membership_fee = FeeCharge.objects.get(user=self.member, fee_schedule__fee_type="membership")
        self.assertEqual(membership_fee.amount, Decimal("200.00"))
        self.assertEqual(membership_fee.status, "charged")

        # --- Step 2: Approve loan (auto-posts processing fee) ---
        self._approve_loan()

        # Processing fee should have been auto-posted by approve_loan_application.
        proc_fee = FeeCharge.objects.get(loan_account=self.loan_account, fee_schedule__fee_type="processing")
        # 1% of 60000 = 600
        self.assertEqual(proc_fee.amount, Decimal("600.00"))
        self.assertEqual(proc_fee.status, "charged")
        self.assertIsNotNone(proc_fee.transaction)

        # Loan disbursement credited the CD account.
        self.cd_account.refresh_from_db()
        # Original 100000 + 60000 disbursement - 200 membership - 600 processing = 159200
        self.assertEqual(self.cd_account.balance, Decimal("159200.00"))

        # --- Step 3: Run interest engine (deposits) ---
        as_of = date(2025, 5, 15)  # 30 days after opening
        deposit_result = interest_engine.accrue_deposits(
            as_of=as_of,
            financial_period=self.fp,
            actor=self.admin,
            audit_via="engine",
        )
        # All 3 deposit accounts should have been credited.
        self.assertEqual(deposit_result["accounts_posted"], 3)
        self.assertGreater(deposit_result["total_interest"], ZERO)

        # Verify CD account got interest.
        self.cd_account.refresh_from_db()
        self.assertGreater(self.cd_account.balance, Decimal("159200.00"))

        # --- Step 4: Run interest engine (loans) ---
        # Mark first EMI as overdue (due date in the past).
        emi1 = LoanRepayment.objects.get(loan_account=self.loan_account, installment_number=1)
        emi1.due_date = date(2025, 5, 1)
        emi1.payment_status = "overdue"
        emi1.save()

        loan_result = interest_engine.accrue_loans(
            as_of=as_of,
            financial_period=self.fp,
            actor=self.admin,
            audit_via="engine",
        )
        self.assertGreater(loan_result["rows_created"], 0)

        # InterestReceivable should exist for the overdue EMI.
        ir = InterestReceivable.objects.get(
            loan_account=self.loan_account,
            due_date=emi1.due_date,
        )
        self.assertEqual(ir.status, "accrued")
        self.assertGreater(ir.amount_accrued, ZERO)

        # --- Step 5: Record EMI payment → receivable reconciled ---
        emi_result = loan_service.record_emi_payment(
            loan_account_id=self.loan_account.id,
            installment_number=1,
            amount_paid=str(emi1.amount_due),
            payment_mode="cash",
            actor=self.admin,
        )
        self.assertEqual(emi_result["repayment"].payment_status, "paid")

        # Receivable should now be collected.
        ir.refresh_from_db()
        self.assertEqual(ir.status, "collected")

        # --- Step 6: Late-payment fee sweep ---
        # Mark EMI 2 as overdue (20 days past due, grace=7).
        emi2 = LoanRepayment.objects.get(loan_account=self.loan_account, installment_number=2)
        emi2.due_date = as_of - timedelta(days=20)
        emi2.payment_status = "overdue"
        emi2.save()

        late_result = fee_service.apply_late_payment_fees(
            as_of=as_of,
            grace_days=7,
            financial_period=self.fp,
        )
        self.assertEqual(late_result["charges_created"], 1)
        late_fee = FeeCharge.objects.get(loan_repayment=emi2, fee_schedule__fee_type="late_payment")
        self.assertEqual(late_fee.amount, Decimal("100.00"))

        # --- Step 7: Annual maintenance fee sweep ---
        annual_result = fee_service.apply_annual_maintenance_fees(
            financial_period=self.fp,
            actor=self.admin,
        )
        self.assertEqual(annual_result["charges_created"], 1)

        # --- Step 8: Idempotency checks ---
        # Re-run interest engine — should be no-op for deposits (same as_of).
        deposit_result2 = interest_engine.accrue_deposits(
            as_of=as_of,
            financial_period=self.fp,
            actor=self.admin,
        )
        self.assertEqual(deposit_result2["accounts_posted"], 0)

        # Re-run late fee sweep — should be no-op.
        late_result2 = fee_service.apply_late_payment_fees(
            as_of=as_of,
            grace_days=7,
            financial_period=self.fp,
        )
        self.assertEqual(late_result2["charges_created"], 0)

        # Re-run annual maintenance — should be no-op.
        annual_result2 = fee_service.apply_annual_maintenance_fees(
            financial_period=self.fp,
            actor=self.admin,
        )
        self.assertEqual(annual_result2["charges_created"], 0)
        self.assertEqual(annual_result2["charges_skipped"], 1)

        # --- Step 9: Society live position ---
        position = society_service.compute_live_position(financial_period=self.fp)
        self.assertGreater(position["total_member_deposits"], ZERO)
        self.assertGreater(position["total_loan_outstanding"], ZERO)
        self.assertGreater(position["total_fees_collected"], ZERO)
        self.assertGreater(position["total_interest_receivable"], ZERO)

        # --- Step 10: FY close → P&L lock → distribute ---
        # Persist financial snapshot first.
        pl_row, soc_row, pl_updated = persist_financial_snapshots(self.fp, calculated_by=self.admin)
        self.assertTrue(pl_updated)
        self.assertGreater(pl_row.total_income, ZERO)

        # Close the period (locks P&L).
        close_result = fp_service.close_period(
            period_id=self.fp.id,
            actor=self.admin,
        )
        self.assertEqual(close_result["period"].status, "closed")
        pl_row.refresh_from_db()
        self.assertTrue(pl_row.is_locked)

        # Distribute surplus.
        dist_result = surplus_service.distribute_surplus(
            self.fp,
            actor=self.admin,
        )
        self.assertFalse(dist_result["already_distributed"])
        self.assertGreater(dist_result["total_allocated"], ZERO)
        self.assertEqual(len(dist_result["allocations"]), 3)

        # Verify fund balances increased.
        self.fund_statutory.refresh_from_db()
        self.fund_education.refresh_from_db()
        self.fund_welfare.refresh_from_db()
        self.assertGreater(self.fund_statutory.balance, ZERO)
        self.assertGreater(self.fund_education.balance, ZERO)
        self.assertGreater(self.fund_welfare.balance, ZERO)

        # Verify idempotency of distribution.
        dist_result2 = surplus_service.distribute_surplus(self.fp, actor=self.admin)
        self.assertTrue(dist_result2["already_distributed"])

        # --- Step 11: Verify audit trail completeness ---
        audit_count = AuditLog.objects.count()
        self.assertGreater(audit_count, 5)  # Multiple audit entries created

        # Verify key audit entries exist.
        self.assertTrue(AuditLog.objects.filter(action="approve", entity_type="loan").exists())
        self.assertTrue(AuditLog.objects.filter(entity_type="fee").exists())
        self.assertTrue(AuditLog.objects.filter(action="create", entity_type="fund").exists())


class InterestEngineMultiAccountTest(TestCase):
    """Verify the interest engine handles all deposit types in one run."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_multi",
            email="admin_multi@example.com",
            password="Pass1234!",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem_multi",
            email="mem_multi@example.com",
            password="Pass1234!",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0600",
        )
        self.fp = FinancialPeriod.objects.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            status="open",
            is_active=True,
        )
        opening = date(2025, 4, 1)
        # Create one of each eligible deposit type.
        for acc_type, rate in [
            ("cd", "7.00"),
            ("fd", "8.50"),
            ("rd", "7.50"),
            ("sukanya", "8.00"),
            ("suputra", "7.25"),
        ]:
            MemberAccount.objects.create(
                user=self.member,
                account_number=f"{acc_type.upper()}-2025-00600",
                account_type=acc_type,
                opening_date=opening,
                balance=Decimal("10000.00"),
                interest_rate=Decimal(rate),
                last_interest_calc_date=opening,
            )
        # Share and OD should be excluded.
        MemberAccount.objects.create(
            user=self.member,
            account_number="SHR-2025-00600",
            account_type="share",
            opening_date=opening,
            balance=Decimal("5000.00"),
            interest_rate=Decimal("0"),
            last_interest_calc_date=opening,
        )
        MemberAccount.objects.create(
            user=self.member,
            account_number="OD-2025-00600",
            account_type="od",
            opening_date=opening,
            balance=Decimal("-3000.00"),
            interest_rate=Decimal("12.00"),
            last_interest_calc_date=opening,
        )

    def test_engine_posts_interest_to_all_eligible_types(self):
        """CD, FD, RD, Sukanya, Suputra all get interest; share and OD are excluded."""
        result = interest_engine.accrue_deposits(
            as_of=date(2025, 5, 1),
            financial_period=self.fp,
            actor=self.admin,
        )
        self.assertEqual(result["accounts_posted"], 5)
        self.assertGreater(result["total_interest"], ZERO)

        # Verify each eligible account got a transaction.
        for acc_type in ["cd", "fd", "rd", "sukanya", "suputra"]:
            acc = MemberAccount.objects.get(account_type=acc_type, user=self.member)
            txn_count = Transaction.objects.filter(
                member_account=acc,
                transaction_type="interest",
            ).count()
            self.assertEqual(txn_count, 1, f"{acc_type} should have 1 interest transaction")

        # Share and OD should have zero interest transactions.
        for acc_type in ["share", "od"]:
            acc = MemberAccount.objects.get(account_type=acc_type, user=self.member)
            txn_count = Transaction.objects.filter(
                member_account=acc,
                transaction_type="interest",
            ).count()
            self.assertEqual(txn_count, 0, f"{acc_type} should have 0 interest transactions")

    def test_engine_idempotent_same_day(self):
        """Running the engine twice on the same as_of date is a no-op."""
        as_of = date(2025, 5, 1)
        interest_engine.accrue_deposits(as_of=as_of, financial_period=self.fp, actor=self.admin)
        result2 = interest_engine.accrue_deposits(as_of=as_of, financial_period=self.fp, actor=self.admin)
        self.assertEqual(result2["accounts_posted"], 0)
        self.assertEqual(result2["total_interest"], ZERO)

    def test_full_engine_runs_both_sides(self):
        """run_full_engine executes deposits + loans atomically."""
        result = interest_engine.run_full_engine(
            as_of=date(2025, 5, 1),
            financial_period=self.fp,
            actor=self.admin,
        )
        self.assertIn("deposits", result)
        self.assertIn("loans", result)
        self.assertEqual(result["deposits"]["accounts_posted"], 5)


ZERO = Decimal("0.00")
