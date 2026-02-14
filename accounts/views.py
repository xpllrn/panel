from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from .forms import LoginForm


def signup_view(request):
    """Signup is disabled. Members are created by admins via the admin portal."""
    return redirect("/login/")


def _get_redirect_url(user):
    """Get the appropriate redirect URL based on user role."""
    if user.is_staff or user.is_admin_role():
        return "/home/"
    return "/member/"


def login_view(request):
    """Default login is member login"""
    return member_login_view(request)


def admin_login_view(request):
    """Admin login page"""
    if request.user.is_authenticated:
        return redirect(_get_redirect_url(request.user))

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not (user.is_staff or user.is_admin_role()):
                messages.error(request, "You do not have admin access.")
                return redirect("/portal/login/")
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("/home/")
    else:
        form = LoginForm()

    return render(request, "accounts/admin_login.html", {"form": form})


def member_login_view(request):
    """Member login page"""
    if request.user.is_authenticated:
        return redirect(_get_redirect_url(request.user))

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(_get_redirect_url(user))
    else:
        form = LoginForm()

    return render(request, "accounts/member_login.html", {"form": form})


@login_required
def logout_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("/member/login/")
