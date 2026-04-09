from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts import api_views

app_name = "api"

urlpatterns = [
    # Root
    path("", api_views.api_info, name="api_info"),
    # Auth
    path("auth/login/", api_views.auth_login_start_view, name="auth_login_start"),
    path("auth/login/verify-otp/", api_views.auth_verify_otp_view, name="auth_verify_otp"),
    path("auth/login/resend-otp/", api_views.auth_resend_otp_view, name="auth_resend_otp"),
    path("auth/login/password/", TokenObtainPairView.as_view(), name="token_obtain_password"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/profile/", api_views.auth_profile_view, name="auth_profile"),
    path("auth/profile/update/", api_views.auth_profile_update_view, name="auth_profile_update"),
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
    # Admin: Receipts
    path("admin/receipts/", api_views.admin_receipts_list, name="admin_receipts_list"),
    path("admin/receipts/create/", api_views.admin_receipts_create, name="admin_receipts_create"),
    path("admin/receipts/<int:receipt_id>/", api_views.admin_receipts_detail, name="admin_receipts_detail"),
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
        "admin/reports/distribute-profit/",
        api_views.admin_reports_distribute_profit,
        name="admin_reports_distribute_profit",
    ),
    # Admin: Interest & Dividends
    path("admin/interest/post/", api_views.admin_post_interest, name="admin_post_interest"),
    path("admin/dividend/distribute/", api_views.admin_distribute_dividend, name="admin_distribute_dividend"),
    # Admin: Audit Logs
    path("admin/audit-logs/", api_views.admin_audit_logs_list, name="admin_audit_logs_list"),
    # Member: Dashboard
    path("member/dashboard/", api_views.member_dashboard, name="member_dashboard"),
    # Member: Accounts
    path("member/accounts/", api_views.member_accounts_list, name="member_accounts_list"),
    path("member/accounts/<int:account_id>/", api_views.member_accounts_detail, name="member_accounts_detail"),
    # Member: Loans
    path("member/loans/", api_views.member_loans_list, name="member_loans_list"),
    path("member/loans/<int:loan_id>/", api_views.member_loans_detail, name="member_loans_detail"),
    # Member: Transactions
    path("member/transactions/", api_views.member_transactions_list, name="member_transactions_list"),
    # Member: Notifications
    path("member/notifications/", api_views.member_notifications_list, name="member_notifications_list"),
    path(
        "member/notifications/<int:notification_id>/read/",
        api_views.member_notifications_mark_read,
        name="member_notifications_mark_read",
    ),
    path(
        "member/notifications/mark-all-read/",
        api_views.member_notifications_mark_all_read,
        name="member_notifications_mark_all_read",
    ),
    path("member/devices/register/", api_views.register_device_token_view, name="register_device_token"),
    path("member/devices/unregister/", api_views.unregister_device_token_view, name="unregister_device_token"),
    # Email & Notifications
    path("email/preferences/", api_views.email_preferences_view, name="email_preferences"),
    path("email/send-verification/", api_views.send_verification_email_view, name="send_verification_email"),
    path("email/verify/", api_views.verify_email_view, name="verify_email"),
    path("email/change/request/", api_views.request_email_change_view, name="request_email_change"),
    path("email/change/confirm/", api_views.confirm_email_change_view, name="confirm_email_change"),
]
