from django.urls import path

from . import api_views, views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("login/", views.login_view, name="login"),
    path("verify-email/<str:token>/", views.verify_email_link_view, name="verify_email_link"),
    # Signup disabled - members are created by admins via admin portal
    # path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("member-disabled/", views.member_portal_disabled_view, name="member_portal_disabled"),
    # API routes (for api.localhost)
    path("api/", api_views.api_info, name="api_info"),
]
