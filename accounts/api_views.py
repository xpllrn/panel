import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.api_permissions import IsAdmin, IsMember
from accounts.email_utils import (
    send_email_change_confirmed,
    send_email_change_otp_email,
    send_email_moved_security_notice,
    send_login_otp_email,
    send_password_change_alert,
    send_phone_changed_alert,
)
from accounts.models import (
    AuditLog,
    FeeCharge,
    FeeSchedule,
    FinancialPeriod,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    InterestReceivable,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    LoginOTPChallenge,
    MemberAccount,
    Notification,
    ProfitAndLoss,
    SocietyAccount,
    Transaction,
    User,
    UserDevice,
)
from accounts.notification_service import dispatch_user_notification, send_member_test_push
from accounts.serializers import (
    AuditLogSerializer,
    FeeChargeSerializer,
    FeeScheduleSerializer,
    FundAccountSerializer,
    FundAllocationRuleSerializer,
    FundTransactionSerializer,
    InterestReceivableSerializer,
    LoanApplicationDetailSerializer,
    LoanCreateSerializer,
    LoanDetailSerializer,
    LoanListSerializer,
    LoanRepaymentSerializer,
    MemberAccountCreateSerializer,
    MemberAccountSerializer,
    MemberProfileSerializer,
    NotificationSerializer,
    ProfitAndLossSerializer,
    SocietyAccountSerializer,
    TransactionCreateSerializer,
    TransactionSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    loan_merged_list_dict,
)
from accounts.services import interest_engine
from accounts.services import loans as loan_service
from accounts.services import transactions as transaction_service
from accounts.services.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
)
from accounts.utils import (
    LoanListItem,
    _get_client_ip,
    active_financial_period,
    apply_fund_allocations,
    financial_period_overlapping,
    log_action,
    mask_email_for_display,
    persist_financial_snapshots,
    sync_loan_interest_receivables,
    user_active_share_capital_total,
    validate_password_strength,
)

# ========================================
# Auth Endpoints
# ========================================


@api_view(["GET"])
@permission_classes([])
def api_info(request):
    """API information and available endpoints."""
    return Response(
        {
            "name": "Delhi Aam Nagrik API",
            "version": "1.0.0",
            "auth": {
                "login_start": "/api/v1/auth/login/",
                "login_verify_otp": "/api/v1/auth/login/verify-otp/",
                "login_resend_otp": "/api/v1/auth/login/resend-otp/",
                "refresh": "/api/v1/auth/refresh/",
                "profile": "/api/v1/auth/profile/",
                "profile_password": "/api/v1/auth/profile/password/",
            },
            "admin": {
                "members": "/api/v1/admin/members/",
                "accounts": "/api/v1/admin/accounts/",
                "loans": "/api/v1/admin/loans/",
                "transactions": "/api/v1/admin/transactions/",
                "funds": "/api/v1/admin/funds/",
                "reports": "/api/v1/admin/reports/summary/",
                "audit-logs": "/api/v1/admin/audit-logs/",
            },
            "member": {
                "dashboard": "/api/v1/member/dashboard/",
                "accounts": "/api/v1/member/accounts/",
                "loans": "/api/v1/member/loans/",
                "transactions": "/api/v1/member/transactions/",
            },
            "docs": "/api/v1/docs/",
        }
    )


