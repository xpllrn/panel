"""
Transaction posting & voucher staging — single source of truth for L4 of the
diagram (Transaction · Voucher · Instrument).

Public surface:

    post_transaction(...)           — single-line credit/debit, balance update,
                                      optional loan-repayment settlement
    post_transactions_bulk(...)     — multi-line direct posting + optional fund credit
    post_voucher(...)               — stage a voucher with N entries (no balance
                                      update; settlement happens later via the
                                      voucher transfer / fund flow)
    next_transaction_number()       — atomic TXN-YYYY-NNNNN generator
    next_voucher_number()           — atomic VCR-YYYY-NNNNN generator
    is_credit_transaction_type(t)   — boolean helper

Adapters (`admin_portal.views.add_transaction_view`, `accounts.api_views.admin_transactions_create`)
parse the HTTP request, call into this module, and format the response.

Side effects that this module DOES manage:
- balance update via F() expression
- transaction number generation
- loan-repayment status flip + LoanAccount aggregate refresh

Side effects this module DOES NOT manage (intentional — adapter concerns):
- push / email notifications  (`dispatch_user_notification`)
- automated fund allocations on `interest`-type transactions
  (`apply_fund_allocations` — still tied to `request`; will move when
  Phase B4 overhauls fees / allocations)

Phase A2 (Instrument wiring) will land inside this module — the
`instrument` kwarg is already accepted by `post_transaction` and threaded
through to `Transaction.instrument`; today it is always `None` because no
adapter passes it yet. The same is true for `transaction_date` which will
flip from `auto_now_add` to a caller-supplied value.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum

from accounts.models import (
    AuditLog,
    FundAccount,
    FundTransaction,
    LoanRepayment,
    MemberAccount,
    Transaction,
    User,
    Voucher,
    VoucherEntry,
)
from accounts.services.exceptions import NotFoundError, ValidationError

CREDIT_TYPES = ("credit", "interest", "dividend", "share_capital")
VOUCHER_TYPES = ("receipt", "payment", "contra", "journal")
MAX_NUMBER_GENERATION_RETRIES = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_credit_transaction_type(transaction_type):
    """True if the transaction increases the member-account balance."""
    return transaction_type in CREDIT_TYPES


def next_transaction_number(*, today=None):
    """Atomic TXN-YYYY-NNNNN generator.

    Caller MUST be inside a `transaction.atomic()` block that retries on
    `IntegrityError`.
    """
    today = today or date.today()
    year = today.year
    last_txn = (
        Transaction.objects.select_for_update()
        .filter(transaction_number__startswith=f"TXN-{year}-")
        .order_by("-transaction_number")
        .first()
    )
    if not last_txn:
        return f"TXN-{year}-00001"
    try:
        seq = int(last_txn.transaction_number.split("-")[-1]) + 1
    except (ValueError, IndexError):
        seq = 1
    return f"TXN-{year}-{seq:05d}"


def next_voucher_number(*, today=None):
    """Atomic VCR-YYYY-NNNNN generator. Same atomic-block requirement as
    `next_transaction_number`."""
    today = today or date.today()
    year = today.year
    last_voucher = (
        Voucher.objects.select_for_update()
        .filter(voucher_number__startswith=f"VCR-{year}-")
        .order_by("-voucher_number")
        .first()
    )
    if not last_voucher:
        return f"VCR-{year}-00001"
    try:
        seq = int(last_voucher.voucher_number.split("-")[-1]) + 1
    except (ValueError, IndexError):
        seq = 1
    return f"VCR-{year}-{seq:05d}"


def _write_audit(*, actor, action, entity_type, entity_id, description, ip_address=None):
    """AuditLog row from a service — no `request` coupling."""
    AuditLog.objects.create(
        user=actor if (actor is not None and actor.is_authenticated) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )


# ---------------------------------------------------------------------------
# Core: single-line posting
# ---------------------------------------------------------------------------


def post_transaction(
    *,
    member_account_id,
    transaction_type,
    amount,
    description="",
    payment_mode="cash",
    reference_number="",
    remarks="",
    loan_repayment_id=None,
    instrument=None,
    transaction_date=None,
    actor=None,
    ip_address=None,
    audit=True,
    audit_via="panel",
):
    """Post a single transaction line to a member account.

    Locks the account row, validates the type and (for debits) the balance,
    updates the balance using an F() expression, generates a TXN-YYYY-NNNNN
    number atomically, creates the `Transaction`, and — if
    `loan_repayment_id` is given — settles that repayment and refreshes the
    parent LoanAccount aggregates.

    Returns the created `Transaction`.

    Raises:
        NotFoundError   — account does not exist / is soft-deleted.
        ValidationError — bad amount, bad type, insufficient balance.

    Note: `instrument` and `transaction_date` are accepted but currently
    threaded through unchanged. Phase A2 will populate them from adapters.
    """
    if transaction_type not in dict(Transaction.TRANSACTION_TYPE_CHOICES):
        raise ValidationError(f"Invalid transaction type: {transaction_type!r}.")

    try:
        amount_decimal = Decimal(str(amount))
    except Exception as exc:
        raise ValidationError("Amount is invalid.") from exc
    if amount_decimal <= 0:
        raise ValidationError("Amount must be greater than zero.")

    for attempt in range(MAX_NUMBER_GENERATION_RETRIES):
        try:
            with transaction.atomic():
                try:
                    account = MemberAccount.objects.select_for_update().get(id=member_account_id, is_deleted=False)
                except MemberAccount.DoesNotExist as exc:
                    raise NotFoundError("Account not found.") from exc

                if is_credit_transaction_type(transaction_type):
                    new_balance = account.balance + amount_decimal
                    MemberAccount.objects.filter(id=account.id).update(
                        balance=F("balance") + amount_decimal,
                        last_transaction_date=date.today(),
                    )
                else:
                    if amount_decimal > account.balance:
                        raise ValidationError(
                            f"Insufficient balance for {account.account_number}. "
                            f"Available \u20b9{account.balance}, requested \u20b9{amount_decimal}."
                        )
                    new_balance = account.balance - amount_decimal
                    MemberAccount.objects.filter(id=account.id).update(
                        balance=F("balance") - amount_decimal,
                        last_transaction_date=date.today(),
                    )

                txn_kwargs = dict(
                    transaction_number=next_transaction_number(),
                    user=account.user,
                    member_account=account,
                    transaction_type=transaction_type,
                    amount=amount_decimal,
                    description=(description or "").strip() or None,
                    payment_mode=payment_mode,
                    reference_number=(reference_number or "").strip() or None,
                    balance_after=new_balance,
                    created_by=actor,
                    remarks=(remarks or "").strip() or None,
                )
                if instrument is not None:
                    txn_kwargs["instrument"] = instrument
                if transaction_date is not None:
                    txn_kwargs["transaction_date"] = transaction_date

                txn = Transaction.objects.create(**txn_kwargs)

                if loan_repayment_id:
                    _settle_loan_repayment(
                        repayment_id=loan_repayment_id,
                        user_id=account.user_id,
                        amount=amount_decimal,
                        payment_mode=payment_mode,
                        reference_number=reference_number,
                        txn=txn,
                    )

            if audit:
                via = "via API: " if audit_via == "api" else ""
                _write_audit(
                    actor=actor,
                    ip_address=ip_address,
                    action="create",
                    entity_type="transaction",
                    entity_id=txn.id,
                    description=(
                        f"Created transaction {via}{txn.transaction_number} - {transaction_type} "
                        f"\u20b9{amount_decimal}"
                    ),
                )
            return txn

        except IntegrityError:
            if attempt == MAX_NUMBER_GENERATION_RETRIES - 1:
                raise
            continue


def _settle_loan_repayment(*, repayment_id, user_id, amount, payment_mode, reference_number, txn):
    """Mark a LoanRepayment paid/partial and refresh its parent LoanAccount.

    Silent no-op if the repayment doesn't exist or isn't on an active loan
    of the same user — preserves the previous adapter behaviour.
    """
    try:
        repayment = LoanRepayment.objects.select_for_update().get(
            id=repayment_id,
            loan_account__user_id=user_id,
            loan_account__status="active",
        )
    except LoanRepayment.DoesNotExist:
        return

    repayment.paid_date = date.today()
    repayment.amount_paid = amount
    repayment.payment_mode = payment_mode
    repayment.reference_number = (reference_number or "").strip() or None
    repayment.payment_status = "paid" if amount >= repayment.amount_due else "partial"
    repayment.transaction = txn
    repayment.save()

    loan = repayment.loan_account
    loan.total_paid = LoanRepayment.objects.filter(loan_account=loan, payment_status="paid").aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")
    loan.emis_paid = LoanRepayment.objects.filter(loan_account=loan, payment_status="paid").count()
    loan.emis_overdue = LoanRepayment.objects.filter(loan_account=loan, payment_status="overdue").count()
    loan.overdue_amount = LoanRepayment.objects.filter(loan_account=loan, payment_status="overdue").aggregate(
        total=Sum("amount_due")
    )["total"] or Decimal("0.00")
    if not LoanRepayment.objects.filter(loan_account=loan).exclude(payment_status="paid").exists():
        loan.status = "closed"
        loan.closure_date = date.today()
        loan.outstanding_balance = Decimal("0.00")
    loan.save()


# ---------------------------------------------------------------------------
# Multi-line direct posting (panel "add transaction" without voucher path)
# ---------------------------------------------------------------------------


def post_transactions_bulk(
    *,
    user_id,
    lines,
    payment_mode="cash",
    reference_number="",
    remarks="",
    fund_id=None,
    actor=None,
    ip_address=None,
    audit_via="panel",
):
    """Direct multi-line posting. One atomic block; each `line` becomes a
    `Transaction` row via `post_transaction`. Optionally credits a fund
    account with the grand total.

    `lines` is a list of dicts shaped like::

        {
            "account_id":         42,
            "transaction_type":   "credit"|"debit"|"interest"|...,
            "amount":             "1250.00",
            "description":        "Monthly RD deposit",   # optional
            "loan_repayment_id":  17,                     # optional
        }

    Returns: ``{"transactions": [Transaction, ...], "fund_transaction": FundTransaction or None}``.

    Raises:
        NotFoundError   — user / account / fund missing.
        ValidationError — empty list, bad type, bad amount, insufficient balance.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Member not found.") from exc

    if not isinstance(lines, list) or not lines:
        raise ValidationError("At least one account entry is required.")

    created = []
    fund_txn = None
    with transaction.atomic():
        for line in lines:
            line_type = (line.get("transaction_type") or "").strip()
            if line_type == "loan_emi":
                line_type = "credit"
            if line_type not in dict(Transaction.TRANSACTION_TYPE_CHOICES):
                raise ValidationError("Invalid transaction type in entry.")

            # Verify the account belongs to the named user before delegating
            # to post_transaction, which only enforces is_deleted=False.
            account_id = line.get("account_id")
            try:
                MemberAccount.objects.get(id=account_id, user=user, is_deleted=False)
            except MemberAccount.DoesNotExist as exc:
                raise NotFoundError("Account not found for this member.") from exc

            txn = post_transaction(
                member_account_id=account_id,
                transaction_type=line_type,
                amount=line.get("amount", 0),
                description=line.get("description", ""),
                payment_mode=payment_mode,
                reference_number=reference_number,
                remarks=remarks,
                loan_repayment_id=line.get("loan_repayment_id") or None,
                actor=actor,
                ip_address=ip_address,
                audit=False,  # rolled up below
            )
            created.append(txn)

        if fund_id:
            try:
                fund = FundAccount.objects.select_for_update().get(id=fund_id, is_deleted=False, is_active=True)
            except FundAccount.DoesNotExist as exc:
                raise NotFoundError("Fund not found.") from exc

            total_amount = sum((t.amount for t in created), Decimal("0.00"))
            FundAccount.objects.filter(id=fund.id).update(balance=F("balance") + total_amount)
            fund.refresh_from_db(fields=["balance"])
            fund_txn = FundTransaction.objects.create(
                fund=fund,
                transaction_type="credit",
                amount=total_amount,
                description=f"Transaction settlement from {user.display_name}",
                payment_mode="internal",
                reference_number=(reference_number or "").strip() or None,
                balance_after=fund.balance,
                source_member=user,
                created_by=actor,
            )

    via = "via API: " if audit_via == "api" else ""
    _write_audit(
        actor=actor,
        ip_address=ip_address,
        action="create",
        entity_type="transaction",
        entity_id=created[-1].id if created else None,
        description=f"Created {len(created)} transaction line(s) {via}for {user.display_name}",
    )
    return {"transactions": created, "fund_transaction": fund_txn}


