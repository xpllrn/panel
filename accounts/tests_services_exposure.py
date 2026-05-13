"""Tests for accounts.services.exposure.

Locks in the externally-observable behaviour of the member-exposure snapshot
so Phase B8 (loan eligibility), the MCP server, and the future
`GET /api/v1/admin/members/{id}/exposure` endpoint can rely on it.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    FeeCharge,
    FeeSchedule,
    Guarantor,
    LoanTypeConfiguration,
    MemberAccount,
    ShareCapital,
)
from accounts.services import exposure as exposure_service
from accounts.services import loans as loan_service
from accounts.services.exceptions import NotFoundError

User = get_user_model()


class ExposureServiceTests(TestCase):
    """Behavioural lock-ins for accounts.services.exposure."""

    def setUp(self):
        """Build a rich exposure fixture for member 1 + a guarantor-only member 2."""
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
        self.member1 = User.objects.create_user(
            username="mem1",
            email="mem1@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="One",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0001",
        )
        self.member2 = User.objects.create_user(
            username="mem2",
            email="mem2@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Two",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0002",
        )

        # Deposits for member 1: CD 5000 + FD 10000 + RD 2000 = 17000.
        MemberAccount.objects.create(
            user=self.member1,
            account_number="CD000001",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("5000.00"),
            status="active",
        )
        MemberAccount.objects.create(
            user=self.member1,
            account_number="FD000001",
            account_type="fd",
            opening_date=date.today(),
            balance=Decimal("10000.00"),
            status="active",
        )
        MemberAccount.objects.create(
            user=self.member1,
            account_number="RD000001",
            account_type="rd",
            opening_date=date.today(),
            balance=Decimal("2000.00"),
            status="active",
        )
        # Share-type MemberAccount with balance 1000 — must NOT count towards
        # deposits (share capital is tracked via the ShareCapital model).
        MemberAccount.objects.create(
            user=self.member1,
            account_number="SH000001",
            account_type="share",
            opening_date=date.today(),
            balance=Decimal("1000.00"),
            status="active",
        )
        # OD with -3000 — the member has drawn 3000 against the facility.
        MemberAccount.objects.create(
            user=self.member1,
            account_number="OD000001",
            account_type="od",
            opening_date=date.today(),
            balance=Decimal("-3000.00"),
            status="active",
        )

        ShareCapital.objects.create(
            user=self.member1,
            number_of_shares=25,
            face_value_per_share=Decimal("100.00"),
            issue_date=date.today(),
            status="issued",
        )  # total_value -> 2500.00 (computed in save()).

        LoanTypeConfiguration.objects.create(
            loan_type="personal",
            interest_rate=Decimal("10.00"),
            is_active=True,
        )

        # Approved loan for member 1, principal 20000. After approval and
        # before any EMI is paid, outstanding_balance == principal.
        app = loan_service.create_loan_application(
            user_id=self.member1.id,
            loan_type="personal",
            principal_amount="20000",
            interest_rate="10",
            tenure_months=12,
            actor=self.admin,
        )
        self.loan = loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today(),
            actor=self.approver,
        )

        # Member 2 guarantees member 1's loan — manual Guarantor row so the
        # test fixture does not depend on a member-id lookup path.
        Guarantor.objects.create(
            loan_account=self.loan,
            user=self.member2,
            name=self.member2.display_name,
            relationship="friend",
            is_member=True,
            is_verified=False,
        )

        # 1 pending-ish fee for member 1 — the FeeCharge model currently
        # exposes only `charged / waived / refunded`, so we use `charged`
        # (the closest semantic match to "still owed").
        schedule = FeeSchedule.objects.create(
            fee_type="membership",
            name="Annual Membership",
            amount=Decimal("300.00"),
            applies_to="membership",
            is_active=True,
            effective_date=date.today(),
        )
        FeeCharge.objects.create(
            fee_schedule=schedule,
            user=self.member1,
            amount=Decimal("300.00"),
            status="charged",
        )

    # ------------------------------------------------------------------
    # get_member_exposure — aggregation correctness
    # ------------------------------------------------------------------

    def test_get_member_exposure_aggregates_correctly(self):
        """The full snapshot matches the hand-computed totals from setUp."""
        snap = exposure_service.get_member_exposure(self.member1)

        self.assertEqual(snap["share_capital"], Decimal("2500.00"))
        self.assertEqual(snap["deposits"], Decimal("17000.00"))
        self.assertEqual(snap["od_drawn"], Decimal("3000.00"))
        self.assertEqual(snap["loan_outstanding"], Decimal("20000.00"))
        self.assertEqual(snap["guarantee_contingent"], Decimal("0.00"))
        self.assertEqual(snap["fees_outstanding"], Decimal("300.00"))

        expected_net = (
            snap["deposits"]
            + snap["share_capital"]
            - snap["od_drawn"]
            - snap["loan_outstanding"]
            - snap["guarantee_contingent"]
            - snap["fees_outstanding"]
        )
        self.assertEqual(snap["net_exposure"], expected_net)

    def test_get_member_exposure_guarantor_contingent(self):
        """Member 2 (guarantor only) sees member 1's loan outstanding as a contingent liability."""
        member1_snap = exposure_service.get_member_exposure(self.member1)
        member2_snap = exposure_service.get_member_exposure(self.member2)

        self.assertEqual(
            member2_snap["guarantee_contingent"],
            member1_snap["loan_outstanding"],
        )
        # Member 2 has no positions of their own — only the guarantee.
        self.assertEqual(member2_snap["deposits"], Decimal("0.00"))
        self.assertEqual(member2_snap["share_capital"], Decimal("0.00"))
        self.assertEqual(member2_snap["loan_outstanding"], Decimal("0.00"))
        self.assertEqual(member2_snap["fees_outstanding"], Decimal("0.00"))

    def test_get_member_exposure_empty_member_returns_zeros(self):
        """A user with no accounts, loans, fees, or guarantees gets a zero-filled snapshot."""
        empty = User.objects.create_user(
            username="empty1",
            email="empty1@example.com",
            password="Pass1234!",
            first_name="Empty",
            last_name="Member",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0003",
        )
        snap = exposure_service.get_member_exposure(empty)
        for key in (
            "share_capital",
            "deposits",
            "od_drawn",
            "loan_outstanding",
            "guarantee_contingent",
            "fees_outstanding",
            "net_exposure",
        ):
            self.assertEqual(snap[key], Decimal("0.00"), msg=f"{key} should be 0.00")

    def test_get_member_exposure_by_id_unknown_raises_not_found(self):
        """The id-based helper raises `NotFoundError` for an unknown user id."""
        with self.assertRaises(NotFoundError):
            exposure_service.get_member_exposure_by_id(user_id=99999999)

    def test_get_member_exposure_handles_inactive_accounts(self):
        """A closed CD with a huge balance must NOT contribute to deposits."""
        MemberAccount.objects.create(
            user=self.member1,
            account_number="CD999999",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("999999.00"),
            status="closed",
        )
        snap = exposure_service.get_member_exposure(self.member1)
        self.assertEqual(snap["deposits"], Decimal("17000.00"))

    def test_get_member_exposure_handles_closed_loan(self):
        """Closing the loan drops `loan_outstanding` (and the guarantor's contingent) to zero."""
        self.loan.status = "closed"
        self.loan.save(update_fields=["status"])

        member1_snap = exposure_service.get_member_exposure(self.member1)
        member2_snap = exposure_service.get_member_exposure(self.member2)

        self.assertEqual(member1_snap["loan_outstanding"], Decimal("0.00"))
        self.assertEqual(member2_snap["guarantee_contingent"], Decimal("0.00"))

    def test_get_member_exposure_returns_decimals_not_floats(self):
        """Every value in the snapshot is a `Decimal`, never a `float` or `int`."""
        snap = exposure_service.get_member_exposure(self.member1)
        for key, value in snap.items():
            self.assertIsInstance(value, Decimal, msg=f"{key} must be Decimal, got {type(value).__name__}")
