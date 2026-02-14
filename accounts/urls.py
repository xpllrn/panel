from django.urls import path

from . import api_views, views

urlpatterns = [
    path("", views.member_login_view, name="login"),
    path("login/", views.member_login_view, name="member_login"),
    path("admin/login/", views.admin_login_view, name="admin_login"),
    path("member/login/", views.member_login_view, name="member_login_alt"),
    # Signup disabled - members are created by admins via admin portal
    # path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    # API routes (for api.localhost)
    path("api/", api_views.api_info, name="api_info"),
]