@api_view(["GET"])
def auth_profile_view(request):
    """Get current authenticated user profile."""
    serializer = MemberProfileSerializer(request.user)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auth_profile_update_view(request):
    """Update editable profile fields for authenticated user."""
    mobile_primary = request.data.get("mobile_primary")
    date_of_birth = request.data.get("date_of_birth")
    previous_mobile = request.user.mobile_primary

    updated_fields = []

    if mobile_primary is not None:
        mobile_primary = str(mobile_primary).strip() or None
        request.user.mobile_primary = mobile_primary
        updated_fields.append("mobile_primary")

    if date_of_birth is not None:
        raw_dob = str(date_of_birth).strip()
        if raw_dob:
            try:
                parsed = datetime.strptime(raw_dob, "%Y-%m-%d").date()
            except ValueError:
                return Response({"success": False, "error": "date_of_birth must be in YYYY-MM-DD format."}, status=400)
            request.user.date_of_birth = parsed
        else:
            request.user.date_of_birth = None
        updated_fields.append("date_of_birth")

    if not updated_fields:
        return Response({"success": False, "error": "No valid fields provided."}, status=400)

    try:
        request.user.full_clean()
        request.user.save(update_fields=updated_fields)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=400)

    if "mobile_primary" in updated_fields:
        old_m = (previous_mobile or "").strip()
        new_m = (request.user.mobile_primary or "").strip()
        if old_m != new_m:
            send_phone_changed_alert(request.user, previous_mobile or "", request.user.mobile_primary or "")

    serializer = MemberProfileSerializer(request.user)
    return Response({"success": True, "message": "Profile updated successfully.", "profile": serializer.data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auth_password_change_view(request):
    """Change password for the authenticated member (mobile app / API)."""
    current_password = request.data.get("current_password", "")
    new_password = request.data.get("new_password", "")
    if not current_password or not new_password:
        return Response(
            {"success": False, "error": "current_password and new_password are required."},
            status=400,
        )

    user = request.user
    if not user.check_password(current_password):
        return Response({"success": False, "error": "Current password is incorrect."}, status=400)

    is_valid, errors = validate_password_strength(new_password, user=user)
    if not is_valid:
        return Response({"success": False, "error": errors[0] if errors else "Invalid password."}, status=400)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    log_action(request, "update", "member", user.id, "Member changed password via API")
    send_password_change_alert(user)
    return Response({"success": True, "message": "Password updated successfully."})


def _build_rate_limit_key(username, request):
    ip_address = request.META.get("REMOTE_ADDR", "")
    return f"otp_login_start:{username.lower()}:{ip_address}"


def _check_rate_limit(username, request):
    limit_key = _build_rate_limit_key(username, request)
    current = cache.get(limit_key, 0)
    max_attempts = 5
    if current >= max_attempts:
        return False
    cache.set(limit_key, current + 1, timeout=15 * 60)
    return True


def _is_login_otp_bypass_user(user):
    """Return True when user is explicitly allowlisted for review OTP bypass."""
    allowed = getattr(settings, "LOGIN_OTP_BYPASS_USERNAMES", [])
    username = (getattr(user, "username", "") or "").strip().lower()
    return bool(username and username in allowed)


def _get_login_otp_bypass_code():
    """Return configured bypass OTP code or empty string."""
    return (getattr(settings, "LOGIN_OTP_BYPASS_CODE", "") or "").strip()


def _generate_numeric_otp():
    return str(secrets.randbelow(900000) + 100000)


def _email_change_cache_key(user_id):
    """One pending email-change challenge per user (new request replaces old)."""
    return f"email_change:user:{user_id}"


def _email_change_rate_limit_key(user_id):
    return f"email_change:rate:{user_id}"


def _normalize_and_validate_email(raw):
    """Return normalized email or None with error message tuple (None, err_msg)."""
    email = (raw or "").strip().lower()
    if not email:
        return None, "new_email is required."
    try:
        validate_email(email)
    except ValidationError:
        return None, "Enter a valid email address."
    return email, None


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_login_start_view(request):
    """Validate username/password and send email OTP."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response({"success": False, "error": "Username and password are required."}, status=400)

    if not _check_rate_limit(username, request):
        return Response({"success": False, "error": "Too many login requests. Please try again later."}, status=429)

    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({"success": False, "error": "Invalid username or password."}, status=401)

    if not user.is_active or user.status != "active":
        return Response({"success": False, "error": "No active account found with the given credentials."}, status=401)

    bypass_enabled_for_user = _is_login_otp_bypass_user(user)
    bypass_code = _get_login_otp_bypass_code() if bypass_enabled_for_user else ""
    if bypass_enabled_for_user and not bypass_code:
        return Response({"success": False, "error": "Login bypass is not configured correctly."}, status=500)

    if not bypass_enabled_for_user and not user.email:
        return Response({"success": False, "error": "No email configured for this account."}, status=400)

    otp_code = bypass_code if bypass_enabled_for_user else _generate_numeric_otp()
    challenge_token = secrets.token_urlsafe(32)
    otp_expiry_minutes = getattr(settings, "LOGIN_OTP_EXPIRY_MINUTES", 15)
    max_attempts = getattr(settings, "LOGIN_OTP_MAX_ATTEMPTS", 5)
    expires_at = timezone.now() + timedelta(minutes=otp_expiry_minutes)

    LoginOTPChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=timezone.now())
    challenge = LoginOTPChallenge.objects.create(
        user=user,
        challenge_token=challenge_token,
        otp_hash=make_password(otp_code),
        expires_at=expires_at,
        max_attempts=max_attempts,
        request_ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )

    if bypass_enabled_for_user:
        log_action(request, "login", "system", user.id, f"Review OTP bypass challenge issued: {user.username}")
    else:
        email_sent = send_login_otp_email(user, otp_code, expires_minutes=otp_expiry_minutes)
        if not email_sent:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=["consumed_at"])
            return Response({"success": False, "error": "Failed to send OTP email. Try again later."}, status=500)
        log_action(request, "login", "system", user.id, f"OTP sent for login: {user.username}")

    return Response(
        {
            "success": True,
            "message": (
                "OTP challenge created. Use the review OTP provided in app access instructions."
                if bypass_enabled_for_user
                else "OTP sent to your email address."
            ),
            "challenge_token": challenge.challenge_token,
            "expires_in_seconds": otp_expiry_minutes * 60,
            "email_masked": mask_email_for_display(user.email) if user.email else "",
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_resend_otp_view(request):
    """Resend OTP for an active login challenge."""
    challenge_token = request.data.get("challenge_token", "").strip()
    if not challenge_token:
        return Response({"success": False, "error": "challenge_token is required."}, status=400)

    try:
        challenge = LoginOTPChallenge.objects.select_related("user").get(
            challenge_token=challenge_token,
            consumed_at__isnull=True,
        )
    except LoginOTPChallenge.DoesNotExist:
        return Response({"success": False, "error": "Invalid or expired login challenge."}, status=400)

    if challenge.is_expired:
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        return Response({"success": False, "error": "OTP challenge expired. Start login again."}, status=400)

    bypass_enabled_for_user = _is_login_otp_bypass_user(challenge.user)
    bypass_code = _get_login_otp_bypass_code() if bypass_enabled_for_user else ""
    if bypass_enabled_for_user and not bypass_code:
        return Response({"success": False, "error": "Login bypass is not configured correctly."}, status=500)

    otp_code = bypass_code if bypass_enabled_for_user else _generate_numeric_otp()
    challenge.otp_hash = make_password(otp_code)
    otp_expiry_minutes = getattr(settings, "LOGIN_OTP_EXPIRY_MINUTES", 15)
    challenge.expires_at = timezone.now() + timedelta(minutes=otp_expiry_minutes)
    challenge.attempt_count = 0
    challenge.save(update_fields=["otp_hash", "expires_at", "attempt_count"])

    if not bypass_enabled_for_user:
        if not send_login_otp_email(challenge.user, otp_code, expires_minutes=otp_expiry_minutes):
            return Response({"success": False, "error": "Failed to resend OTP."}, status=500)
    else:
        log_action(
            request,
            "login",
            "system",
            challenge.user.id,
            f"Review OTP bypass challenge resent: {challenge.user.username}",
        )

    return Response(
        {
            "success": True,
            "message": ("Review OTP challenge refreshed." if bypass_enabled_for_user else "OTP resent successfully."),
            "expires_in_seconds": otp_expiry_minutes * 60,
            "email_masked": mask_email_for_display(challenge.user.email) if challenge.user.email else "",
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_verify_otp_view(request):
    """Verify login OTP and issue JWT tokens."""
    challenge_token = request.data.get("challenge_token", "").strip()
    otp = str(request.data.get("otp", "")).strip()
    if not challenge_token or not otp:
        return Response({"success": False, "error": "challenge_token and otp are required."}, status=400)

    try:
        challenge = LoginOTPChallenge.objects.select_related("user").get(
            challenge_token=challenge_token,
            consumed_at__isnull=True,
        )
    except LoginOTPChallenge.DoesNotExist:
        return Response({"success": False, "error": "Invalid or expired login challenge."}, status=400)

    if challenge.is_expired:
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        return Response({"success": False, "error": "OTP expired. Please login again."}, status=400)

    if challenge.attempt_count >= challenge.max_attempts:
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        return Response({"success": False, "error": "Maximum OTP attempts exceeded."}, status=429)

    if not check_password(otp, challenge.otp_hash):
        LoginOTPChallenge.objects.filter(id=challenge.id).update(attempt_count=F("attempt_count") + 1)
        challenge.refresh_from_db(fields=["attempt_count"])
        return Response(
            {
                "success": False,
                "error": "Invalid OTP.",
                "attempts_left": max(challenge.max_attempts - challenge.attempt_count, 0),
            },
            status=400,
        )

    user = challenge.user
    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at"])

    refresh = RefreshToken.for_user(user)
    log_action(request, "login", "system", user.id, f"User logged in with OTP: {user.username}")

    return Response(
        {
            "success": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
    )


# ========================================
# Admin: Members
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_members_list(request):
    """List all members with search and filtering."""
    qs = User.objects.filter(is_deleted=False, role="member").order_by("-date_joined")

    # Search
    search = request.query_params.get("search", "")
    if search:
        from django.db.models import Q

        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(member_id__icontains=search)
            | Q(mobile_primary__icontains=search)
        )

    # Filters
    member_status = request.query_params.get("status", "")
    if member_status:
        qs = qs.filter(status=member_status)

    member_type = request.query_params.get("member_type", "")
    if member_type:
        qs = qs.filter(member_type=member_type)

    # Pagination
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 20))
    page = paginator.paginate_queryset(qs, request)
    serializer = UserListSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_members_create(request):
    """Create a new member."""
    serializer = UserCreateSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        log_action(request, "create", "member", user.id, f"Created member via API: {user.display_name}")

        # Apply fund allocation rules for member_registration
        apply_fund_allocations(
            request,
            "member_registration",
            Decimal("200"),
            f"Member registration: {user.display_name}",
            source_member=user,
        )

        return Response(UserDetailSerializer(user).data, status=status.HTTP_201_CREATED)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_members_detail(request, user_id):
    """Get member detail."""
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
    except User.DoesNotExist:
        return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UserDetailSerializer(user)
    data = serializer.data

    # Include accounts and loans summary
    data["accounts"] = MemberAccountSerializer(
        MemberAccount.objects.filter(user=user, is_deleted=False), many=True
    ).data
    data["active_loans"] = LoanListSerializer(
        LoanAccount.objects.filter(user=user, status="active").select_related("application", "user"),
        many=True,
    ).data

    return Response(data)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAdmin])
def admin_members_update(request, user_id):
    """Update member details."""
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
    except User.DoesNotExist:
        return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UserDetailSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        log_action(request, "update", "member", user.id, f"Updated member via API: {user.display_name}")
        return Response(serializer.data)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def admin_members_delete(request, user_id):
    """Soft-delete a member."""
    try:
        user = User.objects.get(id=user_id, is_deleted=False)
    except User.DoesNotExist:
        return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    from django.utils import timezone

    user.is_deleted = True
    user.deleted_at = timezone.now()
    user.is_active = False
    user.save()
    log_action(request, "delete", "member", user.id, f"Deleted member via API: {user.display_name}")
    return Response(status=status.HTTP_204_NO_CONTENT)


# ========================================
# Admin: Accounts
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_accounts_list(request):
    """List all member accounts."""
    qs = MemberAccount.objects.filter(is_deleted=False).select_related("user").order_by("-created_at")

    account_type = request.query_params.get("type", "")
    if account_type:
        qs = qs.filter(account_type=account_type)

    account_status = request.query_params.get("status", "")
    if account_status:
        qs = qs.filter(status=account_status)

    user_id = request.query_params.get("user", "")
    if user_id:
        qs = qs.filter(user_id=user_id)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = MemberAccountSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_accounts_create(request):
    """Create a new member account."""
    serializer = MemberAccountCreateSerializer(data=request.data)
    if serializer.is_valid():
        # Generate account number
        year = date.today().year
        acc_type = serializer.validated_data["account_type"].upper()
        last_acc = (
            MemberAccount.objects.filter(account_number__startswith=f"{acc_type}-{year}")
            .order_by("-account_number")
            .first()
        )
        if last_acc:
            try:
                last_seq = int(last_acc.account_number.split("-")[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        account = serializer.save(
            account_number=f"{acc_type}-{year}-{next_seq:05d}",
            balance=serializer.validated_data.get("principal_amount", Decimal("0.00")),
        )
        log_action(request, "create", "account", account.id, f"Created account via API: {account.account_number}")
        # Phase B4: auto-post membership fee (once per user per FY).
        from accounts.services import fees as fee_service

        fee_service.apply_membership_fee(
            account.user,
            member_account=account,
            actor=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            audit_via="api",
        )
        return Response(MemberAccountSerializer(account).data, status=status.HTTP_201_CREATED)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_accounts_detail(request, account_id):
    """Get account detail with recent transactions."""
    try:
        account = MemberAccount.objects.select_related("user").get(id=account_id, is_deleted=False)
    except MemberAccount.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

    data = MemberAccountSerializer(account).data
    data["recent_transactions"] = TransactionSerializer(
        Transaction.objects.filter(member_account=account).order_by("-created_at")[:20], many=True
    ).data
    return Response(data)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAdmin])
def admin_accounts_update(request, account_id):
    """Update account details."""
    try:
        account = MemberAccount.objects.get(id=account_id, is_deleted=False)
    except MemberAccount.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = MemberAccountSerializer(account, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        log_action(request, "update", "account", account.id, f"Updated account via API: {account.account_number}")
        return Response(serializer.data)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def admin_accounts_delete(request, account_id):
    """Soft-delete an account."""
    try:
        account = MemberAccount.objects.get(id=account_id, is_deleted=False)
    except MemberAccount.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

    if account.balance > 0:
        return Response({"error": "Cannot delete account with positive balance"}, status=status.HTTP_400_BAD_REQUEST)

    from django.utils import timezone

    account.is_deleted = True
    account.deleted_at = timezone.now()
    account.status = "closed"
    account.save()
    log_action(request, "delete", "account", account.id, f"Deleted account via API: {account.account_number}")
    return Response(status=status.HTTP_204_NO_CONTENT)


# ========================================
# Admin: Transactions
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_transactions_list(request):
    """List all transactions."""
    qs = Transaction.objects.select_related("user", "member_account", "instrument").order_by("-created_at")

    txn_type = request.query_params.get("type", "")
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)

    user_id = request.query_params.get("user", "")
    if user_id:
        qs = qs.filter(user_id=user_id)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = TransactionSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_transactions_create(request):
    """Create a transaction (delegates to `services.transactions.post_transaction`)."""
    serializer = TransactionCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    inst_payload = data.get("instrument") or None
    try:
        txn = transaction_service.post_transaction(
            member_account_id=data["member_account"],
            transaction_type=data["transaction_type"],
            amount=data["amount"],
            description=data.get("description", ""),
            payment_mode=data.get("payment_mode", "cash"),
            reference_number=data.get("reference_number", ""),
            instrument_payload=inst_payload,
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)

    dispatch_user_notification(
        user=txn.user,
        title="Transaction Update",
        message=(
            f"{txn.transaction_type.title()} of \u20b9{txn.amount} "
            f"posted to account {txn.member_account.account_number}."
        ),
        notification_type="transaction",
        metadata={
            "transaction_id": txn.id,
            "transaction_number": txn.transaction_number,
            "account_id": txn.member_account_id,
            "transaction_type": txn.transaction_type,
            "amount": str(txn.amount),
        },
        email_template="payment_success",
    )

    txn = Transaction.objects.select_related("user", "member_account", "instrument").get(pk=txn.pk)
    return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_transactions_detail(request, transaction_id):
    """Get transaction detail."""
    try:
        txn = Transaction.objects.select_related("user", "member_account", "instrument").get(id=transaction_id)
    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(TransactionSerializer(txn).data)


# ========================================
# Admin: Loans
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_loans_list(request):
    """List loan accounts and open applications (merged)."""
    accounts_qs = LoanAccount.objects.select_related("application", "user").all()
    open_apps_qs = (
        LoanApplication.objects.filter(status__in=["pending", "rejected"])
        .select_related("user")
        .exclude(pk__in=LoanAccount.objects.values_list("application_id", flat=True))
    )

    loan_status = request.query_params.get("status", "")
    if loan_status:
        if loan_status in ("active", "closed", "defaulted", "written_off"):
            accounts_qs = accounts_qs.filter(status=loan_status)
            open_apps_qs = open_apps_qs.none()
        elif loan_status in ("pending", "rejected"):
            accounts_qs = accounts_qs.none()
            open_apps_qs = open_apps_qs.filter(status=loan_status)
        else:
            accounts_qs = accounts_qs.none()
            open_apps_qs = open_apps_qs.none()

    loan_type = request.query_params.get("type", "")
    if loan_type:
        accounts_qs = accounts_qs.filter(application__loan_type=loan_type)
        open_apps_qs = open_apps_qs.filter(loan_type=loan_type)

    user_id = request.query_params.get("user", "")
    if user_id:
        accounts_qs = accounts_qs.filter(user_id=user_id)
        open_apps_qs = open_apps_qs.filter(user_id=user_id)

    rows = [LoanListItem(account=a) for a in accounts_qs.order_by("-created_at")]
    rows.extend(LoanListItem(application=a) for a in open_apps_qs.order_by("-created_at"))
    rows.sort(key=lambda r: r.created_at, reverse=True)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(rows, request)
    data = [loan_merged_list_dict(r) for r in page]
    return paginator.get_paginated_response(data)


def _service_error_to_response(exc):
    """Translate a `ServiceError` into an HTTP `Response`.

    Maps exception subclass → status code:
        NotFoundError         → 404
        PermissionDeniedError → 403
        ConflictError         → 409 (includes FinancialPeriodError)
        ValidationError       → 400 (default for any other ServiceError)
    """
    if isinstance(exc, NotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PermissionDeniedError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, ConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return Response({"error": exc.message}, status=code)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_loans_create(request):
    """Create a new loan application (delegates to `services.loans.create_loan_application`)."""
    serializer = LoanCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    try:
        app = loan_service.create_loan_application(
            user_id=data.get("user"),
            loan_type=data.get("loan_type"),
            principal_amount=data.get("principal_amount"),
            interest_rate=data.get("interest_rate"),
            interest_type=data.get("interest_type", "reducing"),
            tenure_months=data.get("tenure_months"),
            purpose=data.get("purpose") or "",
            guarantor_name=data.get("guarantor_name") or "",
            guarantor_member_id=data.get("guarantor_member_id") or "",
            guarantor_contact=data.get("guarantor_contact") or "",
            collateral_type=data.get("collateral_type") or "",
            collateral_value=data.get("collateral_value"),
            processing_fee=data.get("processing_fee") or Decimal("0"),
            disbursement_account_id=data.get("disbursement_account"),
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)

    return Response(LoanApplicationDetailSerializer(app).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_loans_detail(request, loan_id):
    """Get loan application or account detail. Use ?kind=application|account to disambiguate."""
    kind = request.query_params.get("kind", "").strip()

    if kind == "application":
        try:
            app = LoanApplication.objects.select_related("user", "approved_by", "created_by").get(id=loan_id)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
        data = LoanApplicationDetailSerializer(app).data
        data["repayments"] = []
        return Response(data)

    ac_select = (
        "application",
        "user",
        "disbursement_account",
        "created_by",
        "application__approved_by",
        "application__created_by",
    )

    if kind == "account":
        try:
            ac = LoanAccount.objects.select_related(*ac_select).get(id=loan_id)
        except LoanAccount.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
        data = LoanDetailSerializer(ac).data
        data["repayments"] = LoanRepaymentSerializer(
            LoanRepayment.objects.filter(loan_account=ac).order_by("installment_number"), many=True
        ).data
        return Response(data)

    try:
        ac = LoanAccount.objects.select_related(*ac_select).get(id=loan_id)
        data = LoanDetailSerializer(ac).data
        data["repayments"] = LoanRepaymentSerializer(
            LoanRepayment.objects.filter(loan_account=ac).order_by("installment_number"), many=True
        ).data
        return Response(data)
    except LoanAccount.DoesNotExist:
        pass

    try:
        app = LoanApplication.objects.select_related("user", "approved_by", "created_by").get(id=loan_id)
        data = LoanApplicationDetailSerializer(app).data
        data["repayments"] = []
        return Response(data)
    except LoanApplication.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_loans_approve(request, loan_id):
    """Approve a pending LoanApplication (delegates to `services.loans.approve_loan_application`)."""
    raw_acct = request.data.get("disbursement_account")
    disbursement_account_id = None
    if raw_acct not in (None, ""):
        try:
            disbursement_account_id = int(raw_acct)
        except (TypeError, ValueError):
            return Response({"error": "Invalid disbursement account ID."}, status=status.HTTP_400_BAD_REQUEST)

    processing_fee = request.data.get("processing_fee")
    if processing_fee is not None and str(processing_fee).strip() == "":
        processing_fee = None

    try:
        acct = loan_service.approve_loan_application(
            application_id=loan_id,
            disbursement_date=request.data.get("disbursement_date"),
            disbursement_account_id=disbursement_account_id,
            processing_fee=processing_fee,
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)

    dispatch_user_notification(
        user=acct.user,
        title="Loan Approved",
        message=f"Your loan {acct.loan_number} has been approved and is now active.",
        notification_type="loan",
        metadata={"loan_id": acct.id, "loan_number": acct.loan_number, "status": acct.status},
        email_template="loan_approval",
    )

    return Response(LoanDetailSerializer(acct).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_loans_record_emi(request, loan_id):
    """Record an EMI payment (delegates to `services.loans.record_emi_payment`)."""
    try:
        result = loan_service.record_emi_payment(
            loan_account_id=loan_id,
            installment_number=request.data.get("installment_number"),
            amount_paid=request.data.get("amount_paid"),
            payment_mode=request.data.get("payment_mode", "cash"),
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)

    repayment = result["repayment"]
    loan_ac = result["loan_account"]
    penalty = result["penalty"]

    dispatch_user_notification(
        user=loan_ac.user,
        title="EMI Payment Recorded",
        message=f"EMI #{repayment.installment_number} of \u20b9{repayment.amount_paid} recorded for {loan_ac.loan_number}.",
        notification_type="loan",
        metadata={
            "loan_id": loan_ac.id,
            "loan_number": loan_ac.loan_number,
            "installment_number": int(repayment.installment_number),
            "amount_paid": str(repayment.amount_paid),
            "penalty": str(penalty),
        },
        email_template="payment_success",
    )

    return Response(
        {
            "success": True,
            "repayment": LoanRepaymentSerializer(repayment).data,
            "loan_status": loan_ac.status,
            "outstanding_balance": str(loan_ac.outstanding_balance),
            "penalty": str(penalty),
        }
    )


# ========================================
# Admin: Funds
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_funds_list(request):
    """List all funds."""
    funds = FundAccount.objects.filter(is_deleted=False).order_by("name")
    return Response(FundAccountSerializer(funds, many=True).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_funds_create(request):
    """Create a new fund."""
    serializer = FundAccountSerializer(data=request.data)
    if serializer.is_valid():
        # Generate account number
        fund_type = serializer.validated_data["fund_type"].upper()
        last_fund = (
            FundAccount.objects.filter(account_number__startswith=f"FND-{fund_type}")
            .order_by("-account_number")
            .first()
        )
        next_seq = 1
        if last_fund:
            try:
                next_seq = int(last_fund.account_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                pass

        fund = serializer.save(
            account_number=f"FND-{fund_type}-{next_seq:03d}",
            created_by=request.user,
        )
        log_action(request, "create", "fund", fund.id, f"Created fund via API: {fund.name}")
        return Response(FundAccountSerializer(fund).data, status=status.HTTP_201_CREATED)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_funds_detail(request, fund_id):
    """Get fund detail with transactions."""
    try:
        fund = FundAccount.objects.get(id=fund_id, is_deleted=False)
    except FundAccount.DoesNotExist:
        return Response({"error": "Fund not found"}, status=status.HTTP_404_NOT_FOUND)

    data = FundAccountSerializer(fund).data
    data["transactions"] = FundTransactionSerializer(
        FundTransaction.objects.filter(fund=fund).order_by("-created_at")[:50], many=True
    ).data
    return Response(data)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAdmin])
def admin_funds_update(request, fund_id):
    """Update fund details."""
    try:
        fund = FundAccount.objects.get(id=fund_id, is_deleted=False)
    except FundAccount.DoesNotExist:
        return Response({"error": "Fund not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = FundAccountSerializer(fund, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        log_action(request, "update", "fund", fund.id, f"Updated fund via API: {fund.name}")
        return Response(serializer.data)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def admin_funds_delete(request, fund_id):
    """Soft-delete a fund."""
    try:
        fund = FundAccount.objects.get(id=fund_id, is_deleted=False)
    except FundAccount.DoesNotExist:
        return Response({"error": "Fund not found"}, status=status.HTTP_404_NOT_FOUND)

    from django.utils import timezone

    fund.is_deleted = True
    fund.deleted_at = timezone.now()
    fund.save()
    log_action(request, "delete", "fund", fund.id, f"Deleted fund via API: {fund.name}")
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_funds_add_transaction(request, fund_id):
    """Add a transaction to a fund."""
    try:
        with transaction.atomic():
            fund = FundAccount.objects.select_for_update().get(id=fund_id, is_deleted=False)

            txn_type = request.data.get("transaction_type")
            amount = Decimal(str(request.data.get("amount", "0")))
            description = request.data.get("description", "")

            if amount <= 0:
                return Response({"error": "Amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)

            if txn_type == "debit" and fund.balance < amount:
                return Response({"error": "Insufficient fund balance"}, status=status.HTTP_400_BAD_REQUEST)

            if txn_type == "credit":
                new_balance = fund.balance + amount
                FundAccount.objects.filter(id=fund.id).update(balance=F("balance") + amount)
            else:
                new_balance = fund.balance - amount
                FundAccount.objects.filter(id=fund.id).update(balance=F("balance") - amount)

            fund_txn = FundTransaction.objects.create(
                fund=fund,
                transaction_type=txn_type,
                amount=amount,
                description=description,
                balance_after=new_balance,
                payment_mode=request.data.get("payment_mode", "internal"),
                created_by=request.user,
            )
            log_action(
                request, "create", "fund", fund.id, f"Fund transaction via API: {txn_type} ₹{amount} - {fund.name}"
            )

        return Response(FundTransactionSerializer(fund_txn).data, status=status.HTTP_201_CREATED)

    except FundAccount.DoesNotExist:
        return Response({"error": "Fund not found"}, status=status.HTTP_404_NOT_FOUND)


# ========================================
# Admin: Allocation Rules
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_allocation_rules_list(request):
    """List all allocation rules."""
    rules = FundAllocationRule.objects.select_related("fund").all()
    return Response(FundAllocationRuleSerializer(rules, many=True).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_allocation_rules_create(request):
    """Create an allocation rule."""
    serializer = FundAllocationRuleSerializer(data=request.data)
    if serializer.is_valid():
        rule = serializer.save(created_by=request.user)
        log_action(request, "create", "fund", rule.id, f"Created allocation rule via API: {rule}")
        return Response(FundAllocationRuleSerializer(rule).data, status=status.HTTP_201_CREATED)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAdmin])
def admin_allocation_rules_update(request, rule_id):
    """Update an allocation rule."""
    try:
        rule = FundAllocationRule.objects.get(id=rule_id)
    except FundAllocationRule.DoesNotExist:
        return Response({"error": "Rule not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = FundAllocationRuleSerializer(rule, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def admin_allocation_rules_delete(request, rule_id):
    """Delete an allocation rule."""
    try:
        rule = FundAllocationRule.objects.get(id=rule_id)
    except FundAllocationRule.DoesNotExist:
        return Response({"error": "Rule not found"}, status=status.HTTP_404_NOT_FOUND)

    rule.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ========================================
# Admin: Reports
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_reports_summary(request):
    """Get financial summary for a period."""
    from accounts.utils import get_financial_summary

    period = request.query_params.get("period", "year")
    year = int(request.query_params.get("year", date.today().year))

    if period == "month":
        import calendar

        month = int(request.query_params.get("month", date.today().month))
        start_date = date(year, month, 1)
        end_date = date(year, month, calendar.monthrange(year, month)[1])
    elif period == "quarter":
        import calendar

        quarter = int(request.query_params.get("quarter", (date.today().month - 1) // 3 + 1))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        start_date = date(year, start_month, 1)
        end_date = date(year, end_month, calendar.monthrange(year, end_month)[1])
    else:
        start_date = date(year, 4, 1)
        end_date = date(year + 1, 3, 31)

    summary = get_financial_summary(start_date, end_date)
    summary["period_start"] = str(start_date)
    summary["period_end"] = str(end_date)

    return Response(summary)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_reports_distribute_profit(request):
    """Distribute annual profit to funds from locked P&L ``net_surplus`` (Phase A6).

    Body: optional ``financial_period_id`` (preferred), or ``year`` (April–March FY start year)
    to resolve the period via overlap.
    """
    fp = None
    fp_raw = request.data.get("financial_period_id")
    if fp_raw is not None and str(fp_raw).strip().isdigit():
        fp = get_object_or_404(FinancialPeriod, pk=int(str(fp_raw).strip()))
    else:
        year = int(request.data.get("year", date.today().year))
        start_date = date(year, 4, 1)
        end_date = date(year + 1, 3, 31)
        fp = financial_period_overlapping(start_date, end_date)

    if not fp:
        return Response({"error": "No financial period for the given year or id."}, status=status.HTTP_400_BAD_REQUEST)

    pl = ProfitAndLoss.objects.filter(financial_period=fp).first()
    if not pl:
        return Response(
            {"error": "No P&L snapshot for this financial period. Save a snapshot first."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not pl.is_locked:
        return Response(
            {"error": "P&L is not locked for this period. Close the financial year before distributing."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    net_surplus = pl.net_surplus
    if net_surplus <= 0:
        return Response(
            {"error": f"No distributable surplus for {fp.label}. Locked net surplus: ₹{net_surplus}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    transactions = apply_fund_allocations(
        request,
        "annual_profit",
        net_surplus,
        f"Annual profit distribution for {fp.label} (locked P&L net surplus)",
    )

    if not transactions:
        return Response(
            {"error": "No allocation rules configured for 'Annual Profit'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    total_allocated = sum(t.amount for t in transactions)
    log_action(
        request,
        "create",
        "fund",
        None,
        f"Distributed locked P&L surplus ₹{net_surplus} for {fp.label} via API. Allocated ₹{total_allocated}.",
    )

    return Response(
        {
            "financial_period_id": fp.id,
            "net_surplus": str(net_surplus),
            "total_allocated": str(total_allocated),
            "allocations": FundTransactionSerializer(transactions, many=True).data,
        }
    )


# ========================================
# Admin: Audit Logs
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_audit_logs_list(request):
    """List audit logs."""
    qs = AuditLog.objects.select_related("user").order_by("-created_at")

    action = request.query_params.get("action", "")
    if action:
        qs = qs.filter(action=action)

    entity_type = request.query_params.get("entity_type", "")
    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 50))
    page = paginator.paginate_queryset(qs, request)
    serializer = AuditLogSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ========================================
# Admin: Phase 4 finance (fees, receivables, snapshots)
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_fee_schedules_list(request):
    qs = FeeSchedule.objects.all().order_by("-effective_date", "fee_type")
    active = request.query_params.get("is_active", "")
    if active.lower() in ("true", "1", "yes"):
        qs = qs.filter(is_active=True)
    elif active.lower() in ("false", "0", "no"):
        qs = qs.filter(is_active=False)
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 50))
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(FeeScheduleSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_fee_charges_list(request):
    qs = FeeCharge.objects.select_related("fee_schedule", "user", "loan_account").order_by("-created_at")
    status_filter = request.query_params.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)
    user_id = request.query_params.get("user_id", "")
    if user_id.isdigit():
        qs = qs.filter(user_id=int(user_id))
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 50))
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(FeeChargeSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_interest_receivables_list(request):
    qs = InterestReceivable.objects.select_related("loan_account", "financial_period").order_by("-due_date")
    st = request.query_params.get("status", "")
    if st:
        qs = qs.filter(status=st)
    loan_id = request.query_params.get("loan_account_id", "")
    if loan_id.isdigit():
        qs = qs.filter(loan_account_id=int(loan_id))
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 50))
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(InterestReceivableSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_profit_loss_list(request):
    qs = ProfitAndLoss.objects.select_related("financial_period", "calculated_by").order_by("-calculation_date")
    fp_id = request.query_params.get("financial_period_id", "")
    if fp_id.isdigit():
        qs = qs.filter(financial_period_id=int(fp_id))
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 20))
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(ProfitAndLossSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_profit_loss_detail(request, snapshot_id):
    pl = get_object_or_404(ProfitAndLoss.objects.select_related("financial_period"), pk=snapshot_id)
    return Response(ProfitAndLossSerializer(pl).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_society_snapshots_list(request):
    qs = SocietyAccount.objects.select_related("financial_period").order_by("-last_updated")
    fp_id = request.query_params.get("financial_period_id", "")
    if fp_id.isdigit():
        qs = qs.filter(financial_period_id=int(fp_id))
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get("page_size", 20))
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(SocietyAccountSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_society_main_account(request):
    """Phase B5: Society Main Account — live derived totals + snapshot comparison.

    Returns the society's live financial position computed from the database,
    the stored SocietyAccount snapshot for the active (or requested) FY, and
    a field-by-field drift comparison.

    Query params:
        financial_period_id (optional): target a specific FY instead of the active one.
    """
    from accounts.services import society as society_service

    fp = None
    fp_id = request.query_params.get("financial_period_id", "")
    if fp_id.isdigit():
        fp = FinancialPeriod.objects.filter(id=int(fp_id)).first()
        if not fp:
            return Response(
                {"error": f"FinancialPeriod with id={fp_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    result = society_service.get_main_account(financial_period=fp)

    # Serialize Decimal values to strings for JSON safety.
    def _serialize_position(pos):
        if pos is None:
            return None
        return {k: str(v) if isinstance(v, Decimal) else v for k, v in pos.items()}

    return Response({
        "financial_period": result["financial_period"],
        "live": _serialize_position(result["live"]),
        "snapshot": _serialize_position(result["snapshot"]),
        "drift": _serialize_position(result["drift"]),
        "snapshot_stale": result["snapshot_stale"],
    })


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_finance_save_snapshot(request):
    """Persist ProfitAndLoss + SocietyAccount from computed summary for a financial period."""
    pid = request.data.get("financial_period_id")
    if pid:
        fp = get_object_or_404(FinancialPeriod, pk=pid)
    else:
        fp = active_financial_period()
        if not fp:
            return Response(
                {"error": "No active financial period; pass financial_period_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    pl_row, soc_row, pl_updated = persist_financial_snapshots(fp, calculated_by=request.user)
    log_action(
        request,
        "create",
        "system",
        None,
        f"Saved financial snapshot for {fp.label} (P&L updated={pl_updated}).",
    )
    return Response(
        {
            "profit_and_loss": ProfitAndLossSerializer(pl_row).data,
            "society_account": SocietyAccountSerializer(soc_row).data,
            "profit_and_loss_updated": pl_updated,
        }
    )


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_finance_sync_receivables(request):
    """Create/update InterestReceivable rows from unpaid EMIs due on or before as_of_date."""
    as_of = date.today()
    raw = request.data.get("as_of_date") or request.query_params.get("as_of_date")
    if raw:
        try:
            as_of = datetime.strptime(str(raw), "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "as_of_date must be YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

    fp = None
    fp_id = request.data.get("financial_period_id") or request.query_params.get("financial_period_id")
    if fp_id:
        fp = get_object_or_404(FinancialPeriod, pk=fp_id)

    n = sync_loan_interest_receivables(as_of_date=as_of, financial_period=fp)
    log_action(
        request,
        "update",
        "system",
        None,
        f"Synced loan interest receivables as of {as_of} ({n} installments).",
    )
    return Response({"as_of_date": str(as_of), "installments_considered": n})


# ========================================
# Member: Dashboard
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_dashboard(request):
    """Member dashboard with account summary."""
    user = request.user

    accounts = MemberAccount.objects.filter(user=user, is_deleted=False, status="active")
    active_loans = LoanAccount.objects.filter(user=user, status="active").select_related("application", "user")
    recent_txns = Transaction.objects.filter(user=user).select_related("member_account")[:10]

    return Response(
        {
            "member": MemberProfileSerializer(user).data,
            "total_accounts": accounts.count(),
            "total_balance": str(sum(a.balance for a in accounts)),
            "total_active_loans": active_loans.count(),
            "total_outstanding": str(sum(loan.outstanding_balance for loan in active_loans)),
            "share_capital": str(user_active_share_capital_total(user)),
            "dividend_payable": str(user.dividend_payable_balance),
            "accounts": MemberAccountSerializer(accounts[:5], many=True).data,
            "active_loans": LoanListSerializer(active_loans[:5], many=True).data,
            "recent_transactions": TransactionSerializer(recent_txns, many=True).data,
        }
    )


# ========================================
# Member: Accounts
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_accounts_list(request):
    """List member's own accounts."""
    qs = MemberAccount.objects.filter(user=request.user, is_deleted=False).order_by("-created_at")

    account_type = request.query_params.get("type", "")
    if account_type:
        qs = qs.filter(account_type=account_type)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(MemberAccountSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsMember])
def member_accounts_detail(request, account_id):
    """Get member's account detail with transactions."""
    try:
        account = MemberAccount.objects.get(id=account_id, user=request.user, is_deleted=False)
    except MemberAccount.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

    data = MemberAccountSerializer(account).data
    data["transactions"] = TransactionSerializer(
        Transaction.objects.filter(member_account=account).order_by("-created_at")[:50], many=True
    ).data
    return Response(data)


# ========================================
# Member: Loans
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_loans_list(request):
    """List member's loan accounts and open applications."""
    user = request.user
    accounts_qs = LoanAccount.objects.filter(user=user).select_related("application", "user")
    open_apps_qs = (
        LoanApplication.objects.filter(user=user, status__in=["pending", "rejected"])
        .select_related("user")
        .exclude(pk__in=LoanAccount.objects.filter(user=user).values_list("application_id", flat=True))
    )

    loan_status = request.query_params.get("status", "")
    if loan_status:
        if loan_status in ("active", "closed", "defaulted", "written_off"):
            accounts_qs = accounts_qs.filter(status=loan_status)
            open_apps_qs = open_apps_qs.none()
        elif loan_status in ("pending", "rejected"):
            accounts_qs = accounts_qs.none()
            open_apps_qs = open_apps_qs.filter(status=loan_status)
        else:
            accounts_qs = accounts_qs.none()
            open_apps_qs = open_apps_qs.none()

    rows = [LoanListItem(account=a) for a in accounts_qs.order_by("-created_at")]
    rows.extend(LoanListItem(application=a) for a in open_apps_qs.order_by("-created_at"))
    rows.sort(key=lambda r: r.created_at, reverse=True)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(rows, request)
    data = [loan_merged_list_dict(r) for r in page]
    return paginator.get_paginated_response(data)


@api_view(["GET"])
@permission_classes([IsMember])
def member_loans_detail(request, loan_id):
    """Get member's loan application or account. Use ?kind=application|account to disambiguate."""
    user = request.user
    kind = request.query_params.get("kind", "").strip()

    if kind == "application":
        try:
            app = LoanApplication.objects.get(id=loan_id, user=user)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
        data = LoanApplicationDetailSerializer(app).data
        data["repayments"] = []
        return Response(data)

    ac_select = (
        "application",
        "user",
        "disbursement_account",
        "created_by",
        "application__approved_by",
        "application__created_by",
    )

    if kind == "account":
        try:
            ac = LoanAccount.objects.select_related(*ac_select).get(id=loan_id, user=user)
        except LoanAccount.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
        data = LoanDetailSerializer(ac).data
        data["repayments"] = LoanRepaymentSerializer(
            LoanRepayment.objects.filter(loan_account=ac).order_by("installment_number"), many=True
        ).data
        return Response(data)

    try:
        ac = LoanAccount.objects.select_related(*ac_select).get(id=loan_id, user=user)
        data = LoanDetailSerializer(ac).data
        data["repayments"] = LoanRepaymentSerializer(
            LoanRepayment.objects.filter(loan_account=ac).order_by("installment_number"), many=True
        ).data
        return Response(data)
    except LoanAccount.DoesNotExist:
        pass

    try:
        app = LoanApplication.objects.select_related("user", "approved_by", "created_by").get(id=loan_id, user=user)
        data = LoanApplicationDetailSerializer(app).data
        data["repayments"] = []
        return Response(data)
    except LoanApplication.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)


