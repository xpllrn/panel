"""
Transaction posting & voucher staging — single source of truth for L4 of the
diagram (Transaction · Voucher · Instrument).

Public surface:

    post_transaction(...)           — single-line credit/debit, balance update,
                                      optional loan-repayment settlement
    post_transactions_bulk(...)     — multi-line direct posting + optional fund credit
    post_voucher(...)               — stage a voucher with N entries (no balance
                                      update yet); optional ``instrument_payload`` for
                                      non-cash ``payment_mode`` (``Voucher.instrument``).
                                      Settlement happens later via voucher transfer / fund flow.
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

Phase A2: when ``payment_mode`` is not ``cash`` and no pre-built ``instrument``
instance is passed, ``instrument_payload`` (optional dict) is merged with
the top-level ``reference_number`` to create an ``Instrument`` row and link
it on the ``Transaction``. ``transaction_date`` remains an optional override.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum

from accounts.models import (
    AuditLog,
    FundAccount,
    FundTransaction,
    Instrument,
    LoanRepayment,
    MemberAccount,
    Transaction,
    User,
    Voucher,
    VoucherEntry,
    ifsc_validator,
)
from accounts.services.exceptions import NotFoundError, ValidationError

CREDIT_TYPES = ("credit", "interest", "dividend", "share_capital")
VOUCHER_TYPES = ("receipt", "payment", "contra", "journal")
MAX_NUMBER_GENERATION_RETRIES = 5


def _instrument_type_for_payment_mode(payment_mode):
    """Map Transaction ``payment_mode`` to a non-cash ``Instrument.instrument_type``.

    Returns ``None`` for modes that never carry a physical / external instrument:
    - ``cash`` (operator-handed cash)
    - ``internal`` (system-generated postings, e.g. interest engine, fund transfers)
    - empty / missing mode
    """
    if not payment_mode or payment_mode in ("cash", "internal"):
        return None
    return {
        "cheque": "cheque",
        "dd": "dd",
        "neft": "neft",
        "rtgs": "rtgs",
        "upi": "upi",
        "imps": "imps",
        "online": "neft",
    }.get(payment_mode, "neft")


def _strip_or_none(val):
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _create_instrument_row(*, payment_mode, amount_decimal, transaction_reference, payload):
    """Persist an ``Instrument`` for a non-cash payment (Phase A2).

    ``payload`` is a flat dict of optional keys: ``instrument_type``, ``cheque_number``,
    ``drawer_name``, ``drawer_bank``, ``drawer_ifsc``, ``cheque_date`` (``YYYY-MM-DD``),
    ``reference_number`` (UTR / instrument ref), ``upi_vpa``, ``cheque_status``, ``is_cleared``.

    ``transaction_reference`` is the top-level receipt reference (often cheque no. or UTR).
    """
    inst_type = _instrument_type_for_payment_mode(payment_mode)
    if inst_type is None:
        return None

    payload = payload or {}
    override = _strip_or_none(payload.get("instrument_type"))
    if override and override != "cash":
        valid = {c[0] for c in Instrument.INSTRUMENT_TYPE_CHOICES}
        if override not in valid:
            raise ValidationError(f"Invalid instrument_type: {override!r}.")
        inst_type = override

    cheque_number = _strip_or_none(payload.get("cheque_number")) or _strip_or_none(transaction_reference)
    drawer_name = _strip_or_none(payload.get("drawer_name"))
    drawer_bank = _strip_or_none(payload.get("drawer_bank"))
    drawer_ifsc = _strip_or_none(payload.get("drawer_ifsc"))
    if drawer_ifsc:
        try:
            ifsc_validator(drawer_ifsc)
        except Exception as exc:
            raise ValidationError("Invalid IFSC on instrument.") from exc

    cheque_date = None
    raw_cd = payload.get("cheque_date")
    if raw_cd is not None:
        from datetime import date as date_cls
        from datetime import datetime

        if isinstance(raw_cd, date_cls):
            cheque_date = raw_cd
        else:
            raw_s = _strip_or_none(str(raw_cd))
            if raw_s:
                try:
                    cheque_date = datetime.strptime(raw_s, "%Y-%m-%d").date()
                except ValueError as exc:
                    raise ValidationError("cheque_date must be YYYY-MM-DD.") from exc

    inst_ref = _strip_or_none(payload.get("reference_number")) or _strip_or_none(transaction_reference)
    upi_vpa = _strip_or_none(payload.get("upi_vpa"))

    cheque_status = _strip_or_none(payload.get("cheque_status")) or "submitted"
    valid_cs = {c[0] for c in Instrument.CHEQUE_STATUS_CHOICES}
    if cheque_status not in valid_cs:
        cheque_status = "submitted"

    is_cleared = bool(payload.get("is_cleared"))

    ref_for_instrument = inst_ref if inst_type in ("neft", "rtgs", "upi", "imps") else None

    return Instrument.objects.create(
        instrument_type=inst_type,
        amount=amount_decimal,
        cheque_number=cheque_number if inst_type in ("cheque", "dd") else None,
        drawer_name=drawer_name,
        drawer_bank=drawer_bank,
        drawer_ifsc=drawer_ifsc,
        cheque_date=cheque_date,
        cheque_status=cheque_status if inst_type in ("cheque", "dd") else None,
        reference_number=ref_for_instrument,
        upi_vpa=upi_vpa if inst_type == "upi" else None,
        is_cleared=is_cleared,
    )


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
    instrument_payload=None,
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

    When ``payment_mode`` is not ``cash`` and ``instrument`` is not provided,
    builds an :class:`~accounts.models.Instrument` from ``instrument_payload``
    (optional dict) plus ``reference_number`` and attaches it to the new
    transaction. Pass a pre-saved ``instrument`` to attach an existing row
    (e.g. one shared ``Instrument`` for a multi-line bulk post).

    Returns the created `Transaction`.

    Raises:
        NotFoundError   — account does not exist / is soft-deleted.
        ValidationError — bad amount, bad type, insufficient balance.

    ``transaction_date`` overrides the posting date on the ``Transaction`` row
    when provided.
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

                resolved_instrument = instrument
                if resolved_instrument is None and payment_mode != "cash":
                    resolved_instrument = _create_instrument_row(
                        payment_mode=payment_mode,
                        amount_decimal=amount_decimal,
                        transaction_reference=(reference_number or "").strip(),
                        payload=instrument_payload or {},
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
                if resolved_instrument is not None:
                    txn_kwargs["instrument"] = resolved_instrument
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
                        f"Created transaction {via}{txn.transaction_number} - {transaction_type} \u20b9{amount_decimal}"
                    ),
                )
            return txn

        except IntegrityError:
            if attempt == MAX_NUMBER_GENERATION_RETRIES - 1:
                raise
            continue


def _settle_loan_repayment(*, repayment_id, user_id, amount, payment_mode, reference_number, txn):
    """Mark a LoanRepayment paid/partial, refresh its parent LoanAccount, and
    (Phase B3) reconcile the matching ``InterestReceivable``.

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

    if repayment.payment_status == "paid":
        from accounts.services import interest_engine

        interest_engine.reconcile_emi_to_receivable(repayment, transaction=txn)

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
    instrument_payload=None,
    actor=None,
    ip_address=None,
    audit_via="panel",
):
    """Direct multi-line posting. One atomic block; each `line` becomes a
    `Transaction` row via `post_transaction`. Optionally credits a fund
    account with the grand total.

    For non-cash ``payment_mode``, one :class:`~accounts.models.Instrument` is
    created for the **sum** of all line amounts and linked to every line's
    ``Transaction`` (single physical instrument paying multiple ledger lines).

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

    work_items = []
    for line in lines:
        if not isinstance(line, dict):
            raise ValidationError("Each entry must be an object.")

        line_type = (line.get("transaction_type") or "").strip()
        if line_type == "loan_emi":
            line_type = "credit"
        if line_type not in dict(Transaction.TRANSACTION_TYPE_CHOICES):
            raise ValidationError("Invalid transaction type in entry.")

        account_id = line.get("account_id")
        try:
            MemberAccount.objects.get(id=account_id, user=user, is_deleted=False)
        except MemberAccount.DoesNotExist as exc:
            raise NotFoundError("Account not found for this member.") from exc

        try:
            line_amount = Decimal(str(line.get("amount", 0)))
        except Exception as exc:
            raise ValidationError("Amount is invalid in entry.") from exc
        if line_amount <= 0:
            raise ValidationError("Each line amount must be greater than zero.")

        work_items.append((line, account_id, line_type, line_amount))

    total_for_instrument = sum(w[3] for w in work_items)

    created = []
    fund_txn = None
    with transaction.atomic():
        shared_instrument = None
        if payment_mode != "cash":
            shared_instrument = _create_instrument_row(
                payment_mode=payment_mode,
                amount_decimal=total_for_instrument,
                transaction_reference=(reference_number or "").strip(),
                payload=instrument_payload or {},
            )

        for line, account_id, line_type, _line_amount in work_items:
            txn = post_transaction(
                member_account_id=account_id,
                transaction_type=line_type,
                amount=line.get("amount", 0),
                description=line.get("description", ""),
                payment_mode=payment_mode,
                reference_number=reference_number,
                remarks=remarks,
                loan_repayment_id=line.get("loan_repayment_id") or None,
                instrument=shared_instrument,
                instrument_payload=None,
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
    instrument_payload=None,
    actor=None,
    ip_address=None,
    audit_via="panel",
):
    """Stage a Voucher + N VoucherEntry rows.

    No balance changes — the voucher is settled later via
    `transfer_voucher_to_fund_view` (panel) or its API equivalent. This is
    the "cheque arrived, awaiting clearing" / "cash collected, awaiting
    deposit" stage.

    When ``payment_mode`` is not ``cash``, creates one :class:`~accounts.models.Instrument`
    for the voucher total (same shape as bulk direct posting) and stores it on
    ``Voucher.instrument`` so transfer can attach it to each posted ``Transaction``.

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

    work_items = []
    total_amount = Decimal("0.00")
    for line in lines:
        if not isinstance(line, dict):
            raise ValidationError("Each voucher entry must be an object.")

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

        work_items.append(
            {
                "account": account,
                "transaction_type": line_type,
                "amount": line_amount,
                "description": (line.get("description") or "").strip() or None,
                "loan_repayment_id": line.get("loan_repayment_id") or None,
            }
        )
        total_amount += line_amount

    with transaction.atomic():
        shared_instrument = None
        if payment_mode != "cash":
            shared_instrument = _create_instrument_row(
                payment_mode=payment_mode,
                amount_decimal=total_amount,
                transaction_reference=(reference_number or "").strip(),
                payload=instrument_payload or {},
            )

        voucher = Voucher.objects.create(
            voucher_number=next_voucher_number(),
            user=user,
            voucher_type=voucher_type,
            total_amount=total_amount,
            payment_mode=payment_mode,
            reference_number=(reference_number or "").strip() or None,
            remarks=(remarks or "").strip() or None,
            created_by=actor,
            instrument=shared_instrument,
        )

        for item in work_items:
            VoucherEntry.objects.create(
                voucher=voucher,
                member_account=item["account"],
                transaction_type=item["transaction_type"],
                amount=item["amount"],
                description=item["description"],
                linked_loan_repayment_id=item["loan_repayment_id"],
            )

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
