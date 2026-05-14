"""
Tests for the admin_portal app.
Covers views, API endpoints, and member management functionality.
"""

from datetime import date, timedelta
import json

from django.contrib.auth import get_user_model
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone
from django.urls import reverse

from accounts.models import (
    FundAccount,
    FundAllocationRule,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    Transaction,
    Voucher,
)

User = get_user_model()


class AdminRequiredDecoratorTests(TestCase):
    """Tests for admin_required decorator."""

    def setUp(self):
        """Create test users."""
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.member_user = User.objects.create_user(
            username="member", email="member@example.com", password="MemberPass123!", role="member"
        )

    def test_admin_can_access_members_page(self):
        """Admin users should access members page."""
        self.client.login(username="admin", password="AdminPass123!")
        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_access_members_page(self):
        """Non-admin users should be forbidden."""
        self.client.login(username="member", password="MemberPass123!")
        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated users should redirect to login."""
        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)


class MembersViewTests(TestCase):
    """Tests for members_view."""

    def setUp(self):
        """Create admin user and test members."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        # Create multiple test members
        for i in range(30):
            User.objects.create_user(username=f"member{i}", email=f"member{i}@example.com", password="MemberPass123!")
        self.client.login(username="admin", password="AdminPass123!")

    def test_members_list_renders(self):
        """Should render members list page."""
        response = self.client.get(reverse("members"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/members.html")

    def test_pagination_works(self):
        """Should paginate with 25 members per page."""
        response = self.client.get(reverse("members"))
        self.assertTrue("page_obj" in response.context)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj.object_list), 25)

    def test_page_2_has_remaining(self):
        """Second page should have remaining members."""
        response = self.client.get(reverse("members"), {"page": 2})
        page_obj = response.context["page_obj"]
        # 31 total (30 + admin), page 2 should have 6
        self.assertEqual(len(page_obj.object_list), 6)

    def test_search_filters_results(self):
        """Search should filter members by username."""
        response = self.client.get(reverse("members"), {"q": "member1"})
        page_obj = response.context["page_obj"]
        # Should match member1, member10-19 = 11 members
        for user in page_obj.object_list:
            self.assertIn("member1", user.username)

    def test_search_preserves_in_context(self):
        """Search query should be in context for template."""
        response = self.client.get(reverse("members"), {"q": "test"})
        self.assertEqual(response.context["search_query"], "test")


class AddMemberViewTests(TestCase):
    """Tests for add_member_view API."""

    def setUp(self):
        """Create admin user."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.client.login(username="admin", password="AdminPass123!")

    def test_add_member_success(self):
        """Should create new member with auto-generated password from DOB."""
        response = self.client.post(
            reverse("add_member"),
            {
                "username": "newmember",
                "email": "new@example.com",
                "full_name": "Tanmay Sharma",
                "date_of_birth": "1990-02-11",
                "role": "member",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(User.objects.filter(username="newmember").exists())
        # Password should be DDMM + first 4 chars of name (no spaces, uppercase)
        self.assertEqual(data["password"], "1102TANM")

    def test_add_member_missing_dob(self):
        """Should reject when date of birth is missing."""
        response = self.client.post(
            reverse("add_member"),
            {
                "username": "newmember",
                "email": "new@example.com",
                "full_name": "Tanmay Sharma",
                "role": "member",
            },
        )
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("date of birth", data["error"].lower())

    def test_add_member_missing_full_name(self):
        """Should reject when full name is missing."""
        response = self.client.post(
            reverse("add_member"),
            {
                "username": "newmember",
                "email": "new@example.com",
                "date_of_birth": "1990-02-11",
                "role": "member",
            },
        )
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("full name", data["error"].lower())

    def test_add_member_duplicate_username(self):
        """Should reject duplicate username."""
        User.objects.create_user(username="existing", email="existing@example.com", password="Pass123!")
        response = self.client.post(
            reverse("add_member"),
            {
                "username": "existing",
                "email": "new@example.com",
                "full_name": "Tanmay Sharma",
                "date_of_birth": "1990-02-11",
                "role": "member",
            },
        )
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("exists", data["error"].lower())


class DeleteMemberViewTests(TestCase):
    """Tests for delete_member_view API."""

    def setUp(self):
        """Create admin and test member."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.member = User.objects.create_user(
            username="todelete", email="delete@example.com", password="DeletePass123!"
        )
        self.client.login(username="admin", password="AdminPass123!")

    def test_delete_member_success(self):
        """Should soft-delete member (set is_deleted=True, not destroy)."""
        response = self.client.post(reverse("delete_member", args=[self.member.id]), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        # User should still exist in DB but be marked as deleted
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_deleted)
        self.assertIsNotNone(self.member.deleted_at)
        self.assertEqual(self.member.status, "closed")
        self.assertFalse(self.member.is_active)

    def test_delete_nonexistent_member(self):
        """Should return error for nonexistent member."""
        response = self.client.post(reverse("delete_member", args=[99999]), content_type="application/json")
        data = response.json()
        self.assertFalse(data["success"])

    def test_deleted_member_excluded_from_list(self):
        """Soft-deleted members should not appear in the members list."""
        # Soft-delete the member
        self.client.post(reverse("delete_member", args=[self.member.id]), content_type="application/json")
        # Check members page
        response = self.client.get(reverse("members"))
        page_obj = response.context["page_obj"]
        member_ids = [u.id for u in page_obj.object_list]
        self.assertNotIn(self.member.id, member_ids)

    def test_deleted_member_excluded_from_search(self):
        """Soft-deleted members should not appear in search results."""
        self.member.first_name = "Deleted"
        self.member.last_name = "User"
        self.member.save()
        # Soft-delete
        self.client.post(reverse("delete_member", args=[self.member.id]), content_type="application/json")
        # Search
        response = self.client.get(reverse("search_members"), {"q": "Deleted"})
        data = response.json()
        result_ids = [r["id"] for r in data["results"]]
        self.assertNotIn(self.member.id, result_ids)