# ========================================
# Member: Transactions
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_transactions_list(request):
    """List member's transactions across all accounts."""
    qs = Transaction.objects.filter(user=request.user).select_related("member_account").order_by("-created_at")

    txn_type = request.query_params.get("type", "")
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)

    account_id = request.query_params.get("account", "")
    if account_id:
        qs = qs.filter(member_account_id=account_id)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(TransactionSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsMember])
def member_transactions_detail(request, transaction_id):
    """Get a single member transaction/receipt detail."""
    try:
        receipt = Transaction.objects.select_related("member_account").get(id=transaction_id, user=request.user)
    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(TransactionSerializer(receipt).data)


@api_view(["GET"])
@permission_classes([IsMember])
def member_notifications_list(request):
    """List member notifications with unread count."""
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")

    unread_only = request.query_params.get("unread", "")
    if unread_only.lower() in ["1", "true", "yes"]:
        qs = qs.filter(is_read=False)

    from rest_framework.pagination import PageNumberPagination

    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    data = NotificationSerializer(page, many=True).data

    return Response(
        {
            "count": qs.count(),
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "unread_count": unread_count,
            "results": data,
        }
    )


@api_view(["POST"])
@permission_classes([IsMember])
def member_notifications_mark_read(request, notification_id):
    """Mark a single notification as read."""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        return Response({"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])

    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsMember])
