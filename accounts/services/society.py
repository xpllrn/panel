"""
Society Main Account — Phase B5.

Computes the society's live financial position by aggregating all member
deposits, loan outstanding, interest payable/receivable, fees collected,
and fund balances. Compares the live position against the stored
``SocietyAccount`` snapshot to surface drift.

Public surface:

    compute_live_position(financial_period=None)
        — aggregate live totals from the database.

    get_main_account(financial_period=None)
        — returns {live, snapshot, drift, financial_period}.

Design notes:

* The live position is always computed fresh from the database — it is never
  cached. This is intentional: the society main account is the single source
  of truth for the society's financial health, and stale data is worse than a
  slightly slower query.

* The snapshot is the last persisted ``SocietyAccount`` row for the given FY.
  It is updated by ``persist_financial_snapshots`` (called from the panel
  reports page or the REST ``/api/v1/admin/reports/snapshot/save/`` endpoint).

* Drift is computed field-by-field: ``live_value - snapshot_value``. A positive
  drift means the live position is higher than the snapshot. Zero drift across
  all fields means the snapshot is up-to-date.
"""

from decimal import Decimal

from django.db.models import Sum

from accounts.models import (
    FeeCharge,
    FinancialPeriod,
    FundAccount,
    InterestReceivable,
    LoanAccount,
    MemberAccount,
    SocietyAccount,
)

__all__ = [
    "compute_live_position",
    "get_main_account",
]

ZERO = Decimal("0.00")

# Fields on SocietyAccount that we compute live and compare.
POSITION_FIELDS = [
    "total_member_deposits",
    "total_loan_outstanding",
    "total_interest_payable",
    "total_interest_receivable",
    "total_fees_collected",
    "total_fund_balance",
    "net_surplus",
]


def _q(value):
    """Quantise a value to 2dp Decimal; None → 0.00."""
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def _resolve_financial_period(financial_period):
    """Return the given period or the active one."""
    if financial_period is not None:
        return financial_period
    return FinancialPeriod.objects.filter(is_active=True).first()


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


def compute_live_position(financial_period=None):
    """Aggregate the society's live financial position from the database.

    Returns a dict with the same keys as ``SocietyAccount`` fields:
    ``total_member_deposits``, ``total_loan_outstanding``,
    ``total_interest_payable``, ``total_interest_receivable``,
    ``total_fees_collected``, ``total_fund_balance``, ``net_surplus``.

    All values are 2-dp ``Decimal`` instances.
    """
    fp = _resolve_financial_period(financial_period)

    # --- Deposits: active accounts excluding share and OD ---
    deposit_accounts = MemberAccount.objects.filter(
        is_deleted=False,
        status="active",
    ).exclude(account_type__in=["share", "od"])

    total_member_deposits = _q(deposit_accounts.aggregate(s=Sum("balance"))["s"])

    # --- Interest payable to depositors (accrued but not yet paid out) ---
    total_interest_payable = _q(deposit_accounts.aggregate(s=Sum("accrued_interest"))["s"])

    # --- Loan outstanding ---
    total_loan_outstanding = _q(
        LoanAccount.objects.filter(status="active").aggregate(s=Sum("outstanding_balance"))["s"]
    )

    # --- Interest receivable from loans (accrued minus collected) ---
    ir_rows = InterestReceivable.objects.filter(status="accrued").aggregate(
        accrued=Sum("amount_accrued"),
        collected=Sum("amount_collected"),
    )
    ir_accrued = _q(ir_rows["accrued"])
    ir_collected = _q(ir_rows["collected"])
    total_interest_receivable = _q(ir_accrued - ir_collected)

    # --- Fees collected in the current FY ---
    fee_filter = {"status": "charged"}
    if fp:
        fee_filter["created_at__date__gte"] = fp.start_date
        fee_filter["created_at__date__lte"] = fp.end_date
    total_fees_collected = _q(FeeCharge.objects.filter(**fee_filter).aggregate(s=Sum("amount"))["s"])

    # --- Fund balances ---
    total_fund_balance = _q(FundAccount.objects.filter(is_deleted=False).aggregate(s=Sum("balance"))["s"])

    # --- Net surplus: income - expense (simplified live view) ---
    # Income = interest receivable (accrued) + fees collected
    # Expense = interest payable
    # This is a simplified live approximation; the full P&L uses
    # get_financial_summary which is more detailed but also more expensive.
    net_surplus = _q(total_interest_receivable + total_fees_collected - total_interest_payable)

    return {
        "total_member_deposits": total_member_deposits,
        "total_loan_outstanding": total_loan_outstanding,
        "total_interest_payable": total_interest_payable,
        "total_interest_receivable": total_interest_receivable,
        "total_fees_collected": total_fees_collected,
        "total_fund_balance": total_fund_balance,
        "net_surplus": net_surplus,
    }


def get_main_account(financial_period=None):
    """Return the society's live position, stored snapshot, and drift.

    Returns a dict::

        {
            "financial_period": {id, label, start_date, end_date, status} or None,
            "live": { ...position fields... },
            "snapshot": { ...position fields... } or None,
            "drift": { ...field: live - snapshot... } or None,
            "snapshot_stale": bool,
        }

    ``snapshot`` is ``None`` when no ``SocietyAccount`` row exists for the FY.
    ``drift`` is ``None`` in that case too. ``snapshot_stale`` is ``True`` when
    any drift value is non-zero.
    """
    fp = _resolve_financial_period(financial_period)
    live = compute_live_position(financial_period=fp)

    fp_data = None
    if fp:
        fp_data = {
            "id": fp.id,
            "label": fp.label,
            "start_date": str(fp.start_date),
            "end_date": str(fp.end_date),
            "status": fp.status,
        }

    # Load the stored snapshot.
    snapshot_row = None
    if fp:
        snapshot_row = SocietyAccount.objects.filter(financial_period=fp).first()

    if snapshot_row is None:
        return {
            "financial_period": fp_data,
            "live": live,
            "snapshot": None,
            "drift": None,
            "snapshot_stale": True,
        }

    snapshot = {}
    drift = {}
    any_drift = False
    for field in POSITION_FIELDS:
        snap_val = _q(getattr(snapshot_row, field, ZERO))
        live_val = live[field]
        snapshot[field] = snap_val
        diff = _q(live_val - snap_val)
        drift[field] = diff
        if diff != ZERO:
            any_drift = True

    snapshot["last_updated"] = snapshot_row.last_updated.isoformat() if snapshot_row.last_updated else None

    return {
        "financial_period": fp_data,
        "live": live,
        "snapshot": snapshot,
        "drift": drift,
        "snapshot_stale": any_drift,
    }
