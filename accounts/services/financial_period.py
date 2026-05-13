"""
FinancialPeriod service — diagram layer 1 (FY open / close / continue).

All FY business logic that does NOT touch `request.session` lives here so
both the panel and the API (and the future MCP server) call the same
implementations.

Request-scoped FY helpers (working-FY session override, report date parsing
from query params) remain in `admin_portal/portal_fy.py` — they are panel
concerns.

Today this module provides the pure read helpers:

    active()                         — the currently-active FinancialPeriod row
    overlapping(start, end)          — period whose range intersects [start, end]
    default_indian_fy_bounds(today)  — Apr–Mar FY bounds when no row exists
    month_options_in_window(window)  — month picker options for reports
    quarter_ranges_in_window(window) — quarter picker segments
    parse_month_key_in_window(...)   — month_key → (start, end) clamped to FY

Phase A5 will add the lifecycle operations here:

    open_period(label, start, end, *, actor, ip_address) -> FinancialPeriod
    continue_period(fy_id, *, actor, ip_address)
    close_period(fy_id, *, actor, ip_address)             # locks P&L, snapshots
                                                          # SocietyAccount, activates next

Until A5, `accounts.utils.active_financial_period` and
`accounts.utils.financial_period_overlapping` are kept as backward-compat
shims that simply delegate here, so the many existing call sites keep
working unchanged.
"""

import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog, FinancialPeriod, ProfitAndLoss, SocietyAccount
from accounts.services.exceptions import ConflictError, NotFoundError, ValidationError

# ---------------------------------------------------------------------------
# Pure read helpers
# ---------------------------------------------------------------------------


def active():
    """Return the currently-active `FinancialPeriod`, or `None` if none is set.

    "Active" means `is_active=True`. If multiple rows are flagged active (a
    data anomaly), the most-recent `start_date` wins.
    """
    return FinancialPeriod.objects.filter(is_active=True).order_by("-start_date").first()


def overlapping(start_date, end_date):
    """Return a `FinancialPeriod` whose range intersects [start_date, end_date].

    When multiple rows overlap, the active period is preferred, then the
    most-recent `start_date`.

    Returns `None` if either bound is missing or no period intersects.
    """
    if not start_date or not end_date:
        return None
    return (
        FinancialPeriod.objects.filter(start_date__lte=end_date, end_date__gte=start_date)
        .order_by("-is_active", "-start_date")
        .first()
    )


# ---------------------------------------------------------------------------
# Indian FY bounds (Apr–Mar)
# ---------------------------------------------------------------------------


def default_indian_fy_bounds(today=None):
    """April–March FY bounds for `today` (used when no `FinancialPeriod` row exists)."""
    today = today or date.today()
    start = date(today.year, 4, 1) if today.month >= 4 else date(today.year - 1, 4, 1)
    end = date(start.year + 1, 3, 31)
    return start, end


# ---------------------------------------------------------------------------
# Report-window helpers (month / quarter pickers)
# ---------------------------------------------------------------------------


def month_options_in_window(fy_window):
    """Month picker options for a report period.

    `fy_window` is anything with `.start_date` and `.end_date` attributes —
    either a `FinancialPeriod` row or a `SimpleNamespace` produced by
    `admin_portal.portal_fy.effective_fy_window`.

    Returns: `[{"key": "YYYY-MM", "label": "Apr 2025"}, ...]`.
    """
    opts = []
    cur = fy_window.start_date.replace(day=1)
    end = fy_window.end_date
    while cur <= end:
        key = f"{cur.year:04d}-{cur.month:02d}"
        opts.append({"key": key, "label": cur.strftime("%b %Y")})
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return opts


