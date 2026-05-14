from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts import api_views

app_name = "api"

urlpatterns = [
    # Root
    path("", api_views.api_info, name="api_info"),
    # Auth — OTP / email-OTP login flow moved to legacy/ along with the member
    # portal & android app. Active auth surface is JWT password login + refresh.
    # The dormant view functions (`auth_login_start_view`, `auth_verify_otp_view`,
    # `auth_resend_otp_view`) still exist in `accounts/api_views.py` for revival.
    path("auth/login/password/", TokenObtainPairView.as_view(), name="token_obtain_password"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/profile/", api_views.auth_profile_view, name="auth_profile"),
    path("auth/profile/update/", api_views.auth_profile_update_view, name="auth_profile_update"),
    path("auth/profile/password/", api_views.auth_password_change_view, name="auth_password_change"),
    # Admin: Members
    path("admin/members/", api_views.admin_members_list, name="admin_members_list"),
    path("admin/members/create/", api_views.admin_members_create, name="admin_members_create"),
    path("admin/members/<int:user_id>/", api_views.admin_members_detail, name="admin_members_detail"),
    path("admin/members/<int:user_id>/update/", api_views.admin_members_update, name="admin_members_update"),
    path("admin/members/<int:user_id>/delete/", api_views.admin_members_delete, name="admin_members_delete"),
    # Admin: Accounts
    path("admin/accounts/", api_views.admin_accounts_list, name="admin_accounts_list"),
    path("admin/accounts/create/", api_views.admin_accounts_create, name="admin_accounts_create"),
    path("admin/accounts/<int:account_id>/", api_views.admin_accounts_detail, name="admin_accounts_detail"),
    path("admin/accounts/<int:account_id>/update/", api_views.admin_accounts_update, name="admin_accounts_update"),
    path("admin/accounts/<int:account_id>/delete/", api_views.admin_accounts_delete, name="admin_accounts_delete"),
    # Admin: Transactions (formerly Receipts)
    path("admin/transactions/", api_views.admin_transactions_list, name="admin_transactions_list"),
    path("admin/transactions/create/", api_views.admin_transactions_create, name="admin_transactions_create"),
    path(
        "admin/transactions/<int:transaction_id>/",
        api_views.admin_transactions_detail,
        name="admin_transactions_detail",
    ),
    # Admin: Loans
    path("admin/loans/", api_views.admin_loans_list, name="admin_loans_list"),
    path("admin/loans/create/", api_views.admin_loans_create, name="admin_loans_create"),
    path("admin/loans/<int:loan_id>/", api_views.admin_loans_detail, name="admin_loans_detail"),
    path("admin/loans/<int:loan_id>/approve/", api_views.admin_loans_approve, name="admin_loans_approve"),
    path("admin/loans/<int:loan_id>/record-emi/", api_views.admin_loans_record_emi, name="admin_loans_record_emi"),
    # Admin: Funds
    path("admin/funds/", api_views.admin_funds_list, name="admin_funds_list"),
    path("admin/funds/create/", api_views.admin_funds_create, name="admin_funds_create"),
    path("admin/funds/<int:fund_id>/", api_views.admin_funds_detail, name="admin_funds_detail"),
    path("admin/funds/<int:fund_id>/update/", api_views.admin_funds_update, name="admin_funds_update"),
    path("admin/funds/<int:fund_id>/delete/", api_views.admin_funds_delete, name="admin_funds_delete"),
    path(
        "admin/funds/<int:fund_id>/add-transaction/",
        api_views.admin_funds_add_transaction,
        name="admin_funds_add_transaction",
    ),
    # Admin: Allocation Rules
    path("admin/allocation-rules/", api_views.admin_allocation_rules_list, name="admin_allocation_rules_list"),
    path(
        "admin/allocation-rules/create/", api_views.admin_allocation_rules_create, name="admin_allocation_rules_create"
    ),
    path(
        "admin/allocation-rules/<int:rule_id>/update/",
        api_views.admin_allocation_rules_update,
        name="admin_allocation_rules_update",
    ),
    path(
        "admin/allocation-rules/<int:rule_id>/delete/",
        api_views.admin_allocation_rules_delete,
        name="admin_allocation_rules_delete",
    ),
    # Admin: Reports
    path("admin/reports/summary/", api_views.admin_reports_summary, name="admin_reports_summary"),
    path(
        "admin/reports/snapshot/save/",
        api_views.admin_finance_save_snapshot,
        name="admin_finance_save_snapshot",
    ),
    path(
        "admin/reports/distribute-profit/",
        api_views.admin_reports_distribute_profit,
        name="admin_reports_distribute_profit",
    ),
    path("admin/fee-schedules/", api_views.admin_fee_schedules_list, name="admin_fee_schedules_list"),
    path("admin/fee-charges/", api_views.admin_fee_charges_list, name="admin_fee_charges_list"),
    path(
        "admin/interest-receivables/",
        api_views.admin_interest_receivables_list,
        name="admin_interest_receivables_list",
    ),
    path("admin/profit-loss/", api_views.admin_profit_loss_list, name="admin_profit_loss_list"),
    path(
        "admin/profit-loss/<int:snapshot_id>/",
        api_views.admin_profit_loss_detail,
        name="admin_profit_loss_detail",
    ),
    path(
        "admin/society-snapshots/",
        api_views.admin_society_snapshots_list,
        name="admin_society_snapshots_list",
    ),
    path(
        "admin/society/main-account/",
        api_views.admin_society_main_account,
        name="admin_society_main_account",
    ),
    path(
        "admin/finance/sync-receivables/",
        api_views.admin_finance_sync_receivables,
        name="admin_finance_sync_receivables",
    ),
    # Admin: Interest & Dividends
    path("admin/interest/post/", api_views.admin_post_interest, name="admin_post_interest"),
    path("admin/dividend/distribute/", api_views.admin_distribute_dividend, name="admin_distribute_dividend"),
    # Admin: Audit Logs
    path("admin/audit-logs/", api_views.admin_audit_logs_list, name="admin_audit_logs_list"),
    # Member REST surface (dashboard, accounts, loans, transactions, notifications,
    # push tokens) moved to legacy/ — the dormant view functions are still in
    # `accounts/api_views.py` for revival when the member portal is restored.
    # Email & Notifications
    path("email/preferences/", api_views.email_preferences_view, name="email_preferences"),
    path("email/send-verification/", api_views.send_verification_email_view, name="send_verification_email"),
    path("email/verify/", api_views.verify_email_view, name="verify_email"),
    path("email/change/request/", api_views.request_email_change_view, name="request_email_change"),
    path("email/change/confirm/", api_views.confirm_email_change_view, name="confirm_email_change"),
    # Admin: Financial Periods (Phase A5)
    path(
        "admin/financial-periods/",
        api_views.admin_financial_periods_dispatch,
        name="admin_financial_periods_list",
    ),
    path(
        "admin/financial-periods/current/",
        api_views.admin_financial_periods_current,
        name="admin_financial_periods_current",
    ),
    path(
        "admin/financial-periods/<int:pk>/continue/",
        api_views.admin_financial_periods_continue,
        name="admin_financial_periods_continue",
    ),
    path(
        "admin/financial-periods/<int:pk>/close/",
        api_views.admin_financial_periods_close,
        name="admin_financial_periods_close",
    ),
]
