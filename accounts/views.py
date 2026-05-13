from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import LoginForm, SetupAdminProfileForm, SetupKYCForm, SetupPenaltyForm, SetupSocietyForm
from .models import (
    AccountTypeConfiguration,
    LoanTypeConfiguration,
    MemberKYC,
    SocietyConfiguration,
    User,
)
from .utils import log_action, split_full_name

SETUP_SESSION_KEY = "initial_setup_payload"
SETUP_STEP_MIN = 1
SETUP_STEP_MAX = 7


def is_initial_setup_complete():
    """Return True once the setup wizard has been finalized."""
    return SocietyConfiguration.objects.filter(setup_completed_at__isnull=False).exists()


def _get_redirect_url(user):
    """Get the appropriate redirect URL based on user role."""
    if user.is_staff or user.is_admin_role():
        return "/home/"
    return "/member-disabled/"


def _normalize_step(value):
    try:
        step = int(value)
    except (TypeError, ValueError):
        step = SETUP_STEP_MIN
    return max(SETUP_STEP_MIN, min(SETUP_STEP_MAX, step))


def _get_setup_payload(request):
    payload = request.session.get(SETUP_SESSION_KEY, {})
    return payload if isinstance(payload, dict) else {}


def _save_setup_payload(request, payload):
    request.session[SETUP_SESSION_KEY] = payload
    request.session.modified = True


def _account_rows_from_payload(payload):
    rows = payload.get("account_configs") or []
    return rows or [{"type": "", "interest_rate": ""}]


def _loan_rows_from_payload(payload):
    rows = payload.get("loan_configs") or []
    return rows or [{"type": "", "interest_rate": ""}]


def _collect_rate_rows(request, name_field_name, rate_field_name):
    rows = []
    used = set()
    selected_names = request.POST.getlist(name_field_name)
    selected_rates = request.POST.getlist(rate_field_name)

    for selected_name, selected_rate in zip(selected_names, selected_rates):
        selected_name = (selected_name or "").strip()
        selected_rate = (selected_rate or "").strip()
        if not selected_name and not selected_rate:
            continue
        if not selected_name:
            return None, "Name is required for each row."
        if len(selected_name) > 100:
            return None, "Each name must be 100 characters or fewer."
        normalized_name = selected_name.lower()
        if normalized_name in used:
            return None, "Duplicate names are not allowed."
        try:
            rate_value = Decimal(selected_rate)
        except InvalidOperation:
            return None, f"Invalid interest rate for {selected_name}."
        if rate_value < 0:
            return None, f"Interest rate cannot be negative for {selected_name}."
        used.add(normalized_name)
        rows.append({"type": selected_name, "interest_rate": f"{rate_value.quantize(Decimal('0.01'))}"})

    if not rows:
        return None, "Add at least one type and interest rate."
    return rows, None


def _save_temporary_logo(uploaded_file):
    ext = ""
    if "." in uploaded_file.name:
        ext = "." + uploaded_file.name.rsplit(".", 1)[-1].lower()
    filename = f"setup-temp/{uuid4().hex}{ext}"
    return default_storage.save(filename, uploaded_file)


