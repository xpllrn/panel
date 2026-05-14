"""Tests for the apply_fees management command — Phase B4."""

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import (
    FeeSchedule,
    FinancialPeriod,
    LoanRepayment,
    LoanTypeConfiguration,
    MemberAccount,
    SocietyConfiguration,
)
from accounts.services import loans as loan_service

User = get_user_model()


class ApplyFeesCommandTests(TestCase):
    """Tests for python manage.py apply_fees."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_cmd",
            email="admin_cmd@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="Cmd",
            is_staff=True,
            role="admin",
        )
        self.approver = User.objects.create_user(
            username="approver_cmd",
            email="approver_cmd@example.com",
            password="Pass1234!",
            first_name="Approver",
            last_name="Cmd",
            is_staff=True,
            role="admin",
        )
        self.member = User.objects.create_user(
            username="mem_cmd",
            email="mem_cmd@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Cmd",
            is_staff=False,
            role="member",
            member_id="MEM-2026-0050",
        )
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD-2026-00050",
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
        FeeSchedule.objects.create(
            fee_type="late_payment",
            name="Late Payment Fee",
            amount=Decimal("150.00"),
            applies_to="loan",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
        FeeSchedule.objects.create(
            fee_type="annual_maintenance",
            name="Annual Maintenance",
            amount=Decimal("100.00"),
            applies_to="membership",
            is_active=True,
            effective_date=date(2025, 4, 1),
        )
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
            late_fee_grace_days=0,
        )

    def test_no_flags_raises_error(self):
        """Must specify at least --late or --annual."""
        with self.assertRaises(CommandError):
            call_command("apply_fees")

    def test_late_flag_runs_sweep(self):
        """--late runs the late-payment sweep."""
        # Create an overdue loan.
        app = loan_service.create_loan_application(
            user_id=self.member.id,
            loan_type="personal",
            principal_amount="60000",
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
        emi = LoanRepayment.objects.filter(loan_account=loan_ac, installment_number=1).first()
        emi.due_date = date.today() - timedelta(days=15)
        emi.payment_status = "overdue"
        emi.save()

        out = StringIO()
        call_command("apply_fees", "--late", stdout=out)
        output = out.getvalue()
        self.assertIn("[late_payment]", output)
        self.assertIn("created=1", output)

    def test_annual_flag_runs_sweep(self):
        """--annual runs the annual maintenance sweep."""
        out = StringIO()
        call_command("apply_fees", "--annual", stdout=out)
        output = out.getvalue()
        self.assertIn("[annual_maintenance]", output)
        self.assertIn("created=1", output)

    def test_both_flags(self):
        """--late --annual runs both sweeps."""
        out = StringIO()
        call_command("apply_fees", "--late", "--annual", stdout=out)
        output = out.getvalue()
        self.assertIn("[late_payment]", output)
        self.assertIn("[annual_maintenance]", output)

    def test_bad_as_of_raises_error(self):
        """Invalid --as-of format raises CommandError."""
        with self.assertRaises(CommandError):
            call_command("apply_fees", "--late", "--as-of", "not-a-date")

    def test_missing_period_raises_error(self):
        """Non-existent --period raises CommandError."""
        with self.assertRaises(CommandError):
            call_command("apply_fees", "--annual", "--period", "9999")

    def test_idempotent_on_rerun(self):
        """Running --annual twice produces 0 on second run."""
        call_command("apply_fees", "--annual")
        out = StringIO()
        call_command("apply_fees", "--annual", stdout=out)
        self.assertIn("created=0", out.getvalue())
