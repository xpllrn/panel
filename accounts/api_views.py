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
from django.db.models import F, Sum
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.api_permissions import IsAdmin, IsMember
from accounts.email_utils import send_email_change_otp_email, send_login_otp_email
from accounts.models import (
    AuditLog,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    InterestPayout,
    Loan,
    LoanRepayment,
    LoginOTPChallenge,
    MemberAccount,
    Notification,
    Receipt,
    User,
    UserDevice,
)
from accounts.notification_service import dispatch_user_notification, send_member_test_push
from accounts.serializers import (
    AuditLogSerializer,
    FundAccountSerializer,
    FundAllocationRuleSerializer,
    FundTransactionSerializer,
    LoanCreateSerializer,
    LoanDetailSerializer,
    LoanListSerializer,
    LoanRepaymentSerializer,
    MemberAccountCreateSerializer,
    MemberAccountSerializer,
    MemberProfileSerializer,
    NotificationSerializer,
    ReceiptCreateSerializer,
    ReceiptSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
)
from accounts.utils import apply_fund_allocations, log_action

# ========================================
# Auth Endpoints
# ========================================


@api_view(["GET"])
@permission_classes([])
def api_info(request):
    """API information and available endpoints."""
    return Response(
        {
            "name": "Panels API",
            "version": "1.0.0",
            "auth": {
                "login_start": "/api/v1/auth/login/",
                "login_verify_otp": "/api/v1/auth/login/verify-otp/",
                "login_resend_otp": "/api/v1/auth/login/resend-otp/",
                "refresh": "/api/v1/auth/refresh/",
                "profile": "/api/v1/auth/profile/",
            },
            "admin": {
                "members": "/api/v1/admin/members/",
                "accounts": "/api/v1/admin/accounts/",
                "loans": "/api/v1/admin/loans/",
                "receipts": "/api/v1/admin/receipts/",
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

    serializer = MemberProfileSerializer(request.user)
    return Response({"success": True, "message": "Profile updated successfully.", "profile": serializer.data})


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

    if not user.email:
        return Response({"success": False, "error": "No email configured for this account."}, status=400)

    otp_code = _generate_numeric_otp()
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

    email_sent = send_login_otp_email(user, otp_code, expires_minutes=otp_expiry_minutes)
    if not email_sent:
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        return Response({"success": False, "error": "Failed to send OTP email. Try again later."}, status=500)

    log_action(request, "login", "system", user.id, f"OTP sent for login: {user.username}")
    return Response(
        {
            "success": True,
            "message": "OTP sent to your email address.",
            "challenge_token": challenge.challenge_token,
            "expires_in_seconds": otp_expiry_minutes * 60,
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

    otp_code = _generate_numeric_otp()
    challenge.otp_hash = make_password(otp_code)
    otp_expiry_minutes = getattr(settings, "LOGIN_OTP_EXPIRY_MINUTES", 15)
    challenge.expires_at = timezone.now() + timedelta(minutes=otp_expiry_minutes)
    challenge.attempt_count = 0
    challenge.save(update_fields=["otp_hash", "expires_at", "attempt_count"])

    if not send_login_otp_email(challenge.user, otp_code, expires_minutes=otp_expiry_minutes):
        return Response({"success": False, "error": "Failed to resend OTP."}, status=500)

    return Response(
        {"success": True, "message": "OTP resent successfully.", "expires_in_seconds": otp_expiry_minutes * 60}
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
        Loan.objects.filter(user=user, status__in=["active", "approved"]), many=True
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
    data["recent_transactions"] = ReceiptSerializer(
        Receipt.objects.filter(member_account=account).order_by("-created_at")[:20], many=True
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
# Admin: Receipts / Transactions
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_receipts_list(request):
    """List all receipts/transactions."""
    qs = Receipt.objects.select_related("user", "member_account").order_by("-created_at")

    txn_type = request.query_params.get("type", "")
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)

    user_id = request.query_params.get("user", "")
    if user_id:
        qs = qs.filter(user_id=user_id)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = ReceiptSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_receipts_create(request):
    """Create a receipt (deposit/withdrawal)."""
    serializer = ReceiptCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    amount = data["amount"]
    txn_type = data["transaction_type"]

    try:
        with transaction.atomic():
            account = MemberAccount.objects.select_for_update().get(id=data["member_account"], is_deleted=False)

            # Validate withdrawal
            if txn_type in ("debit", "transfer") and account.balance < amount:
                return Response({"error": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)

            # Update balance
            if txn_type in ("credit", "interest", "dividend", "share_capital"):
                new_balance = account.balance + amount
                MemberAccount.objects.filter(id=account.id).update(
                    balance=F("balance") + amount, last_transaction_date=date.today()
                )
            else:
                new_balance = account.balance - amount
                MemberAccount.objects.filter(id=account.id).update(
                    balance=F("balance") - amount, last_transaction_date=date.today()
                )

            # Generate receipt number
            year = date.today().year
            last_receipt = (
                Receipt.objects.select_for_update()
                .filter(receipt_number__startswith=f"RCP-{year}-")
                .order_by("-receipt_number")
                .first()
            )
            if last_receipt:
                try:
                    last_seq = int(last_receipt.receipt_number.split("-")[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = 1
            else:
                next_seq = 1

            receipt = Receipt.objects.create(
                receipt_number=f"RCP-{year}-{next_seq:05d}",
                user=account.user,
                member_account=account,
                transaction_type=txn_type,
                amount=amount,
                description=data.get("description", ""),
                payment_mode=data.get("payment_mode", "cash"),
                reference_number=data.get("reference_number", ""),
                balance_after=new_balance,
                created_by=request.user,
            )

            log_action(
                request,
                "create",
                "receipt",
                receipt.id,
                f"Created receipt via API: {receipt.receipt_number} - {txn_type} ₹{amount}",
            )

            dispatch_user_notification(
                user=account.user,
                title="Transaction Update",
                message=f"{txn_type.title()} of ₹{amount} posted to account {account.account_number}.",
                notification_type="transaction",
                metadata={
                    "receipt_id": receipt.id,
                    "receipt_number": receipt.receipt_number,
                    "account_id": account.id,
                    "transaction_type": txn_type,
                    "amount": str(amount),
                },
                email_template="payment_success",
            )

        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)
    except MemberAccount.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_receipts_detail(request, receipt_id):
    """Get receipt detail."""
    try:
        receipt = Receipt.objects.select_related("user", "member_account").get(id=receipt_id)
    except Receipt.DoesNotExist:
        return Response({"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(ReceiptSerializer(receipt).data)


# ========================================
# Admin: Loans
# ========================================


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_loans_list(request):
    """List all loans."""
    qs = Loan.objects.select_related("user").order_by("-created_at")

    loan_status = request.query_params.get("status", "")
    if loan_status:
        qs = qs.filter(status=loan_status)

    loan_type = request.query_params.get("type", "")
    if loan_type:
        qs = qs.filter(loan_type=loan_type)

    user_id = request.query_params.get("user", "")
    if user_id:
        qs = qs.filter(user_id=user_id)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = LoanListSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_loans_create(request):
    """Create a new loan application."""
    serializer = LoanCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        member = User.objects.get(id=data["user"], is_deleted=False)
    except User.DoesNotExist:
        return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    # Generate loan number
    year = date.today().year
    last_loan = Loan.objects.filter(loan_number__startswith=f"LN-{year}").order_by("-loan_number").first()
    if last_loan:
        try:
            last_seq = int(last_loan.loan_number.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    # Calculate EMI
    principal = data["principal_amount"]
    rate = data["interest_rate"]
    tenure = data["tenure_months"]
    monthly_rate = rate / Decimal("1200")
    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** tenure
        emi = (principal * monthly_rate * factor / (factor - 1)).quantize(Decimal("0.01"))
    else:
        emi = (principal / tenure).quantize(Decimal("0.01"))

    total_payable = (emi * tenure).quantize(Decimal("0.01"))

    disbursement_account = None
    if data.get("disbursement_account"):
        try:
            disbursement_account = MemberAccount.objects.get(
                id=data["disbursement_account"], user=member, is_deleted=False
            )
        except MemberAccount.DoesNotExist:
            pass

    loan = Loan.objects.create(
        loan_number=f"LN-{year}-{next_seq:05d}",
        user=member,
        loan_type=data["loan_type"],
        principal_amount=principal,
        interest_rate=rate,
        interest_type=data.get("interest_type", "reducing"),
        tenure_months=tenure,
        emi_amount=emi,
        total_payable=total_payable,
        outstanding_balance=principal,
        total_emis=tenure,
        processing_fee=data.get("processing_fee", Decimal("0")),
        application_date=date.today(),
        disbursement_account=disbursement_account,
        purpose=data.get("purpose", ""),
        guarantor_name=data.get("guarantor_name", ""),
        guarantor_member_id=data.get("guarantor_member_id", ""),
        guarantor_contact=data.get("guarantor_contact", ""),
        collateral_type=data.get("collateral_type", ""),
        collateral_value=data.get("collateral_value"),
        created_by=request.user,
    )

    log_action(request, "create", "loan", loan.id, f"Created loan via API: {loan.loan_number} - ₹{principal}")
    return Response(LoanDetailSerializer(loan).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_loans_detail(request, loan_id):
    """Get loan detail with repayment schedule."""
    try:
        loan = Loan.objects.select_related("user").get(id=loan_id)
    except Loan.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

    data = LoanDetailSerializer(loan).data
    data["repayments"] = LoanRepaymentSerializer(
        LoanRepayment.objects.filter(loan=loan).order_by("installment_number"), many=True
    ).data
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_loans_approve(request, loan_id):
    """Approve a pending loan and generate repayment schedule."""
    try:
        loan = Loan.objects.get(id=loan_id)
    except Loan.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

    if loan.status != "pending":
        return Response({"error": "Only pending loans can be approved"}, status=status.HTTP_400_BAD_REQUEST)

    # Segregation of duties
    if loan.created_by == request.user:
        return Response(
            {"error": "You cannot approve a loan you created. Another admin must approve it."},
            status=status.HTTP_403_FORBIDDEN,
        )

    disbursement_date_str = request.data.get("disbursement_date")
    if not disbursement_date_str:
        return Response({"error": "disbursement_date is required"}, status=status.HTTP_400_BAD_REQUEST)

    from datetime import datetime

    disbursement_date = datetime.strptime(str(disbursement_date_str), "%Y-%m-%d").date()

    import calendar

    loan.status = "active"
    loan.approval_date = date.today()
    loan.disbursement_date = disbursement_date
    loan.approved_by = request.user

    # Calculate first EMI date
    if disbursement_date.month == 12:
        first_emi_month, first_emi_year = 1, disbursement_date.year + 1
    else:
        first_emi_month, first_emi_year = disbursement_date.month + 1, disbursement_date.year

    max_day = calendar.monthrange(first_emi_year, first_emi_month)[1]
    first_emi_day = min(disbursement_date.day, max_day)
    first_emi_date = date(first_emi_year, first_emi_month, first_emi_day)
    loan.first_emi_date = first_emi_date

    # Generate repayment schedule
    remaining = loan.principal_amount
    monthly_rate = loan.interest_rate / Decimal("1200")
    emi = loan.emi_amount
    current_date = first_emi_date

    repayments = []
    for i in range(1, loan.tenure_months + 1):
        interest = (remaining * monthly_rate).quantize(Decimal("0.01"))
        principal_component = emi - interest

        if i == loan.tenure_months:
            principal_component = remaining
            interest = max(emi - principal_component, Decimal("0"))

        remaining_after = max(remaining - principal_component, Decimal("0"))

        repayments.append(
            LoanRepayment(
                loan=loan,
                installment_number=i,
                due_date=current_date,
                amount_due=emi if i < loan.tenure_months else principal_component + interest,
                principal_component=principal_component,
                interest_component=interest,
                balance_after=remaining_after,
                payment_status="upcoming",
            )
        )

        remaining = remaining_after

        if current_date.month == 12:
            next_month, next_year = 1, current_date.year + 1
        else:
            next_month, next_year = current_date.month + 1, current_date.year
        max_day = calendar.monthrange(next_year, next_month)[1]
        current_date = date(next_year, next_month, min(first_emi_date.day, max_day))

    if repayments:
        loan.last_emi_date = repayments[-1].due_date

    loan.save()
    LoanRepayment.objects.bulk_create(repayments)

    dispatch_user_notification(
        user=loan.user,
        title="Loan Approved",
        message=f"Your loan {loan.loan_number} has been approved and is now active.",
        notification_type="loan",
        metadata={"loan_id": loan.id, "loan_number": loan.loan_number, "status": loan.status},
        email_template="loan_approval",
    )

    log_action(request, "approve", "loan", loan.id, f"Approved loan via API: {loan.loan_number}")
    return Response(LoanDetailSerializer(loan).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_loans_record_emi(request, loan_id):
    """Record an EMI payment."""
    try:
        installment_number = request.data.get("installment_number")
        amount_paid = request.data.get("amount_paid")
        payment_mode = request.data.get("payment_mode", "cash")

        if not installment_number or not amount_paid:
            return Response(
                {"error": "installment_number and amount_paid are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        amount = Decimal(str(amount_paid))
        if amount <= 0:
            return Response({"error": "amount_paid must be positive"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            loan = Loan.objects.select_for_update().get(id=loan_id)
            if loan.status != "active":
                return Response({"error": "Only active loans can receive payments"}, status=status.HTTP_400_BAD_REQUEST)

            repayment = LoanRepayment.objects.select_for_update().get(
                loan=loan, installment_number=int(installment_number)
            )
            if repayment.payment_status == "paid":
                return Response({"error": "This installment is already paid"}, status=status.HTTP_400_BAD_REQUEST)

            # Calculate late penalty
            penalty = Decimal("0.00")
            if repayment.due_date < date.today():
                days_late = (date.today() - repayment.due_date).days
                months_late = max(1, days_late / 30)
                penalty = (repayment.amount_due * Decimal("2") * Decimal(str(months_late)) / Decimal("100")).quantize(
                    Decimal("0.01")
                )

            repayment.paid_date = date.today()
            repayment.amount_paid = amount
            repayment.penalty = penalty
            repayment.payment_mode = payment_mode
            repayment.payment_status = "paid" if amount >= repayment.amount_due else "partial"

            # Create receipt
            member_account = loan.disbursement_account
            if not member_account:
                member_account = MemberAccount.objects.filter(user=loan.user, status="active").first()

            receipt = None
            if member_account:
                member_account = MemberAccount.objects.select_for_update().get(id=member_account.id)
                year = date.today().year
                last_receipt = (
                    Receipt.objects.select_for_update()
                    .filter(receipt_number__startswith=f"RCP-{year}-")
                    .order_by("-receipt_number")
                    .first()
                )
                next_seq = 1
                if last_receipt:
                    try:
                        next_seq = int(last_receipt.receipt_number.split("-")[-1]) + 1
                    except (ValueError, IndexError):
                        pass

                new_balance = member_account.balance + amount
                MemberAccount.objects.filter(id=member_account.id).update(
                    balance=F("balance") + amount, last_transaction_date=date.today()
                )

                receipt = Receipt.objects.create(
                    receipt_number=f"RCP-{year}-{next_seq:05d}",
                    user=loan.user,
                    member_account=member_account,
                    transaction_type="credit",
                    amount=amount,
                    description=f"Loan EMI #{installment_number} - {loan.loan_number}",
                    payment_mode=payment_mode,
                    balance_after=new_balance,
                    created_by=request.user,
                )
                repayment.receipt = receipt

            repayment.save()

            # Update loan totals
            loan.total_paid += amount
            loan.outstanding_balance -= repayment.principal_component
            if loan.outstanding_balance < 0:
                loan.outstanding_balance = Decimal("0")
            loan.emis_paid = LoanRepayment.objects.filter(loan=loan, payment_status="paid").count()

            # Mark overdue EMIs
            LoanRepayment.objects.filter(loan=loan, payment_status="upcoming", due_date__lt=date.today()).update(
                payment_status="overdue"
            )

            loan.emis_overdue = LoanRepayment.objects.filter(loan=loan, payment_status="overdue").count()
            loan.overdue_amount = LoanRepayment.objects.filter(loan=loan, payment_status="overdue").aggregate(
                total=Sum("amount_due")
            )["total"] or Decimal("0")

            # Check if all paid
            unpaid = LoanRepayment.objects.filter(loan=loan).exclude(payment_status="paid").count()
            if unpaid == 0:
                loan.status = "closed"
                loan.closure_date = date.today()
                loan.outstanding_balance = Decimal("0")

            loan.save()

            log_action(
                request,
                "update",
                "loan",
                loan.id,
                f"Recorded EMI #{installment_number} via API: ₹{amount} for {loan.loan_number}",
            )

            dispatch_user_notification(
                user=loan.user,
                title="EMI Payment Recorded",
                message=f"EMI #{installment_number} of ₹{amount} recorded for {loan.loan_number}.",
                notification_type="loan",
                metadata={
                    "loan_id": loan.id,
                    "loan_number": loan.loan_number,
                    "installment_number": int(installment_number),
                    "amount_paid": str(amount),
                    "penalty": str(penalty),
                },
                email_template="payment_success",
            )

        return Response(
            {
                "success": True,
                "repayment": LoanRepaymentSerializer(repayment).data,
                "loan_status": loan.status,
                "outstanding_balance": str(loan.outstanding_balance),
                "penalty": str(penalty),
            }
        )

    except Loan.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
    except LoanRepayment.DoesNotExist:
        return Response({"error": "Installment not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
    """Distribute annual profit to funds."""
    from accounts.utils import get_financial_summary

    year = int(request.data.get("year", date.today().year))
    start_date = date(year, 4, 1)
    end_date = date(year + 1, 3, 31)

    summary = get_financial_summary(start_date, end_date)
    net_profit = summary["net_profit"]

    if net_profit <= 0:
        return Response(
            {"error": f"No distributable profit for FY {year}-{year + 1}"}, status=status.HTTP_400_BAD_REQUEST
        )

    transactions = apply_fund_allocations(
        request,
        "annual_profit",
        net_profit,
        f"Annual profit distribution for FY {year}-{year + 1}",
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
        f"Distributed profit ₹{net_profit} for FY {year}-{year + 1} via API. Allocated ₹{total_allocated}.",
    )

    return Response(
        {
            "net_profit": str(net_profit),
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
# Member: Dashboard
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_dashboard(request):
    """Member dashboard with account summary."""
    user = request.user

    accounts = MemberAccount.objects.filter(user=user, is_deleted=False, status="active")
    active_loans = Loan.objects.filter(user=user, status__in=["active", "approved"])
    recent_txns = Receipt.objects.filter(user=user).select_related("member_account")[:10]

    return Response(
        {
            "member": MemberProfileSerializer(user).data,
            "total_accounts": accounts.count(),
            "total_balance": str(sum(a.balance for a in accounts)),
            "total_active_loans": active_loans.count(),
            "total_outstanding": str(sum(loan.outstanding_balance for loan in active_loans)),
            "share_capital": str(user.share_capital_amount),
            "dividend_payable": str(user.dividend_payable_balance),
            "accounts": MemberAccountSerializer(accounts[:5], many=True).data,
            "active_loans": LoanListSerializer(active_loans[:5], many=True).data,
            "recent_transactions": ReceiptSerializer(recent_txns, many=True).data,
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
    data["transactions"] = ReceiptSerializer(
        Receipt.objects.filter(member_account=account).order_by("-created_at")[:50], many=True
    ).data
    return Response(data)


# ========================================
# Member: Loans
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_loans_list(request):
    """List member's own loans."""
    qs = Loan.objects.filter(user=request.user).order_by("-created_at")

    loan_status = request.query_params.get("status", "")
    if loan_status:
        qs = qs.filter(status=loan_status)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(LoanListSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsMember])
def member_loans_detail(request, loan_id):
    """Get member's loan detail with repayments."""
    try:
        loan = Loan.objects.get(id=loan_id, user=request.user)
    except Loan.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

    data = LoanDetailSerializer(loan).data
    data["repayments"] = LoanRepaymentSerializer(
        LoanRepayment.objects.filter(loan=loan).order_by("installment_number"), many=True
    ).data
    return Response(data)


# ========================================
# Member: Transactions
# ========================================


@api_view(["GET"])
@permission_classes([IsMember])
def member_transactions_list(request):
    """List member's transactions across all accounts."""
    qs = Receipt.objects.filter(user=request.user).select_related("member_account").order_by("-created_at")

    txn_type = request.query_params.get("type", "")
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)

    account_id = request.query_params.get("account", "")
    if account_id:
        qs = qs.filter(member_account_id=account_id)

    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(ReceiptSerializer(page, many=True).data)


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
    """Calculate and post accrued interest to all eligible deposit accounts."""
    today = date.today()

    accounts = (
        MemberAccount.objects.filter(is_deleted=False, status="active", interest_rate__gt=0)
        .exclude(account_type__in=["share", "od"])
        .select_related("user")
    )

    total_posted = Decimal("0.00")
    accounts_updated = 0

    with transaction.atomic():
        for account in accounts:
            if account.last_interest_calc_date and account.last_interest_calc_date >= today:
                continue

            calc_start = account.last_interest_calc_date or account.opening_date
            if calc_start >= today:
                continue

            days = (today - calc_start).days
            if days <= 0:
                continue

            interest_amount = (
                account.balance * account.interest_rate * Decimal(str(days)) / Decimal("36500")
            ).quantize(Decimal("0.01"))

            if interest_amount <= 0:
                continue

            MemberAccount.objects.filter(id=account.id).update(
                accrued_interest=F("accrued_interest") + interest_amount,
                balance=F("balance") + interest_amount,
                last_interest_calc_date=today,
                last_transaction_date=today,
            )

            InterestPayout.objects.create(
                account=account,
                amount=interest_amount,
                period_start=calc_start,
                period_end=today,
                created_by=request.user,
            )

            # Create receipt with consistent RCP-YYYY-NNNNN format
            year = today.year
            last_receipt = (
                Receipt.objects.filter(receipt_number__startswith=f"RCP-{year}-").order_by("-receipt_number").first()
            )
            if last_receipt:
                try:
                    last_seq = int(last_receipt.receipt_number.split("-")[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = 1
            else:
                next_seq = 1
            new_receipt_number = f"RCP-{year}-{next_seq:05d}"

            Receipt.objects.create(
                user=account.user,
                member_account=account,
                receipt_number=new_receipt_number,
                transaction_type="interest",
                amount=interest_amount,
                description=f"Interest credit {calc_start.strftime('%b %d')} - {today.strftime('%b %d, %Y')} @ {account.interest_rate}%",
                payment_mode="internal",
                balance_after=account.balance + interest_amount,
                created_by=request.user,
            )

            dispatch_user_notification(
                user=account.user,
                title="Interest Credited",
                message=f"₹{interest_amount} interest credited to account {account.account_number}.",
                notification_type="transaction",
                metadata={
                    "account_id": account.id,
                    "account_number": account.account_number,
                    "interest_amount": str(interest_amount),
                },
                email_template="interest_credit",
            )

            total_posted += interest_amount
            accounts_updated += 1

    return Response(
        {
            "success": True,
            "message": f"Posted ₹{total_posted} interest to {accounts_updated} accounts.",
            "total_posted": str(total_posted),
            "accounts_updated": accounts_updated,
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

    eligible_members = User.objects.filter(
        is_deleted=False, status="active", eligible_for_dividend=True, share_capital_amount__gt=0
    )

    if not eligible_members.exists():
        return Response({"error": "No eligible members with share capital"}, status=status.HTTP_400_BAD_REQUEST)

    total_distributed = Decimal("0.00")
    member_count = 0

    with transaction.atomic():
        for member in eligible_members:
            dividend_amount = (member.share_capital_amount * dividend_rate / Decimal("100")).quantize(Decimal("0.01"))
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
    return Response({"success": True, "message": "Email updated successfully.", "email": request.user.email})