def member_notifications_mark_all_read(request):
    """Mark all member notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    return Response({"success": True})


@api_view(["GET", "POST"])
@permission_classes([IsMember])
def member_push_preferences_view(request):
    """Get or update push notification preference for the member."""
    if request.method == "GET":
        return Response({"push_notifications_enabled": request.user.push_notifications_enabled})

    enabled = request.data.get("push_notifications_enabled")
    if enabled is None:
        return Response({"success": False, "error": "push_notifications_enabled is required."}, status=400)

    request.user.push_notifications_enabled = bool(enabled)
    request.user.save(update_fields=["push_notifications_enabled"])
    return Response(
        {
            "success": True,
            "push_notifications_enabled": request.user.push_notifications_enabled,
        }
    )


@api_view(["POST"])
@permission_classes([IsMember])
def member_notifications_test_push_view(request):
    """Send one demo FCM message (rate-limited)."""
    if not request.user.push_notifications_enabled:
        return Response({"success": False, "error": "Turn on push notifications first."}, status=400)

    rate_key = f"member_push_test:{request.user.id}"
    sent_count = cache.get(rate_key, 0)
    if sent_count >= 5:
        return Response(
            {"success": False, "error": "Too many test notifications. Try again in an hour."},
            status=429,
        )
    cache.set(rate_key, sent_count + 1, timeout=3600)

    result = send_member_test_push(request.user)
    if not result.get("success"):
        reason = result.get("reason", "unknown")
        if reason == "push_disabled":
            return Response({"success": False, "error": "Push is disabled for your account."}, status=400)
        if reason == "fcm_disabled":
            return Response({"success": False, "error": "Push service is not configured on the server."}, status=503)
        if reason == "no_devices":
            return Response(
                {
                    "success": False,
                    "error": "No device registered. Open the app while logged in to register this phone.",
                },
                status=400,
            )
        if reason == "sdk_missing":
            return Response({"success": False, "error": "Push SDK missing on server."}, status=503)
        return Response({"success": False, "error": "Could not send test notification."}, status=500)

    return Response(
        {
            "success": True,
            "message": "Test notification sent.",
            "delivered": result.get("delivered", 0),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_device_token_view(request):
    """Register or update FCM device token for current user."""
    token = request.data.get("token", "").strip()
    platform = request.data.get("platform", "android").strip().lower()

    if not token:
        return Response({"success": False, "error": "token is required."}, status=400)

    if platform not in ["android", "ios", "web"]:
        return Response({"success": False, "error": "Invalid platform."}, status=400)

    device, _ = UserDevice.objects.update_or_create(
        token=token,
        defaults={
            "user": request.user,
            "platform": platform,
            "is_active": True,
        },
    )
    return Response({"success": True, "device_id": device.id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unregister_device_token_view(request):
    """Deactivate FCM device token for current user."""
    token = request.data.get("token", "").strip()
    if not token:
        return Response({"success": False, "error": "token is required."}, status=400)

    UserDevice.objects.filter(user=request.user, token=token).update(is_active=False, last_seen=timezone.now())
    return Response({"success": True})


# ========================================
# Admin: Interest Posting
# ========================================


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_post_interest(request):
    """Calculate and post accrued interest to all eligible deposit accounts.

    Phase B1: delegates to ``accounts.services.interest_engine.accrue_deposits``.
    Same set of accounts (CD/FD/RD/Sukanya/Suputra — `share`+`od` excluded)
    and same per-account window as before. Push / email notifications are
    fired for each posted ``InterestPayout`` after the engine returns.
    """
    fp = active_financial_period()
    result = interest_engine.accrue_deposits(
        as_of=date.today(),
        financial_period=fp,
        actor=request.user,
        ip_address=_get_client_ip(request),
        audit_via="api",
    )

    for payout in result["payouts"]:
        dispatch_user_notification(
            user=payout.account.user,
            title="Interest Credited",
            message=(
                f"\u20b9{payout.amount} interest credited to account "
                f"{payout.account.account_number}."
            ),
            notification_type="transaction",
            metadata={
                "account_id": payout.account.id,
                "account_number": payout.account.account_number,
                "interest_amount": str(payout.amount),
            },
            email_template="interest_credit",
        )

    return Response(
        {
            "success": True,
            "message": (
                f"Posted \u20b9{result['total_posted']} interest to "
                f"{result['accounts_updated']} accounts."
            ),
            "total_posted": str(result["total_posted"]),
            "accounts_updated": result["accounts_updated"],
        }
    )


# ========================================
# Admin: Dividend Distribution
# ========================================


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_distribute_dividend(request):
    """Calculate and distribute dividends to eligible members based on share capital."""
    year = int(request.data.get("year", date.today().year))
    dividend_rate = request.data.get("dividend_rate")

    if not dividend_rate:
        return Response({"error": "dividend_rate is required"}, status=status.HTTP_400_BAD_REQUEST)

    dividend_rate = Decimal(str(dividend_rate))
    if dividend_rate <= 0 or dividend_rate > 100:
        return Response({"error": "dividend_rate must be between 0.01 and 100"}, status=status.HTTP_400_BAD_REQUEST)

    eligible_members = (
        User.objects.filter(
            is_deleted=False,
            status="active",
            eligible_for_dividend=True,
        )
        .annotate(
            share_capital_total=Coalesce(
                Sum(
                    "share_holdings__total_value",
                    filter=Q(
                        share_holdings__status="issued",
                        share_holdings__redemption_date__isnull=True,
                    ),
                ),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .filter(share_capital_total__gt=0)
    )

    if not eligible_members.exists():
        return Response({"error": "No eligible members with share capital"}, status=status.HTTP_400_BAD_REQUEST)

    total_distributed = Decimal("0.00")
    member_count = 0

    with transaction.atomic():
        for member in eligible_members:
            dividend_amount = (member.share_capital_total * dividend_rate / Decimal("100")).quantize(Decimal("0.01"))
            if dividend_amount <= 0:
                continue

            User.objects.filter(id=member.id).update(
                dividend_payable_balance=F("dividend_payable_balance") + dividend_amount,
                last_dividend_paid_date=date.today(),
            )

            total_distributed += dividend_amount
            member_count += 1

        # Deduct from Dividend Fund
        dividend_fund = FundAccount.objects.filter(fund_type="dividend", is_deleted=False, is_active=True).first()
        if dividend_fund:
            new_balance = dividend_fund.balance - total_distributed
            FundAccount.objects.filter(id=dividend_fund.id).update(balance=F("balance") - total_distributed)
            FundTransaction.objects.create(
                fund=dividend_fund,
                transaction_type="debit",
                amount=total_distributed,
                description=f"Dividend distribution FY {year}-{year + 1} @ {dividend_rate}%",
                payment_mode="internal",
                balance_after=new_balance,
                trigger_event="manual",
                created_by=request.user,
            )

    return Response(
        {
            "success": True,
            "message": f"Distributed ₹{total_distributed} @ {dividend_rate}% to {member_count} members.",
            "total_distributed": str(total_distributed),
            "member_count": member_count,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def email_preferences_view(request):
    """Get or update user email preferences."""
    if request.method == "GET":
        return Response(
            {
                "email_notifications": request.user.email_notifications,
                "sms_notifications": request.user.sms_notifications,
                "email_verified": request.user.email_verified,
                "email": request.user.email,
            }
        )

    elif request.method == "POST":
        email_notifications = request.data.get("email_notifications")
        sms_notifications = request.data.get("sms_notifications")

        if email_notifications is not None:
            request.user.email_notifications = bool(email_notifications)

        if sms_notifications is not None:
            request.user.sms_notifications = bool(sms_notifications)

        request.user.save(update_fields=["email_notifications", "sms_notifications"])

        return Response(
            {
                "success": True,
                "message": "Email preferences updated successfully.",
                "email_notifications": request.user.email_notifications,
                "sms_notifications": request.user.sms_notifications,
            }
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_verification_email_view(request):
    """Send email verification link to user."""
    if request.user.email_verified:
        return Response({"success": False, "error": "Email is already verified."}, status=400)

    if not request.user.email:
        return Response(
            {"success": False, "error": "No email address found. Please update your profile with an email address."},
            status=400,
        )

    success = request.user.send_verification_email()

    if success:
        return Response({"success": True, "message": "Verification email sent successfully."})
    else:
        return Response(
            {"success": False, "error": "Failed to send verification email. Please try again later."}, status=500
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_view(request):
    """Verify email with token."""
    token = request.data.get("token")

    if not token:
        return Response({"success": False, "error": "Verification token is required."}, status=400)

    try:
        user = User.objects.get(email_verification_token=token)
        success = user.verify_email(token)

        if success:
            return Response({"success": True, "message": "Email verified successfully!"})
        else:
            return Response({"success": False, "error": "Invalid or expired verification token."}, status=400)

    except User.DoesNotExist:
        return Response({"success": False, "error": "Invalid verification token."}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_email_change_view(request):
    """Request email change by sending OTP to the new email.

    One pending challenge per user; a new request replaces any previous pending OTP.
    Rate limited to reduce abuse.
    """
    raw = request.data.get("new_email", "")
    new_email, err = _normalize_and_validate_email(raw)
    if err:
        return Response({"success": False, "error": err}, status=400)

    current = (request.user.email or "").strip().lower()
    if new_email == current:
        return Response({"success": False, "error": "New email is same as current email."}, status=400)

    if User.objects.filter(email__iexact=new_email).exclude(id=request.user.id).exists():
        return Response({"success": False, "error": "This email is already in use."}, status=400)

    rate_key = _email_change_rate_limit_key(request.user.id)
    send_count = cache.get(rate_key, 0)
    if send_count >= 5:
        return Response(
            {"success": False, "error": "Too many email change requests. Please try again in an hour."},
            status=429,
        )

    otp_code = _generate_numeric_otp()
    challenge_token = secrets.token_urlsafe(32)
    expires_minutes = 10
    expires_at = timezone.now() + timedelta(minutes=expires_minutes)
    cache_key = _email_change_cache_key(request.user.id)
    cache_payload = {
        "challenge_token": challenge_token,
        "new_email": new_email,
        "otp_hash": make_password(otp_code),
        "expires_at": expires_at.isoformat(),
        "otp_attempts": 0,
    }
    cache.set(cache_key, cache_payload, timeout=expires_minutes * 60)
    cache.set(rate_key, send_count + 1, timeout=3600)

    sent = send_email_change_otp_email(request.user, new_email, otp_code, expires_minutes=expires_minutes)
    if not sent:
        cache.delete(cache_key)
        return Response({"success": False, "error": "Failed to send OTP to new email."}, status=500)

    return Response(
        {
            "success": True,
            "message": "Verification OTP sent to new email.",
            "challenge_token": challenge_token,
            "expires_in_seconds": expires_minutes * 60,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_email_change_view(request):
    """Confirm email change with OTP sent to new email."""
    challenge_token = request.data.get("challenge_token", "").strip()
    otp = request.data.get("otp", "").strip()
    if not challenge_token or not otp:
        return Response({"success": False, "error": "challenge_token and otp are required."}, status=400)

    cache_key = _email_change_cache_key(request.user.id)
    payload = cache.get(cache_key)
    if not payload:
        return Response({"success": False, "error": "Invalid or expired email change challenge."}, status=400)

    if payload.get("challenge_token") != challenge_token:
        return Response({"success": False, "error": "Invalid challenge token."}, status=400)

    expires_at_raw = payload.get("expires_at")
    try:
        expires_at = timezone.datetime.fromisoformat(expires_at_raw)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
    except Exception:
        cache.delete(cache_key)
        return Response({"success": False, "error": "Invalid email change challenge."}, status=400)

    if expires_at <= timezone.now():
        cache.delete(cache_key)
        return Response({"success": False, "error": "OTP expired. Request email change again."}, status=400)

    max_attempts = 5
    attempts = int(payload.get("otp_attempts") or 0)
    otp_hash = payload.get("otp_hash", "")
    if not check_password(otp, otp_hash):
        attempts += 1
        if attempts >= max_attempts:
            cache.delete(cache_key)
            return Response(
                {"success": False, "error": "Too many invalid OTP attempts. Request a new code."},
                status=400,
            )
        payload["otp_attempts"] = attempts
        cache.set(cache_key, payload, timeout=int((expires_at - timezone.now()).total_seconds()) or 60)
        return Response(
            {"success": False, "error": "Invalid OTP.", "attempts_remaining": max_attempts - attempts},
            status=400,
        )

    new_email = payload.get("new_email", "").strip().lower()
    if not new_email:
        cache.delete(cache_key)
        return Response({"success": False, "error": "Invalid email change payload."}, status=400)

    if User.objects.filter(email__iexact=new_email).exclude(id=request.user.id).exists():
        cache.delete(cache_key)
        return Response({"success": False, "error": "This email is already in use."}, status=400)

    old_email = request.user.email
    with transaction.atomic():
        request.user.email = new_email
        request.user.email_verified = True
        request.user.email_verification_token = None
        request.user.email_verification_sent_at = None
        request.user.save(
            update_fields=["email", "email_verified", "email_verification_token", "email_verification_sent_at"]
        )

    cache.delete(cache_key)
    log_action(
        request,
        "update",
        "member",
        request.user.id,
        f"Email changed from {old_email} to {new_email}",
    )
    if old_email and str(old_email).strip():
        send_email_moved_security_notice(old_email, request.user.display_name, new_email)
    send_email_change_confirmed(request.user)
    return Response({"success": True, "message": "Email updated successfully.", "email": request.user.email})


# ============================================================================
# Admin: Financial Periods (Phase A5)
# ----------------------------------------------------------------------------
# Lifecycle endpoints for FinancialPeriod. All business logic lives in
# `accounts.services.financial_period`; these views just translate HTTP into
# service calls and map `ServiceError` subclasses to HTTP status codes via
# `_service_error_to_response`.
# ============================================================================

from accounts.serializers import FinancialPeriodSerializer  # noqa: E402
from accounts.services import financial_period as fp_service  # noqa: E402


def admin_financial_periods_list(request):
    """List all financial periods (most recent first)."""
    qs = FinancialPeriod.objects.all().order_by("-start_date")
    return Response(FinancialPeriodSerializer(qs, many=True).data)


def admin_financial_periods_create(request):
    """Open a new financial period.

    Body: `{name, start_date, end_date}`. The new period becomes active and any
    previously-active period is demoted (status untouched).
    """
    name = (request.data.get("name") or "").strip()
    start_date = request.data.get("start_date")
    end_date = request.data.get("end_date")
    try:
        period = fp_service.open_period(
            name=name,
            start_date=start_date,
            end_date=end_date,
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)
    return Response(FinancialPeriodSerializer(period).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_financial_periods_dispatch(request):
    """GET → list periods; POST → open a new period.

    Both behaviours live behind a single `/admin/financial-periods/` URL so
    the surface matches the rest of the public API conventions.
    """
    if request.method == "POST":
        return admin_financial_periods_create(request)
    return admin_financial_periods_list(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_financial_periods_current(request):
    """Return the currently-active financial period or 404 if none is set."""
    period = fp_service.active()
    if period is None:
        return Response({"error": "No active financial period."}, status=status.HTTP_404_NOT_FOUND)
    return Response(FinancialPeriodSerializer(period).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_financial_periods_continue(request, pk):
    """Set the chosen non-closed period as the active one."""
    try:
        period = fp_service.continue_period(
            period_id=pk,
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)
    return Response(FinancialPeriodSerializer(period).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_financial_periods_close(request, pk):
    """Close the period and lock its P&L snapshot."""
    try:
        result = fp_service.close_period(
            period_id=pk,
            actor=request.user,
            ip_address=_get_client_ip(request),
            audit_via="api",
        )
    except ServiceError as e:
        return _service_error_to_response(e)
    return Response(
        {
            "period": FinancialPeriodSerializer(result["period"]).data,
            "profit_and_loss_id": result["pnl"].id if result["pnl"] else None,
            "society_account_id": result["society_account"].id if result["society_account"] else None,
        }
    )