# ---------------------------------------------------------------------------
# Voucher staging
# ---------------------------------------------------------------------------


def post_voucher(
    *,
    user_id,
    voucher_type,
    lines,
    payment_mode="cash",
    reference_number="",
    remarks="",
    actor=None,
    ip_address=None,
    audit_via="panel",
):
    """Stage a Voucher + N VoucherEntry rows.

    No balance changes — the voucher is settled later via
    `transfer_voucher_to_fund_view` (panel) or its API equivalent. This is
    the "cheque arrived, awaiting clearing" / "cash collected, awaiting
    deposit" stage.

    `voucher_type` MUST be one of "receipt", "payment", "contra", "journal".

    Returns the created `Voucher`.

    Raises:
        ValidationError — bad voucher type, empty lines, bad line type/amount.
        NotFoundError   — user or any line's account missing.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Member not found.") from exc

    if voucher_type not in VOUCHER_TYPES:
        voucher_type = "receipt"
    if not isinstance(lines, list) or not lines:
        raise ValidationError("At least one voucher entry is required.")

    with transaction.atomic():
        voucher = Voucher.objects.create(
            voucher_number=next_voucher_number(),
            user=user,
            voucher_type=voucher_type,
            total_amount=Decimal("0.00"),
            payment_mode=payment_mode,
            reference_number=(reference_number or "").strip() or None,
            remarks=(remarks or "").strip() or None,
            created_by=actor,
        )

        total_amount = Decimal("0.00")
        for line in lines:
            line_type = (line.get("transaction_type") or "").strip()
            if line_type == "loan_emi":
                line_type = "credit"
            if line_type not in dict(Transaction.TRANSACTION_TYPE_CHOICES):
                raise ValidationError(f"Invalid transaction type: {line_type!r}.")

            try:
                account = MemberAccount.objects.get(id=line.get("account_id"), user=user, is_deleted=False)
            except MemberAccount.DoesNotExist as exc:
                raise NotFoundError("Account not found for this member.") from exc

            try:
                line_amount = Decimal(str(line.get("amount", 0)))
            except Exception as exc:
                raise ValidationError("Voucher line amount is invalid.") from exc
            if line_amount <= 0:
                raise ValidationError("Each voucher line amount must be positive.")

            VoucherEntry.objects.create(
                voucher=voucher,
                member_account=account,
                transaction_type=line_type,
                amount=line_amount,
                description=(line.get("description") or "").strip() or None,
                linked_loan_repayment_id=line.get("loan_repayment_id") or None,
            )
            total_amount += line_amount

        voucher.total_amount = total_amount
        voucher.save(update_fields=["total_amount"])

    via = "via API: " if audit_via == "api" else ""
    _write_audit(
        actor=actor,
        ip_address=ip_address,
        action="create",
        entity_type="voucher",
        entity_id=voucher.id,
        description=(
            f"Created voucher {via}{voucher.voucher_number} with {voucher.entries.count()} line(s) "
            f"for {user.display_name}"
        ),
    )
    return voucher
