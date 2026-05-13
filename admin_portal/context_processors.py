"""Template context: working financial year and web auth mode for admin UI."""

from django.conf import settings


def web_auth_context(request):
    """Expose whether the staff panel runs without a login screen."""
    return {"WEB_LOGIN_DISABLED": getattr(settings, "WEB_LOGIN_DISABLED", False)}


def portal_fy(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    if not (getattr(request.user, "is_staff", False) or request.user.is_admin_role()):
        return {}
    from admin_portal.portal_fy import effective_fy_window, resolve_portal_financial_period

    from accounts.models import FinancialPeriod, SocietyConfiguration

    return {
        "portal_working_fy": resolve_portal_financial_period(request),
        "portal_fy_window": effective_fy_window(request),
        "portal_fy_periods": FinancialPeriod.objects.order_by("-start_date")[:80],
        "portal_society_config": SocietyConfiguration.objects.order_by("id").first(),
    }