def _finalize_setup(payload):
    admin_data = payload.get("admin", {})
    kyc_data = payload.get("kyc", {})
    society_data = payload.get("society", {})
    penalty_data = payload.get("penalty", {})
    account_configs = payload.get("account_configs", [])
    loan_configs = payload.get("loan_configs", [])

    required_payload = [
        admin_data.get("username"),
        admin_data.get("password"),
        kyc_data.get("aadhaar_number"),
        kyc_data.get("pan_number"),
        society_data.get("society_name"),
        penalty_data.get("late_payment_penalty_per_day"),
        account_configs,
        loan_configs,
    ]
    if not all(required_payload):
        return False, "Setup details are incomplete. Please finish all steps."

    first_name, last_name = split_full_name(admin_data.get("full_name", ""))
    if not first_name:
        return False, "Full name is required."

    with transaction.atomic():
        config, _ = SocietyConfiguration.objects.get_or_create(
            pk=1, defaults={"society_name": society_data["society_name"]}
        )
        config.society_name = society_data["society_name"]
        config.late_payment_penalty_per_day = penalty_data["late_payment_penalty_per_day"]
        config.setup_completed_at = timezone.now()
        logo_path = (society_data.get("society_logo_temp_path") or "").strip()
        if logo_path:
            config.society_logo = logo_path
        config.save()

        admin_user = User.objects.filter(is_staff=True).order_by("id").first()
        username = admin_data["username"]
        email = admin_data["email"]
        if admin_user:
            if User.objects.filter(username=username).exclude(pk=admin_user.pk).exists():
                return False, "Username already exists. Choose a different username."
            if User.objects.filter(email=email).exclude(pk=admin_user.pk).exists():
                return False, "Email already exists. Choose a different email."
            admin_user.username = username
            admin_user.email = email
            admin_user.first_name = first_name
            admin_user.last_name = last_name
            admin_user.mobile_primary = admin_data.get("mobile_primary")
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.role = "admin"
            admin_user.portal_access_enabled = True
            admin_user.set_password(admin_data["password"])
            admin_user.save()
        else:
            admin_user = User.objects.create_superuser(
                username=username,
                email=email,
                password=admin_data["password"],
                first_name=first_name,
                last_name=last_name,
            )
            admin_user.mobile_primary = admin_data.get("mobile_primary")
            admin_user.role = "admin"
            admin_user.portal_access_enabled = True
            admin_user.save(update_fields=["mobile_primary", "role", "portal_access_enabled"])

        MemberKYC.objects.update_or_create(
            user=admin_user,
            defaults={
                "aadhaar_number": kyc_data.get("aadhaar_number"),
                "pan_number": kyc_data.get("pan_number"),
                "kyc_status": "verified",
                "kyc_verified_date": timezone.localdate(),
                "kyc_verified_by": admin_user.display_name,
            },
        )

        AccountTypeConfiguration.objects.all().delete()
        AccountTypeConfiguration.objects.bulk_create(
            [
                AccountTypeConfiguration(
                    account_type=item["type"],
                    interest_rate=item["interest_rate"],
                    display_order=index,
                )
                for index, item in enumerate(account_configs)
            ]
        )

        LoanTypeConfiguration.objects.all().delete()
        LoanTypeConfiguration.objects.bulk_create(
            [
                LoanTypeConfiguration(
                    loan_type=item["type"],
                    interest_rate=item["interest_rate"],
                    display_order=index,
                )
                for index, item in enumerate(loan_configs)
            ]
        )

    return True, None


def _highest_setup_step(payload):
    highest = 1
    admin_data = payload.get("admin", {})
    kyc_data = payload.get("kyc", {})
    society_data = payload.get("society", {})
    account_configs = payload.get("account_configs", [])
    loan_configs = payload.get("loan_configs", [])
    penalty_data = payload.get("penalty", {})

    if admin_data.get("username") and admin_data.get("password"):
        highest = 2
    if highest >= 2 and kyc_data.get("aadhaar_number") and kyc_data.get("pan_number"):
        highest = 3
    if highest >= 3 and society_data.get("society_name"):
        highest = 4
    if highest >= 4 and account_configs:
        highest = 5
    if highest >= 5 and loan_configs:
        highest = 6
    if highest >= 6 and penalty_data.get("late_payment_penalty_per_day"):
        highest = 7
    return highest


def signup_view(request):
    """Signup is disabled. Members are created by admins via the admin portal."""
    return redirect("/login/")


