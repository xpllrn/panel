"""
Unified Interest Engine — Phase B1.

Single source of truth for posting interest. Both adapters
(`admin_portal.views.post_interest_view` HTML and
`accounts.api_views.admin_post_interest` REST) delegate here. A future
management command (Phase B2 — ``python manage.py run_interest_engine``)
will call the same functions from cron.

Public surface:

    accrue_deposits(...)     — credit interest to every eligible deposit
                                account since its ``last_interest_calc_date``.
    accrue_loans(...)        — ensure ``InterestReceivable`` rows exist for
                                unpaid EMIs due on or before ``as_of``.
    run_full_engine(...)     — both sides in one atomic block.

Design notes:

* Deposit interest posting goes through
  :func:`accounts.services.transactions.post_transaction` so the balance
  update, transaction-number generation, audit hooks, and (eventually) fund
  allocations live in one place. ``payment_mode="internal"`` keeps these
  rows out of the cash / cheque / NEFT instrument flow (Phase A2).
* The engine is **idempotent for a given as-of date**: every account has
  ``last_interest_calc_date`` advanced to ``as_of`` once interest is posted,
  so a second run on the same day is a no-op.
* ``share`` and ``od`` deposit types are intentionally excluded — share
  capital earns dividend (Phase B9, not interest) and OD is a debit-balance
  product (interest accrues *against* the member, not in their favour).
* Loan-side accrual reuses the existing repayment schedule (each
  ``LoanRepayment`` already carries its ``interest_component`` from the
  EMI calculator); we just materialise an ``InterestReceivable`` row per
  unpaid due date. Reconciliation when an EMI is paid is Phase B3.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from accounts.models import (
    AuditLog,
    InterestPayout,
    InterestReceivable,
    LoanRepayment,
    MemberAccount,
)
from accounts.services import transactions as transaction_service
from accounts.services.interest import InterestCalculatorService

__all__ = [
    "DEPOSIT_ACCOUNT_TYPES_FOR_ACCRUAL",
    "accrue_deposits",
    "accrue_loans",
    "reconcile_emi_to_receivable",
    "run_full_engine",
]

# Deposit account types that earn member-side interest.
# Excludes ``share`` (dividend, Phase B9) and ``od`` (debit-balance product).
DEPOSIT_ACCOUNT_TYPES_FOR_ACCRUAL = ("fd", "cd", "rd", "sukanya", "suputra")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_financial_period(financial_period):
    """Return ``financial_period`` if given, else the active FY (or ``None``)."""
    if financial_period is not None:
        return financial_period
    from accounts.utils import active_financial_period

    return active_financial_period()


def _write_engine_audit(*, actor, action, description):
    """Write a single AuditLog row from the engine. ``entity_type="system"``
    + ``entity_id=None`` is the documented fallback (see Phase A5 notes)."""
    AuditLog.objects.create(
        user=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
        action=action,
        entity_type="system",
        entity_id=None,
        description=description,
    )


# ---------------------------------------------------------------------------
# Deposit side — credit interest to member accounts
# ---------------------------------------------------------------------------


def accrue_deposits(
    *,
    as_of=None,
    financial_period=None,
    actor=None,
    ip_address=None,
    audit_via="engine",
):
    """Post interest credits on every eligible deposit account.

    For each ``MemberAccount`` of type ``fd / cd / rd / sukanya / suputra``
    that is ``status="active"`` with ``interest_rate > 0``:

    1. Compute simple interest for the window
       ``(last_interest_calc_date or opening_date, as_of]``.
    2. If interest > 0:
        - call :func:`post_transaction` with ``transaction_type="interest"``,
          ``payment_mode="internal"`` (balance bumps via F(), gets a
          TXN-YYYY-NNNNN number, audit row created),
        - bump ``accrued_interest`` and advance ``last_interest_calc_date``,
        - create the ``InterestPayout(status="credited")`` snapshot.

    Returns::

        {
            "accounts_updated": int,
            "total_posted": Decimal,
            "payouts": [InterestPayout, ...],
            "period_end": date,
        }
    """
    period_end = as_of or date.today()
    fp = _resolve_financial_period(financial_period)

    accounts = (
        MemberAccount.objects.filter(
            is_deleted=False,
            status="active",
            interest_rate__gt=0,
            account_type__in=DEPOSIT_ACCOUNT_TYPES_FOR_ACCRUAL,
        )
        .select_related("user")
        .order_by("id")
    )

    total_posted = Decimal("0.00")
    payouts = []

    for account in accounts:
        calc_start = account.last_interest_calc_date or account.opening_date
        if calc_start is None or calc_start >= period_end:
            continue
        days = (period_end - calc_start).days
        if days <= 0:
            continue

        interest_amount = InterestCalculatorService.daily_simple_interest(account.balance, account.interest_rate, days)
        if interest_amount <= 0:
            continue

        txn = transaction_service.post_transaction(
            member_account_id=account.id,
            transaction_type="interest",
            amount=interest_amount,
            description=(
                f"Interest credit {calc_start.strftime('%b %d')} - "
                f"{period_end.strftime('%b %d, %Y')} @ {account.interest_rate}%"
            ),
            payment_mode="internal",
            transaction_date=period_end,
            actor=actor,
            ip_address=ip_address,
            audit=False,
            audit_via=audit_via,
        )

        MemberAccount.objects.filter(id=account.id).update(
            accrued_interest=F("accrued_interest") + interest_amount,
            last_interest_calc_date=period_end,
        )

        payout = InterestPayout.objects.create(
            account=account,
            amount=interest_amount,
            period_start=calc_start,
            period_end=period_end,
            transaction=txn,
            financial_period=fp,
            status="credited",
            created_by=actor,
        )
        payouts.append(payout)
        total_posted += interest_amount

    if payouts:
        _write_engine_audit(
            actor=actor,
            action="create",
            description=(
                f"Interest engine ({audit_via}): posted \u20b9{total_posted} to "
                f"{len(payouts)} account(s) for period ending {period_end}."
            ),
        )

    return {
        "accounts_updated": len(payouts),
        "total_posted": total_posted,
        "payouts": payouts,
        "period_end": period_end,
    }


# ---------------------------------------------------------------------------
# Loan side — materialise InterestReceivable rows
# ---------------------------------------------------------------------------


def accrue_loans(
    *,
    as_of=None,
    financial_period=None,
    actor=None,
    audit_via="engine",
):
    """Ensure an ``InterestReceivable`` row exists for every unpaid EMI on an
    active loan whose ``due_date <= as_of``.

    Mirrors the behaviour of the legacy
    :func:`accounts.utils.sync_loan_interest_receivables` helper but lives
    inside the service layer and writes an aggregated audit row. The helper
    in ``utils.py`` will keep working as a thin shim.

    Returns::

        {
            "installments_considered": int,
            "rows_created": int,
            "rows_updated": int,
            "as_of": date,
        }
    """
    period_end = as_of or date.today()
    fp = _resolve_financial_period(financial_period)

    qs = (
        LoanRepayment.objects.filter(
            loan_account__status="active",
            due_date__lte=period_end,
        )
        .exclude(payment_status="paid")
        .select_related("loan_account")
        .order_by("id")
    )

    rows_created = 0
    rows_updated = 0
    considered = 0

    for rep in qs:
        if rep.interest_component is None or rep.interest_component <= 0:
            continue
        considered += 1
        obj, created = InterestReceivable.objects.get_or_create(
            loan_account=rep.loan_account,
            due_date=rep.due_date,
            defaults={
                "financial_period": fp,
                "amount_accrued": rep.interest_component,
                "amount_collected": Decimal("0"),
                "status": "accrued",
            },
        )
        if created:
            rows_created += 1
            continue
        if obj.status == "accrued":
            dirty = False
            if obj.amount_accrued != rep.interest_component:
                obj.amount_accrued = rep.interest_component
                dirty = True
            if fp is not None and obj.financial_period_id != getattr(fp, "id", None):
                obj.financial_period = fp
                dirty = True
            if dirty:
                obj.save(update_fields=["amount_accrued", "financial_period"])
                rows_updated += 1

    if rows_created or rows_updated:
        _write_engine_audit(
            actor=actor,
            action="update",
            description=(
                f"Interest engine ({audit_via}): accrued loan interest — "
                f"{rows_created} new / {rows_updated} updated receivable(s) "
                f"as of {period_end}."
            ),
        )

    return {
        "installments_considered": considered,
        "rows_created": rows_created,
        "rows_updated": rows_updated,
        "as_of": period_end,
    }


# ---------------------------------------------------------------------------
# Full engine — both sides in one atomic block
# ---------------------------------------------------------------------------


def run_full_engine(
    *,
    as_of=None,
    financial_period=None,
    actor=None,
    ip_address=None,
    audit_via="engine",
):
    """Run both ``accrue_deposits`` and ``accrue_loans`` atomically.

    Idempotent for a given ``as_of`` date — running it a second time on the
    same day posts nothing on the deposit side (every eligible account has
    ``last_interest_calc_date == as_of``) and only refreshes loan receivable
    amounts if an EMI's ``interest_component`` was edited in between.
    """
    with transaction.atomic():
        deposits = accrue_deposits(
            as_of=as_of,
            financial_period=financial_period,
            actor=actor,
            ip_address=ip_address,
            audit_via=audit_via,
        )
        loans = accrue_loans(
            as_of=as_of,
            financial_period=financial_period,
            actor=actor,
            audit_via=audit_via,
        )
    return {"deposits": deposits, "loans": loans}


# ---------------------------------------------------------------------------
# EMI ↔ Receivable reconciliation (Phase B3)
# ---------------------------------------------------------------------------


def reconcile_emi_to_receivable(
    repayment,
    *,
    transaction=None,
    financial_period=None,
):
    """Settle the loan-side ``InterestReceivable`` for an EMI that was just paid.

    Engine-aware behaviour:

    * If ``repayment.payment_status != "paid"`` or
      ``interest_component <= 0`` → no-op (returns ``0``).
    * If an ``InterestReceivable`` already exists for
      ``(loan_account, due_date)``:
        - ``status="accrued"`` → flip to ``collected``, set
          ``amount_collected = amount_accrued``, ``collected_date``, and
          link the EMI ``transaction``.
        - ``status="collected"`` → idempotent; only fill in ``transaction``
          if it was not previously linked. Does not bump amounts.
        - ``status="written_off"`` → left untouched (operator decision).
    * If no row exists yet (e.g. the EMI was paid before the daily engine
      run materialised the receivable), create one already in
      ``collected`` state — ``amount_accrued = amount_collected =
      interest_component``, ``collected_date = paid_date``, transaction
      linked. This keeps ``InterestReceivable`` a complete log of every
      loan-side interest amount the society has earned regardless of
      timing.

    Returns ``1`` when a row was created or updated, otherwise ``0``.

    Parameters
    ----------
    repayment : LoanRepayment
        The repayment whose status was just set to ``paid``.
    transaction : Transaction or None
        The EMI's ``Transaction`` row (for the new
        ``InterestReceivable.transaction`` link).
    financial_period : FinancialPeriod or None
        Used as the receivable's ``financial_period`` when a new row is
        created. Defaults to the active FY.
    """
    if repayment is None:
        return 0
    if repayment.payment_status != "paid":
        return 0
    if repayment.interest_component is None or repayment.interest_component <= 0:
        return 0

    fp = _resolve_financial_period(financial_period)
    interest = repayment.interest_component
    paid_date = repayment.paid_date or date.today()

    obj, created = InterestReceivable.objects.get_or_create(
        loan_account_id=repayment.loan_account_id,
        due_date=repayment.due_date,
        defaults={
            "financial_period": fp,
            "amount_accrued": interest,
            "amount_collected": interest,
            "status": "collected",
            "collected_date": paid_date,
            "transaction": transaction,
        },
    )
    if created:
        return 1

    if obj.status == "accrued":
        obj.amount_collected = obj.amount_accrued
        obj.status = "collected"
        obj.collected_date = paid_date
        if transaction is not None:
            obj.transaction = transaction
        obj.save(update_fields=["amount_collected", "status", "collected_date", "transaction"])
        return 1

    if obj.status == "collected" and obj.transaction_id is None and transaction is not None:
        obj.transaction = transaction
        obj.save(update_fields=["transaction"])
        return 1

    return 0
