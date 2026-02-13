import functools

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Loan, LoanRepayment, MemberAccount, Receipt


# ========================================
# Decorator
# ========================================


def member_required(view_func):
    """Decorator to ensure user is a logged-in member (not admin/staff)."""

    @functools.wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_admin_role():
            return redirect("/home/")
        if not request.user.portal_access_enabled:
            return HttpResponseForbidden("Your portal access has been disabled. Contact admin.")
        return view_func(request, *args, **kwargs)

    return wrapper


# ========================================
# Dashboard
# ========================================


@member_required
def member_dashboard_view(request):
    """Member dashboard with account summary, recent transactions, and loan overview."""
    user = request.user

    # Account summary
    accounts = MemberAccount.objects.filter(user=user, is_deleted=False)
    active_accounts = accounts.filter(status="active")
    total_balance = sum(a.balance for a in active_accounts)

    # Recent transactions (last 5)
    recent_transactions = Receipt.objects.filter(user=user).select_related("member_account")[:5]

    # Active loans
    active_loans = Loan.objects.filter(user=user, status__in=["active", "approved"])
    total_outstanding = sum(l.outstanding_balance for l in active_loans)

    context = {
        "total_accounts": active_accounts.count(),
        "total_balance": total_balance,
        "total_active_loans": active_loans.count(),
        "total_outstanding": total_outstanding,
        "recent_transactions": recent_transactions,
        "active_loans": active_loans[:5],
        "accounts": active_accounts[:5],
    }
    return render(request, "member/dashboard.html", context)


# ========================================
# Accounts
# ========================================


@member_required
def member_accounts_view(request):
    """List all of the member's accounts."""
    user = request.user
    accounts_qs = MemberAccount.objects.filter(user=user, is_deleted=False).order_by("-created_at")

    # Filter by type
    account_type = request.GET.get("type", "")
    if account_type:
        accounts_qs = accounts_qs.filter(account_type=account_type)

    # Filter by status
    status = request.GET.get("status", "")
    if status:
        accounts_qs = accounts_qs.filter(status=status)

    paginator = Paginator(accounts_qs, 10)
    page = request.GET.get("page", 1)
    accounts = paginator.get_page(page)

    context = {
        "accounts": accounts,
        "account_type_choices": MemberAccount.ACCOUNT_TYPE_CHOICES,
        "status_choices": MemberAccount.STATUS_CHOICES,
        "current_type": account_type,
        "current_status": status,
    }
    return render(request, "member/accounts.html", context)


@member_required
def member_account_detail_view(request, account_id):
    """View a single account with its transaction history."""
    account = get_object_or_404(MemberAccount, id=account_id, user=request.user, is_deleted=False)

    # Transactions for this account
    transactions_qs = Receipt.objects.filter(member_account=account).order_by("-created_at")

    paginator = Paginator(transactions_qs, 15)
    page = request.GET.get("page", 1)
    transactions = paginator.get_page(page)

    context = {
        "account": account,
        "transactions": transactions,
    }
    return render(request, "member/account_detail.html", context)


# ========================================
# Loans
# ========================================


@member_required
def member_loans_view(request):
    """List all of the member's loans."""
    user = request.user
    loans_qs = Loan.objects.filter(user=user).order_by("-created_at")

    # Filter by status
    status = request.GET.get("status", "")
    if status:
        loans_qs = loans_qs.filter(status=status)

    # Filter by type
    loan_type = request.GET.get("type", "")
    if loan_type:
        loans_qs = loans_qs.filter(loan_type=loan_type)

    paginator = Paginator(loans_qs, 10)
    page = request.GET.get("page", 1)
    loans = paginator.get_page(page)

    context = {
        "loans": loans,
        "loan_type_choices": Loan.LOAN_TYPE_CHOICES,
        "status_choices": Loan.STATUS_CHOICES,
        "current_status": status,
        "current_type": loan_type,
    }
    return render(request, "member/loans.html", context)


@member_required
def member_loan_detail_view(request, loan_id):
    """View a single loan with its repayment schedule."""
    loan = get_object_or_404(Loan, id=loan_id, user=request.user)
    repayments = LoanRepayment.objects.filter(loan=loan).order_by("installment_number")

    context = {
        "loan": loan,
        "repayments": repayments,
    }
    return render(request, "member/loan_detail.html", context)


# ========================================
# Transactions
# ========================================


@member_required
def member_transactions_view(request):
    """List all transactions across all of the member's accounts."""
    user = request.user
    transactions_qs = Receipt.objects.filter(user=user).select_related("member_account").order_by("-created_at")

    # Filter by transaction type
    txn_type = request.GET.get("type", "")
    if txn_type:
        transactions_qs = transactions_qs.filter(transaction_type=txn_type)

    # Filter by account
    account_id = request.GET.get("account", "")
    if account_id:
        transactions_qs = transactions_qs.filter(member_account_id=account_id)

    paginator = Paginator(transactions_qs, 20)
    page = request.GET.get("page", 1)
    transactions = paginator.get_page(page)

    # Get member's accounts for filter dropdown
    member_accounts = MemberAccount.objects.filter(user=user, is_deleted=False)

    context = {
        "transactions": transactions,
        "transaction_type_choices": Receipt.TRANSACTION_TYPE_CHOICES,
        "member_accounts": member_accounts,
        "current_type": txn_type,
        "current_account": account_id,
    }
    return render(request, "member/transactions.html", context)


# ========================================
# Profile
# ========================================


@member_required
def member_profile_view(request):
    """View member profile and change password."""
    user = request.user
    password_changed = False
    password_error = None

    if request.method == "POST" and "change_password" in request.POST:
        current_password = request.POST.get("current_password", "")
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not user.check_password(current_password):
            password_error = "Current password is incorrect."
        elif new_password != confirm_password:
            password_error = "New passwords do not match."
        elif len(new_password) < 8:
            password_error = "Password must be at least 8 characters."
        else:
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            password_changed = True

    context = {
        "member": user,
        "password_changed": password_changed,
        "password_error": password_error,
    }
    return render(request, "member/profile.html", context)