def setup_wizard_view(request):
    """Collect first-run setup details and create initial admin + configuration."""
    if is_initial_setup_complete():
        if request.user.is_authenticated:
            return redirect(_get_redirect_url(request.user))
        return redirect("/login/")

    payload = _get_setup_payload(request)
    requested_step = request.POST.get("step") if request.method == "POST" else request.GET.get("step")
    step = _normalize_step(requested_step)
    allowed_step = _highest_setup_step(payload)
    if step > allowed_step:
        step = allowed_step
    next_step = min(step + 1, SETUP_STEP_MAX)
    previous_step = max(step - 1, SETUP_STEP_MIN)
    step_error = None

    if request.method == "POST":
        if step == 1:
            form = SetupAdminProfileForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data["username"].strip()
                email = form.cleaned_data["email"].strip().lower()
                if User.objects.filter(username=username).exists():
                    form.add_error("username", "This username is already in use.")
                if User.objects.filter(email=email).exists():
                    form.add_error("email", "This email is already in use.")
                if form.errors:
                    return render(
                        request,
                        "accounts/setup_wizard.html",
                        {
                            "step": step,
                            "total_steps": SETUP_STEP_MAX,
                            "form": form,
                            "payload": payload,
                            "next_step": next_step,
                            "previous_step": previous_step,
                        },
                    )
                payload["admin"] = {
                    "full_name": form.cleaned_data["full_name"].strip(),
                    "username": username,
                    "email": email,
                    "mobile_primary": form.cleaned_data["mobile_primary"].strip(),
                    "password": form.cleaned_data["password"],
                }
                _save_setup_payload(request, payload)
                return redirect(f"/setup/?step={next_step}")
        elif step == 2:
            form = SetupKYCForm(request.POST)
            if form.is_valid():
                payload["kyc"] = {
                    "aadhaar_number": form.cleaned_data["aadhaar_number"].strip(),
                    "pan_number": form.cleaned_data["pan_number"].strip().upper(),
                }
                _save_setup_payload(request, payload)
                return redirect(f"/setup/?step={next_step}")
        elif step == 3:
            form = SetupSocietyForm(request.POST, request.FILES)
            if form.is_valid():
                society_data = {"society_name": form.cleaned_data["society_name"].strip()}
                logo = form.cleaned_data.get("society_logo")
                if logo:
                    society_data["society_logo_temp_path"] = _save_temporary_logo(logo)
                elif payload.get("society", {}).get("society_logo_temp_path"):
                    society_data["society_logo_temp_path"] = payload["society"]["society_logo_temp_path"]
                payload["society"] = society_data
                _save_setup_payload(request, payload)
                return redirect(f"/setup/?step={next_step}")
        elif step == 4:
            rows, error = _collect_rate_rows(request, "account_type_name", "account_interest_rate")
            if error:
                step_error = error
            else:
                payload["account_configs"] = rows
                _save_setup_payload(request, payload)
                return redirect(f"/setup/?step={next_step}")
        elif step == 5:
            rows, error = _collect_rate_rows(request, "loan_type_name", "loan_interest_rate")
            if error:
                step_error = error
            else:
                payload["loan_configs"] = rows
                _save_setup_payload(request, payload)
                return redirect(f"/setup/?step={next_step}")
        elif step == 6:
            form = SetupPenaltyForm(request.POST)
            if form.is_valid():
                payload["penalty"] = {
                    "late_payment_penalty_per_day": str(form.cleaned_data["late_payment_penalty_per_day"])
                }
                _save_setup_payload(request, payload)
                return redirect(f"/setup/?step={next_step}")
        elif step == 7:
            success, error = _finalize_setup(payload)
            if success:
                request.session.pop(SETUP_SESSION_KEY, None)
                messages.success(
                    request,
                    "Setup completed. You can now log in with the admin username and password you just configured.",
                )
                return redirect("/login/")
            messages.error(request, error or "Setup could not be finalized.")

    default_admin = payload.get("admin", {})
    default_kyc = payload.get("kyc", {})
    default_society = payload.get("society", {})
    default_penalty = payload.get("penalty", {})

    if step == 1:
        form = SetupAdminProfileForm(initial=default_admin)
    elif step == 2:
        form = SetupKYCForm(initial=default_kyc)
    elif step == 3:
        form = SetupSocietyForm(initial=default_society)
    elif step == 6:
        form = SetupPenaltyForm(initial=default_penalty)
    else:
        form = None

    return render(
        request,
        "accounts/setup_wizard.html",
        {
            "step": step,
            "total_steps": SETUP_STEP_MAX,
            "form": form,
            "payload": payload,
            "next_step": next_step,
            "previous_step": previous_step,
            "step_error": step_error,
            "account_rows": _account_rows_from_payload(payload),
            "loan_rows": _loan_rows_from_payload(payload),
        },
    )


def login_view(request):
    if not is_initial_setup_complete():
        return redirect("/setup/")

    if getattr(settings, "WEB_LOGIN_DISABLED", False):
        if request.user.is_authenticated:
            return redirect(_get_redirect_url(request.user))
        staff = User.objects.filter(is_staff=True).order_by("pk").first()
        if staff:
            login(request, staff, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(_get_redirect_url(staff))
        return HttpResponse(
            "Web login is disabled but no staff user exists. Complete /setup/ or create a superuser.",
            status=503,
        )

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

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "society_config": SocietyConfiguration.objects.order_by("id").first(),
        },
    )


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
    if getattr(settings, "WEB_LOGIN_DISABLED", False):
        return redirect("/home/")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    log_action(request, "logout", "system", request.user.id, f"User logged out: {request.user.display_name}")
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("/login/")
