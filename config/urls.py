from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from admin_portal import views as admin_views


def root_redirect(request):
    """Redirect root to admin home or member portal based on role"""
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_admin_role():
            return redirect("/home/")
        return redirect("/member/")
    return redirect("/member/login/")


urlpatterns = [
    path("", root_redirect, name="root"),
    path("member/", include("member_portal.urls")),
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
    path("accounts/<int:account_id>/edit/", admin_views.edit_account_view, name="edit_account"),
    path("accounts/<int:account_id>/delete/", admin_views.delete_member_account_view, name="delete_member_account"),
    path(
        "accounts/<int:account_id>/transactions/",
        admin_views.get_account_transactions_view,
        name="get_account_transactions",
    ),
    path("api/members/search/", admin_views.search_members_view, name="search_members"),
    path("api/members/<int:user_id>/accounts/", admin_views.get_member_accounts_view, name="get_member_accounts"),
    path(
        "api/members/<int:user_id>/transactions/",
        admin_views.get_member_transactions_view,
        name="get_member_transactions",
    ),
    path("receipts/", admin_views.receipts_view, name="receipts"),
    path("receipts/add/", admin_views.add_receipt_view, name="add_receipt"),
    path("receipts/<int:receipt_id>/get/", admin_views.get_receipt_view, name="get_receipt"),
    path("loans/", admin_views.loans_view, name="loans"),
    path("loans/add/", admin_views.add_loan_view, name="add_loan"),
    path("loans/<int:loan_id>/get/", admin_views.get_loan_view, name="get_loan"),
    path("loans/<int:loan_id>/approve/", admin_views.approve_loan_view, name="approve_loan"),
    path("loans/<int:loan_id>/record-emi/", admin_views.record_emi_payment_view, name="record_emi_payment"),
    path("tickets/", admin_views.admin_tickets_view, name="admin_tickets"),
    path("tickets/<int:ticket_id>/", admin_views.admin_ticket_detail_view, name="admin_ticket_detail"),
    path("audit-logs/", admin_views.audit_logs_view, name="audit_logs"),
    path("audit-logs/<int:log_id>/get/", admin_views.get_audit_log_view, name="get_audit_log"),
    path("calculator/", admin_views.calculator_view, name="calculator"),
    path("export/members/", admin_views.export_members_view, name="export_members"),
    path("export/accounts/", admin_views.export_accounts_view, name="export_accounts"),
    path("export/receipts/", admin_views.export_receipts_view, name="export_receipts"),
    path("export/loans/", admin_views.export_loans_view, name="export_loans"),
    path("profile/", admin_views.profile_view, name="profile"),
    path("profile/account/<int:account_id>/delete/", admin_views.delete_account_view, name="delete_account"),
    path("", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
