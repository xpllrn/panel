"""
Working financial year for the admin portal (session + optional DB period).

Changing the working FY updates which date range FY-scoped reporting and tools use.
Member balances and transactions are unchanged — only reporting context moves.

All pure FY helpers (FY bounds, month/quarter pickers, month-key parsing,
active/overlapping lookup) live in `accounts.services.financial_period`
so the panel, the API and the future MCP server share one implementation.
This module hosts only the request-scoped wrappers that read or mutate
`request.session`.
"""

from types import SimpleNamespace

from accounts.services import financial_period as fp_service

# Re-export pure helpers so legacy `from admin_portal.portal_fy import ...`
# imports keep working without touching call sites.
default_indian_fy_bounds = fp_service.default_indian_fy_bounds
month_options_in_window = fp_service.month_options_in_window
quarter_ranges_in_window = fp_service.quarter_ranges_in_window
parse_month_key_in_window = fp_service.parse_month_key_in_window

PORTAL_FY_SESSION_KEY = "portal_financial_period_id"


def resolve_portal_financial_period(request):
    """Active working FY: session override, else `FinancialPeriod` marked active/open."""
    from accounts.models import FinancialPeriod

    pid = request.session.get(PORTAL_FY_SESSION_KEY)
    if pid:
        fp = FinancialPeriod.objects.filter(pk=pid).first()
        if fp:
            return fp
    return fp_service.active()


def effective_fy_window(request):
    """
    FinancialPeriod instance or a lightweight namespace with start_date, end_date, label
    for helpers that need a contiguous FY range.
    """
    fp = resolve_portal_financial_period(request)
    if fp:
        return fp
    s, e = fp_service.default_indian_fy_bounds()
    return SimpleNamespace(
        start_date=s,
        end_date=e,
        label=f"FY {s.year}-{str(e.year)[-2:]}",
        id=None,
    )


def set_working_financial_period(request, period_id):
    """Persist selected FinancialPeriod pk in session (None = clear override, use active row)."""
    if period_id is None or period_id == "":
        request.session.pop(PORTAL_FY_SESSION_KEY, None)
    else:
        request.session[PORTAL_FY_SESSION_KEY] = int(period_id)
    request.session.modified = True


def report_dates_from_request(request):
    """
    Compute report start/end + template context helpers.
    Returns dict with keys: start_date, end_date, period, fy_year_label, month, selected_quarter,
    month_key, fy_month_options, fy_quarters, working_fy, using_session_fy, fy_window.
    """
    period = request.GET.get("period", "year")
    month_key = request.GET.get("month_key", "").strip()
    account_type_filter = request.GET.get("account_type", "").strip()
    selected_quarter = int(request.GET.get("quarter", 1))

    working = resolve_portal_financial_period(request)
    fy_window = effective_fy_window(request)
    using_session_fy = bool(request.session.get(PORTAL_FY_SESSION_KEY))

    fy_month_options = fp_service.month_options_in_window(fy_window)
    fy_quarters = fp_service.quarter_ranges_in_window(fy_window)

    if month_key:
        parts = month_key.split("-")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            period = "month"
        else:
            month_key = ""

    if period == "month":
        if not month_key and fy_month_options:
            month_key = fy_month_options[0]["key"]
        if not month_key:
            s, _ = fp_service.default_indian_fy_bounds()
            month_key = f"{s.year:04d}-{s.month:02d}"
        start_date, end_date = fp_service.parse_month_key_in_window(month_key, fy_window)
        y_part, m_part = month_key.split("-")
        year = int(y_part)
        month = int(m_part)
    elif period == "quarter":
        q = max(1, selected_quarter)
        if not fy_quarters:
            start_date, end_date = fy_window.start_date, fy_window.end_date
            selected_quarter = 1
        else:
            q = min(q, len(fy_quarters))
            selected_quarter = q
            seg = fy_quarters[q - 1]
            start_date, end_date = seg["start"], seg["end"]
        year = fy_window.start_date.year
        month = fy_window.start_date.month
        month_key = month_key or f"{year:04d}-{month:02d}"
    else:
        period = "year"
        start_date = fy_window.start_date
        end_date = fy_window.end_date
        year = start_date.year
        month = fy_window.start_date.month
        month_key = month_key or f"{fy_window.start_date.year:04d}-{fy_window.start_date.month:02d}"

    fy_year_label = fy_window.start_date.year

    return {
        "start_date": start_date,
        "end_date": end_date,
        "period": period,
        "year": year,
        "month": month,
        "selected_quarter": selected_quarter,
        "month_key": month_key,
        "account_type_filter": account_type_filter,
        "fy_month_options": fy_month_options,
        "fy_quarters": fy_quarters,
        "working_fy": working,
        "fy_window": fy_window,
        "using_session_fy": using_session_fy,
        "fy_year_label": fy_year_label,
    }
