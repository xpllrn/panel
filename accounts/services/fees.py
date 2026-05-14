"""
Fee automation service — Phase B4.

Single source of truth for posting fees. Adapters (panel views, REST API,
management commands, future MCP tools) delegate here.

Public surface:

    resolve_active_fee_schedule(fee_type, applies_to, as_of=None)
        — find the most recent active FeeSchedule for a given type/target.

    compute_fee_amount(schedule, base=None)
        — resolve the fee amount from a schedule (flat or percentage).

    apply_processing_fee(loan_account, *, actor, ip_address, audit_via)
        — post a processing-fee FeeCharge + debit Transaction on loan approval.

    apply_membership_fee(user, *, member_account, actor, ip_address, audit_via, financial_period)
        — post a membership fee once per user per FY.

    apply_late_payment_fees(*, as_of, grace_days, financial_period, actor, ip_address, audit_via)
        — daily sweep: one late_payment FeeCharge per overdue EMI past grace.

    apply_annual_maintenance_fees(*, financial_period, actor, ip_address, audit_via)
        — yearly sweep: one annual_maintenance FeeCharge per active member per FY.

Design notes:

* Every fee-posting function is **idempotent** — safe to re-run from cron.
  Idempotency keys:
  - processing: one per LoanAccount (checked via loan_account FK + fee_type).
  - late_payment: one per LoanRepayment (checked via loan_repayment FK).
  - membership: one per (user, fee_type, financial_period).
  - annual_maintenance: one per (user, fee_type, financial_period).

* Fee posting goes through `services.transactions.post_transaction` so the
  balance update, TXN number, and audit hooks are centralised.

* When no active FeeSchedule exists for a fee_type, the function is a no-op
  (returns None). This lets operators disable fees by deactivating schedules.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from accounts.models import (
    AuditLog,
    FeeCharge,
    FeeSchedule,
    FinancialPeriod,
    LoanRepayment,
    MemberAccount,
    SocietyConfiguration,
    User,
)
from accounts.services import transactions as transaction_service

__all__ = [
    "apply_annual_maintenance_fees",
    "apply_late_payment_fees",
    "apply_membership_fee",
    "apply_processing_fee",
    "compute_fee_amount",
    "resolve_active_fee_schedule",
]

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_financial_period(financial_period):
    """Return ``financial_period`` if given, else the active FY (or ``None``)."""
    if financial_period is not None:
        return financial_period
    return FinancialPeriod.objects.filter(is_active=True).first()


def _write_fee_audit(*, actor, action, entity_type, entity_id, description, ip_address=None):
    """Write an AuditLog row from the fee service."""
    AuditLog.objects.create(
        user=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )


def _write_sweep_audit(*, actor, action, description):
    """Write a single summary AuditLog row for a batch sweep (late fees / annual)."""
    AuditLog.objects.create(
        user=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
        action=action,
        entity_type="fee",
        entity_id=None,
        description=description,
    )


def _get_grace_days():
    """Read the operator-configured grace days from SocietyConfiguration."""
    val = SocietyConfiguration.objects.order_by("id").values_list("late_fee_grace_days", flat=True).first()
    return val if val is not None else 0


# ---------------------------------------------------------------------------
# Public: schedule resolution
# ---------------------------------------------------------------------------


def resolve_active_fee_schedule(fee_type, applies_to, as_of=None):
    """Return the most recent active FeeSchedule for (fee_type, applies_to)
    whose effective_date <= as_of. Returns None if nothing matches.
    """
    if as_of is None:
        as_of = date.today()
    return (
        FeeSchedule.objects.filter(
            fee_type=fee_type,
            applies_to=applies_to,
            is_active=True,
            effective_date__lte=as_of,
        )
        .order_by("-effective_date")
        .first()
    )


def compute_fee_amount(schedule, base=None):
    """Resolve the fee amount from a FeeSchedule.

    If ``schedule.amount`` is set, use it (flat fee).
    Otherwise compute ``schedule.percentage * base / 100``.
    Returns Decimal quantised to 2dp, or ZERO if unresolvable.
    """
    if schedule is None:
        return ZERO
    if schedule.amount is not None and schedule.amount > 0:
        return Decimal(schedule.amount).quantize(Decimal("0.01"))
    if schedule.percentage is not None and schedule.percentage > 0 and base is not None:
        return (Decimal(schedule.percentage) * Decimal(str(base)) / Decimal("100")).quantize(Decimal("0.01"))
    return ZERO


# ---------------------------------------------------------------------------
# Public: processing fee on loan approval
# ---------------------------------------------------------------------------


def apply_processing_fee(loan_account, *, actor=None, ip_address=None, audit_via="panel"):
    """Post a processing-fee FeeCharge + debit Transaction for a newly approved loan.

    Idempotent: skips if a FeeCharge(fee_type="processing") already exists for
    this LoanAccount.

    Returns the created FeeCharge, or None if no fee was posted (no schedule,
    zero amount, or already exists).
    """
    # Already charged?
    if FeeCharge.objects.filter(
        loan_account=loan_account,
        fee_schedule__fee_type="processing",
    ).exists():
        return None

    schedule = resolve_active_fee_schedule("processing", "loan", as_of=loan_account.disbursement_date)
    if schedule is None:
        return None

    # Compute amount: use the explicit processing_fee on the LoanAccount if
    # the operator typed one in, otherwise fall back to the schedule.
    if loan_account.processing_fee and loan_account.processing_fee > 0:
        amount = Decimal(loan_account.processing_fee).quantize(Decimal("0.01"))
    else:
        amount = compute_fee_amount(schedule, base=loan_account.principal_amount)

    if amount <= 0:
        return None

    # Find the account to debit (disbursement account or first active account).
    debit_account = loan_account.disbursement_account
    if not debit_account:
        debit_account = (
            MemberAccount.objects.filter(user=loan_account.user, status="active", is_deleted=False)
            .order_by("id")
            .first()
        )
    if not debit_account:
        # Cannot post a debit without an account — store as pending.
        charge = FeeCharge.objects.create(
            fee_schedule=schedule,
            user=loan_account.user,
            loan_account=loan_account,
            amount=amount,
            status="pending",
        )
        return charge

    with transaction.atomic():
        txn = transaction_service.post_transaction(
            member_account_id=debit_account.id,
            transaction_type="debit",
            amount=amount,
            description=f"Processing fee: {loan_account.loan_number}",
            payment_mode="internal",
            actor=actor,
            ip_address=ip_address,
            audit=False,
            audit_via=audit_via,
        )
        charge = FeeCharge.objects.create(
            fee_schedule=schedule,
            user=loan_account.user,
            loan_account=loan_account,
            member_account=debit_account,
            amount=amount,
            status="charged",
            transaction=txn,
        )

    via = "via API: " if audit_via == "api" else ""
    _write_fee_audit(
        actor=actor,
        ip_address=ip_address,
        action="create",
        entity_type="fee",
        entity_id=charge.id,
        description=(
            f"Processing fee {via}₹{amount} charged on loan "
            f"{loan_account.loan_number} ({loan_account.user.display_name})"
        ),
    )
    return charge


# ---------------------------------------------------------------------------
# Public: membership fee on first account opening
# ---------------------------------------------------------------------------


def apply_membership_fee(
    user, *, member_account=None, actor=None, ip_address=None, audit_via="panel", financial_period=None
):
    """Post a membership fee once per user per FY.

    Idempotent: skips if a FeeCharge(fee_type="membership", user, financial_period)
    already exists.

    Returns the created FeeCharge, or None if no fee was posted.
    """
    fp = _resolve_financial_period(financial_period)

    # Already charged for this FY?
    qs = FeeCharge.objects.filter(
        user=user,
        fee_schedule__fee_type="membership",
    )
    if fp:
        qs = qs.filter(financial_period=fp)
    if qs.exists():
        return None

    schedule = resolve_active_fee_schedule("membership", "membership")
    if schedule is None:
        return None

    amount = compute_fee_amount(schedule)
    if amount <= 0:
        return None

    # Find an account to debit.
    debit_account = member_account
    if not debit_account:
        debit_account = (
            MemberAccount.objects.filter(user=user, status="active", is_deleted=False).order_by("id").first()
        )
    if not debit_account:
        charge = FeeCharge.objects.create(
            fee_schedule=schedule,
            user=user,
            member_account=None,
            amount=amount,
            status="pending",
            financial_period=fp,
        )
        return charge

    with transaction.atomic():
        txn = transaction_service.post_transaction(
            member_account_id=debit_account.id,
            transaction_type="debit",
            amount=amount,
            description=f"Membership fee: {user.display_name}",
            payment_mode="internal",
            actor=actor,
            ip_address=ip_address,
            audit=False,
            audit_via=audit_via,
        )
        charge = FeeCharge.objects.create(
            fee_schedule=schedule,
            user=user,
            member_account=debit_account,
            amount=amount,
            status="charged",
            transaction=txn,
            financial_period=fp,
        )

    via = "via API: " if audit_via == "api" else ""
    _write_fee_audit(
        actor=actor,
        ip_address=ip_address,
        action="create",
        entity_type="fee",
        entity_id=charge.id,
        description=f"Membership fee {via}₹{amount} charged for {user.display_name}",
    )
    return charge


# ---------------------------------------------------------------------------
# Public: late-payment fee sweep (daily cron)
# ---------------------------------------------------------------------------


def apply_late_payment_fees(
    *, as_of=None, grace_days=None, financial_period=None, actor=None, ip_address=None, audit_via="cron"
):
    """Sweep all overdue EMIs past grace and post a late_payment FeeCharge for each.

    Idempotent: uses FeeCharge.loan_repayment FK to skip EMIs already charged.

    Returns a dict: {charges_created, charges_skipped, as_of}.
    """
    if as_of is None:
        as_of = date.today()
    if grace_days is None:
        grace_days = _get_grace_days()

    fp = _resolve_financial_period(financial_period)
    schedule = resolve_active_fee_schedule("late_payment", "loan", as_of=as_of)
    if schedule is None:
        return {"charges_created": 0, "charges_skipped": 0, "as_of": as_of}

    # Cutoff: EMIs due before this date are eligible for a late fee.
    cutoff_date = as_of - timedelta(days=grace_days)

    # Find overdue EMIs that don't already have a late_payment FeeCharge.
    overdue_emis = (
        LoanRepayment.objects.filter(
            payment_status="overdue",
            due_date__lt=cutoff_date,
            loan_account__status="active",
        )
        .exclude(
            fee_charges__fee_schedule__fee_type="late_payment",
        )
        .select_related("loan_account", "loan_account__user", "loan_account__disbursement_account")
    )

    charges_created = 0
    charges_skipped = 0

    for emi in overdue_emis:
        loan_ac = emi.loan_account
        amount = compute_fee_amount(schedule, base=emi.amount_due)
        if amount <= 0:
            charges_skipped += 1
            continue

        # Find account to debit.
        debit_account = loan_ac.disbursement_account
        if not debit_account or debit_account.status != "active" or debit_account.is_deleted:
            debit_account = (
                MemberAccount.objects.filter(user=loan_ac.user, status="active", is_deleted=False)
                .order_by("id")
                .first()
            )

        if not debit_account:
            # Store as pending — no account to debit.
            FeeCharge.objects.create(
                fee_schedule=schedule,
                user=loan_ac.user,
                loan_account=loan_ac,
                loan_repayment=emi,
                amount=amount,
                status="pending",
                financial_period=fp,
            )
            charges_created += 1
            continue

        with transaction.atomic():
            txn = transaction_service.post_transaction(
                member_account_id=debit_account.id,
                transaction_type="debit",
                amount=amount,
                description=f"Late payment fee: {loan_ac.loan_number} EMI #{emi.installment_number}",
                payment_mode="internal",
                actor=actor,
                ip_address=ip_address,
                audit=False,
                audit_via=audit_via,
            )
            FeeCharge.objects.create(
                fee_schedule=schedule,
                user=loan_ac.user,
                loan_account=loan_ac,
                loan_repayment=emi,
                member_account=debit_account,
                amount=amount,
                status="charged",
                transaction=txn,
                financial_period=fp,
            )
        charges_created += 1

    if charges_created > 0:
        _write_sweep_audit(
            actor=actor,
            action="create",
            description=(
                f"Fee engine ({audit_via}): posted {charges_created} late_payment fee(s) "
                f"as of {as_of} (grace={grace_days}d)."
            ),
        )

    return {"charges_created": charges_created, "charges_skipped": charges_skipped, "as_of": as_of}


# ---------------------------------------------------------------------------
# Public: annual maintenance fee sweep (yearly / FY-open)
# ---------------------------------------------------------------------------


def apply_annual_maintenance_fees(*, financial_period=None, actor=None, ip_address=None, audit_via="cron"):
    """Post an annual_maintenance FeeCharge for every active member in the FY.

    Idempotent: uses (user, fee_type, financial_period) to skip already-charged members.

    Returns a dict: {charges_created, charges_skipped}.
    """
    fp = _resolve_financial_period(financial_period)
    if fp is None:
        return {"charges_created": 0, "charges_skipped": 0}

    schedule = resolve_active_fee_schedule("annual_maintenance", "membership", as_of=fp.start_date)
    if schedule is None:
        return {"charges_created": 0, "charges_skipped": 0}

    amount = compute_fee_amount(schedule)
    if amount <= 0:
        return {"charges_created": 0, "charges_skipped": 0}

    # All active members (role=member, not soft-deleted).
    members = User.objects.filter(role="member", is_active=True)

    # Members already charged for this FY.
    already_charged_user_ids = set(
        FeeCharge.objects.filter(
            fee_schedule__fee_type="annual_maintenance",
            financial_period=fp,
        ).values_list("user_id", flat=True)
    )

    charges_created = 0
    charges_skipped = 0

    for member in members.iterator():
        if member.id in already_charged_user_ids:
            charges_skipped += 1
            continue

        debit_account = (
            MemberAccount.objects.filter(user=member, status="active", is_deleted=False).order_by("id").first()
        )

        if not debit_account:
            FeeCharge.objects.create(
                fee_schedule=schedule,
                user=member,
                amount=amount,
                status="pending",
                financial_period=fp,
            )
            charges_created += 1
            continue

        with transaction.atomic():
            txn = transaction_service.post_transaction(
                member_account_id=debit_account.id,
                transaction_type="debit",
                amount=amount,
                description=f"Annual maintenance fee: FY {fp.label}",
                payment_mode="internal",
                actor=actor,
                ip_address=ip_address,
                audit=False,
                audit_via=audit_via,
            )
            FeeCharge.objects.create(
                fee_schedule=schedule,
                user=member,
                member_account=debit_account,
                amount=amount,
                status="charged",
                transaction=txn,
                financial_period=fp,
            )
        charges_created += 1

    if charges_created > 0:
        _write_sweep_audit(
            actor=actor,
            action="create",
            description=(
                f"Fee engine ({audit_via}): posted {charges_created} annual_maintenance fee(s) for {fp.label}."
            ),
        )

    return {"charges_created": charges_created, "charges_skipped": charges_skipped}
