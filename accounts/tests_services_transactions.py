"""Tests for accounts.services.transactions.

Locks in the externally-observable behaviour of the transaction posting and
voucher staging service so future phases (A2 instruments, B4 fee allocation)
cannot silently regress the public surface:

    post_transaction, post_transactions_bulk, post_voucher,
    next_transaction_number, next_voucher_number, is_credit_transaction_type.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from accounts.models import (
    AuditLog,
    FundAccount,
    FundTransaction,
    Instrument,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    Transaction,
    Voucher,
    VoucherEntry,
)
from accounts.services import transactions as txn_service
from accounts.services.exceptions import NotFoundError, ValidationError

User = get_user_model()


class TransactionServiceTests(TestCase):
    """Behavioural lock-ins for accounts.services.transactions."""

    def setUp(self):
        """Two staff actors, a member, a CD account, and a Welfare fund.

        Tests that need an account balance override it in-place; tests that
        need a loan repayment build it directly via Model.objects.create so
        we don't depend on the loan service here.
        """
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
        self.fund = FundAccount.objects.create(
            name="Welfare",
            fund_type="welfare",
            account_number="FND-2025-0001",
            balance=Decimal("0"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_balance(self, value):
        """Force the test account's balance to `value` without writing a Transaction."""
        MemberAccount.objects.filter(id=self.account.id).update(balance=Decimal(str(value)))
        self.account.refresh_from_db()

    def _make_active_loan_with_upcoming_repayment(self):
        """Build a fresh active LoanAccount with one upcoming installment, directly."""
        app = LoanApplication.objects.create(
            application_number="LA-2025-00001",
            user=self.member,
            loan_type="personal",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            application_date=date.today(),
            status="approved",
            approval_date=date.today(),
            created_by=self.admin,
            approved_by=self.approver,
        )
        loan = LoanAccount.objects.create(
            loan_number="LN-2025-00001",
            application=app,
            user=self.member,
            status="active",
            principal_amount=Decimal("10000"),
            interest_rate=Decimal("10"),
            interest_type="reducing",
            tenure_months=12,
            emi_amount=Decimal("879.16"),
            total_payable=Decimal("10550.00"),
            total_paid=Decimal("0"),
            outstanding_balance=Decimal("10000"),
            overdue_amount=Decimal("0"),
            disbursement_date=date.today(),
            first_emi_date=date.today(),
            total_emis=12,
            emis_paid=0,
            emis_overdue=0,
            created_by=self.admin,
        )
        repayment = LoanRepayment.objects.create(
            loan_account=loan,
            installment_number=1,
            due_date=date.today(),
            amount_due=Decimal("879.16"),
            principal_component=Decimal("795.83"),
            interest_component=Decimal("83.33"),
            payment_status="upcoming",
        )
        return loan, repayment

    # ------------------------------------------------------------------
    # Helper / generator functions
    # ------------------------------------------------------------------

    def test_is_credit_transaction_type_classification(self):
        """The credit/debit classifier matches the service's CREDIT_TYPES tuple."""
        for t in ("credit", "interest", "dividend", "share_capital"):
            self.assertTrue(txn_service.is_credit_transaction_type(t), t)
        for t in ("debit", "transfer"):
            self.assertFalse(txn_service.is_credit_transaction_type(t), t)

    def test_next_transaction_number_returns_format(self):
        """An empty DB yields TXN-YYYY-00001 and a subsequent persisted row bumps the sequence."""
        year = date.today().year
        with transaction.atomic():
            first = txn_service.next_transaction_number()
        self.assertEqual(first, f"TXN-{year}-00001")

        Transaction.objects.create(
            transaction_number=first,
            user=self.member,
            member_account=self.account,
            transaction_type="credit",
            amount=Decimal("1"),
            balance_after=Decimal("1"),
        )

        with transaction.atomic():
            second = txn_service.next_transaction_number()
        self.assertEqual(second, f"TXN-{year}-00002")

    def test_next_voucher_number_returns_format(self):
        """An empty DB yields VCR-YYYY-00001 and a subsequent persisted row bumps the sequence."""
        year = date.today().year
        with transaction.atomic():
            first = txn_service.next_voucher_number()
        self.assertEqual(first, f"VCR-{year}-00001")

        Voucher.objects.create(
            voucher_number=first,
            user=self.member,
            voucher_type="receipt",
            total_amount=Decimal("0"),
        )

        with transaction.atomic():
            second = txn_service.next_voucher_number()
        self.assertEqual(second, f"VCR-{year}-00002")

    # ------------------------------------------------------------------
    # post_transaction
    # ------------------------------------------------------------------

    def test_post_transaction_credit_updates_balance_and_creates_audit(self):
        """A credit posting bumps the balance, stamps last_transaction_date, and writes an audit row."""
        txn = txn_service.post_transaction(
            member_account_id=self.account.id,
            transaction_type="credit",
            amount=Decimal("100"),
            description="Initial deposit",
            actor=self.admin,
        )
        self.assertEqual(txn.amount, Decimal("100"))
        self.assertEqual(txn.transaction_type, "credit")

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("100"))
        self.assertEqual(self.account.last_transaction_date, date.today())

        audit = AuditLog.objects.get(action="create", entity_type="transaction", entity_id=txn.id)
        self.assertTrue(audit.description.startswith("Created transaction "))

    def test_post_transaction_debit_with_insufficient_balance_raises_validation(self):
        """A debit larger than the available balance raises ValidationError with 'Insufficient balance'."""
        self._set_balance("50")
        with self.assertRaises(ValidationError) as ctx:
            txn_service.post_transaction(
                member_account_id=self.account.id,
                transaction_type="debit",
                amount=Decimal("100"),
                actor=self.admin,
            )
        self.assertIn("Insufficient balance", ctx.exception.message)

    def test_post_transaction_invalid_type_raises_validation(self):
        """An unknown transaction_type raises ValidationError."""
        with self.assertRaises(ValidationError):
            txn_service.post_transaction(
                member_account_id=self.account.id,
                transaction_type="bogus",
                amount=Decimal("10"),
                actor=self.admin,
            )

    def test_post_transaction_zero_amount_raises_validation(self):
        """amount=0 raises ValidationError('Amount must be greater than zero.')."""
        with self.assertRaises(ValidationError) as ctx:
            txn_service.post_transaction(
                member_account_id=self.account.id,
                transaction_type="credit",
                amount=Decimal("0"),
                actor=self.admin,
            )
        self.assertEqual(ctx.exception.message, "Amount must be greater than zero.")

    def test_post_transaction_unknown_account_raises_not_found(self):
        """An unknown member_account_id raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            txn_service.post_transaction(
                member_account_id=99999999,
                transaction_type="credit",
                amount=Decimal("10"),
                actor=self.admin,
            )

    def test_post_transaction_with_loan_repayment_id_settles_repayment(self):
        """A credit posting with a loan_repayment_id flips the repayment to paid and refreshes loan totals."""
        loan, repayment = self._make_active_loan_with_upcoming_repayment()

        txn = txn_service.post_transaction(
            member_account_id=self.account.id,
            transaction_type="credit",
            amount=repayment.amount_due,
            loan_repayment_id=repayment.id,
            actor=self.admin,
        )

        repayment.refresh_from_db()
        self.assertEqual(repayment.payment_status, "paid")
        self.assertEqual(repayment.transaction_id, txn.id)

        loan.refresh_from_db()
        self.assertEqual(loan.emis_paid, 1)

    def test_post_transaction_cash_does_not_create_instrument(self):
        """Cash postings leave ``Transaction.instrument`` unset."""
        txn = txn_service.post_transaction(
            member_account_id=self.account.id,
            transaction_type="credit",
            amount=Decimal("10"),
            payment_mode="cash",
            actor=self.admin,
        )
        self.assertIsNone(txn.instrument_id)

    def test_post_transaction_neft_creates_instrument(self):
        """Non-cash mode creates an Instrument linked to the new Transaction."""
        txn = txn_service.post_transaction(
            member_account_id=self.account.id,
            transaction_type="credit",
            amount=Decimal("250"),
            payment_mode="neft",
            reference_number="UTR123456",
            instrument_payload={"reference_number": "UTR123456"},
            actor=self.admin,
        )
        self.assertIsNotNone(txn.instrument_id)
        inst = Instrument.objects.get(id=txn.instrument_id)
        self.assertEqual(inst.instrument_type, "neft")
        self.assertEqual(inst.amount, Decimal("250"))
        self.assertEqual(inst.reference_number, "UTR123456")

    def test_post_transaction_invalid_instrument_ifsc_raises_validation(self):
        """Bad drawer IFSC in instrument_payload raises ValidationError."""
        with self.assertRaises(ValidationError):
            txn_service.post_transaction(
                member_account_id=self.account.id,
                transaction_type="credit",
                amount=Decimal("10"),
                payment_mode="cheque",
                reference_number="CHQ001",
                instrument_payload={"drawer_ifsc": "BADIFSC"},
                actor=self.admin,
            )

    def test_post_transactions_bulk_non_cash_shares_one_instrument(self):
        """Bulk NEFT lines attach the same Instrument whose amount is the line sum."""
        lines = [
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "100"},
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "50"},
        ]
        result = txn_service.post_transactions_bulk(
            user_id=self.member.id,
            lines=lines,
            payment_mode="neft",
            reference_number="UTRBULK1",
            instrument_payload={"reference_number": "UTRBULK1"},
            actor=self.admin,
        )
        txns = result["transactions"]
        self.assertEqual(len(txns), 2)
        i0 = txns[0].instrument_id
        i1 = txns[1].instrument_id
        self.assertIsNotNone(i0)
        self.assertEqual(i0, i1)
        inst = Instrument.objects.get(id=i0)
        self.assertEqual(inst.amount, Decimal("150"))
        self.assertEqual(inst.reference_number, "UTRBULK1")

    # ------------------------------------------------------------------
    # post_transactions_bulk
    # ------------------------------------------------------------------

    def test_post_transactions_bulk_creates_multiple_lines(self):
        """Three credit lines create three Transactions, bump the balance by the sum, and roll up one audit row."""
        lines = [
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "100"},
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "50"},
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "25"},
        ]
        result = txn_service.post_transactions_bulk(
            user_id=self.member.id,
            lines=lines,
            actor=self.admin,
        )
        self.assertEqual(len(result["transactions"]), 3)
        self.assertIsNone(result["fund_transaction"])

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("175"))

        audits = AuditLog.objects.filter(action="create", entity_type="transaction")
        self.assertEqual(audits.count(), 1)

    def test_post_transactions_bulk_empty_lines_raises_validation(self):
        """An empty `lines` list raises ValidationError('At least one account entry is required.')."""
        with self.assertRaises(ValidationError) as ctx:
            txn_service.post_transactions_bulk(
                user_id=self.member.id,
                lines=[],
                actor=self.admin,
            )
        self.assertEqual(ctx.exception.message, "At least one account entry is required.")

    def test_post_transactions_bulk_unknown_user_raises_not_found(self):
        """An unknown user_id raises NotFoundError('Member not found.')."""
        with self.assertRaises(NotFoundError) as ctx:
            txn_service.post_transactions_bulk(
                user_id=99999999,
                lines=[{"account_id": self.account.id, "transaction_type": "credit", "amount": "10"}],
                actor=self.admin,
            )
        self.assertEqual(ctx.exception.message, "Member not found.")

    def test_post_transactions_bulk_with_fund_id_credits_fund(self):
        """Passing fund_id credits the fund with the rolled-up total and writes a FundTransaction(credit)."""
        lines = [
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "100"},
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "200"},
        ]
        result = txn_service.post_transactions_bulk(
            user_id=self.member.id,
            lines=lines,
            fund_id=self.fund.id,
            actor=self.admin,
        )
        self.assertEqual(len(result["transactions"]), 2)
        self.assertIsNotNone(result["fund_transaction"])
        self.assertEqual(result["fund_transaction"].transaction_type, "credit")
        self.assertEqual(result["fund_transaction"].amount, Decimal("300"))

        self.fund.refresh_from_db()
        self.assertEqual(self.fund.balance, Decimal("300"))
        self.assertTrue(FundTransaction.objects.filter(fund=self.fund, transaction_type="credit").exists())

    # ------------------------------------------------------------------
    # post_voucher
    # ------------------------------------------------------------------

    def test_post_voucher_creates_voucher_with_entries(self):
        """Two voucher lines create a Voucher with total=sum and 2 VoucherEntry rows; balances stay UNCHANGED."""
        balance_before = self.account.balance
        lines = [
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "200"},
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "300"},
        ]
        voucher = txn_service.post_voucher(
            user_id=self.member.id,
            voucher_type="receipt",
            lines=lines,
            actor=self.admin,
        )
        self.assertIsInstance(voucher, Voucher)
        self.assertEqual(voucher.total_amount, Decimal("500"))
        self.assertEqual(VoucherEntry.objects.filter(voucher=voucher).count(), 2)
        self.assertRegex(voucher.voucher_number, r"^VCR-\d{4}-\d{5}$")
        self.assertIsNone(voucher.instrument_id)

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, balance_before)

    def test_post_voucher_neft_creates_instrument_on_voucher(self):
        """Staging a non-cash voucher attaches one Instrument (total = line sum)."""
        lines = [{"account_id": self.account.id, "transaction_type": "credit", "amount": "75"}]
        voucher = txn_service.post_voucher(
            user_id=self.member.id,
            voucher_type="receipt",
            lines=lines,
            payment_mode="neft",
            reference_number="VUTR-V-1",
            instrument_payload={"reference_number": "VUTR-V-1"},
            actor=self.admin,
        )
        self.assertIsNotNone(voucher.instrument_id)
        inst = Instrument.objects.get(id=voucher.instrument_id)
        self.assertEqual(inst.instrument_type, "neft")
        self.assertEqual(inst.amount, Decimal("75"))

    def test_post_voucher_invalid_voucher_type_defaults_to_receipt(self):
        """An unknown voucher_type is silently normalised to 'receipt' (mirrors prior view behaviour)."""
        voucher = txn_service.post_voucher(
            user_id=self.member.id,
            voucher_type="bogus",
            lines=[
                {"account_id": self.account.id, "transaction_type": "credit", "amount": "10"},
            ],
            actor=self.admin,
        )
        self.assertEqual(voucher.voucher_type, "receipt")

    def test_post_voucher_empty_lines_raises_validation(self):
        """An empty `lines` list raises ValidationError('At least one voucher entry is required.')."""
        with self.assertRaises(ValidationError) as ctx:
            txn_service.post_voucher(
                user_id=self.member.id,
                voucher_type="receipt",
                lines=[],
                actor=self.admin,
            )
        self.assertEqual(ctx.exception.message, "At least one voucher entry is required.")

    def test_post_voucher_invalid_line_type_raises_validation(self):
        """An unknown line transaction_type raises ValidationError."""
        with self.assertRaises(ValidationError):
            txn_service.post_voucher(
                user_id=self.member.id,
                voucher_type="receipt",
                lines=[
                    {"account_id": self.account.id, "transaction_type": "bogus", "amount": "10"},
                ],
                actor=self.admin,
            )

    def test_post_voucher_non_positive_line_amount_raises_validation(self):
        """amount=0 in a line raises ValidationError('Each voucher line amount must be positive.')."""
        with self.assertRaises(ValidationError) as ctx:
            txn_service.post_voucher(
                user_id=self.member.id,
                voucher_type="receipt",
                lines=[
                    {"account_id": self.account.id, "transaction_type": "credit", "amount": "0"},
                ],
                actor=self.admin,
            )
        self.assertEqual(ctx.exception.message, "Each voucher line amount must be positive.")

    # ------------------------------------------------------------------
    # A4: vouchers are opt-in (cash no longer force-flips to voucher)
    # ------------------------------------------------------------------

    def test_post_transactions_bulk_with_cash_does_not_auto_stage_voucher(self):
        """payment_mode='cash' posts Transactions directly; no Voucher is staged on the side."""
        lines = [
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "100"},
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "50"},
        ]
        result = txn_service.post_transactions_bulk(
            user_id=self.member.id,
            lines=lines,
            payment_mode="cash",
            actor=self.admin,
        )
        self.assertIsInstance(result["transactions"], list)
        self.assertEqual(len(result["transactions"]), 2)
        self.assertFalse(
            Voucher.objects.filter(user=self.member).exists(),
            "post_transactions_bulk(payment_mode='cash') must not stage a Voucher on the side.",
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("150"))

    def test_post_voucher_explicit_voucher_type_works_for_cash(self):
        """When the operator opts in, post_voucher still stages a cash receipt voucher correctly."""
        lines = [
            {"account_id": self.account.id, "transaction_type": "credit", "amount": "250"},
        ]
        voucher = txn_service.post_voucher(
            user_id=self.member.id,
            voucher_type="receipt",
            payment_mode="cash",
            lines=lines,
            actor=self.admin,
        )
        self.assertIsInstance(voucher, Voucher)
        self.assertEqual(voucher.payment_mode, "cash")
        self.assertEqual(voucher.voucher_type, "receipt")
        self.assertEqual(voucher.total_amount, Decimal("250"))
        self.assertEqual(VoucherEntry.objects.filter(voucher=voucher).count(), 1)
        self.assertIsNone(voucher.instrument_id)

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("0"))
