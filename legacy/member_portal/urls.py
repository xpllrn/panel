from django.urls import path

from . import views

app_name = "member_portal"

urlpatterns = [
    path("", views.member_dashboard_view, name="dashboard"),
    path("accounts/", views.member_accounts_view, name="accounts"),
    path("accounts/<int:account_id>/", views.member_account_detail_view, name="account_detail"),
    path("accounts/<int:account_id>/statement/", views.member_account_statement_view, name="account_statement"),
    path("loans/", views.member_loans_view, name="loans"),
    path("loans/<str:loan_kind>/<int:loan_id>/", views.member_loan_detail_view, name="loan_detail"),
    path("transactions/", views.member_transactions_view, name="transactions"),
    path("profile/", views.member_profile_view, name="profile"),
    path("service-worker.js", views.service_worker_view, name="service_worker"),
]