def quarter_ranges_in_window(fy_window):
    """Up to four quarter segments inside `fy_window`.

    Returns: `[{"num": 1..4, "start": date, "end": date, "label": "Q1 (Apr–Jun 2025)"}, ...]`.
    Stops early if the window is shorter than a full year.
    """
    out = []
    cur = fy_window.start_date.replace(day=1)
    end_cap = fy_window.end_date
    for qi in range(1, 5):
        if cur > end_cap:
            break
        sm, sy = cur.month, cur.year
        em = sm + 2
        ey = sy
        while em > 12:
            em -= 12
            ey += 1
        last_d = calendar.monthrange(ey, em)[1]
        seg_end = date(ey, em, last_d)
        if seg_end > end_cap:
            seg_end = end_cap
        label = f"Q{qi} ({cur.strftime('%b')}\u2013{seg_end.strftime('%b %Y')})"
        out.append({"num": qi, "start": cur, "end": seg_end, "label": label})
        if seg_end >= end_cap:
            break
        nxt = seg_end + timedelta(days=1)
        cur = date(nxt.year, nxt.month, 1)
    return out


def parse_month_key_in_window(month_key, fy_window):
    """`"YYYY-MM"` → `(start_date, end_date)` clamped to `fy_window`."""
    try:
        y_str, m_str = month_key.split("-")
        y, m = int(y_str), int(m_str)
    except (ValueError, TypeError, AttributeError):
        cur = fy_window.start_date.replace(day=1)
        y, m = cur.year, cur.month
    first = date(y, m, 1)
    if first < fy_window.start_date.replace(day=1):
        first = fy_window.start_date.replace(day=1)
        y, m = first.year, first.month
    last_d = calendar.monthrange(y, m)[1]
    last = date(y, m, last_d)
    if last > fy_window.end_date:
        last = fy_window.end_date
    start = max(first, fy_window.start_date)
    return start, last


# ---------------------------------------------------------------------------
# Audit helper (local to the service layer — no HTTP coupling)
# ---------------------------------------------------------------------------


def _write_audit(*, actor, action, entity_id, description, ip_address=None):
    """Write an AuditLog row from this service.

    `FinancialPeriod` is not in `AuditLog.ENTITY_CHOICES`, so we record under
    the `system` entity type and stash the period's id in `entity_id` for
    traceability. The description always starts with the verb so callers can
    grep for "Created ... ", "Updated ... ", "Closed ... ".
    """
    AuditLog.objects.create(
        user=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
        action=action,
        entity_type="system",
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )


def _audit_prefix(audit_via):
    """Return the panel/api description prefix used across the service layer."""
    return "via API: " if audit_via == "api" else ""


# ---------------------------------------------------------------------------
# Lifecycle: open / continue / close
# ---------------------------------------------------------------------------


def open_period(*, name, start_date, end_date, actor, ip_address=None, audit_via="panel"):
    """Create and activate a new `FinancialPeriod`.

    Args:
        name:        Human label, e.g. "FY 2025-26". Stored as `FinancialPeriod.label`.
        start_date:  Inclusive period start (date).
        end_date:    Inclusive period end (date). Must be strictly after start_date.
        actor:       The `User` performing the action.
        ip_address:  Optional caller IP, recorded on the audit row.
        audit_via:   "panel" (default) or "api"; prepends "via API: " to the audit
                     description so reviewers can tell which surface fired it.

    Behaviour:
        * Validates dates and rejects ranges that overlap any existing period.
        * Rejects duplicate labels with `ConflictError`.
        * Demotes the previously-active period (`is_active=False`, status untouched).
        * Persists the new row as `status="open", is_active=True`.
        * Writes one AuditLog row (action="create", entity_type="system").

    Returns:
        The freshly-created `FinancialPeriod`.

    Raises:
        ValidationError: missing fields, swapped/equal dates, or overlapping range.
        ConflictError:   a period with the same `name` already exists.
    """
    if not name or not str(name).strip():
        raise ValidationError("Period name is required.")
    if not start_date or not end_date:
        raise ValidationError("Start and end dates are required.")
    if start_date >= end_date:
        raise ValidationError("End date must be after start date.")

    label = str(name).strip()

    if FinancialPeriod.objects.filter(label=label).exists():
        raise ConflictError(f"A financial period named '{label}' already exists.")

    clash = overlapping(start_date, end_date)
    if clash is not None:
        raise ValidationError(
            f"Date range overlaps an existing period: {clash.label} ({clash.start_date} – {clash.end_date})."
        )

    with transaction.atomic():
        FinancialPeriod.objects.filter(is_active=True).update(is_active=False)
        period = FinancialPeriod.objects.create(
            label=label,
            start_date=start_date,
            end_date=end_date,
            status="open",
            is_active=True,
            created_by=actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None,
        )

    _write_audit(
        actor=actor,
        action="create",
        entity_id=period.id,
        description=(f"{_audit_prefix(audit_via)}Created financial period: {label} ({start_date} – {end_date})"),
        ip_address=ip_address,
    )
    return period


