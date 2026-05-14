"""
Surplus distribution service — Phase B9.

Single source of truth for distributing the locked P&L net surplus to
statutory fund accounts according to active ``FundAllocationRule`` rows.

Public surface:

    distribute_surplus(financial_period, *, actor, ip_address, audit_via)
        — validate locked P&L, compute allocations, credit fund accounts.

    compute_allocations(net_surplus, trigger_event="annual_profit")
        — pure computation: returns the list of (rule, amount) pairs without
          side effects. Useful for preview / dry-run.

Design notes:

* This service replaces the inline logic in ``distribute_profit_view`` (panel)
  and ``admin_reports_distribute_profit`` (REST). Both adapters should delegate
  here.

* Idempotent: if ``FundTransaction`` rows with
  ``trigger_event="annual_profit"`` and ``financial_period=fp`` already exist,
  the function returns the existing allocations without posting again.

* The distribution is recorded as ``FundTransaction(type="credit")`` rows —
  one per fund — with ``trigger_event="annual_profit"`` and
  ``allocation_rule`` linked. This is the same mechanism
  ``apply_fund_allocations`` uses today.

* A journal-style ``Voucher`` is NOT created because ``VoucherEntry`` requires
  a ``MemberAccount`` FK which doesn't apply to society-level fund credits.
  The ``FundTransaction`` rows + ``AuditLog`` provide the full audit trail.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F

from accounts.models import (
    AuditLog,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    ProfitAndLoss,
)
from accounts.services.exceptions import NotFoundError, ValidationError

__all__ = [
    "compute_allocations",
    "distribute_surplus",
]

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _write_audit(*, actor, action, entity_type, entity_id, description, ip_address=None):
    """Write an AuditLog row from the surplus service."""
    AuditLog.objects.create(
        user=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )


# ---------------------------------------------------------------------------
# Public: compute allocations (pure, no side effects)
# ---------------------------------------------------------------------------


def compute_allocations(net_surplus, trigger_event="annual_profit"):
    """Compute the allocation amounts for each active rule.

    Returns a list of dicts::

        [
            {"rule": FundAllocationRule, "fund": FundAccount, "amount": Decimal},
            ...
        ]

    Rules with ``min_threshold`` above ``net_surplus`` are skipped.
    Amounts are capped at ``max_cap`` when set.
    Only rules with a positive computed amount are included.
    """
    if net_surplus is None or net_surplus <= 0:
        return []

    rules = (
        FundAllocationRule.objects.filter(trigger_event=trigger_event, is_active=True)
        .select_related("fund")
        .order_by("priority_order", "id")
    )

    allocations = []
    for rule in rules:
        if rule.min_threshold is not None and net_surplus < rule.min_threshold:
            continue

        if rule.allocation_type == "fixed":
            amount = rule.amount or ZERO
        elif rule.allocation_type == "percentage":
            amount = (net_surplus * (rule.percentage or ZERO)) / Decimal("100")
        else:
            continue

        if rule.max_cap is not None and amount > rule.max_cap:
            amount = rule.max_cap

        amount = amount.quantize(Decimal("0.01"))
        if amount <= 0:
            continue

        allocations.append(
            {
                "rule": rule,
                "fund": rule.fund,
                "amount": amount,
            }
        )

    return allocations


# ---------------------------------------------------------------------------
# Public: distribute surplus
# ---------------------------------------------------------------------------


def distribute_surplus(financial_period, *, actor=None, ip_address=None, audit_via="panel"):
    """Distribute the locked P&L net surplus to fund accounts.

    Validates:
        - A ``ProfitAndLoss`` row exists for the period.
        - The P&L is locked (``is_locked=True``).
        - ``net_surplus > 0``.
        - Not already distributed (idempotent).

    Returns a dict::

        {
            "financial_period": FinancialPeriod,
            "net_surplus": Decimal,
            "total_allocated": Decimal,
            "allocations": [FundTransaction, ...],
            "already_distributed": bool,
        }

    Raises:
        NotFoundError   — no P&L snapshot for the period.
        ValidationError — P&L not locked, or net_surplus <= 0.
        ConflictError   — (not raised; idempotent return instead).
    """
    pl = ProfitAndLoss.objects.filter(financial_period=financial_period).first()
    if not pl:
        raise NotFoundError(f"No P&L snapshot for {financial_period.label}. Save a financial snapshot first.")
    if not pl.is_locked:
        raise ValidationError(
            f"P&L is not locked for {financial_period.label}. Close the financial year before distributing."
        )

    net_surplus = pl.net_surplus
    if net_surplus is None or net_surplus <= 0:
        raise ValidationError(
            f"No distributable surplus for {financial_period.label}. Locked net surplus: ₹{net_surplus}."
        )

    # Idempotency: check if already distributed for this period.
    existing = list(
        FundTransaction.objects.filter(
            trigger_event="annual_profit",
            financial_period=financial_period,
        ).select_related("fund")
    )
    if existing:
        total_existing = sum(t.amount for t in existing)
        return {
            "financial_period": financial_period,
            "net_surplus": net_surplus,
            "total_allocated": total_existing,
            "allocations": existing,
            "already_distributed": True,
        }

    # Compute allocations.
    allocation_plan = compute_allocations(net_surplus, trigger_event="annual_profit")
    if not allocation_plan:
        raise ValidationError(
            "No active allocation rules configured for 'Annual Profit'. Add rules in the Allocation Rules page."
        )

    # Execute: credit each fund atomically.
    created_transactions = []
    with transaction.atomic():
        for item in allocation_plan:
            rule = item["rule"]
            fund = item["fund"]
            amount = item["amount"]

            # Lock the fund row.
            locked_fund = FundAccount.objects.select_for_update().get(id=fund.id, is_deleted=False)
            new_balance = locked_fund.balance + amount
            FundAccount.objects.filter(id=locked_fund.id).update(balance=F("balance") + amount)

            fund_txn = FundTransaction.objects.create(
                fund=locked_fund,
                transaction_type="credit",
                amount=amount,
                description=(
                    f"Annual profit distribution for {financial_period.label} (locked P&L net surplus ₹{net_surplus})"
                ),
                payment_mode="internal",
                balance_after=new_balance,
                trigger_event="annual_profit",
                created_by=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
                financial_period=financial_period,
                allocation_rule=rule,
            )
            created_transactions.append(fund_txn)

    # Update P&L fund_allocations_total.
    total_allocated = sum(t.amount for t in created_transactions)
    ProfitAndLoss.objects.filter(id=pl.id).update(fund_allocations_total=total_allocated)

    # Audit.
    via = "via API: " if audit_via == "api" else ""
    _write_audit(
        actor=actor,
        ip_address=ip_address,
        action="create",
        entity_type="fund",
        entity_id=None,
        description=(
            f"Distributed surplus {via}₹{net_surplus} for {financial_period.label}. "
            f"Allocated ₹{total_allocated} across {len(created_transactions)} fund(s)."
        ),
    )

    return {
        "financial_period": financial_period,
        "net_surplus": net_surplus,
        "total_allocated": total_allocated,
        "allocations": created_transactions,
        "already_distributed": False,
    }
