"""Tests for accounts.services.financial_period lifecycle (Phase A5).

These tests pin down the externally-observable behaviour of
`open_period`, `continue_period`, and `close_period` so subsequent
phases (P&L engine in Phase B, MCP exposure later) cannot silently
regress the contract.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import AuditLog, FinancialPeriod, ProfitAndLoss, SocietyAccount
from accounts.services import financial_period as fp_service
from accounts.services.exceptions import ConflictError, NotFoundError, ValidationError

User = get_user_model()


class FinancialPeriodServiceTests(TestCase):
    """Behavioural lock-ins for accounts.services.financial_period lifecycle ops."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="fpadmin1",
            email="fpadmin1@example.com",
            password="Pass1234!",
            first_name="Phin",
            last_name="Admin",
            is_staff=True,
            role="admin",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _open(self, *, name, start, end, actor=None):
        return fp_service.open_period(
            name=name,
            start_date=start,
            end_date=end,
            actor=actor or self.admin,
        )

    # ------------------------------------------------------------------
    # open_period
    # ------------------------------------------------------------------

    def test_open_period_creates_active_and_demotes_previous(self):
        """Opening a second FY demotes the first one (without changing its status)."""
        fy1 = self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        self.assertTrue(fy1.is_active)
        self.assertEqual(fy1.status, "open")

        fy2 = self._open(name="FY 2025-26", start=date(2025, 4, 1), end=date(2026, 3, 31))
        fy1.refresh_from_db()

        self.assertTrue(fy2.is_active)
        self.assertEqual(fy2.status, "open")
        self.assertFalse(fy1.is_active)
        self.assertEqual(fy1.status, "open", "Demoted period must keep its status")

    def test_open_period_overlapping_raises_validation(self):
        """A new period whose range overlaps an existing one is rejected."""
        self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        with self.assertRaises(ValidationError):
            self._open(name="FY Q4 2024", start=date(2025, 1, 1), end=date(2025, 6, 30))

    def test_open_period_duplicate_name_raises_conflict(self):
        """Reusing a name (label) raises ConflictError, not ValidationError."""
        self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        with self.assertRaises(ConflictError):
            self._open(name="FY 2024-25", start=date(2026, 4, 1), end=date(2027, 3, 31))

    def test_open_period_swapped_dates_raises_validation(self):
        """`start_date > end_date` (and `start_date == end_date`) are both rejected."""
        with self.assertRaises(ValidationError):
            self._open(name="FY Swap A", start=date(2025, 4, 1), end=date(2024, 4, 1))
        with self.assertRaises(ValidationError):
            self._open(name="FY Swap B", start=date(2025, 4, 1), end=date(2025, 4, 1))

    # ------------------------------------------------------------------
    # continue_period
    # ------------------------------------------------------------------

    def test_continue_period_reactivates(self):
        """A demoted-but-open period can be continued; closed cannot."""
        fy1 = self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        fy2 = self._open(name="FY 2025-26", start=date(2025, 4, 1), end=date(2026, 3, 31))

        # Happy case: fy1 is demoted-but-open. Continue should re-activate it
        # and demote fy2.
        fy1.refresh_from_db()
        fy2.refresh_from_db()
        self.assertFalse(fy1.is_active)
        self.assertTrue(fy2.is_active)

        result = fp_service.continue_period(period_id=fy1.id, actor=self.admin)
        fy1.refresh_from_db()
        fy2.refresh_from_db()

        self.assertEqual(result.id, fy1.id)
        self.assertTrue(fy1.is_active)
        self.assertEqual(fy1.status, "open")
        self.assertFalse(fy2.is_active)
        self.assertEqual(fy2.status, "open")

        # Now close fy1 and confirm continuing a closed period is rejected.
        fp_service.close_period(period_id=fy1.id, actor=self.admin)
        with self.assertRaises(ValidationError):
            fp_service.continue_period(period_id=fy1.id, actor=self.admin)

    def test_continue_period_missing_raises_not_found(self):
        """`continue_period` on a non-existent id raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            fp_service.continue_period(period_id=999_999, actor=self.admin)

    # ------------------------------------------------------------------
    # close_period
    # ------------------------------------------------------------------

    def test_close_period_locks_pnl_and_demotes_period(self):
        """Closing locks the P&L snapshot and flips the period to closed/inactive."""
        fy = self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))

        result = fp_service.close_period(period_id=fy.id, actor=self.admin)
        fy.refresh_from_db()

        self.assertEqual(fy.status, "closed")
        self.assertFalse(fy.is_active)

        pnl = result["pnl"]
        self.assertIsInstance(pnl, ProfitAndLoss)
        pnl.refresh_from_db()
        self.assertTrue(pnl.is_locked)
        self.assertIsNotNone(pnl.locked_date)
        self.assertEqual(pnl.locked_by_id, self.admin.id)
        self.assertEqual(pnl.financial_period_id, fy.id)

        # SocietyAccount snapshot exists for this period.
        society = result["society_account"]
        self.assertIsInstance(society, SocietyAccount)
        self.assertEqual(society.financial_period_id, fy.id)

    def test_close_period_idempotent_blocked(self):
        """Calling close_period twice on the same period raises ValidationError."""
        fy = self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        fp_service.close_period(period_id=fy.id, actor=self.admin)
        with self.assertRaises(ValidationError):
            fp_service.close_period(period_id=fy.id, actor=self.admin)

    def test_close_period_writes_audit_via_api_marker(self):
        """`audit_via="api"` prepends the `via API: Closed` marker to the audit row."""
        fy = self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        fp_service.close_period(period_id=fy.id, actor=self.admin, audit_via="api")

        latest = AuditLog.objects.order_by("-created_at").first()
        self.assertIsNotNone(latest)
        self.assertTrue(
            latest.description.startswith("via API: Closed "),
            f"Expected audit description to start with 'via API: Closed '; got {latest.description!r}",
        )
        self.assertEqual(latest.entity_id, fy.id)

    def test_close_period_missing_raises_not_found(self):
        """`close_period` on a non-existent id raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            fp_service.close_period(period_id=999_999, actor=self.admin)

    # ------------------------------------------------------------------
    # Cross-cutting: open_period writes an audit row
    # ------------------------------------------------------------------

    def test_open_period_writes_create_audit(self):
        """`open_period` writes a `create` audit row referencing the new id."""
        fy = self._open(name="FY 2024-25", start=date(2024, 4, 1), end=date(2025, 3, 31))
        latest = AuditLog.objects.order_by("-created_at").first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.action, "create")
        self.assertEqual(latest.entity_type, "system")
        self.assertEqual(latest.entity_id, fy.id)
        self.assertTrue(latest.description.startswith("Created financial period: FY 2024-25"))
        # Confirm the FinancialPeriod actually exists and the helper sees it.
        self.assertEqual(FinancialPeriod.objects.filter(id=fy.id).count(), 1)
