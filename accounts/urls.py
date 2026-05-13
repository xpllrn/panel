from django.urls import path

from . import api_views, views

urlpatterns = [
    path("setup/", views.setup_wizard_view, name="setup_wizard"),
    path("", views.login_view, name="login"),
    path("login/", views.login_view, name="login"),
    path("verify-email/<str:token>/", views.verify_email_link_view, name="verify_email_link"),
    # Signup disabled - members are created by admins via admin portal
    # path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    # `member_portal_disabled_view` stub moved to legacy/ along with the rest of
    # the member portal. Re-add a route here if/when the portal is revived.
    # API routes (for api.localhost)
    path("api/", api_views.api_info, name="api_info"),
]