class EditMemberViewTests(TestCase):
    """Tests for edit_member_view API."""

    def setUp(self):
        """Create admin and test member."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.member = User.objects.create_user(
            username="editme",
            email="edit@example.com",
            password="EditPass123!",
            first_name="Original",
            last_name="Name",
        )
        self.client.login(username="admin", password="AdminPass123!")

    def test_edit_member_success(self):
        """Should update member details."""
        response = self.client.post(
            reverse("edit_member", args=[self.member.id]),
            {
                "username": "editme",
                "email": "updated@example.com",
                "name": "Updated Name",
                "phone": "9876543210",
                "role": "member",
            },
        )
        data = response.json()
        self.assertTrue(data["success"])

        # Verify changes
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "updated@example.com")
        self.assertEqual(self.member.first_name, "Updated")
        self.assertEqual(self.member.last_name, "Name")

    def test_edit_member_with_password(self):
        """Should update password when provided."""
        response = self.client.post(
            reverse("edit_member", args=[self.member.id]),
            {
                "username": "editme",
                "email": "edit@example.com",
                "name": "Original Name",
                "role": "member",
                "password": "NewStrongPass123!",
            },
        )
        data = response.json()
        self.assertTrue(data["success"])

        # Verify new password works
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password("NewStrongPass123!"))

    def test_edit_member_updates_name(self):
        """Should update first_name and last_name when name is changed."""
        response = self.client.post(
            reverse("edit_member", args=[self.member.id]),
            {
                "username": "editme",
                "email": "edit@example.com",
                "name": "New Full Name",
                "role": "member",
            },
        )
        data = response.json()
        self.assertTrue(data["success"])

        self.member.refresh_from_db()
        self.assertEqual(self.member.first_name, "New")
        self.assertEqual(self.member.last_name, "Full Name")


class GetMemberViewTests(TestCase):
    """Tests for get_member_view API."""

    def setUp(self):
        """Create admin and test member."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.member = User.objects.create_user(
            username="viewme",
            email="view@example.com",
            password="ViewPass123!",
            first_name="View",
            last_name="Member",
            mobile_primary="9876543210",
        )
        self.client.login(username="admin", password="AdminPass123!")

    def test_get_member_returns_data(self):
        """Should return member data as JSON."""
        response = self.client.get(reverse("get_member", args=[self.member.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["username"], "viewme")
        self.assertEqual(data["user"]["email"], "view@example.com")

    def test_get_nonexistent_member(self):
        """Should return error for nonexistent member."""
        response = self.client.get(reverse("get_member", args=[99999]))
        data = response.json()
        self.assertFalse(data["success"])


class MemberStatusLifecycleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin2", email="admin2@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.member = User.objects.create_user(
            username="statusmember", email="status@example.com", password="MemberPass123!", role="member"
        )
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="FD-TEST-001",
            account_type="fd",
            status="active",
            opening_date=timezone.now().date(),
            balance=Decimal("1500.00"),
            interest_rate=Decimal("7.50"),
        )
        self.client.login(username="admin2", password="AdminPass123!")

    def test_inactive_blocked_when_pending_emi_exists(self):
        app = LoanApplication.objects.create(
            application_number="LA-TEST-ADM-001",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("50000"),
            interest_rate=Decimal("12"),
            tenure_months=12,
            application_date=timezone.now().date(),
            status="approved",
            approval_date=timezone.now().date(),
        )
        loan = LoanAccount.objects.create(
            loan_number="LN-TEST-001",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("50000"),
            interest_rate=Decimal("12"),
            interest_type="reducing",
            tenure_months=12,
            emi_amount=Decimal("5000"),
            total_payable=Decimal("60000"),
            total_paid=Decimal("0"),
            outstanding_balance=Decimal("50000"),
            total_emis=12,
            emis_paid=0,
            emis_overdue=0,
        )
        LoanRepayment.objects.create(
            loan_account=loan,
            installment_number=1,
            due_date=timezone.now().date() - timedelta(days=20),
            amount_due=Decimal("5000"),
            amount_paid=Decimal("0"),
            payment_status="overdue",
        )
        response = self.client.post(
            reverse("edit_member", args=[self.member.id]),
            {
                "username": self.member.username,
                "email": self.member.email,
                "full_name": "Status Member",
                "role": "member",
                "status": "inactive",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

    def test_resign_after_inactive_period_generates_settlement_receipt(self):
        self.member.status = "inactive"
        self.member.inactive_since = timezone.now().date() - timedelta(days=40)
        self.member.save(update_fields=["status", "inactive_since"])
        response = self.client.post(
            reverse("edit_member", args=[self.member.id]),
            {
                "username": self.member.username,
                "email": self.member.email,
                "full_name": "Status Member",
                "role": "member",
                "status": "resign",
            },
        )
        self.assertTrue(response.json()["success"])
        self.member.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(self.member.status, "resign")
        self.assertFalse(self.member.is_active)
        self.assertEqual(self.account.balance, Decimal("0.00"))
        self.assertTrue(Transaction.objects.filter(user=self.member, transaction_type="debit").exists())


class VoucherFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin3", email="admin3@example.com", password="AdminPass123!", role="admin", is_staff=True
        )
        self.member = User.objects.create_user(
            username="vouchermember", email="voucher@example.com", password="MemberPass123!", role="member"
        )
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="RD-TEST-001",
            account_type="rd",
            status="active",
            opening_date=timezone.now().date(),
            balance=Decimal("0.00"),
            interest_rate=Decimal("7.00"),
        )
        self.fund = FundAccount.objects.create(
            name="Main Fund",
            fund_type="other",
            account_number="FUND-001",
            balance=Decimal("0.00"),
            created_by=self.admin,
        )
        self.client.login(username="admin3", password="AdminPass123!")

    def test_voucher_create_and_transfer(self):
        response = self.client.post(
            reverse("add_transaction"),
            {
                "user_id": self.member.id,
                "use_voucher": "1",
                "payment_mode": "cash",
                "account_entries": '[{"account_id": %d, "transaction_type": "credit", "amount": "500.00"}]'
                % self.account.id,
            },
        )
        self.assertTrue(response.json()["success"])
        voucher_id = response.json()["voucher_id"]
        transfer = self.client.post(
            reverse("transfer_voucher_to_fund", args=[voucher_id]),
            {"fund_id": self.fund.id},
        )
        self.assertTrue(transfer.json()["success"])
        voucher = Voucher.objects.get(id=voucher_id)
        self.assertEqual(voucher.status, "transferred")
        self.assertTrue(Transaction.objects.filter(user=self.member).exists())

    def test_neft_voucher_stores_instrument_and_transfer_attaches_to_transactions(self):
        """Non-cash voucher path creates Voucher.instrument; transfer reuses it on each Transaction."""
        response = self.client.post(
            reverse("add_transaction"),
            {
                "user_id": self.member.id,
                "use_voucher": "1",
                "payment_mode": "neft",
                "reference_number": "VUTR-NEFT-1",
                "instrument_payload": json.dumps({"reference_number": "VUTR-NEFT-1"}),
                "account_entries": '[{"account_id": %d, "transaction_type": "credit", "amount": "100.00"}]'
                % self.account.id,
            },
        )
        self.assertTrue(response.json()["success"], msg=response.content)
        voucher_id = response.json()["voucher_id"]
        voucher = Voucher.objects.get(id=voucher_id)
        self.assertIsNotNone(voucher.instrument_id)
        transfer = self.client.post(
            reverse("transfer_voucher_to_fund", args=[voucher_id]),
            {"fund_id": self.fund.id},
        )
        self.assertTrue(transfer.json()["success"])
        txn = Transaction.objects.filter(user=self.member).order_by("-id").first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.instrument_id, voucher.instrument_id)
