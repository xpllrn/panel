from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Loan, MemberAccount, Receipt, User


class MemberPortalTestMixin:
    """Shared setup for member portal tests."""

    def setUp(self):
        # Create an admin user
        self.admin_user = User.objects.create_user(
            username="admin_test",
            password="admin12345",
            is_staff=True,
            role="admin",
        )

        # Create a member user
        self.member_user = User.objects.create_user(
            username="member_test",
            password="member12345",
            first_name="Test",
            last_name="Member",
            member_id="MEM001",
            role="member",
            portal_access_enabled=True,
        )

        # Create another member to test data isolation
        self.other_member = User.objects.create_user(
            username="other_member",
            password="other12345",
            first_name="Other",
            last_name="Person",
            member_id="MEM002",
            role="member",
            portal_access_enabled=True,
        )

        self.client = Client()


class MemberRequiredDecoratorTests(MemberPortalTestMixin, TestCase):
    """Tests for the member_required decorator."""

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated users should be redirected to login."""
        response = self.client.get(reverse("member_portal:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_admin_redirects_to_admin_home(self):
        """Admin users should be redirected to /home/."""
        self.client.login(username="admin_test", password="admin12345")
        response = self.client.get(reverse("member_portal:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/home/", response.url)

    def test_member_with_disabled_portal_gets_403(self):
        """Members with portal_access_enabled=False should get 403."""
        self.member_user.portal_access_enabled = False
        self.member_user.save()
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_valid_member_gets_200(self):
        """Valid members should access the dashboard."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:dashboard"))
        self.assertEqual(response.status_code, 200)


class MemberDashboardTests(MemberPortalTestMixin, TestCase):
    """Tests for the member dashboard view."""

    def test_dashboard_renders(self):
        """Dashboard should render for authenticated member."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome")

    def test_dashboard_context_has_required_keys(self):
        """Dashboard context should include summary data."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:dashboard"))
        self.assertIn("total_accounts", response.context)
        self.assertIn("total_balance", response.context)
        self.assertIn("total_active_loans", response.context)


class MemberAccountsTests(MemberPortalTestMixin, TestCase):
    """Tests for member accounts views."""

    def setUp(self):
        super().setUp()
        from datetime import date

        # Create an account for the member
        self.member_account = MemberAccount.objects.create(
            user=self.member_user,
            account_number="ACC001",
            account_type="fd",
            status="active",
            balance=50000.00,
            interest_rate=7.5,
            principal_amount=50000.00,
            opening_date=date(2025, 1, 1),
        )

        # Create an account for other member
        self.other_account = MemberAccount.objects.create(
            user=self.other_member,
            account_number="ACC002",
            account_type="rd",
            status="active",
            balance=10000.00,
            interest_rate=6.0,
            principal_amount=10000.00,
            opening_date=date(2025, 1, 1),
        )

    def test_accounts_list_shows_own_accounts_only(self):
        """Member should only see their own accounts."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:accounts"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACC001")
        self.assertNotContains(response, "ACC002")

    def test_account_detail_shows_own_account(self):
        """Member should see their own account details."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:account_detail", args=[self.member_account.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACC001")

    def test_account_detail_blocks_other_members_account(self):
        """Member should NOT see another member's account."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:account_detail", args=[self.other_account.id]))
        self.assertEqual(response.status_code, 404)


class MemberLoansTests(MemberPortalTestMixin, TestCase):
    """Tests for member loans views."""

    def setUp(self):
        super().setUp()
        from datetime import date

        self.member_loan = Loan.objects.create(
            user=self.member_user,
            loan_number="LN001",
            loan_type="personal",
            status="active",
            principal_amount=100000.00,
            interest_rate=10.5,
            tenure_months=24,
            emi_amount=4634.00,
            total_payable=111216.00,
            total_paid=0,
            outstanding_balance=111216.00,
            application_date=date(2025, 1, 1),
            created_by=self.admin_user,
        )

        self.other_loan = Loan.objects.create(
            user=self.other_member,
            loan_number="LN002",
            loan_type="home",
            status="active",
            principal_amount=500000.00,
            interest_rate=8.5,
            tenure_months=60,
            emi_amount=10000.00,
            total_payable=600000.00,
            total_paid=0,
            outstanding_balance=600000.00,
            application_date=date(2025, 1, 1),
            created_by=self.admin_user,
        )

    def test_loans_list_shows_own_loans_only(self):
        """Member should only see their own loans."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:loans"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LN001")
        self.assertNotContains(response, "LN002")

    def test_loan_detail_blocks_other_members_loan(self):
        """Member should NOT see another member's loan."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:loan_detail", args=[self.other_loan.id]))
        self.assertEqual(response.status_code, 404)


class MemberProfileTests(MemberPortalTestMixin, TestCase):
    """Tests for the member profile view."""

    def test_profile_renders(self):
        """Profile should render for authenticated member."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get(reverse("member_portal:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Member")
        self.assertContains(response, "MEM001")

    def test_change_password_success(self):
        """Member should be able to change their password."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.post(
            reverse("member_portal:profile"),
            {
                "change_password": "1",
                "current_password": "member12345",
                "new_password": "newpass12345",
                "confirm_password": "newpass12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully")

        # Verify new password works
        self.member_user.refresh_from_db()
        self.assertTrue(self.member_user.check_password("newpass12345"))

    def test_change_password_wrong_current(self):
        """Should error if current password is wrong."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.post(
            reverse("member_portal:profile"),
            {
                "change_password": "1",
                "current_password": "wrongpass",
                "new_password": "newpass12345",
                "confirm_password": "newpass12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current password is incorrect")

    def test_change_password_mismatch(self):
        """Should error if new passwords don't match."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.post(
            reverse("member_portal:profile"),
            {
                "change_password": "1",
                "current_password": "member12345",
                "new_password": "newpass12345",
                "confirm_password": "differentpass",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New passwords do not match")


class LoginRedirectTests(MemberPortalTestMixin, TestCase):
    """Tests for role-based login redirect."""

    def test_admin_redirected_to_home(self):
        """Admin should be redirected to /home/ after login."""
        response = self.client.post(
            "/login/",
            {"username": "admin_test", "password": "admin12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/home/")

    def test_member_redirected_to_member_portal(self):
        """Member should be redirected to /member/ after login."""
        response = self.client.post(
            "/login/",
            {"username": "member_test", "password": "member12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/member/")

    def test_root_redirect_admin(self):
        """Root / should redirect admin to /home/."""
        self.client.login(username="admin_test", password="admin12345")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/home/")

    def test_root_redirect_member(self):
        """Root / should redirect member to /member/."""
        self.client.login(username="member_test", password="member12345")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/member/")

    def test_root_redirect_unauthenticated(self):
        """Root / should redirect unauthenticated to /login/."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/")
