"""
Optional web authentication bypass for the staff HTML panel.

When WEB_LOGIN_DISABLED is True, anonymous browser requests (excluding API and
Django admin routes) are logged in as the first staff user once setup is complete.
"""

from django.conf import settings
from django.contrib.auth import login

from accounts.models import User
from accounts.views import is_initial_setup_complete


def _should_skip_auto_login(request):
    path = request.path
    if path.startswith("/api/"):
        return True
    if path.startswith("/admin/"):
        return True
    static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
    if path.startswith(static_url):
        return True
    media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
    if media_url != "/" and path.startswith(media_url):
        return True
    if path == "/health/" or path == "/favicon.ico":
        return True
    return False


class AutoStaffLoginMiddleware:
    """Attach the primary staff user to the session when web login is disabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "WEB_LOGIN_DISABLED", False) and not _should_skip_auto_login(request):
            if is_initial_setup_complete() and not request.user.is_authenticated:
                staff = User.objects.filter(is_staff=True).order_by("pk").first()
                if staff:
                    login(request, staff, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)