def continue_period(*, period_id, actor, ip_address=None, audit_via="panel"):
    """Set the chosen `FinancialPeriod` as the currently-active one.

    Only a non-closed period may be re-activated. Any other active period is
    demoted (`is_active=False`) without changing its own status, so a closed
    period that happens to be flagged active stays closed.

    Returns:
        The re-activated `FinancialPeriod`.

    Raises:
        NotFoundError:   the period does not exist.
        ValidationError: the period is closed (closed periods cannot be reopened).
    """
    try:
        period = FinancialPeriod.objects.get(id=period_id)
    except FinancialPeriod.DoesNotExist as exc:
        raise NotFoundError("Financial period not found.") from exc

    if period.status == "closed":
        raise ValidationError("Closed periods cannot be continued; open a new period instead.")

    with transaction.atomic():
        FinancialPeriod.objects.exclude(id=period.id).filter(is_active=True).update(is_active=False)
        period.is_active = True
        if period.status != "open":
            period.status = "open"
        period.save(update_fields=["is_active", "status", "updated_at"])

    _write_audit(
        actor=actor,
        action="update",
        entity_id=period.id,
        description=f"{_audit_prefix(audit_via)}Updated financial period (continued): {period.label}",
        ip_address=ip_address,
    )
    return period


def close_period(*, period_id, actor, ip_address=None, audit_via="panel"):
    """Close a `FinancialPeriod` and lock its P&L snapshot.

    Inside one atomic block:
        1. Loads the period for update.
        2. Refuses to close anything that is not currently `status="open"`.
        3. Ensures a `ProfitAndLoss` row exists for the period (creates a
           zeroed placeholder if needed — the P&L engine in Phase B will
           backfill it).
        4. Marks the P&L row as locked (is_locked, locked_by, locked_date).
        5. Ensures a `SocietyAccount` snapshot row exists for the period.
           Both `ProfitAndLoss` and `SocietyAccount` use only zero-default
           fields here; the future engine will populate real aggregates.
        6. Sets the period to `status="closed", is_active=False`.

    Returns:
        dict with keys:
            "period":          the closed FinancialPeriod
            "pnl":             the (now locked) ProfitAndLoss row
            "society_account": the SocietyAccount snapshot row (or None if
                               creation was skipped for any reason)

    Raises:
        NotFoundError:   the period does not exist.
        ValidationError: the period is not currently open.
    """
    now = timezone.now()
    with transaction.atomic():
        try:
            period = FinancialPeriod.objects.select_for_update().get(id=period_id)
        except FinancialPeriod.DoesNotExist as exc:
            raise NotFoundError("Financial period not found.") from exc

        if period.status != "open":
            raise ValidationError("Only open periods can be closed.")

        pnl, _ = ProfitAndLoss.objects.get_or_create(
            financial_period=period,
            defaults={"calculation_date": now, "calculated_by": actor},
        )
        pnl.is_locked = True
        pnl.locked_by = actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None
        pnl.locked_date = now
        pnl.save(update_fields=["is_locked", "locked_by", "locked_date", "updated_at"])

        society_account, _ = SocietyAccount.objects.get_or_create(financial_period=period)

        period.status = "closed"
        period.is_active = False
        period.save(update_fields=["status", "is_active", "updated_at"])

    _write_audit(
        actor=actor,
        action="approve",
        entity_id=period.id,
        description=f"{_audit_prefix(audit_via)}Closed financial period: {period.label}",
        ip_address=ip_address,
    )
    return {"period": period, "pnl": pnl, "society_account": society_account}
