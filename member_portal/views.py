import functools
import io
from datetime import date, timedelta

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Loan, LoanRepayment, MemberAccount, Receipt
from accounts.utils import log_action

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
    total_outstanding = sum(loan.outstanding_balance for loan in active_loans)

    # Share capital info
    share_capital = user.share_capital_amount
    number_of_shares = user.number_of_shares
    dividend_payable = user.dividend_payable_balance

    # Dividend transactions
    dividend_transactions = Receipt.objects.filter(user=user, transaction_type="dividend").order_by("-created_at")[:5]

    context = {
        "total_accounts": active_accounts.count(),
        "total_balance": total_balance,
        "total_active_loans": active_loans.count(),
        "total_outstanding": total_outstanding,
        "recent_transactions": recent_transactions,
        "active_loans": active_loans[:5],
        "accounts": active_accounts[:5],
        "share_capital": share_capital,
        "number_of_shares": number_of_shares,
        "dividend_payable": dividend_payable,
        "dividend_transactions": dividend_transactions,
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
            log_action(request, "update", "member", user.id, f"Member changed password: {user.display_name}")
            password_changed = True

    context = {
        "member": user,
        "password_changed": password_changed,
        "password_error": password_error,
    }
    return render(request, "member/profile.html", context)


# ========================================
# Account Statement PDF Download
# ========================================


@member_required
def member_account_statement_view(request, account_id):
    """Generate and download a PDF account statement."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    account = get_object_or_404(MemberAccount, id=account_id, user=request.user, is_deleted=False)

    # Date range: default last 3 months
    months = int(request.GET.get("months", 3))
    end_date = date.today()
    start_date = end_date - timedelta(days=months * 30)

    transactions = Receipt.objects.filter(
        member_account=account,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).order_by("created_at")

    # Build PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    header_style = ParagraphStyle("Header", parent=styles["Title"], fontSize=16, spaceAfter=6)
    elements.append(Paragraph("Account Statement", header_style))

    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
    elements.append(Paragraph(f"Generated on {end_date.strftime('%d %b %Y')}", sub_style))
    elements.append(Spacer(1, 10 * mm))

    # Account info table
    info_data = [
        ["Account Number", account.account_number, "Account Type", account.get_account_type_display()],
        ["Member", request.user.display_name, "Member ID", request.user.member_id or "N/A"],
        ["Balance", f"Rs. {account.balance:,.2f}", "Interest Rate", f"{account.interest_rate}%"],
        [
            "Period",
            f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
            "Status",
            account.get_status_display(),
        ],
    ]
    info_table = Table(info_data, colWidths=[80, 140, 80, 140])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 8 * mm))

    # Transactions table
    elements.append(Paragraph("Transaction History", ParagraphStyle("SH", parent=styles["Heading3"], fontSize=12)))
    elements.append(Spacer(1, 3 * mm))

    txn_data = [["Date", "Receipt #", "Type", "Description", "Amount", "Balance"]]
    for txn in transactions:
        sign = "+" if txn.transaction_type in ("credit", "interest", "dividend", "share_capital") else "-"
        txn_data.append(
            [
                txn.created_at.strftime("%d %b %Y"),
                txn.receipt_number,
                txn.get_transaction_type_display(),
                (txn.description or "")[:30],
                f"{sign} Rs. {txn.amount:,.2f}",
                f"Rs. {txn.balance_after:,.2f}",
            ]
        )

    if len(txn_data) == 1:
        txn_data.append(["", "", "", "No transactions in this period", "", ""])

    txn_table = Table(txn_data, colWidths=[60, 70, 55, 110, 75, 75])
    txn_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.93, 0.93, 0.93)),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (4, 0), (5, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
            ]
        )
    )
    elements.append(txn_table)

    # Summary
    elements.append(Spacer(1, 6 * mm))
    total_credits = sum(
        t.amount for t in transactions if t.transaction_type in ("credit", "interest", "dividend", "share_capital")
    )
    total_debits = sum(
        t.amount for t in transactions if t.transaction_type not in ("credit", "interest", "dividend", "share_capital")
    )

    summary_data = [
        ["Total Credits", f"Rs. {total_credits:,.2f}"],
        ["Total Debits", f"Rs. {total_debits:,.2f}"],
        ["Closing Balance", f"Rs. {account.balance:,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[120, 120])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 1, colors.black),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(summary_table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="statement_{account.account_number}_{end_date.strftime("%Y%m%d")}.pdf"'
    )
    return response
