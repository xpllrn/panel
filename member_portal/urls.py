from django.urls import path

from . import views

app_name = "member_portal"

urlpatterns = [
    path("", views.member_dashboard_view, name="dashboard"),
    path("accounts/", views.member_accounts_view, name="accounts"),
    path("accounts/<int:account_id>/", views.member_account_detail_view, name="account_detail"),
    path("loans/", views.member_loans_view, name="loans"),
    path("loans/<int:loan_id>/", views.member_loan_detail_view, name="loan_detail"),
    path("transactions/", views.member_transactions_view, name="transactions"),
    path("tickets/", views.member_tickets_view, name="tickets"),
    path("tickets/create/", views.member_ticket_create_view, name="ticket_create"),
    path("tickets/<int:ticket_id>/", views.member_ticket_detail_view, name="ticket_detail"),
    path("profile/", views.member_profile_view, name="profile"),
]

