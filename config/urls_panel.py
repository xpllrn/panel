"""
URLconf for the staff/member HTML panel service (`config.settings`).

Mounted by the `panel` container in docker-compose. Exposes:
- the staff HTML admin portal (admin_portal views)
- the member portal (member_portal — currently disabled UI, stub kept)
- the setup wizard, login, logout, email verification flows
- the Django admin at `/admin/`
- panel-internal AJAX under `/api/members/...` (NOT the same as the public /api/v1/)

Deliberately omits:
- the public `/api/v1/` surface (lives in the `api` service — see `config/urls_api.py`)
- the OpenAPI schema / Swagger docs (same — API service)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from accounts import views as account_views
from admin_portal import views as admin_views


def root_redirect(request):
    """Redirect root based on current active UI surfaces."""
    if not account_views.is_initial_setup_complete():
        return redirect("/setup/")
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_admin_role():
            return redirect("/home/")
        return redirect("/member-disabled/")
    return redirect("/login/")


def health_check(request):
    """Health check endpoint for uptime monitoring and load balancers."""
    from django.db import connection
    from django.http import JsonResponse

    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok", "service": "panel", "database": "connected"})
    except Exception:
        return JsonResponse({"status": "error", "service": "panel", "database": "disconnected"}, status=503)


urlpatterns = [
    path("", root_redirect, name="root"),
    path("health/", health_check, name="health_check"),
    # Portals
    # Member portal UI moved to legacy/member_portal/. Restore by re-adding the app to
    # INSTALLED_APPS and re-introducing its `path("member/", include("member_portal.urls"))`.
    path("admin/", admin.site.urls),
    path("home/", admin_views.home_view, name="home"),
    path("members/", admin_views.members_view, name="members"),
    path("members/add/", admin_views.add_member_view, name="add_member"),
    path("members/<int:user_id>/get/", admin_views.get_member_view, name="get_member"),
    path("members/<int:user_id>/edit/", admin_views.edit_member_view, name="edit_member"),
    path("members/<int:user_id>/delete/", admin_views.delete_member_view, name="delete_member"),
    path("members/<int:user_id>/reset-password/", admin_views.reset_member_password_view, name="reset_member_password"),
    path("accounts/", admin_views.accounts_view, name="accounts"),
    path("accounts/add/", admin_views.add_account_view, name="add_account"),
    path("accounts/<int:account_id>/get/", admin_views.get_account_view, name="get_account"),
    path("accounts/<int:account_id>/details/", admin_views.account_details_view, name="account_details"),
    path("accounts/<int:account_id>/edit/", admin_views.edit_account_view, name="edit_account"),
    path("accounts/<int:account_id>/delete/", admin_views.delete_member_account_view, name="delete_member_account"),
    path(
        "accounts/<int:account_id>/transactions/",
        admin_views.get_account_transactions_view,
        name="get_account_transactions",
    ),
    # Panel-internal AJAX (DO NOT confuse with the public /api/v1/ surface)
    path("api/members/search/", admin_views.search_members_view, name="search_members"),
    path("api/members/<int:user_id>/accounts/", admin_views.get_member_accounts_view, name="get_member_accounts"),
    path(
        "api/members/<int:user_id>/transactions/",
        admin_views.get_member_transactions_view,
        name="get_member_transactions",
    ),
    path("transactions/", admin_views.transactions_view, name="transactions"),
    path("transactions/add/", admin_views.add_transaction_view, name="add_transaction"),
    path("transactions/vouchers/", admin_views.vouchers_view, name="vouchers"),
    path(
        "transactions/vouchers/<int:voucher_id>/transfer/",
        admin_views.transfer_voucher_to_fund_view,
        name="transfer_voucher_to_fund",
    ),
    path("transactions/<int:transaction_id>/get/", admin_views.get_transaction_view, name="get_transaction"),
    path("loans/", admin_views.loans_view, name="loans"),
    path("loans/add/", admin_views.add_loan_view, name="add_loan"),
    path("loans/<int:loan_id>/get/", admin_views.get_loan_view, name="get_loan"),
    path("loans/<int:loan_id>/approve/", admin_views.approve_loan_view, name="approve_loan"),
    path("loans/<int:loan_id>/record-emi/", admin_views.record_emi_payment_view, name="record_emi_payment"),
    path("audit-logs/", admin_views.audit_logs_view, name="audit_logs"),
    path("audit-logs/<int:log_id>/get/", admin_views.get_audit_log_view, name="get_audit_log"),
    # Funds
    path("funds/", admin_views.funds_view, name="funds"),
    path("funds/add/", admin_views.add_fund_view, name="add_fund"),
    path("funds/<int:fund_id>/get/", admin_views.get_fund_view, name="get_fund"),
    path("funds/<int:fund_id>/edit/", admin_views.edit_fund_view, name="edit_fund"),
    path("funds/<int:fund_id>/delete/", admin_views.delete_fund_view, name="delete_fund"),
    path("funds/<int:fund_id>/add-transaction/", admin_views.add_fund_transaction_view, name="add_fund_transaction"),
    path("funds/<int:fund_id>/transactions/", admin_views.fund_transactions_view, name="fund_transactions"),
    # Allocation Rules
    path("allocation-rules/", admin_views.allocation_rules_view, name="allocation_rules"),
    path("allocation-rules/add/", admin_views.add_allocation_rule_view, name="add_allocation_rule"),
    path("allocation-rules/<int:rule_id>/edit/", admin_views.edit_allocation_rule_view, name="edit_allocation_rule"),
    path(
        "allocation-rules/<int:rule_id>/delete/", admin_views.delete_allocation_rule_view, name="delete_allocation_rule"
    ),
    path("reports/", admin_views.reports_view, name="reports"),
    path("reports/distribute-profit/", admin_views.distribute_profit_view, name="distribute_profit"),
    path("reports/distribute-dividend/", admin_views.distribute_dividend_view, name="distribute_dividend"),
    path("reports/post-interest/", admin_views.post_interest_view, name="post_interest"),
    path("reports/save-snapshot/", admin_views.reports_save_financial_snapshot_view, name="reports_save_snapshot"),
    path("reports/sync-receivables/", admin_views.reports_sync_receivables_view, name="reports_sync_receivables"),
    path("reports/export/", admin_views.export_report_view, name="export_report"),
    path("finance/fees/", admin_views.finance_fees_view, name="finance_fees"),
    path("finance/receivables/", admin_views.finance_receivables_view, name="finance_receivables"),
    path("settings/", admin_views.settings_view, name="settings"),
    # Financial periods (Phase A5): promote orphan page to a real route.
    path("finance/periods/", admin_views.financial_periods_view, name="financial_periods"),
    path("finance/periods/open/", admin_views.open_financial_period_view, name="open_financial_period"),
    path(
        "finance/periods/<int:pk>/continue/",
        admin_views.continue_financial_period_view,
        name="continue_financial_period",
    ),
    path(
        "finance/periods/<int:pk>/close/",
        admin_views.close_financial_period_view,
        name="close_financial_period",
    ),
    path("database/", admin_views.database_view, name="database"),
    path("export/members/", admin_views.export_members_view, name="export_members"),
    path("export/accounts/", admin_views.export_accounts_view, name="export_accounts"),
    path("export/transactions/", admin_views.export_transactions_view, name="export_transactions"),
    path("export/loans/", admin_views.export_loans_view, name="export_loans"),
    path("profile/", admin_views.profile_view, name="profile"),
    path("", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
