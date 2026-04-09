from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from .forms import LoginForm
from .models import User
from .utils import log_action


def signup_view(request):
    """Signup is disabled. Members are created by admins via the admin portal."""
    return redirect("/login/")


def _get_redirect_url(user):
    """Get the appropriate redirect URL based on user role."""
    if user.is_staff or user.is_admin_role():
        return "/home/"
    return "/member/"


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_get_redirect_url(request.user))

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            log_action(request, "login", "system", user.id, f"User logged in: {user.display_name}")
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(_get_redirect_url(user))
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def verify_email_link_view(request, token):
    """Handle GET link from verification email (matches FRONTEND_URL/verify-email/<token>/)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    try:
        user = User.objects.get(email_verification_token=token)
    except User.DoesNotExist:
        return render(
            request,
            "accounts/verify_email.html",
            {
                "success": False,
                "error_message": "This verification link is invalid or has already been used.",
            },
        )

    if user.email_verified:
        return render(
            request,
            "accounts/verify_email.html",
            {
                "success": False,
                "error_message": "This email address is already verified.",
            },
        )

    if user.verify_email(token):
        return render(request, "accounts/verify_email.html", {"success": True})

    return render(
        request,
        "accounts/verify_email.html",
        {
            "success": False,
            "error_message": "Verification could not be completed. Request a new verification email from your profile.",
        },
    )


@login_required
def logout_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    log_action(request, "logout", "system", request.user.id, f"User logged out: {request.user.display_name}")
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("/login/")
