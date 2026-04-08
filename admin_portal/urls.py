from django.urls import path

from . import views

app_name = "admin_portal"

urlpatterns = [
    path("home/", views.home_view, name="home"),
    path("members/", views.members_view, name="members"),
    path("members/add/", views.add_member_view, name="add_member"),
    path("members/<int:user_id>/", views.get_member_view, name="get_member"),
    path("members/<int:user_id>/edit/", views.edit_member_view, name="edit_member"),
    path("members/<int:user_id>/delete/", views.delete_member_view, name="delete_member"),
    path("members/<int:user_id>/reset-password/", views.reset_member_password_view, name="reset_member_password"),
    path("members/<int:user_id>/accounts/", views.get_member_accounts_view, name="get_member_accounts"),
    path("members/<int:user_id>/transactions/", views.get_member_transactions_view, name="get_member_transactions"),
    path("members/search/", views.search_members_view, name="search_members"),
    path("members/export/", views.export_members_view, name="export_members"),
    # Accounts
    path("accounts/", views.accounts_view, name="accounts"),
    path("accounts/add/", views.add_account_view, name="add_account"),
    path("accounts/<int:account_id>/", views.get_account_view, name="get_account"),
    path("accounts/<int:account_id>/edit/", views.edit_account_view, name="edit_account"),
    path("accounts/<int:account_id>/delete/", views.delete_member_account_view, name="delete_account"),
    path("accounts/<int:account_id>/transactions/", views.get_account_transactions_view, name="get_account_transactions"),
    path("accounts/export/", views.export_accounts_view, name="export_accounts"),
    # Receipts
    path("receipts/", views.receipts_view, name="receipts"),
    path("receipts/add/", views.add_receipt_view, name="add_receipt"),
    path("receipts/<int:receipt_id>/", views.get_receipt_view, name="get_receipt"),
    path("receipts/export/", views.export_receipts_view, name="export_receipts"),
    # Loans
    path("loans/", views.loans_view, name="loans"),
    path("loans/add/", views.add_loan_view, name="add_loan"),
    path("loans/<int:loan_id>/", views.get_loan_view, name="get_loan"),
    path("loans/<int:loan_id>/approve/", views.approve_loan_view, name="approve_loan"),
    path("loans/<int:loan_id>/record-emi/", views.record_emi_payment_view, name="record_emi_payment"),
    path("loans/export/", views.export_loans_view, name="export_loans"),
    # Funds
    path("funds/", views.funds_view, name="funds"),
    path("funds/add/", views.add_fund_view, name="add_fund"),
    path("funds/<int:fund_id>/", views.get_fund_view, name="get_fund"),
    path("funds/<int:fund_id>/edit/", views.edit_fund_view, name="edit_fund"),
    path("funds/<int:fund_id>/delete/", views.delete_fund_view, name="delete_fund"),
    path("funds/<int:fund_id>/add-transaction/", views.add_fund_transaction_view, name="add_fund_transaction"),
    path("funds/<int:fund_id>/transactions/", views.fund_transactions_view, name="fund_transactions"),
    # Allocation Rules
    path("allocation-rules/", views.allocation_rules_view, name="allocation_rules"),
    path("allocation-rules/add/", views.add_allocation_rule_view, name="add_allocation_rule"),
    path("allocation-rules/<int:rule_id>/edit/", views.edit_allocation_rule_view, name="edit_allocation_rule"),
    path("allocation-rules/<int:rule_id>/delete/", views.delete_allocation_rule_view, name="delete_allocation_rule"),
    # Audit Logs
    path("audit-logs/", views.audit_logs_view, name="audit_logs"),
    path("audit-logs/<int:log_id>/", views.get_audit_log_view, name="get_audit_log"),
    # Calculator
    path("calculator/", views.calculator_view, name="calculator"),
    # Profile
    path("profile/", views.profile_view, name="profile"),
]
