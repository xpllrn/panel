from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.api_permissions import IsAdmin, IsMember
from accounts.models import (
    AuditLog,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    InterestPayout,
    Loan,
    LoanRepayment,
    MemberAccount,
    Receipt,
    User,
)
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
            "name": "Cooperative Society API",
            "version": "1.0.0",
            "auth": {
                "login": "/api/v1/auth/login/",
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

            # Create receipt
            last_receipt = Receipt.objects.order_by("-id").first()
            if last_receipt and last_receipt.receipt_number:
                try:
                    last_num = int(last_receipt.receipt_number.replace("RCT", ""))
                    new_receipt_number = f"RCT{last_num + 1:06d}"
                except (ValueError, IndexError):
                    new_receipt_number = f"RCT{Receipt.objects.count() + 1:06d}"
            else:
                new_receipt_number = "RCT000001"

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
