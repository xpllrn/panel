from django.urls import path

from . import api_views, views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("login/", views.login_view, name="login"),
    # Signup disabled - members are created by admins via admin portal
    # path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    # API routes (for api.localhost)
    path("api/", api_views.api_info, name="api_info"),
]
