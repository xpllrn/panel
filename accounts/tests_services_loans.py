"""Tests for accounts.services.loans.

Locks in the externally-observable behaviour of the loan service so future
phases (A1, A2, B4) cannot silently regress the public surface:

    create_loan_application, approve_loan_application, record_emi_payment,
    has_unpaid_emi, next_application_number, next_loan_account_number.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    AuditLog,
    Guarantor,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    LoanTypeConfiguration,
    MemberAccount,
    Transaction,
)
from accounts.services import loans as loan_service
from accounts.services.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from accounts.services.interest import InterestCalculatorService

User = get_user_model()


class LoanServiceTests(TestCase):
    """Behavioural lock-ins for accounts.services.loans."""

    def setUp(self):
        """Create two staff actors, a member, a member account, and an active personal LoanTypeConfiguration."""
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
        self.member = User.objects.create_user(
            username="mem1",
            email="mem1@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="One",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0001",
        )
        self.account = MemberAccount.objects.create(
            user=self.member,
            account_number="CD000001",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("0"),
        )
        LoanTypeConfiguration.objects.create(
            loan_type="personal",
            interest_rate=Decimal("10.00"),
            is_active=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_application(self, **overrides):
        """Create a pending LoanApplication; actor defaults to self.admin."""
        kwargs = dict(
            user_id=self.member.id,
            loan_type="personal",
            principal_amount="12000",
            interest_rate="10",
            tenure_months=12,
            actor=self.admin,
        )
        kwargs.update(overrides)
        return loan_service.create_loan_application(**kwargs)

    def _approved_loan(self, **overrides):
        """Create + approve a loan and wire the disbursement_account to self.account.

        Returns (application, loan_account). The service does not assign a
        disbursement_account on approval (Phase A1 will), so the test fixture
        does it here so `record_emi_payment` posts a real Transaction.
        """
        app_overrides = overrides.pop("app_overrides", {})
        app = self._create_application(**app_overrides)
        approve_kwargs = dict(
            application_id=app.id,
            disbursement_date=date.today(),
            actor=self.approver,
        )
        approve_kwargs.update(overrides)
        loan = loan_service.approve_loan_application(**approve_kwargs)
        loan.disbursement_account = self.account
        loan.save(update_fields=["disbursement_account"])
        return app, loan

    # ------------------------------------------------------------------
    # create_loan_application — happy paths
    # ------------------------------------------------------------------

    def test_create_loan_application_returns_persisted_app(self):
        """Returns a pending LoanApplication, formats the number, and writes a panel-style audit row."""
        app = self._create_application()
        self.assertIsInstance(app, LoanApplication)
        self.assertRegex(app.application_number, r"^LA-\d{4}-\d{5}$")
        self.assertEqual(app.status, "pending")
        self.assertEqual(app.created_by_id, self.admin.id)
        audit = AuditLog.objects.get(action="create", entity_type="loan", entity_id=app.id)
        self.assertTrue(audit.description.startswith("Created loan application "))
        self.assertNotIn("via API:", audit.description)

    def test_create_loan_application_audit_via_api_includes_marker(self):
        """audit_via='api' surfaces the 'via API:' marker in the audit description."""
        app = self._create_application(audit_via="api")
        audit = AuditLog.objects.get(action="create", entity_type="loan", entity_id=app.id)
        self.assertIn("via API:", audit.description)

    # ------------------------------------------------------------------
    # approve_loan_application — happy path
    # ------------------------------------------------------------------

    def test_approve_loan_application_creates_account_schedule_guarantor(self):
        """Approval books a LoanAccount, a tenure-long schedule, a Guarantor, and an audit row."""
        app = self._create_application(
            guarantor_name="Test Guarantor",
            guarantor_relationship="brother",
            guarantor_contact="9876543210",
        )
        loan = loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today(),
            actor=self.approver,
        )
        self.assertIsInstance(loan, LoanAccount)
        self.assertEqual(loan.status, "active")
        self.assertRegex(loan.loan_number, r"^LN-\d{4}-\d{5}$")

        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertEqual(app.approved_by_id, self.approver.id)

        self.assertEqual(
            LoanRepayment.objects.filter(loan_account=loan).count(),
            app.tenure_months,
        )

        guarantors = list(Guarantor.objects.filter(loan_account=loan))
        self.assertEqual(len(guarantors), 1)
        self.assertEqual(guarantors[0].name, "Test Guarantor")
        self.assertFalse(guarantors[0].is_member)
        self.assertFalse(guarantors[0].is_verified)

        self.assertTrue(AuditLog.objects.filter(action="approve", entity_type="loan", entity_id=loan.id).exists())

    # ------------------------------------------------------------------
    # record_emi_payment — happy paths
    # ------------------------------------------------------------------

    def test_record_emi_payment_marks_repayment_paid_and_posts_transaction(self):
        """A full EMI payment marks the installment paid, posts a credit Transaction, updates loan totals."""
        _app, loan = self._approved_loan()
        repayment = LoanRepayment.objects.get(loan_account=loan, installment_number=1)
        emi = repayment.amount_due

        result = loan_service.record_emi_payment(
            loan_account_id=loan.id,
            installment_number=1,
            amount_paid=emi,
            actor=self.approver,
        )

        self.assertEqual(set(result.keys()), {"repayment", "loan_account", "transaction", "penalty"})

        repayment.refresh_from_db()
        self.assertEqual(repayment.payment_status, "paid")

        loan.refresh_from_db()
        self.assertEqual(loan.emis_paid, 1)
        self.assertEqual(loan.total_paid, emi)

        txn = result["transaction"]
        self.assertIsNotNone(txn)
        self.assertEqual(txn.transaction_type, "credit")
        self.assertEqual(txn.amount, emi)
        self.assertEqual(txn.member_account_id, self.account.id)
        self.assertEqual(txn.user_id, self.member.id)

    def test_record_emi_payment_partial(self):
        """A part-EMI payment marks the installment partial and keeps the loan active."""
        _app, loan = self._approved_loan()
        repayment = LoanRepayment.objects.get(loan_account=loan, installment_number=1)
        part = (repayment.amount_due / Decimal("2")).quantize(Decimal("0.01"))

        loan_service.record_emi_payment(
            loan_account_id=loan.id,
            installment_number=1,
            amount_paid=part,
            actor=self.approver,
        )

        repayment.refresh_from_db()
        loan.refresh_from_db()
        self.assertEqual(repayment.payment_status, "partial")
        self.assertEqual(loan.status, "active")

    # ------------------------------------------------------------------
    # create_loan_application — sad paths
    # ------------------------------------------------------------------

    def test_create_loan_application_missing_user_id_raises_validation(self):
        """user_id=None raises ValidationError('Member is required.')."""
        with self.assertRaises(ValidationError) as ctx:
            self._create_application(user_id=None)
        self.assertEqual(ctx.exception.message, "Member is required.")

    def test_create_loan_application_unknown_member_raises_not_found(self):
        """A non-existent user_id raises NotFoundError (loan-type guard already passed)."""
        with self.assertRaises(NotFoundError):
            self._create_application(user_id=99999999)

    def test_create_loan_application_disabled_loan_type_raises_validation(self):
        """A loan_type missing from the active LoanTypeConfiguration set raises ValidationError ('disabled')."""
        with self.assertRaises(ValidationError) as ctx:
            self._create_application(loan_type="home")
        self.assertIn("disabled", ctx.exception.message.lower())

    # ------------------------------------------------------------------
    # approve_loan_application — sad paths
    # ------------------------------------------------------------------

    def test_approve_self_created_application_raises_permission_denied(self):
        """The same actor cannot approve their own application (segregation of duties)."""
        app = self._create_application(actor=self.admin)
        with self.assertRaises(PermissionDeniedError):
            loan_service.approve_loan_application(
                application_id=app.id,
                disbursement_date=date.today(),
                actor=self.admin,
            )

    def test_approve_non_pending_application_raises_validation(self):
        """Approving an already-approved application raises ValidationError('Only pending applications can be approved.')."""
        app = self._create_application()
        loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today(),
            actor=self.approver,
        )
        with self.assertRaises(ValidationError) as ctx:
            loan_service.approve_loan_application(
                application_id=app.id,
                disbursement_date=date.today(),
                actor=self.approver,
            )
        self.assertEqual(ctx.exception.message, "Only pending applications can be approved.")

    # ------------------------------------------------------------------
    # record_emi_payment — sad paths
    # ------------------------------------------------------------------

    def test_record_emi_already_paid_raises_validation(self):
        """Paying an already-paid installment raises ValidationError('This installment is already paid.')."""
        _app, loan = self._approved_loan()
        repayment = LoanRepayment.objects.get(loan_account=loan, installment_number=1)
        loan_service.record_emi_payment(
            loan_account_id=loan.id,
            installment_number=1,
            amount_paid=repayment.amount_due,
            actor=self.approver,
        )
        with self.assertRaises(ValidationError) as ctx:
            loan_service.record_emi_payment(
                loan_account_id=loan.id,
                installment_number=1,
                amount_paid=repayment.amount_due,
                actor=self.approver,
            )
        self.assertEqual(ctx.exception.message, "This installment is already paid.")

    def test_record_emi_non_positive_amount_raises_validation(self):
        """amount_paid=0 raises ValidationError('Payment amount must be greater than zero.')."""
        _app, loan = self._approved_loan()
        with self.assertRaises(ValidationError) as ctx:
            loan_service.record_emi_payment(
                loan_account_id=loan.id,
                installment_number=1,
                amount_paid=0,
                actor=self.approver,
            )
        self.assertEqual(ctx.exception.message, "Payment amount must be greater than zero.")

    # ------------------------------------------------------------------
    # has_unpaid_emi
    # ------------------------------------------------------------------

    def test_has_unpaid_emi_true_when_active_unpaid_exists(self):
        """A fresh approved loan with upcoming installments makes has_unpaid_emi return True."""
        self._approved_loan()
        self.assertTrue(loan_service.has_unpaid_emi(self.member))

    def test_has_unpaid_emi_false_when_all_paid(self):
        """Paying every installment leaves no unpaid EMI on any active loan for the member."""
        _app, loan = self._approved_loan()
        for installment_number in range(1, loan.total_emis + 1):
            repayment = LoanRepayment.objects.get(loan_account=loan, installment_number=installment_number)
            loan_service.record_emi_payment(
                loan_account_id=loan.id,
                installment_number=installment_number,
                amount_paid=repayment.amount_due,
                actor=self.approver,
            )
        self.assertFalse(loan_service.has_unpaid_emi(self.member))

    # ------------------------------------------------------------------
    # Phase A1 — disbursement as a real accounting event
    # ------------------------------------------------------------------

    def test_create_loan_application_persists_disbursement_account_and_fee(self):
        """processing_fee + disbursement_account_id flow through create_loan_application.

        LoanApplication carries no columns for either field (verified Phase A1),
        so the service captures the values in the audit description and defers
        the actual posting to approve_loan_application.
        """
        app = self._create_application(
            processing_fee=Decimal("150.00"),
            disbursement_account_id=self.account.id,
        )
        audit = AuditLog.objects.get(action="create", entity_type="loan", entity_id=app.id)
        self.assertIn("processing_fee=", audit.description)
        self.assertIn("150", audit.description)
        self.assertIn(f"disbursement_account_id={self.account.id}", audit.description)

    def test_approve_loan_application_posts_disbursement_credit_transaction(self):
        """Approval with a disbursement_account_id credits the borrower for the full principal."""
        app = self._create_application()
        opening_balance = self.account.balance

        loan = loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today(),
            disbursement_account_id=self.account.id,
            processing_fee=Decimal("250.00"),
            actor=self.approver,
        )

        loan.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(loan.disbursement_account_id, self.account.id)
        self.assertEqual(loan.processing_fee, Decimal("250.00"))

        txn = Transaction.objects.get(
            member_account=self.account,
            transaction_type="credit",
            amount=app.principal_amount,
        )
        self.assertIn(loan.loan_number, (txn.description or ""))
        self.assertEqual(self.account.balance, opening_balance + app.principal_amount)

    def test_approve_loan_application_skips_disbursement_when_no_account(self):
        """No disbursement_account_id ⇒ no Transaction is created on approval."""
        app = self._create_application()
        baseline = Transaction.objects.count()

        loan = loan_service.approve_loan_application(
            application_id=app.id,
            disbursement_date=date.today(),
            actor=self.approver,
        )
        loan.refresh_from_db()

        self.assertIsNone(loan.disbursement_account_id)
        self.assertEqual(Transaction.objects.count(), baseline)

    def test_approve_loan_application_rejects_disbursement_account_of_other_member(self):
        """An account belonging to a different member must be rejected with ValidationError."""
        other_member = User.objects.create_user(
            username="mem2",
            email="mem2@example.com",
            password="Pass1234!",
            first_name="Member",
            last_name="Two",
            is_staff=False,
            role="member",
            member_id="MEM-2025-0002",
        )
        other_account = MemberAccount.objects.create(
            user=other_member,
            account_number="CD000002",
            account_type="cd",
            opening_date=date.today(),
            balance=Decimal("0"),
        )

        app = self._create_application()
        with self.assertRaises(ValidationError) as ctx:
            loan_service.approve_loan_application(
                application_id=app.id,
                disbursement_date=date.today(),
                disbursement_account_id=other_account.id,
                actor=self.approver,
            )
        self.assertEqual(ctx.exception.message, "Disbursement account does not belong to the borrower.")
        self.assertFalse(LoanAccount.objects.filter(application=app).exists())

    def test_calculate_emi_flat_interest_matches_formula(self):
        """interest_type='flat' routes through InterestCalculatorService.calculate_flat_emi.

        For ₹100000 @ 12% p.a. over 12 months: total_interest = 12000,
        total_payable = 112000, EMI = 112000 / 12 = 9333.33 (quantised to paise).
        """
        app = self._create_application(
            principal_amount="100000",
            interest_rate="12",
            tenure_months=12,
            interest_type="flat",
        )
        emi = app.calculate_emi()
        self.assertEqual(emi, Decimal("9333.33"))
        self.assertEqual(
            emi,
            InterestCalculatorService.calculate_flat_emi(Decimal("100000"), Decimal("12"), 12),
        )

    def test_calculate_emi_reducing_unchanged(self):
        """interest_type='reducing' stays on the reducing-balance helper."""
        app = self._create_application(
            principal_amount="100000",
            interest_rate="12",
            tenure_months=12,
            interest_type="reducing",
        )
        expected = InterestCalculatorService.calculate_emi(Decimal("100000"), Decimal("12"), 12)
        self.assertEqual(app.calculate_emi(), expected)
        self.assertEqual(expected, Decimal("8884.88"))
