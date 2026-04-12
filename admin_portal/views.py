import functools
import json
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

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
    Voucher,
    VoucherEntry,
)
from accounts.utils import (
    apply_fund_allocations,
    get_account_type_cashflow,
    get_financial_summary,
    log_action,
    split_full_name,
    validate_password_strength,
)

# Rate limiting cache for member creation (simple in-memory)
_member_creation_timestamps = {}


def admin_required(view_func):
    """Decorator to check if user is staff"""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Access denied. Administrators only.")
        return view_func(request, *args, **kwargs)

    return wrapper


def _credit_transaction(transaction_type):
    return transaction_type in ("credit", "interest", "dividend", "share_capital")


def _next_receipt_number():
    year = date.today().year
    last_receipt = (
        Receipt.objects.select_for_update().filter(receipt_number__startswith=f"RCP-{year}-").order_by("-receipt_number").first()
    )
    if not last_receipt:
        return f"RCP-{year}-00001"
    try:
        seq = int(last_receipt.receipt_number.split("-")[-1]) + 1
    except (ValueError, IndexError):
        seq = 1
    return f"RCP-{year}-{seq:05d}"


def _next_voucher_number():
    year = date.today().year
    last_voucher = (
        Voucher.objects.select_for_update()
        .filter(voucher_number__startswith=f"VCR-{year}-")
        .order_by("-voucher_number")
        .first()
    )
    if not last_voucher:
        return f"VCR-{year}-00001"
    try:
        seq = int(last_voucher.voucher_number.split("-")[-1]) + 1
    except (ValueError, IndexError):
        seq = 1
    return f"VCR-{year}-{seq:05d}"


def _has_unpaid_emi(user):
    return LoanRepayment.objects.filter(
        loan__user=user,
        loan__status="active",
    ).exclude(payment_status="paid").exists()


def _process_receipt_line(user, line, payment_mode, reference_number, remarks, created_by):
    account = MemberAccount.objects.select_for_update().get(id=line["account_id"], user=user)
    amount_decimal = Decimal(str(line["amount"]))
    if amount_decimal <= 0:
        raise ValueError("Each entry amount must be greater than zero")
    transaction_type = line["transaction_type"]
    if _credit_transaction(transaction_type):
        balance_after = account.balance + amount_decimal
        MemberAccount.objects.filter(id=account.id).update(
            balance=F("balance") + amount_decimal,
            last_transaction_date=date.today(),
        )
    else:
        if amount_decimal > account.balance:
            raise ValueError(
                f"Insufficient balance for {account.account_number}. "
                f"Available ₹{account.balance}, requested ₹{amount_decimal}."
            )
        balance_after = account.balance - amount_decimal
        MemberAccount.objects.filter(id=account.id).update(
            balance=F("balance") - amount_decimal,
            last_transaction_date=date.today(),
        )
    receipt = Receipt.objects.create(
        receipt_number=_next_receipt_number(),
        user=user,
        member_account=account,
        transaction_type=transaction_type,
        amount=amount_decimal,
        description=(line.get("description") or "").strip() or None,
        payment_mode=payment_mode,
        reference_number=reference_number or None,
        balance_after=balance_after,
        created_by=created_by,
        remarks=remarks or None,
    )
    loan_repayment_id = line.get("loan_repayment_id")
    if loan_repayment_id:
        try:
            repayment = LoanRepayment.objects.select_for_update().get(
                id=loan_repayment_id,
                loan__user=user,
                loan__status="active",
            )
            repayment.paid_date = date.today()
            repayment.amount_paid = amount_decimal
            repayment.payment_mode = payment_mode
            repayment.reference_number = reference_number or None
            repayment.payment_status = "paid" if amount_decimal >= repayment.amount_due else "partial"
            repayment.receipt = receipt
            repayment.save()
            loan = repayment.loan
            loan.total_paid = LoanRepayment.objects.filter(loan=loan, payment_status="paid").aggregate(total=Sum("amount_paid"))[
                "total"
            ] or Decimal("0.00")
            loan.emis_paid = LoanRepayment.objects.filter(loan=loan, payment_status="paid").count()
            loan.emis_overdue = LoanRepayment.objects.filter(loan=loan, payment_status="overdue").count()
            loan.overdue_amount = LoanRepayment.objects.filter(loan=loan, payment_status="overdue").aggregate(
                total=Sum("amount_due")
            )["total"] or Decimal("0.00")
            if not LoanRepayment.objects.filter(loan=loan).exclude(payment_status="paid").exists():
                loan.status = "closed"
                loan.closure_date = date.today()
                loan.outstanding_balance = Decimal("0.00")
            loan.save()
        except LoanRepayment.DoesNotExist:
            pass
    return receipt


def _apply_member_status_rules(user, new_status, previous_status=None):
    today = timezone.now().date()
    previous_status = previous_status or user.status
    if new_status == "inactive":
        if _has_unpaid_emi(user):
            raise ValueError("Cannot mark member inactive while pending EMI payments exist.")
        if not user.inactive_since:
            user.inactive_since = today
    elif new_status == "active":
        user.inactive_since = None
    elif new_status == "resign":
        if previous_status != "inactive":
            raise ValueError("Member must be inactive before resignation.")
        if not user.inactive_since:
            raise ValueError("Inactive date is required before resignation.")
        if (today - user.inactive_since).days < 30:
            raise ValueError("Member can resign only after 30 days in inactive status.")
        if _has_unpaid_emi(user):
            raise ValueError("Cannot resign member while pending EMI payments exist.")
        user.exit_date = today
        user.is_active = False


@login_required
@admin_required
def home_view(request):
    """Admin dashboard view with stats, charts, and recent transactions"""
    now = timezone.now()
    today = now.date()

    # Member stats
    total_members = User.objects.filter(is_deleted=False).count()
    active_members = User.objects.filter(is_deleted=False, status="active").count()

    # Account stats
    total_accounts = MemberAccount.objects.filter(is_deleted=False).count()
    active_accounts = MemberAccount.objects.filter(is_deleted=False, status="active").count()
    total_deposits = (
        MemberAccount.objects.filter(is_deleted=False, status="active").aggregate(total=Sum("balance"))["total"] or 0
    )

    # Account type distribution (for pie chart) - show total balance by type
    account_type_data = []
    for item in (
        MemberAccount.objects.filter(is_deleted=False, status="active")
        .values("account_type")
        .annotate(total=Sum("balance"))
        .order_by("account_type")
    ):
        account_type_data.append(
            {"account_type": item["account_type"], "total": float(item["total"]) if item["total"] else 0.0}
        )

    # Receipt/transaction stats
    total_receipts = Receipt.objects.count()
    today_receipts = Receipt.objects.filter(created_at__date=today).count()
    today_credit = (
        Receipt.objects.filter(created_at__date=today, transaction_type="credit").aggregate(total=Sum("amount"))[
            "total"
        ]
        or 0
    )
    today_debit = (
        Receipt.objects.filter(created_at__date=today, transaction_type="debit").aggregate(total=Sum("amount"))["total"]
        or 0
    )

    # Transaction trend - last 30 days (for bar chart)
    # Use 30-day window to ensure chart shows data even when recent activity is sparse
    trend_data = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        day_credits = (
            Receipt.objects.filter(
                created_at__date=day, transaction_type__in=["credit", "interest", "dividend", "share_capital"]
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        day_debits = (
            Receipt.objects.filter(created_at__date=day, transaction_type__in=["debit", "transfer"]).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        # Only include days that have transactions to keep chart clean
        if day_credits or day_debits:
            trend_data.append(
                {
                    "date": day.strftime("%b %d"),
                    "day": day.strftime("%a %d"),
                    "credits": float(day_credits),
                    "debits": float(day_debits),
                }
            )

    # If no data in 30 days, show last 7 days anyway (empty bars)
    if not trend_data:
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            trend_data.append(
                {
                    "date": day.strftime("%b %d"),
                    "day": day.strftime("%a"),
                    "credits": 0,
                    "debits": 0,
                }
            )

    # Recent 10 transactions
    recent_transactions = Receipt.objects.select_related("user", "member_account").all().order_by("-created_at")[:10]

    # Overdue loan payments - get overdue repayments grouped by loan/member
    overdue_repayments = (
        LoanRepayment.objects.filter(payment_status="overdue").select_related("loan", "loan__user").order_by("due_date")
    )

    # Build overdue data: group by loan, show earliest overdue + count
    overdue_loans = {}
    for rep in overdue_repayments:
        loan_id = rep.loan_id
        if loan_id not in overdue_loans:
            overdue_loans[loan_id] = {
                "loan_number": rep.loan.loan_number,
                "loan_id": rep.loan.id,
                "member_name": rep.loan.user.display_name,
                "member_id": rep.loan.user.member_id or "",
                "loan_type": rep.loan.get_loan_type_display(),
                "emi_amount": float(rep.amount_due),
                "oldest_due": rep.due_date.strftime("%b %d, %Y"),
                "days_overdue": (today - rep.due_date).days,
                "overdue_count": 0,
                "total_overdue": 0.0,
            }
        overdue_loans[loan_id]["overdue_count"] += 1
        overdue_loans[loan_id]["total_overdue"] += float(rep.amount_due)

    # Sort by days overdue (most overdue first), limit to 10
    overdue_list = sorted(overdue_loans.values(), key=lambda x: -x["days_overdue"])[:10]
    total_overdue_count = len(overdue_loans)

    # Fund stats
    fund_total_balance = FundAccount.objects.filter(is_deleted=False).aggregate(total=Sum("balance"))["total"] or 0
    total_funds = FundAccount.objects.filter(is_deleted=False).count()

    # Net profit for current fiscal year (April-March)
    from accounts.utils import get_financial_summary

    fiscal_year_start = date(today.year, 4, 1) if today.month >= 4 else date(today.year - 1, 4, 1)
    fiscal_year_end = date(fiscal_year_start.year + 1, 3, 31)
    financial_summary = get_financial_summary(fiscal_year_start, fiscal_year_end)
    net_profit = financial_summary["net_profit"]
    gross_revenue = financial_summary["gross_revenue"]

    return render(
        request,
        "admin/home.html",
        {
            "total_members": total_members,
            "active_members": active_members,
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_deposits": total_deposits,
            "total_receipts": total_receipts,
            "today_receipts": today_receipts,
            "today_credit": today_credit,
            "today_debit": today_debit,
            "recent_transactions": recent_transactions,
            "trend_data_json": json.dumps(trend_data),
            "account_type_data_json": json.dumps(account_type_data),
            "overdue_data_json": json.dumps(overdue_list),
            "total_overdue_count": total_overdue_count,
            "fund_total_balance": fund_total_balance,
            "total_funds": total_funds,
            "net_profit": net_profit,
            "gross_revenue": gross_revenue,
        },
    )


@login_required
@admin_required
def members_view(request):
    """Members management view with pagination and search"""
    page = request.GET.get("page", 1)
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    member_type_filter = request.GET.get("member_type", "").strip()
    date_filter = request.GET.get("date_filter", "registered").strip() or "registered"
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    per_page = 25

    # Base queryset
    users = User.objects.filter(is_deleted=False).order_by("-date_joined")

    # Apply search filter if query provided
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(member_id__icontains=query)
            | Q(mobile_primary__icontains=query)
        )
    if status_filter:
        users = users.filter(status=status_filter)
    if member_type_filter:
        users = users.filter(member_type=member_type_filter)
    if date_filter not in ("registered", "resigned"):
        date_filter = "registered"
    if date_filter == "resigned":
        if date_from:
            users = users.filter(exit_date__gte=date_from)
        if date_to:
            users = users.filter(exit_date__lte=date_to)
    else:
        if date_from:
            users = users.filter(date_joined__date__gte=date_from)
        if date_to:
            users = users.filter(date_joined__date__lte=date_to)

    # Paginate
    paginator = Paginator(users, per_page)
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)

    # Summary stats
    total_members = User.objects.filter(is_deleted=False).count()
    active_members = User.objects.filter(is_deleted=False, status="active").count()

    member_status_choices = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("resign", "Resigned"),
    ]

    return render(
        request,
        "admin/members.html",
        {
            "users": users_page,
            "search_query": query,
            "page_obj": users_page,
            "total_members": total_members,
            "active_members": active_members,
            "selected_status": status_filter,
            "selected_member_type": member_type_filter,
            "status_choices": member_status_choices,
            "member_type_choices": User.MEMBER_TYPE_CHOICES,
            "date_filter": date_filter,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
@admin_required
def add_member_view(request):
    """Create a new member with auto-generated password from DOB"""
    if request.method == "POST":
        try:
            # Rate limiting: max 10 member creations per minute per admin
            user_id = request.user.id
            now = timezone.now()
            if user_id in _member_creation_timestamps:
                recent_creates = [ts for ts in _member_creation_timestamps[user_id] if (now - ts).seconds < 60]
                if len(recent_creates) >= 10:
                    return JsonResponse({"success": False, "error": "Rate limit exceeded. Please wait a moment."})
                _member_creation_timestamps[user_id] = recent_creates
            else:
                _member_creation_timestamps[user_id] = []
            _member_creation_timestamps[user_id].append(now)

            username = request.POST.get("username", "").strip()
            email = request.POST.get("email", "").strip()
            full_name = request.POST.get("full_name", "").strip()
            date_of_birth = request.POST.get("date_of_birth", "").strip()
            mobile_primary = request.POST.get("mobile_primary", "").strip()
            role = request.POST.get("role", "member")

            if not username:
                return JsonResponse({"success": False, "error": "Username is required"})

            if not full_name:
                return JsonResponse({"success": False, "error": "Full name is required"})

            if not date_of_birth:
                return JsonResponse({"success": False, "error": "Date of birth is required"})

            # Parse date of birth
            try:
                dob = date.fromisoformat(date_of_birth)
            except ValueError:
                return JsonResponse({"success": False, "error": "Invalid date of birth format"})

            # Auto-generate password: DDMM + first 4 chars of name (uppercase, no spaces)
            name_chars = full_name.replace(" ", "").upper()[:4]
            password = f"{dob.day:02d}{dob.month:02d}{name_chars}"

            # Check for duplicate username
            if User.objects.filter(username=username).exists():
                return JsonResponse({"success": False, "error": "Username already exists"})

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
            )

            # Set name fields
            first_name, last_name = split_full_name(full_name)
            user.first_name = first_name
            user.last_name = last_name
            user.date_of_birth = dob

            if mobile_primary:
                user.mobile_primary = mobile_primary

            if role == "admin":
                user.is_staff = True

            # Wrap member and account creation in transaction
            with transaction.atomic():
                # Auto-generate member_id: MBR-YEAR-SEQUENCE
                year = date.today().year
                last_member = (
                    User.objects.select_for_update()
                    .filter(member_id__startswith=f"MBR-{year}-")
                    .order_by("-member_id")
                    .first()
                )
                if last_member:
                    try:
                        last_seq = int(last_member.member_id.split("-")[-1])
                        next_seq = last_seq + 1
                    except (ValueError, IndexError):
                        next_seq = 1
                else:
                    next_seq = 1

                user.member_id = f"MBR-{year}-{next_seq:05d}"
                user.save()

                # Auto-create all account types for the new member
                account_types = [
                    ("fd", "Fixed Deposit", 7.5),
                    ("cd", "Certificate of Deposit", 7.0),
                    ("rd", "Recurring Deposit", 7.0),
                    ("od", "Overdraft", 12.0),
                    ("share", "Share Account", 0.0),
                    ("sukanya", "Sukanya Yojana", 8.0),
                    ("suputra", "Suputra Yojana", 8.5),
                ]

                created_accounts = []
                for account_type, account_name, default_rate in account_types:
                    # Generate account number: TYPE-USERID-001
                    # Note: Using user.id ensures uniqueness since each user gets one account per type
                    account_number = f"{account_type.upper()}-{user.id:05d}-001"
                    account = MemberAccount.objects.create(
                        user=user,
                        account_number=account_number,
                        account_type=account_type,
                        status="active",
                        balance=0.00,
                        interest_rate=default_rate,
                        opening_date=date.today(),
                    )
                    created_accounts.append((account, account_name))

                # Log member creation
                log_action(
                    request,
                    "create",
                    "member",
                    user.id,
                    f"Created member {username} ({user.display_name}) with 7 auto-generated accounts",
                )

                # Log each account creation
                for account, account_name in created_accounts:
                    log_action(
                        request,
                        "create",
                        "account",
                        account.id,
                        f"Auto-created {account_name} account {account.account_number} for member {username}",
                    )

                # Apply fund allocations for member registration (wrapped in try/except to never break member creation)
                try:
                    apply_fund_allocations(
                        request,
                        "member_registration",
                        Decimal("200.00"),
                        f"Member registration fee: {user.display_name} ({username})",
                        source_member=user,
                    )
                except Exception:
                    pass

            return JsonResponse({"success": True, "user_id": user.id, "password": password})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def delete_member_view(request, user_id):
    """Soft-delete a member (sets is_deleted flag instead of destroying data)"""
    if request.method == "POST":
        try:
            user = User.objects.get(id=user_id, is_deleted=False)
            # Prevent deleting yourself
            if user.id == request.user.id:
                return JsonResponse({"success": False, "error": "You cannot delete yourself"})

            user.is_deleted = True
            user.deleted_at = timezone.now()
            user.status = "closed"
            user.is_active = False
            user.save()

            # Also soft-delete all their accounts
            MemberAccount.objects.filter(user=user, is_deleted=False).update(
                is_deleted=True, deleted_at=timezone.now(), status="closed"
            )

            log_action(
                request,
                "delete",
                "member",
                user.id,
                f"Deleted member {user.username} ({user.display_name})",
            )

            return JsonResponse({"success": True})
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "Member not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def add_account_view(request):
    """Add a new member account"""
    if request.method == "POST":
        try:
            user_id = request.POST.get("user_id")
            account_type = request.POST.get("account_type")
            balance = request.POST.get("balance", "0")
            interest_rate = request.POST.get("interest_rate", "0")
            principal_amount = request.POST.get("principal_amount", "0")
            opening_date = request.POST.get("opening_date")
            maturity_date = request.POST.get("maturity_date") or None
            tenure_months = request.POST.get("tenure_months") or None
            nominee_name = request.POST.get("nominee_name", "").strip()
            nominee_relationship = request.POST.get("nominee_relationship", "").strip()
            remarks = request.POST.get("remarks", "").strip()

            # Validate required fields
            if not user_id:
                return JsonResponse({"success": False, "error": "Member is required"})
            if not account_type:
                return JsonResponse({"success": False, "error": "Account type is required"})
            if not opening_date:
                return JsonResponse({"success": False, "error": "Opening date is required"})

            # Validate user exists
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({"success": False, "error": "Member not found"})

            # Auto-generate account number: PREFIX-YEAR-SEQUENCE
            type_prefix_map = {
                "fd": "FD",
                "cd": "CD",
                "rd": "RD",
                "od": "OD",
                "share": "SHR",
                "sukanya": "SKY",
                "suputra": "SPT",
            }
            prefix = type_prefix_map.get(account_type, "ACC")
            year = date.today().year

            # Convert tenure_months to int if provided
            if tenure_months:
                tenure_months = int(tenure_months)

            # Retry loop for duplicate account numbers
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        # Lock the latest account row to prevent duplicate numbers
                        last_account = (
                            MemberAccount.objects.select_for_update()
                            .filter(account_number__startswith=f"{prefix}-{year}-")
                            .order_by("-account_number")
                            .first()
                        )
                        if last_account:
                            try:
                                last_seq = int(last_account.account_number.split("-")[-1])
                                next_seq = last_seq + 1
                            except (ValueError, IndexError):
                                next_seq = 1
                        else:
                            next_seq = 1

                        account_number = f"{prefix}-{year}-{next_seq:05d}"

                        account = MemberAccount.objects.create(
                            user=user,
                            account_number=account_number,
                            account_type=account_type,
                            balance=balance,
                            interest_rate=interest_rate,
                            principal_amount=principal_amount,
                            opening_date=opening_date,
                            maturity_date=maturity_date,
                            tenure_months=tenure_months,
                            nominee_name=nominee_name or None,
                            nominee_relationship=nominee_relationship or None,
                            remarks=remarks or None,
                        )
                    # If we get here, the transaction succeeded
                    log_action(
                        request,
                        "create",
                        "account",
                        account.id,
                        f"Created account {account_number} ({account_type}) for {user.display_name}",
                    )
                    return JsonResponse({"success": True, "account_id": account.id})
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise
                    continue

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def edit_account_view(request, account_id):
    """Edit a member account"""
    if request.method == "POST":
        try:
            account = MemberAccount.objects.get(id=account_id)

            account.account_type = request.POST.get("account_type", account.account_type)
            account.status = request.POST.get("status", account.status)
            account.balance = request.POST.get("balance", account.balance)
            account.interest_rate = request.POST.get("interest_rate", account.interest_rate)
            account.principal_amount = request.POST.get("principal_amount", account.principal_amount)

            opening_date = request.POST.get("opening_date")
            if opening_date:
                account.opening_date = opening_date

            maturity_date = request.POST.get("maturity_date")
            account.maturity_date = maturity_date or None

            tenure_months = request.POST.get("tenure_months")
            account.tenure_months = int(tenure_months) if tenure_months else None

            account.nominee_name = request.POST.get("nominee_name", "").strip() or None
            account.nominee_relationship = request.POST.get("nominee_relationship", "").strip() or None
            account.remarks = request.POST.get("remarks", "").strip() or None

            account.save()
            log_action(
                request,
                "update",
                "account",
                account.id,
                f"Updated account {account.account_number}",
            )
            return JsonResponse({"success": True})
        except MemberAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Account not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def delete_member_account_view(request, account_id):
    """Soft-delete a member account (sets is_deleted flag instead of destroying data)"""
    if request.method == "POST":
        try:
            account = MemberAccount.objects.get(id=account_id, is_deleted=False)
            account.is_deleted = True
            account.deleted_at = timezone.now()
            account.status = "closed"
            account.save()
            log_action(
                request,
                "delete",
                "account",
                account.id,
                f"Deleted account {account.account_number} ({account.get_account_type_display()}) "
                f"for {account.user.display_name}",
            )
            return JsonResponse({"success": True})
        except MemberAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Account not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def search_members_view(request):
    """Search members for autocomplete"""
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 2:
        return JsonResponse({"results": []})

    users = User.objects.filter(
        Q(username__icontains=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(member_id__icontains=query),
        is_deleted=False,
    )[:10]

    results = [
        {
            "id": user.id,
            "username": user.username,
            "full_name": user.display_name,
            "member_id": user.member_id or "",
        }
        for user in users
    ]

    return JsonResponse({"results": results})


@login_required
@admin_required
def get_member_view(request, user_id):
    """Get member data for viewing and editing"""
    try:
        user = User.objects.get(id=user_id)

        # Build current address string
        current_address = ", ".join(
            filter(
                None,
                [
                    user.current_address_line1,
                    user.current_address_line2,
                    user.current_city,
                    user.current_district,
                    user.current_state,
                    user.current_pincode,
                ],
            )
        )

        # Build permanent address string
        if user.permanent_same_as_current:
            permanent_address = "Same as current address"
        else:
            permanent_address = ", ".join(
                filter(
                    None,
                    [
                        user.permanent_address_line1,
                        user.permanent_address_line2,
                        user.permanent_city,
                        user.permanent_district,
                        user.permanent_state,
                        user.permanent_pincode,
                    ],
                )
            )

        # Get member accounts summary
        accounts = MemberAccount.objects.filter(user=user, is_deleted=False).order_by("account_type")
        accounts_data = [
            {
                "id": a.id,
                "account_number": a.account_number,
                "account_type": a.account_type,
                "account_type_display": a.get_account_type_display(),
                "status": a.status,
                "status_display": a.get_status_display(),
                "balance": str(a.balance),
                "interest_rate": str(a.interest_rate),
                "opening_date": a.opening_date.strftime("%b %d, %Y") if a.opening_date else "",
                "maturity_date": a.maturity_date.strftime("%b %d, %Y") if a.maturity_date else "",
            }
            for a in accounts
        ]

        return JsonResponse(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    # Core Identity
                    "member_id": user.member_id or "",
                    "full_name": user.display_name,
                    "member_type": user.get_member_type_display() if user.member_type else "",
                    "member_type_raw": user.member_type or "",
                    "status": user.get_status_display() if user.status else "",
                    "status_raw": user.status or "",
                    "date_of_joining": user.date_of_joining.strftime("%b %d, %Y") if user.date_of_joining else "",
                    "inactive_since": user.inactive_since.strftime("%b %d, %Y") if user.inactive_since else "",
                    # Personal
                    "date_of_birth": user.date_of_birth.strftime("%b %d, %Y") if user.date_of_birth else "",
                    "age": user.age or "",
                    "gender": user.get_gender_display() if user.gender else "",
                    "marital_status": user.get_marital_status_display() if user.marital_status else "",
                    "occupation": user.occupation or "",
                    "annual_income_bracket": user.annual_income_bracket or "",
                    "education_qualification": user.education_qualification or "",
                    # Contact
                    "mobile_primary": user.mobile_primary or "",
                    "mobile_alternate": user.mobile_alternate or "",
                    "preferred_comm_mode": user.get_preferred_comm_mode_display() if user.preferred_comm_mode else "",
                    "dnd_enabled": user.dnd_enabled,
                    # Address
                    "current_address": current_address or "",
                    "permanent_address": permanent_address or "",
                    # KYC
                    "kyc_status": user.get_kyc_status_display() if user.kyc_status else "",
                    "kyc_verified_date": user.kyc_verified_date.strftime("%b %d, %Y") if user.kyc_verified_date else "",
                    "aadhar_number": user.aadhar_number or "",
                    "pan_number": user.pan_number or "",
                    "voter_id": user.voter_id or "",
                    "passport_number": user.passport_number or "",
                    "driving_license": user.driving_license or "",
                    # Nominee
                    "nominee_name": user.nominee_name or "",
                    "nominee_relationship": user.nominee_relationship or "",
                    "nominee_dob": user.nominee_dob.strftime("%b %d, %Y") if user.nominee_dob else "",
                    "nominee_contact": user.nominee_contact or "",
                    "nominee_address": user.nominee_address or "",
                    "alt_nominee_name": user.alt_nominee_name or "",
                    "alt_nominee_relationship": user.alt_nominee_relationship or "",
                    # Shareholding
                    "share_capital_amount": str(user.share_capital_amount),
                    "number_of_shares": user.number_of_shares,
                    "face_value_per_share": str(user.face_value_per_share),
                    "share_certificate_number": user.share_certificate_number or "",
                    "share_issue_date": user.share_issue_date.strftime("%b %d, %Y") if user.share_issue_date else "",
                    "dividend_payable_balance": str(user.dividend_payable_balance),
                    "last_dividend_paid_date": user.last_dividend_paid_date.strftime("%b %d, %Y")
                    if user.last_dividend_paid_date
                    else "",
                    # Banking flags
                    "eligible_for_accounts": user.eligible_for_accounts,
                    "eligible_for_loans": user.eligible_for_loans,
                    "eligible_for_dividend": user.eligible_for_dividend,
                    "eligible_for_voting": user.eligible_for_voting,
                    "risk_category": user.get_risk_category_display() if user.risk_category else "",
                    # Internal
                    "internal_remarks": user.internal_remarks or "",
                    "closure_reason": user.closure_reason or "",
                    "aml_check_status": user.aml_check_status or "",
                    # Accounts summary
                    "accounts": accounts_data,
                    "accounts_count": len(accounts_data),
                    # Edit modal fields
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "role_display": user.get_role_display_name(),
                    "is_active": user.is_active,
                    "is_staff": user.is_staff,
                    "date_joined": user.date_joined.strftime("%b %d, %Y") if user.date_joined else "",
                    "last_login": user.last_login.strftime("%b %d, %Y %H:%M") if user.last_login else "Never",
                },
            }
        )
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "User not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def edit_member_view(request, user_id):
    """Edit a member"""
    if request.method == "POST":
        try:
            user = User.objects.get(id=user_id)

            username = request.POST.get("username")
            email = request.POST.get("email")
            full_name = request.POST.get("full_name", "").strip() or request.POST.get("name", "").strip()
            mobile_primary = request.POST.get("mobile_primary", "")
            role = request.POST.get("role", "member")
            password = request.POST.get("password", "").strip()
            status = request.POST.get("status", user.status).strip() or user.status
            closure_reason = request.POST.get("closure_reason", "").strip()

            # Validate
            if not all([username, email]):
                return JsonResponse({"success": False, "error": "Username and email are required"})

            # Check if username is taken by another user
            if User.objects.filter(username=username).exclude(id=user_id).exists():
                return JsonResponse({"success": False, "error": "Username already exists"})

            # Check if email is taken by another user
            if User.objects.filter(email=email).exclude(id=user_id).exists():
                return JsonResponse({"success": False, "error": "Email already exists"})

            # Validate role
            valid_roles = ["admin", "member", "viewer"]
            if role not in valid_roles:
                role = "member"
            valid_statuses = ["active", "inactive", "resign"]
            if status not in valid_statuses:
                status = user.status

            # Split name into first_name and last_name using utility
            first_name, last_name = split_full_name(full_name)
            user.first_name = first_name
            user.last_name = last_name

            # Update user
            user.username = username
            user.email = email
            user.mobile_primary = mobile_primary
            user.role = role
            user.is_staff = role == "admin"
            previous_status = user.status
            user.status = status
            if closure_reason:
                user.closure_reason = closure_reason

            # Update password if provided (with validation)
            if password:
                is_valid, errors = validate_password_strength(password)
                if not is_valid:
                    return JsonResponse({"success": False, "error": errors[0]})
                user.set_password(password)

            with transaction.atomic():
                _apply_member_status_rules(user, status, previous_status=previous_status)
                user.save()

                settlement_receipts = []
                if status == "resign":
                    settlement_accounts = MemberAccount.objects.select_for_update().filter(
                        user=user,
                        is_deleted=False,
                        status="active",
                        balance__gt=0,
                    )
                    for account in settlement_accounts:
                        line = {
                            "account_id": account.id,
                            "transaction_type": "debit",
                            "amount": str(account.balance),
                            "description": "Member resignation settlement",
                        }
                        settlement_receipts.append(
                            _process_receipt_line(
                                user=user,
                                line=line,
                                payment_mode="cash",
                                reference_number="",
                                remarks="Auto settlement on resignation",
                                created_by=request.user,
                            )
                        )

            log_action(
                request,
                "update",
                "member",
                user.id,
                f"Updated member {user.username} ({user.display_name}) with status {user.status}",
            )
            if status == "resign" and settlement_receipts:
                log_action(
                    request,
                    "create",
                    "receipt",
                    settlement_receipts[-1].id,
                    f"Generated {len(settlement_receipts)} resignation settlement receipts for {user.display_name}",
                )
            return JsonResponse(
                {
                    "success": True,
                    "settlement_receipts": [r.receipt_number for r in settlement_receipts],
                }
            )
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "User not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def reset_member_password_view(request, user_id):
    """Reset member password to DOB-based format"""
    if request.method == "POST":
        try:
            user = User.objects.get(id=user_id)

            if not user.date_of_birth or not user.first_name:
                return JsonResponse(
                    {"success": False, "error": "Cannot reset password: Date of birth or name is missing"}
                )

            new_password = user.reset_password_to_dob()
            if new_password:
                user.save()
                log_action(
                    request,
                    "reset_password",
                    "member",
                    user.id,
                    f"Reset password for {user.username} ({user.display_name})",
                )
                return JsonResponse(
                    {"success": True, "password": new_password, "message": f"Password reset to: {new_password}"}
                )
            else:
                return JsonResponse({"success": False, "error": "Failed to generate password"})

        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "User not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def profile_view(request):
    """Admin profile view"""
    if request.method == "POST":
        # Handle name field - split into first_name and last_name using utility
        name = request.POST.get("name", "").strip()
        first_name, last_name = split_full_name(name)
        request.user.first_name = first_name
        request.user.last_name = last_name

        request.user.email = request.POST.get("email", "")
        request.user.mobile_primary = request.POST.get("mobile_primary", "")
        request.user.save()
        messages.success(request, "Profile updated successfully!")
        return redirect("/profile/")

    return render(request, "admin/profile.html")


@login_required
@admin_required
def accounts_view(request):
    """Account Book view - shows all members and their account balances in a grid"""
    query = request.GET.get("q", "").strip()
    account_type_filter = request.GET.get("account_type", "").strip()
    account_status_filter = request.GET.get("account_status", "").strip()
    member_status_filter = request.GET.get("member_status", "").strip()
    date_filter = request.GET.get("date_filter", "member_registered").strip() or "member_registered"
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    page = request.GET.get("page", 1)
    per_page = 50

    # Get all members with their accounts
    members = User.objects.filter(role="member", is_deleted=False).order_by("first_name", "last_name")

    # Apply search filter
    if query:
        members = members.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(member_id__icontains=query)
        )
    if member_status_filter:
        members = members.filter(status=member_status_filter)
    if date_filter not in ("member_registered", "account_opened"):
        date_filter = "member_registered"
    if date_filter == "member_registered":
        if date_from:
            members = members.filter(date_joined__date__gte=date_from)
        if date_to:
            members = members.filter(date_joined__date__lte=date_to)

    # Paginate members
    paginator = Paginator(members, per_page)
    try:
        members_page = paginator.page(page)
    except PageNotAnInteger:
        members_page = paginator.page(1)
    except EmptyPage:
        members_page = paginator.page(paginator.num_pages)

    # Build account book data structure
    account_types = MemberAccount.ACCOUNT_TYPE_CHOICES
    account_book = []

    for member in members_page:
        member_data = {
            "id": member.id,
            "name": member.display_name,
            "member_id": member.member_id or "-",
            "username": member.username,
            "account_balances": [],  # List of balances in order
            "total_balance": 0,
        }

        # Get all accounts for this member
        accounts = MemberAccount.objects.filter(user=member, is_deleted=False)
        if account_type_filter:
            accounts = accounts.filter(account_type=account_type_filter)
        if account_status_filter:
            accounts = accounts.filter(status=account_status_filter)
        if date_filter == "account_opened":
            if date_from:
                accounts = accounts.filter(opening_date__gte=date_from)
            if date_to:
                accounts = accounts.filter(opening_date__lte=date_to)
        accounts_dict = {acc.account_type: acc for acc in accounts}

        # Build ordered list of balances matching account_types order
        for account_type, _ in account_types:
            if account_type in accounts_dict:
                acc = accounts_dict[account_type]
                member_data["account_balances"].append(
                    {
                        "balance": acc.balance,
                        "status": acc.status,
                    }
                )
                if acc.status == "active":
                    member_data["total_balance"] += acc.balance
            else:
                member_data["account_balances"].append(
                    {
                        "balance": 0,
                        "status": "inactive",
                    }
                )

        account_book.append(member_data)

    # Calculate totals for each account type
    account_totals = []
    grand_total = 0
    totals_qs = MemberAccount.objects.filter(is_deleted=False)
    if account_status_filter:
        totals_qs = totals_qs.filter(status=account_status_filter)
    if member_status_filter:
        totals_qs = totals_qs.filter(user__status=member_status_filter)
    if date_filter == "member_registered":
        if date_from:
            totals_qs = totals_qs.filter(user__date_joined__date__gte=date_from)
        if date_to:
            totals_qs = totals_qs.filter(user__date_joined__date__lte=date_to)
    else:
        if date_from:
            totals_qs = totals_qs.filter(opening_date__gte=date_from)
        if date_to:
            totals_qs = totals_qs.filter(opening_date__lte=date_to)
    for account_type, _ in account_types:
        type_qs = totals_qs.filter(account_type=account_type)
        total = type_qs.aggregate(total=Sum("balance"))["total"] or 0
        account_totals.append(total)
        grand_total += total

    return render(
        request,
        "admin/accounts.html",
        {
            "account_book": account_book,
            "account_types": account_types,
            "account_totals": account_totals,
            "grand_total": grand_total,
            "search_query": query,
            "selected_account_type": account_type_filter,
            "selected_account_status": account_status_filter,
            "selected_member_status": member_status_filter,
            "account_status_choices": MemberAccount.STATUS_CHOICES,
            "member_status_choices": [("active", "Active"), ("inactive", "Inactive"), ("resign", "Resigned")],
            "page_obj": members_page,
            "date_filter": date_filter,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
@admin_required
def get_account_view(request, account_id):
    """Get account data for viewing/editing"""
    try:
        account = MemberAccount.objects.select_related("user").get(id=account_id)
        return JsonResponse(
            {
                "success": True,
                "account": {
                    "id": account.id,
                    "account_number": account.account_number,
                    "account_type": account.account_type,
                    "account_type_display": account.get_account_type_display(),
                    "status": account.status,
                    "status_display": account.get_status_display(),
                    "balance": str(account.balance),
                    "interest_rate": str(account.interest_rate),
                    "principal_amount": str(account.principal_amount),
                    "opening_date": account.opening_date.strftime("%Y-%m-%d") if account.opening_date else "",
                    "maturity_date": account.maturity_date.strftime("%Y-%m-%d") if account.maturity_date else "",
                    "tenure_months": account.tenure_months or "",
                    "user_id": account.user.id,
                    "user_name": account.user.display_name,
                    "member_id": account.user.member_id or "",
                    "nominee_name": account.nominee_name or "",
                    "nominee_relationship": account.nominee_relationship or "",
                    "remarks": account.remarks or "",
                },
            }
        )
    except MemberAccount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Account not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def get_account_transactions_view(request, account_id):
    """Get paginated transaction history for an account"""
    try:
        account = MemberAccount.objects.get(id=account_id)
        page = int(request.GET.get("page", 1))
        per_page = 20

        receipts = Receipt.objects.filter(member_account=account).order_by("-created_at")
        total = receipts.count()
        start = (page - 1) * per_page
        end = start + per_page
        page_receipts = receipts[start:end]

        transactions = []
        for r in page_receipts:
            transactions.append(
                {
                    "receipt_number": r.receipt_number,
                    "date": r.created_at.strftime("%b %d, %Y") if r.created_at else "-",
                    "type": r.get_transaction_type_display(),
                    "type_raw": r.transaction_type,
                    "description": r.description or "-",
                    "amount": str(r.amount),
                    "balance_after": str(r.balance_after) if r.balance_after is not None else "-",
                }
            )

        return JsonResponse(
            {
                "success": True,
                "transactions": transactions,
                "has_more": end < total,
                "total": total,
                "page": page,
            }
        )
    except MemberAccount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Account not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def account_details_view(request, account_id):
    """HTML account details page to avoid exposing raw JSON route."""
    try:
        account = MemberAccount.objects.select_related("user").get(id=account_id, is_deleted=False)
    except MemberAccount.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect("/accounts/")
    transactions = Receipt.objects.filter(member_account=account).order_by("-created_at")[:50]
    return render(
        request,
        "admin/account_details.html",
        {
            "account": account,
            "transactions": transactions,
        },
    )


# ========================================
# Receipt Views
# ========================================


@login_required
@admin_required
def receipts_view(request):
    """Receipts list view with pagination, search, and filters"""
    page = request.GET.get("page", 1)
    query = request.GET.get("q", "").strip()
    transaction_type = request.GET.get("type", "").strip()
    payment_mode = request.GET.get("mode", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    per_page = 25

    # Base queryset with related data
    receipts = Receipt.objects.select_related("user", "member_account", "created_by").all().order_by("-created_at")

    # Apply search filter
    if query:
        receipts = receipts.filter(
            Q(receipt_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__member_id__icontains=query)
            | Q(member_account__account_number__icontains=query)
            | Q(reference_number__icontains=query)
        )

    # Apply type filter
    if transaction_type:
        receipts = receipts.filter(transaction_type=transaction_type)

    # Apply payment mode filter
    if payment_mode:
        receipts = receipts.filter(payment_mode=payment_mode)
    if date_from:
        receipts = receipts.filter(created_at__date__gte=date_from)
    if date_to:
        receipts = receipts.filter(created_at__date__lte=date_to)

    # Paginate
    paginator = Paginator(receipts, per_page)
    try:
        receipts_page = paginator.page(page)
    except PageNotAnInteger:
        receipts_page = paginator.page(1)
    except EmptyPage:
        receipts_page = paginator.page(paginator.num_pages)

    # Summary stats
    total_receipts = Receipt.objects.count()
    today_receipts = Receipt.objects.filter(created_at__date=timezone.now().date()).count()

    return render(
        request,
        "admin/receipts.html",
        {
            "receipts": receipts_page,
            "search_query": query,
            "selected_type": transaction_type,
            "selected_mode": payment_mode,
            "date_from": date_from,
            "date_to": date_to,
            "transaction_type_choices": Receipt.TRANSACTION_TYPE_CHOICES,
            "payment_mode_choices": Receipt.PAYMENT_MODE_CHOICES,
            "page_obj": receipts_page,
            "total_receipts": total_receipts,
            "today_receipts": today_receipts,
            "society_name": getattr(settings, "SOCIETY_NAME", "Panels"),
            "funds": FundAccount.objects.filter(is_deleted=False, is_active=True).order_by("name"),
            "fund_options_json": json.dumps(
                [
                    {"id": item.id, "name": item.name, "type": item.get_fund_type_display()}
                    for item in FundAccount.objects.filter(is_deleted=False, is_active=True).order_by("name")
                ]
            ),
        },
    )


@login_required
@admin_required
def get_receipt_view(request, receipt_id):
    """Get receipt data for viewing"""
    try:
        receipt = Receipt.objects.select_related("user", "member_account", "created_by").get(id=receipt_id)
        return JsonResponse(
            {
                "success": True,
                "receipt": {
                    "id": receipt.id,
                    "receipt_number": receipt.receipt_number,
                    "transaction_type": receipt.transaction_type,
                    "transaction_type_display": receipt.get_transaction_type_display(),
                    "amount": str(receipt.amount),
                    "description": receipt.description or "",
                    "payment_mode": receipt.payment_mode,
                    "payment_mode_display": receipt.get_payment_mode_display(),
                    "reference_number": receipt.reference_number or "",
                    "balance_after": str(receipt.balance_after),
                    "remarks": receipt.remarks or "",
                    "created_at": receipt.created_at.strftime("%b %d, %Y %I:%M %p") if receipt.created_at else "",
                    "created_date": receipt.created_at.strftime("%b %d, %Y") if receipt.created_at else "",
                    # Member info
                    "member_name": receipt.user.display_name,
                    "member_id": receipt.user.member_id or "",
                    "member_mobile": receipt.user.mobile_primary or "",
                    "member_address": ", ".join(
                        filter(
                            None,
                            [
                                receipt.user.current_address_line1,
                                receipt.user.current_city,
                                receipt.user.current_state,
                                receipt.user.current_pincode,
                            ],
                        )
                    ),
                    # Account info
                    "account_number": receipt.member_account.account_number,
                    "account_type": receipt.member_account.account_type,
                    "account_type_display": receipt.member_account.get_account_type_display(),
                    # Admin info
                    "created_by_name": receipt.created_by.display_name if receipt.created_by else "",
                },
            }
        )
    except Receipt.DoesNotExist:
        return JsonResponse({"success": False, "error": "Receipt not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def add_receipt_view(request):
    """Create one or more receipts, or stage voucher entries."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})
    try:
        user_id = request.POST.get("user_id")
        if not user_id:
            return JsonResponse({"success": False, "error": "Member is required"})
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "Member not found"})

        payment_mode = request.POST.get("payment_mode", "cash")
        reference_number = request.POST.get("reference_number", "").strip()
        remarks = request.POST.get("remarks", "").strip()
        use_voucher = request.POST.get("use_voucher", "").lower() in ("1", "true", "yes", "on")
        if payment_mode == "cash":
            use_voucher = True

        voucher_type = request.POST.get("voucher_type", "voucher").strip() or "voucher"
        fund_id = request.POST.get("fund_id", "").strip()
        account_entries_raw = request.POST.get("account_entries", "").strip()

        if not account_entries_raw:
            return JsonResponse({"success": False, "error": "At least one account entry is required"})

        account_entries = json.loads(account_entries_raw)

        if not isinstance(account_entries, list) or not account_entries:
            return JsonResponse({"success": False, "error": "At least one account entry is required"})

        if use_voucher:
            if voucher_type not in ("voucher", "contra_voucher"):
                voucher_type = "voucher"
            with transaction.atomic():
                voucher = Voucher.objects.create(
                    voucher_number=_next_voucher_number(),
                    user=user,
                    voucher_type=voucher_type,
                    total_amount=Decimal("0.00"),
                    payment_mode=payment_mode,
                    reference_number=reference_number or None,
                    remarks=remarks or None,
                    created_by=request.user,
                )
                total_amount = Decimal("0.00")
                for line in account_entries:
                    line_type = (line.get("transaction_type") or "").strip()
                    if line_type == "loan_emi":
                        line["transaction_type"] = "credit"
                    account = MemberAccount.objects.get(id=line.get("account_id"), user=user, is_deleted=False)
                    line_amount = Decimal(str(line.get("amount", "0")))
                    if line_amount <= 0:
                        return JsonResponse({"success": False, "error": "Each voucher line amount must be positive"})
                    if line["transaction_type"] not in dict(Receipt.TRANSACTION_TYPE_CHOICES):
                        return JsonResponse({"success": False, "error": f"Invalid transaction type: {line['transaction_type']}"})
                    VoucherEntry.objects.create(
                        voucher=voucher,
                        member_account=account,
                        transaction_type=line.get("transaction_type", "credit"),
                        amount=line_amount,
                        description=(line.get("description") or "").strip() or None,
                        linked_loan_repayment_id=line.get("loan_repayment_id") or None,
                    )
                    total_amount += line_amount
                voucher.total_amount = total_amount
                voucher.save(update_fields=["total_amount"])
            log_action(
                request,
                "create",
                "voucher",
                voucher.id,
                f"Created voucher {voucher.voucher_number} with {voucher.entries.count()} line(s) for {user.display_name}",
            )
            return JsonResponse({"success": True, "voucher_id": voucher.id, "voucher_number": voucher.voucher_number})

        created_receipts = []
        with transaction.atomic():
            for line in account_entries:
                line_type = (line.get("transaction_type") or "").strip()
                if line_type == "loan_emi":
                    line["transaction_type"] = "credit"
                if line.get("transaction_type") not in dict(Receipt.TRANSACTION_TYPE_CHOICES):
                    return JsonResponse({"success": False, "error": "Invalid transaction type in entry"})
                receipt = _process_receipt_line(
                    user=user,
                    line=line,
                    payment_mode=payment_mode,
                    reference_number=reference_number,
                    remarks=remarks,
                    created_by=request.user,
                )
                created_receipts.append(receipt)
                if receipt.transaction_type == "interest":
                    try:
                        apply_fund_allocations(
                            request,
                            "loan_interest",
                            receipt.amount,
                            f"Loan interest: {user.display_name} - {receipt.member_account.account_number}",
                            source_member=user,
                        )
                    except Exception:
                        pass
            if fund_id:
                fund = FundAccount.objects.select_for_update().get(id=fund_id, is_deleted=False, is_active=True)
                total_amount = sum((item.amount for item in created_receipts), Decimal("0.00"))
                FundAccount.objects.filter(id=fund.id).update(balance=F("balance") + total_amount)
                fund.refresh_from_db(fields=["balance"])
                FundTransaction.objects.create(
                    fund=fund,
                    transaction_type="credit",
                    amount=total_amount,
                    description=f"Receipt settlement from {user.display_name}",
                    payment_mode="internal",
                    reference_number=reference_number or None,
                    balance_after=fund.balance,
                    source_member=user,
                    created_by=request.user,
                )

        log_action(
            request,
            "create",
            "receipt",
            created_receipts[-1].id,
            f"Created {len(created_receipts)} receipt line(s) for {user.display_name}",
        )
        return JsonResponse(
            {
                "success": True,
                "receipt_id": created_receipts[0].id,
                "receipt_ids": [item.id for item in created_receipts],
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def vouchers_view(request):
    """List pending and transferred vouchers for receipts page."""
    vouchers = Voucher.objects.select_related("user", "created_by", "transferred_to_fund").prefetch_related("entries")[:100]
    data = []
    for voucher in vouchers:
        data.append(
            {
                "id": voucher.id,
                "voucher_number": voucher.voucher_number,
                "member_name": voucher.user.display_name,
                "member_id": voucher.user.member_id or "",
                "total_amount": str(voucher.total_amount),
                "status": voucher.status,
                "status_display": voucher.get_status_display(),
                "voucher_type": voucher.voucher_type,
                "voucher_type_display": voucher.get_voucher_type_display(),
                "line_count": voucher.entries.count(),
                "created_at": voucher.created_at.strftime("%b %d, %Y %I:%M %p"),
                "fund_name": voucher.transferred_to_fund.name if voucher.transferred_to_fund else "",
            }
        )
    return JsonResponse({"success": True, "vouchers": data})


@login_required
@admin_required
def transfer_voucher_to_fund_view(request, voucher_id):
    """Convert voucher lines to receipts and move total to a fund."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})
    fund_id = request.POST.get("fund_id", "").strip()
    if not fund_id:
        return JsonResponse({"success": False, "error": "Fund is required"})
    try:
        with transaction.atomic():
            voucher = Voucher.objects.select_for_update().get(id=voucher_id)
            if voucher.status != "pending":
                return JsonResponse({"success": False, "error": "Voucher is already processed"})
            fund = FundAccount.objects.select_for_update().get(id=fund_id, is_deleted=False, is_active=True)
            receipts = []
            for entry in voucher.entries.select_related("member_account").all():
                line = {
                    "account_id": entry.member_account_id,
                    "transaction_type": entry.transaction_type,
                    "amount": str(entry.amount),
                    "description": entry.description,
                    "loan_repayment_id": entry.linked_loan_repayment_id,
                }
                receipt = _process_receipt_line(
                    user=voucher.user,
                    line=line,
                    payment_mode=voucher.payment_mode,
                    reference_number=voucher.reference_number or "",
                    remarks=voucher.remarks or "",
                    created_by=request.user,
                )
                entry.created_receipt = receipt
                entry.save(update_fields=["created_receipt"])
                receipts.append(receipt)
            FundAccount.objects.filter(id=fund.id).update(balance=F("balance") + voucher.total_amount)
            fund.refresh_from_db(fields=["balance"])
            FundTransaction.objects.create(
                fund=fund,
                transaction_type="credit",
                amount=voucher.total_amount,
                description=f"Voucher transfer {voucher.voucher_number}",
                payment_mode="internal",
                reference_number=voucher.reference_number or None,
                balance_after=fund.balance,
                source_member=voucher.user,
                created_by=request.user,
            )
            voucher.status = "transferred"
            voucher.transferred_to_fund = fund
            voucher.transferred_at = timezone.now()
            voucher.save(update_fields=["status", "transferred_to_fund", "transferred_at"])
        log_action(
            request,
            "create",
            "voucher",
            voucher.id,
            f"Transferred {voucher.get_voucher_type_display()} {voucher.voucher_number} to fund {fund.name}",
        )
        return JsonResponse({"success": True, "receipt_ids": [item.id for item in receipts]})
    except Voucher.DoesNotExist:
        return JsonResponse({"success": False, "error": "Voucher not found"})
    except FundAccount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Fund not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def get_member_accounts_view(request, user_id):
    """Get accounts for a specific member (for cascading dropdown)"""
    try:
        user = User.objects.get(id=user_id)
        accounts = MemberAccount.objects.filter(user=user, status="active", is_deleted=False).order_by("account_type")

        results = [
            {
                "id": account.id,
                "account_number": account.account_number,
                "account_type": account.account_type,
                "account_type_display": account.get_account_type_display(),
                "balance": str(account.balance),
            }
            for account in accounts
        ]

        pending_repayments = (
            LoanRepayment.objects.filter(loan__user=user, loan__status="active")
            .exclude(payment_status="paid")
            .select_related("loan", "loan__disbursement_account")
            .order_by("due_date")[:20]
        )
        pending_emi_data = [
            {
                "id": repayment.id,
                "loan_id": repayment.loan.id,
                "loan_number": repayment.loan.loan_number,
                "installment_number": repayment.installment_number,
                "amount_due": str(repayment.amount_due),
                "due_date": repayment.due_date.strftime("%Y-%m-%d"),
                "status": repayment.payment_status,
                "account_id": repayment.loan.disbursement_account_id or "",
            }
            for repayment in pending_repayments
        ]
        return JsonResponse({"success": True, "accounts": results, "pending_emis": pending_emi_data})
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "Member not found"})


@login_required
@admin_required
def get_member_transactions_view(request, user_id):
    """Get recent transactions for a member (for modal transaction history tab)"""
    try:
        user = User.objects.get(id=user_id)
        page = int(request.GET.get("page", 1))
        per_page = 15

        receipts = Receipt.objects.select_related("member_account").filter(user=user).order_by("-created_at")

        total = receipts.count()
        start = (page - 1) * per_page
        end = start + per_page
        receipts_page = receipts[start:end]

        results = [
            {
                "id": r.id,
                "receipt_number": r.receipt_number,
                "transaction_type": r.transaction_type,
                "transaction_type_display": r.get_transaction_type_display(),
                "amount": str(r.amount),
                "payment_mode_display": r.get_payment_mode_display(),
                "account_number": r.member_account.account_number,
                "balance_after": str(r.balance_after),
                "created_at": r.created_at.strftime("%b %d, %Y") if r.created_at else "",
            }
            for r in receipts_page
        ]

        return JsonResponse(
            {
                "success": True,
                "transactions": results,
                "total": total,
                "page": page,
                "has_more": end < total,
            }
        )
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "Member not found"})


# ========================================
# Loan Views
# ========================================


@login_required
@admin_required
def loans_view(request):
    """Loans list view with pagination, search, and filters"""
    page = request.GET.get("page", 1)
    query = request.GET.get("q", "").strip()
    loan_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    per_page = 25

    # Base queryset with related data
    loans = Loan.objects.select_related("user", "approved_by", "created_by").all().order_by("-created_at")

    # Apply search filter
    if query:
        loans = loans.filter(
            Q(loan_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__member_id__icontains=query)
            | Q(guarantor_name__icontains=query)
        )

    # Apply loan type filter
    if loan_type:
        loans = loans.filter(loan_type=loan_type)

    # Apply status filter
    if status:
        loans = loans.filter(status=status)

    # Paginate
    paginator = Paginator(loans, per_page)
    try:
        loans_page = paginator.page(page)
    except PageNotAnInteger:
        loans_page = paginator.page(1)
    except EmptyPage:
        loans_page = paginator.page(paginator.num_pages)

    # Summary stats
    total_loans = Loan.objects.count()
    active_loans = Loan.objects.filter(status="active").count()
    total_disbursed = Loan.objects.filter(status="active").aggregate(total=Sum("principal_amount"))["total"] or 0
    total_outstanding = Loan.objects.filter(status="active").aggregate(total=Sum("outstanding_balance"))["total"] or 0

    return render(
        request,
        "admin/loans.html",
        {
            "loans": loans_page,
            "search_query": query,
            "selected_type": loan_type,
            "selected_status": status,
            "loan_type_choices": Loan.LOAN_TYPE_CHOICES,
            "status_choices": Loan.STATUS_CHOICES,
            "page_obj": loans_page,
            "total_loans": total_loans,
            "active_loans": active_loans,
            "total_disbursed": total_disbursed,
            "total_outstanding": total_outstanding,
        },
    )


@login_required
@admin_required
def get_loan_view(request, loan_id):
    """Get loan data for viewing - includes repayments schedule"""
    try:
        loan = Loan.objects.select_related("user", "disbursement_account", "approved_by", "created_by").get(id=loan_id)

        repayments = loan.repayments.all().order_by("installment_number")
        repayments_data = [
            {
                "installment_number": r.installment_number,
                "due_date": r.due_date.strftime("%b %d, %Y") if r.due_date else "",
                "due_date_raw": r.due_date.strftime("%Y-%m-%d") if r.due_date else "",
                "paid_date": r.paid_date.strftime("%b %d, %Y") if r.paid_date else "",
                "amount_due": str(r.amount_due),
                "amount_paid": str(r.amount_paid),
                "principal_component": str(r.principal_component),
                "interest_component": str(r.interest_component),
                "penalty": str(r.penalty),
                "balance_after": str(r.balance_after),
                "payment_status": r.payment_status,
                "payment_status_display": r.get_payment_status_display(),
            }
            for r in repayments
        ]

        return JsonResponse(
            {
                "success": True,
                "loan": {
                    "id": loan.id,
                    "loan_number": loan.loan_number,
                    "loan_type": loan.loan_type,
                    "loan_type_display": loan.get_loan_type_display(),
                    "status": loan.status,
                    "status_display": loan.get_status_display(),
                    # Member
                    "member_name": loan.user.display_name,
                    "member_id": loan.user.member_id or "",
                    "user_id": loan.user.id,
                    # Financial
                    "principal_amount": str(loan.principal_amount),
                    "interest_rate": str(loan.interest_rate),
                    "interest_type": loan.interest_type,
                    "interest_type_display": loan.get_interest_type_display(),
                    "tenure_months": loan.tenure_months,
                    "emi_amount": str(loan.emi_amount),
                    "total_payable": str(loan.total_payable),
                    "total_paid": str(loan.total_paid),
                    "outstanding_balance": str(loan.outstanding_balance),
                    "overdue_amount": str(loan.overdue_amount),
                    "completion_percentage": loan.completion_percentage,
                    # Dates
                    "application_date": loan.application_date.strftime("%b %d, %Y") if loan.application_date else "",
                    "approval_date": loan.approval_date.strftime("%b %d, %Y") if loan.approval_date else "",
                    "disbursement_date": loan.disbursement_date.strftime("%b %d, %Y") if loan.disbursement_date else "",
                    "first_emi_date": loan.first_emi_date.strftime("%b %d, %Y") if loan.first_emi_date else "",
                    "last_emi_date": loan.last_emi_date.strftime("%b %d, %Y") if loan.last_emi_date else "",
                    "closure_date": loan.closure_date.strftime("%b %d, %Y") if loan.closure_date else "",
                    # EMI tracking
                    "total_emis": loan.total_emis,
                    "emis_paid": loan.emis_paid,
                    "emis_overdue": loan.emis_overdue,
                    # Guarantor
                    "guarantor_name": loan.guarantor_name or "",
                    "guarantor_member_id": loan.guarantor_member_id or "",
                    "guarantor_relationship": loan.guarantor_relationship or "",
                    "guarantor_contact": loan.guarantor_contact or "",
                    # Collateral
                    "collateral_type": loan.collateral_type or "",
                    "collateral_value": str(loan.collateral_value) if loan.collateral_value else "",
                    "collateral_description": loan.collateral_description or "",
                    # Disbursement account
                    "disbursement_account_number": loan.disbursement_account.account_number
                    if loan.disbursement_account
                    else "",
                    # Internal
                    "purpose": loan.purpose or "",
                    "remarks": loan.remarks or "",
                    "approved_by_name": loan.approved_by.display_name if loan.approved_by else "",
                    "created_by_name": loan.created_by.display_name if loan.created_by else "",
                    "created_at": loan.created_at.strftime("%b %d, %Y") if loan.created_at else "",
                    # Repayments
                    "repayments": repayments_data,
                },
            }
        )
    except Loan.DoesNotExist:
        return JsonResponse({"success": False, "error": "Loan not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def add_loan_view(request):
    """Create a new loan application"""
    if request.method == "POST":
        try:
            user_id = request.POST.get("user_id")
            loan_type = request.POST.get("loan_type")
            principal_amount = request.POST.get("principal_amount")
            interest_rate = request.POST.get("interest_rate")
            interest_type = request.POST.get("interest_type", "reducing")
            tenure_months = request.POST.get("tenure_months")
            purpose = request.POST.get("purpose", "").strip()
            remarks = request.POST.get("remarks", "").strip()

            # Guarantor
            guarantor_name = request.POST.get("guarantor_name", "").strip()
            guarantor_member_id = request.POST.get("guarantor_member_id", "").strip()
            guarantor_relationship = request.POST.get("guarantor_relationship", "").strip()
            guarantor_contact = request.POST.get("guarantor_contact", "").strip()

            # Collateral
            collateral_type = request.POST.get("collateral_type", "").strip()
            collateral_value = request.POST.get("collateral_value") or None
            collateral_description = request.POST.get("collateral_description", "").strip()

            # Validate required fields
            if not user_id:
                return JsonResponse({"success": False, "error": "Member is required"})
            if not loan_type:
                return JsonResponse({"success": False, "error": "Loan type is required"})
            if not principal_amount:
                return JsonResponse({"success": False, "error": "Loan amount is required"})
            if not interest_rate:
                return JsonResponse({"success": False, "error": "Interest rate is required"})
            if not tenure_months:
                return JsonResponse({"success": False, "error": "Tenure is required"})

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({"success": False, "error": "Member not found"})

            principal = Decimal(str(principal_amount))
            rate = Decimal(str(interest_rate))
            tenure = int(tenure_months)

            # Calculate EMI
            if rate > 0:
                monthly_rate = rate / Decimal("1200")
                if interest_type == "flat":
                    total_interest = principal * rate * Decimal(str(tenure)) / Decimal("1200")
                    emi = (principal + total_interest) / Decimal(str(tenure))
                    total_payable = principal + total_interest
                else:
                    # Reducing balance EMI formula
                    factor = (1 + monthly_rate) ** tenure
                    emi = (principal * monthly_rate * factor) / (factor - 1)
                    total_payable = emi * Decimal(str(tenure))
            else:
                emi = principal / Decimal(str(tenure))
                total_payable = principal

            emi = emi.quantize(Decimal("0.01"))
            total_payable = total_payable.quantize(Decimal("0.01"))

            # Auto-generate loan number
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        year = date.today().year
                        last_loan = (
                            Loan.objects.select_for_update()
                            .filter(loan_number__startswith=f"LN-{year}-")
                            .order_by("-loan_number")
                            .first()
                        )
                        if last_loan:
                            try:
                                last_seq = int(last_loan.loan_number.split("-")[-1])
                                next_seq = last_seq + 1
                            except (ValueError, IndexError):
                                next_seq = 1
                        else:
                            next_seq = 1

                        loan_number = f"LN-{year}-{next_seq:05d}"

                        loan = Loan.objects.create(
                            loan_number=loan_number,
                            user=user,
                            loan_type=loan_type,
                            principal_amount=principal,
                            interest_rate=rate,
                            interest_type=interest_type,
                            tenure_months=tenure,
                            emi_amount=emi,
                            total_payable=total_payable,
                            outstanding_balance=principal,
                            total_emis=tenure,
                            application_date=date.today(),
                            purpose=purpose or None,
                            remarks=remarks or None,
                            guarantor_name=guarantor_name or None,
                            guarantor_member_id=guarantor_member_id or None,
                            guarantor_relationship=guarantor_relationship or None,
                            guarantor_contact=guarantor_contact or None,
                            collateral_type=collateral_type or None,
                            collateral_value=Decimal(str(collateral_value)) if collateral_value else None,
                            collateral_description=collateral_description or None,
                            created_by=request.user,
                        )

                    log_action(
                        request,
                        "create",
                        "loan",
                        loan.id,
                        f"Created loan {loan_number} for {user.display_name} - {loan.get_loan_type_display()} Rs.{principal}",
                    )
                    return JsonResponse({"success": True, "loan_id": loan.id})
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise
                    continue

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def audit_logs_view(request):
    """Audit logs list view with filtering and pagination"""
    search_query = request.GET.get("q", "").strip()
    action_filter = request.GET.get("action", "").strip()
    entity_filter = request.GET.get("entity", "").strip()

    logs = AuditLog.objects.select_related("user").all()

    if search_query:
        logs = logs.filter(
            Q(description__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__username__icontains=search_query)
        )

    if action_filter:
        logs = logs.filter(action=action_filter)

    if entity_filter:
        logs = logs.filter(entity_type=entity_filter)

    # Pagination
    paginator = Paginator(logs, 50)
    page = request.GET.get("page")
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "logs": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "action_filter": action_filter,
        "entity_filter": entity_filter,
        "action_choices": AuditLog.ACTION_CHOICES,
        "entity_choices": AuditLog.ENTITY_CHOICES,
        "total_logs": paginator.count,
    }

    return render(request, "admin/audit_logs.html", context)


@login_required
@admin_required
def get_audit_log_view(request, log_id):
    """Get single audit log details"""
    try:
        log = AuditLog.objects.select_related("user").get(id=log_id)
        return JsonResponse(
            {
                "success": True,
                "log": {
                    "id": log.id,
                    "user_name": log.user.display_name if log.user else "System",
                    "user_username": log.user.username if log.user else "",
                    "action": log.action,
                    "action_display": log.get_action_display(),
                    "entity_type": log.entity_type,
                    "entity_type_display": log.get_entity_type_display(),
                    "entity_id": log.entity_id,
                    "description": log.description,
                    "ip_address": log.ip_address or "",
                    "created_at": log.created_at.strftime("%b %d, %Y %I:%M %p"),
                },
            }
        )
    except AuditLog.DoesNotExist:
        return JsonResponse({"success": False, "error": "Audit log not found"})


@login_required
@admin_required
def reports_view(request):
    """Financial reports page with profit calculation and portfolio analysis."""
    # Period selector
    period = request.GET.get("period", "year")
    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    month_key = request.GET.get("month_key", "").strip()
    account_type_filter = request.GET.get("account_type", "").strip()

    if month_key:
        try:
            month_year, month_num = month_key.split("-")
            year = int(month_year)
            month = int(month_num)
            period = "month"
        except (ValueError, TypeError):
            month_key = ""

    if period == "month":
        import calendar

        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
    elif period == "quarter":
        quarter = int(request.GET.get("quarter", (date.today().month - 1) // 3 + 1))
        start_month = (quarter - 1) * 3 + 1
        import calendar

        end_month = start_month + 2
        start_date = date(year, start_month, 1)
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = date(year, end_month, last_day)
    else:  # year
        start_date = date(year, 4, 1)  # Indian fiscal year: April 1
        end_date = date(year + 1, 3, 31)

    summary = get_financial_summary(start_date, end_date)
    account_type_cashflow = get_account_type_cashflow(months=6, account_type=account_type_filter or None)

    # Monthly breakdown for chart (revenue vs expense per month)
    monthly_data = []
    import calendar

    current = start_date
    while current <= end_date:
        month_start = current.replace(day=1)
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = current.replace(day=last_day)
        month_summary = get_financial_summary(month_start, month_end)
        monthly_data.append(
            {
                "month": current.strftime("%b %Y"),
                "revenue": float(month_summary["gross_revenue"]),
                "expense": float(month_summary["total_expenses"]),
                "profit": float(month_summary["net_profit"]),
            }
        )
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    # Fund balances
    fund_balances = FundAccount.objects.filter(is_deleted=False, is_active=True)

    # NPA summary
    npa_loans = [loan for loan in Loan.objects.filter(status="active") if loan.is_npa]
    npa_summary = {}
    for loan in npa_loans:
        cat = loan.npa_category or "substandard"
        if cat not in npa_summary:
            npa_summary[cat] = {"count": 0, "amount": Decimal("0.00")}
        npa_summary[cat]["count"] += 1
        npa_summary[cat]["amount"] += loan.outstanding_balance

    # Maturity alerts - accounts maturing in next 30/60/90 days
    today = date.today()
    maturing_30 = (
        MemberAccount.objects.filter(
            is_deleted=False, status="active", maturity_date__range=(today, today + timedelta(days=30))
        )
        .select_related("user")
        .order_by("maturity_date")
    )
    maturing_60 = MemberAccount.objects.filter(
        is_deleted=False, status="active", maturity_date__range=(today + timedelta(days=31), today + timedelta(days=60))
    ).select_related("user")
    maturing_90 = MemberAccount.objects.filter(
        is_deleted=False, status="active", maturity_date__range=(today + timedelta(days=61), today + timedelta(days=90))
    ).select_related("user")

    # Dividend summary
    total_share_capital = User.objects.filter(is_deleted=False, status="active", share_capital_amount__gt=0).aggregate(
        total=Sum("share_capital_amount")
    )["total"] or Decimal("0.00")
    eligible_dividend_members = User.objects.filter(
        is_deleted=False, status="active", eligible_for_dividend=True, share_capital_amount__gt=0
    ).count()

    context = {
        "summary": summary,
        "monthly_data_json": json.dumps(monthly_data),
        "fund_balances": fund_balances,
        "npa_summary": npa_summary,
        "npa_loans": npa_loans,
        "period": period,
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "current_year": date.today().year,
        "maturing_30": maturing_30,
        "maturing_60_count": maturing_60.count(),
        "maturing_90_count": maturing_90.count(),
        "total_share_capital": total_share_capital,
        "eligible_dividend_members": eligible_dividend_members,
        "account_type_cashflow": account_type_cashflow,
        "selected_account_type": account_type_filter,
        "account_type_choices": MemberAccount.ACCOUNT_TYPE_CHOICES,
        "month": month,
        "month_key": month_key or f"{year:04d}-{month:02d}",
    }
    return render(request, "admin/reports.html", context)


@login_required
@admin_required
def database_view(request):
    """Database schema overview page for admins."""
    model_counts = [
        {"name": "User", "table": User._meta.db_table, "count": User.objects.count(), "purpose": "Members/Admins and profile data"},
        {
            "name": "MemberAccount",
            "table": MemberAccount._meta.db_table,
            "count": MemberAccount.objects.count(),
            "purpose": "Deposit/share/OD account ledgers",
        },
        {"name": "Receipt", "table": Receipt._meta.db_table, "count": Receipt.objects.count(), "purpose": "Posted transactions"},
        {"name": "Voucher", "table": Voucher._meta.db_table, "count": Voucher.objects.count(), "purpose": "Staged vouchers"},
        {
            "name": "VoucherEntry",
            "table": VoucherEntry._meta.db_table,
            "count": VoucherEntry.objects.count(),
            "purpose": "Line items under voucher",
        },
        {"name": "Loan", "table": Loan._meta.db_table, "count": Loan.objects.count(), "purpose": "Loan contracts"},
        {
            "name": "LoanRepayment",
            "table": LoanRepayment._meta.db_table,
            "count": LoanRepayment.objects.count(),
            "purpose": "EMI schedule and payments",
        },
        {"name": "FundAccount", "table": FundAccount._meta.db_table, "count": FundAccount.objects.count(), "purpose": "Society funds"},
        {
            "name": "FundTransaction",
            "table": FundTransaction._meta.db_table,
            "count": FundTransaction.objects.count(),
            "purpose": "Fund ledger entries",
        },
        {"name": "AuditLog", "table": AuditLog._meta.db_table, "count": AuditLog.objects.count(), "purpose": "Audit trail"},
    ]

    relationships = [
        {"from": "User", "to": "MemberAccount", "label": "1:N"},
        {"from": "User", "to": "Receipt", "label": "1:N"},
        {"from": "MemberAccount", "to": "Receipt", "label": "1:N"},
        {"from": "User", "to": "Voucher", "label": "1:N"},
        {"from": "Voucher", "to": "VoucherEntry", "label": "1:N"},
        {"from": "MemberAccount", "to": "VoucherEntry", "label": "1:N"},
        {"from": "User", "to": "Loan", "label": "1:N"},
        {"from": "Loan", "to": "LoanRepayment", "label": "1:N"},
        {"from": "Receipt", "to": "LoanRepayment", "label": "1:N"},
        {"from": "FundAccount", "to": "FundTransaction", "label": "1:N"},
        {"from": "User", "to": "AuditLog", "label": "1:N"},
    ]

    mermaid_lines = [
        "graph LR",
        'U["User"]',
        'MA["MemberAccount"]',
        'R["Receipt"]',
        'V["Voucher"]',
        'VE["VoucherEntry"]',
        'L["Loan"]',
        'LR["LoanRepayment"]',
        'F["FundAccount"]',
        'FT["FundTransaction"]',
        'AL["AuditLog"]',
        "U -->|1:N| MA",
        "U -->|1:N| R",
        "MA -->|1:N| R",
        "U -->|1:N| V",
        "V -->|1:N| VE",
        "MA -->|1:N| VE",
        "U -->|1:N| L",
        "L -->|1:N| LR",
        "R -->|1:N| LR",
        "F -->|1:N| FT",
        "U -->|1:N| AL",
    ]

    return render(
        request,
        "admin/database.html",
        {
            "model_counts": model_counts,
            "relationships": relationships,
            "mermaid_graph": "\n".join(mermaid_lines),
        },
    )


@login_required
@admin_required
def distribute_profit_view(request):
    """Distribute annual profit to funds based on allocation rules."""
    if request.method == "POST":
        try:
            from accounts.utils import get_financial_summary

            year = int(request.POST.get("year", date.today().year))
            start_date = date(year, 4, 1)
            end_date = date(year + 1, 3, 31)

            summary = get_financial_summary(start_date, end_date)
            net_profit = summary["net_profit"]

            if net_profit <= 0:
                return JsonResponse(
                    {"success": False, "error": f"No distributable profit for FY {year}-{year + 1}. Net: ₹{net_profit}"}
                )

            # Apply annual_profit allocation rules
            from accounts.utils import apply_fund_allocations

            transactions = apply_fund_allocations(
                request,
                "annual_profit",
                net_profit,
                f"Annual profit distribution for FY {year}-{year + 1}",
            )

            if not transactions:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "No allocation rules configured for 'Annual Profit'. Add rules in Allocation Rules page.",
                    }
                )

            total_allocated = sum(t.amount for t in transactions)
            log_action(
                request,
                "create",
                "fund",
                None,
                f"Distributed annual profit ₹{net_profit} for FY {year}-{year + 1}. "
                f"Allocated ₹{total_allocated} across {len(transactions)} funds.",
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Distributed ₹{total_allocated} across {len(transactions)} funds.",
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def distribute_dividend_view(request):
    """Calculate and distribute dividends to eligible members based on share capital."""
    if request.method == "POST":
        try:
            year = int(request.POST.get("year", date.today().year))
            dividend_rate = request.POST.get("dividend_rate")

            if not dividend_rate:
                return JsonResponse({"success": False, "error": "Dividend rate is required"})

            dividend_rate = Decimal(dividend_rate)
            if dividend_rate <= 0 or dividend_rate > 100:
                return JsonResponse({"success": False, "error": "Dividend rate must be between 0.01 and 100"})

            # Get eligible members with share capital
            eligible_members = User.objects.filter(
                is_deleted=False,
                status="active",
                eligible_for_dividend=True,
                share_capital_amount__gt=0,
            )

            if not eligible_members.exists():
                return JsonResponse({"success": False, "error": "No eligible members with share capital found"})

            total_distributed = Decimal("0.00")
            member_count = 0

            with transaction.atomic():
                for member in eligible_members:
                    # Dividend = share_capital * rate / 100
                    dividend_amount = (member.share_capital_amount * dividend_rate / Decimal("100")).quantize(
                        Decimal("0.01")
                    )

                    if dividend_amount <= 0:
                        continue

                    # Update member's dividend payable
                    User.objects.filter(id=member.id).update(
                        dividend_payable_balance=F("dividend_payable_balance") + dividend_amount,
                        last_dividend_paid_date=date.today(),
                    )

                    total_distributed += dividend_amount
                    member_count += 1

                # Deduct from Dividend Fund if it exists
                dividend_fund = FundAccount.objects.filter(
                    fund_type="dividend", is_deleted=False, is_active=True
                ).first()

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

                log_action(
                    request,
                    "create",
                    "fund",
                    None,
                    f"Distributed dividend @ {dividend_rate}% for FY {year}-{year + 1}. "
                    f"₹{total_distributed} to {member_count} members.",
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Distributed ₹{total_distributed} as dividend @ {dividend_rate}% to {member_count} members.",
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def post_interest_view(request):
    """Calculate and post accrued interest to eligible deposit accounts."""
    if request.method == "POST":
        try:
            period_end = date.today()

            # Get all active deposit accounts (not share, not OD)
            accounts = (
                MemberAccount.objects.filter(
                    is_deleted=False,
                    status="active",
                    interest_rate__gt=0,
                )
                .exclude(account_type__in=["share", "od"])
                .select_related("user")
            )

            total_posted = Decimal("0.00")
            accounts_updated = 0

            with transaction.atomic():
                for account in accounts:
                    # Skip if interest was already calculated for this period
                    if account.last_interest_calc_date and account.last_interest_calc_date >= period_end:
                        continue

                    # Calculate interest for the period
                    calc_start = account.last_interest_calc_date or account.opening_date
                    if calc_start >= period_end:
                        continue

                    days = (period_end - calc_start).days
                    if days <= 0:
                        continue

                    # Daily interest = balance * rate / 100 / 365
                    interest_amount = (
                        account.balance * account.interest_rate * Decimal(str(days)) / Decimal("36500")
                    ).quantize(Decimal("0.01"))

                    if interest_amount <= 0:
                        continue

                    # Update accrued interest on account
                    MemberAccount.objects.filter(id=account.id).update(
                        accrued_interest=F("accrued_interest") + interest_amount,
                        last_interest_calc_date=period_end,
                    )

                    # Create InterestPayout record
                    InterestPayout.objects.create(
                        account=account,
                        amount=interest_amount,
                        period_start=calc_start,
                        period_end=period_end,
                        created_by=request.user,
                    )

                    # Create a receipt for the interest credit
                    last_receipt = Receipt.objects.order_by("-id").first()
                    if last_receipt and last_receipt.receipt_number:
                        try:
                            last_num = int(last_receipt.receipt_number.replace("RCT", ""))
                            new_receipt_number = f"RCT{last_num + 1:06d}"
                        except (ValueError, IndexError):
                            new_receipt_number = f"RCT{Receipt.objects.count() + 1:06d}"
                    else:
                        new_receipt_number = "RCT000001"

                    new_balance = account.balance + interest_amount
                    Receipt.objects.create(
                        user=account.user,
                        member_account=account,
                        receipt_number=new_receipt_number,
                        transaction_type="interest",
                        amount=interest_amount,
                        description=f"Interest credit for {calc_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')} @ {account.interest_rate}%",
                        payment_mode="internal",
                        balance_after=new_balance,
                        created_by=request.user,
                    )

                    # Update account balance
                    MemberAccount.objects.filter(id=account.id).update(
                        balance=F("balance") + interest_amount,
                        last_transaction_date=period_end,
                    )

                    total_posted += interest_amount
                    accounts_updated += 1

            log_action(
                request,
                "create",
                "account",
                None,
                f"Posted interest for period ending {period_end}. ₹{total_posted} across {accounts_updated} accounts.",
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Posted ₹{total_posted} interest to {accounts_updated} accounts.",
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def export_report_view(request):
    """Export financial report data as CSV."""
    import calendar
    import csv

    from accounts.utils import get_financial_summary

    period = request.GET.get("period", "year")
    year = int(request.GET.get("year", date.today().year))

    if period == "month":
        month = int(request.GET.get("month", date.today().month))
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        filename = f"financial_report_{year}_{month:02d}.csv"
    elif period == "quarter":
        quarter = int(request.GET.get("quarter", (date.today().month - 1) // 3 + 1))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        start_date = date(year, start_month, 1)
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = date(year, end_month, last_day)
        filename = f"financial_report_{year}_Q{quarter}.csv"
    else:
        start_date = date(year, 4, 1)
        end_date = date(year + 1, 3, 31)
        filename = f"financial_report_FY{year}_{year + 1}.csv"

    summary = get_financial_summary(start_date, end_date)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)

    # Header
    writer.writerow(["Financial Report"])
    writer.writerow(["Period", f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"])
    writer.writerow([])

    # Revenue
    writer.writerow(["REVENUE"])
    writer.writerow(["Loan Interest Income", float(summary["loan_interest_income"])])
    writer.writerow(["Penalty Income", float(summary["penalty_income"])])
    writer.writerow(["Processing Fees", float(summary["processing_fees"])])
    writer.writerow(["Gross Revenue", float(summary["gross_revenue"])])
    writer.writerow([])

    # Expenses
    writer.writerow(["EXPENSES"])
    writer.writerow(["Deposit Interest Expense", float(summary["deposit_interest_expense"])])
    writer.writerow(["Monthly Interest Liability", float(summary["monthly_interest_liability"])])
    writer.writerow(["Total Expenses", float(summary["total_expenses"])])
    writer.writerow([])

    # Profit
    writer.writerow(["NET PROFIT", float(summary["net_profit"])])
    writer.writerow([])

    # Loan Portfolio
    writer.writerow(["LOAN PORTFOLIO"])
    writer.writerow(["Active Loans", summary["active_loans_count"]])
    writer.writerow(["Total Disbursed (Period)", float(summary["total_disbursed"])])
    writer.writerow(["Total Outstanding", float(summary["total_loans_outstanding"])])
    writer.writerow(["Total Overdue", float(summary["total_overdue"])])
    writer.writerow(["NPA Count", summary["npa_count"]])
    writer.writerow(["Recovery Rate (%)", summary["recovery_rate"]])
    writer.writerow([])

    # Deposit Portfolio
    writer.writerow(["DEPOSIT PORTFOLIO"])
    writer.writerow(["Account Type", "Balance", "Avg Rate (%)", "Count"])
    for type_name, data in summary["deposit_by_type"].items():
        writer.writerow([type_name, float(data["balance"]), float(data["avg_rate"]), data["count"]])
    writer.writerow([])

    # Monthly Breakdown
    writer.writerow(["MONTHLY BREAKDOWN"])
    writer.writerow(["Month", "Revenue", "Expense", "Net Profit"])
    current = start_date
    while current <= end_date:
        month_start = current.replace(day=1)
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = current.replace(day=last_day)
        month_summary = get_financial_summary(month_start, month_end)
        writer.writerow(
            [
                current.strftime("%b %Y"),
                float(month_summary["gross_revenue"]),
                float(month_summary["total_expenses"]),
                float(month_summary["net_profit"]),
            ]
        )
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    log_action(request, "export", "system", None, f"Exported financial report for {start_date} to {end_date}")
    return response


@login_required
@admin_required
def calculator_view(request):
    """Banking calculator page"""
    return render(request, "admin/calculator.html")


@login_required
@admin_required
def export_members_view(request):
    """Export members list to Excel"""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Members"

    headers = [
        "Member ID",
        "Username",
        "Name",
        "Email",
        "Phone",
        "Status",
        "Member Type",
        "Date of Joining",
        "Date of Birth",
        "Gender",
        "Occupation",
        "KYC Status",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)

    members = User.objects.filter(is_deleted=False, role="member").order_by("member_id")
    for m in members:
        ws.append(
            [
                m.member_id or "",
                m.username,
                m.display_name,
                m.email or "",
                m.mobile_primary or "",
                m.get_status_display(),
                m.get_member_type_display(),
                m.date_of_joining.strftime("%Y-%m-%d") if m.date_of_joining else "",
                m.date_of_birth.strftime("%Y-%m-%d") if m.date_of_birth else "",
                m.get_gender_display() if m.gender else "",
                m.occupation or "",
                m.get_kyc_status_display(),
            ]
        )

    for col in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 40)

    log_action(request, "export", "member", None, "Exported members list to Excel")

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="members.xlsx"'
    wb.save(response)
    return response


@login_required
@admin_required
def export_accounts_view(request):
    """Export accounts list to Excel"""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Accounts"

    headers = [
        "Account Number",
        "Member Name",
        "Member ID",
        "Account Type",
        "Status",
        "Balance",
        "Interest Rate (%)",
        "Principal Amount",
        "Opening Date",
        "Maturity Date",
        "Tenure (Months)",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    accounts = MemberAccount.objects.filter(is_deleted=False).select_related("user").order_by("account_number")
    for a in accounts:
        ws.append(
            [
                a.account_number,
                a.user.display_name,
                a.user.member_id or "",
                a.get_account_type_display(),
                a.get_status_display(),
                float(a.balance),
                float(a.interest_rate),
                float(a.principal_amount),
                a.opening_date.strftime("%Y-%m-%d") if a.opening_date else "",
                a.maturity_date.strftime("%Y-%m-%d") if a.maturity_date else "",
                a.tenure_months or "",
            ]
        )

    for col in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 40)

    log_action(request, "export", "account", None, "Exported accounts list to Excel")

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="accounts.xlsx"'
    wb.save(response)
    return response


@login_required
@admin_required
def export_receipts_view(request):
    """Export receipts list to Excel"""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Receipts"

    headers = [
        "Receipt Number",
        "Member Name",
        "Member ID",
        "Account Number",
        "Transaction Type",
        "Amount",
        "Payment Mode",
        "Reference Number",
        "Balance After",
        "Created By",
        "Date",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    receipts = (
        Receipt.objects.select_related("user", "member_account", "created_by").all().order_by("-created_at")[:5000]
    )
    for r in receipts:
        ws.append(
            [
                r.receipt_number,
                r.user.display_name,
                r.user.member_id or "",
                r.member_account.account_number if r.member_account else "",
                r.get_transaction_type_display(),
                float(r.amount),
                r.get_payment_mode_display(),
                r.reference_number or "",
                float(r.balance_after),
                r.created_by.display_name if r.created_by else "",
                r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            ]
        )

    for col in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 40)

    log_action(request, "export", "receipt", None, "Exported receipts list to Excel")

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="receipts.xlsx"'
    wb.save(response)
    return response


@login_required
@admin_required
def export_loans_view(request):
    """Export loans list to Excel"""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Loans"

    headers = [
        "Loan Number",
        "Member Name",
        "Member ID",
        "Loan Type",
        "Status",
        "Principal Amount",
        "Interest Rate (%)",
        "Interest Type",
        "Tenure (Months)",
        "EMI Amount",
        "Total Payable",
        "Total Paid",
        "Outstanding Balance",
        "Application Date",
        "Approval Date",
        "Disbursement Date",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    loans = Loan.objects.select_related("user").all().order_by("-created_at")
    for loan in loans:
        ws.append(
            [
                loan.loan_number,
                loan.user.display_name,
                loan.user.member_id or "",
                loan.get_loan_type_display(),
                loan.get_status_display(),
                float(loan.principal_amount),
                float(loan.interest_rate),
                loan.get_interest_type_display(),
                loan.tenure_months,
                float(loan.emi_amount),
                float(loan.total_payable),
                float(loan.total_paid),
                float(loan.outstanding_balance),
                loan.application_date.strftime("%Y-%m-%d") if loan.application_date else "",
                loan.approval_date.strftime("%Y-%m-%d") if loan.approval_date else "",
                loan.disbursement_date.strftime("%Y-%m-%d") if loan.disbursement_date else "",
            ]
        )

    for col in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 40)

    log_action(request, "export", "loan", None, "Exported loans list to Excel")

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="loans.xlsx"'
    wb.save(response)
    return response


@login_required
@admin_required
def approve_loan_view(request, loan_id):
    """Approve a pending loan and generate repayment schedule"""
    if request.method == "POST":
        try:
            from decimal import Decimal

            loan = Loan.objects.get(id=loan_id)

            if loan.status != "pending":
                return JsonResponse({"success": False, "error": "Only pending loans can be approved"})

            # Segregation of duties: creator cannot approve their own loan
            if loan.created_by == request.user:
                return JsonResponse(
                    {"success": False, "error": "You cannot approve a loan you created. Another admin must approve it."}
                )

            disbursement_date_str = request.POST.get("disbursement_date")
            if not disbursement_date_str:
                return JsonResponse({"success": False, "error": "Disbursement date is required"})

            from datetime import datetime

            disbursement_date = datetime.strptime(disbursement_date_str, "%Y-%m-%d").date()

            # Update loan status
            loan.status = "active"
            loan.approval_date = date.today()
            loan.disbursement_date = disbursement_date
            loan.approved_by = request.user

            # Calculate first EMI date (1 month after disbursement)
            if disbursement_date.month == 12:
                first_emi_month = 1
                first_emi_year = disbursement_date.year + 1
            else:
                first_emi_month = disbursement_date.month + 1
                first_emi_year = disbursement_date.year

            # Handle month-end edge cases (e.g., Jan 31 -> Feb 28)
            import calendar

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

                # Last EMI adjustment for rounding
                if i == loan.tenure_months:
                    principal_component = remaining
                    interest = emi - principal_component
                    if interest < 0:
                        interest = Decimal("0")
                        emi_adjusted = principal_component
                    else:
                        emi_adjusted = emi
                else:
                    emi_adjusted = emi

                remaining_after = remaining - principal_component
                if remaining_after < 0:
                    remaining_after = Decimal("0")

                repayments.append(
                    LoanRepayment(
                        loan=loan,
                        installment_number=i,
                        due_date=current_date,
                        amount_due=emi_adjusted,
                        principal_component=principal_component,
                        interest_component=interest,
                        balance_after=remaining_after,
                        payment_status="upcoming",
                    )
                )

                remaining = remaining_after

                # Next EMI date
                if current_date.month == 12:
                    next_month = 1
                    next_year = current_date.year + 1
                else:
                    next_month = current_date.month + 1
                    next_year = current_date.year

                max_day = calendar.monthrange(next_year, next_month)[1]
                next_day = min(first_emi_date.day, max_day)
                current_date = date(next_year, next_month, next_day)

            # Set last EMI date
            if repayments:
                loan.last_emi_date = repayments[-1].due_date

            loan.save()
            LoanRepayment.objects.bulk_create(repayments)

            log_action(
                request,
                "approve",
                "loan",
                loan.id,
                f"Approved loan {loan.loan_number} - \u20b9{loan.principal_amount} for {loan.user.display_name}",
            )
            return JsonResponse({"success": True})
        except Loan.DoesNotExist:
            return JsonResponse({"success": False, "error": "Loan not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def record_emi_payment_view(request, loan_id):
    """Record an EMI payment for a loan"""
    if request.method == "POST":
        try:
            installment_number = request.POST.get("installment_number")
            amount_paid = request.POST.get("amount_paid")
            payment_mode = request.POST.get("payment_mode", "cash")

            if not installment_number:
                return JsonResponse({"success": False, "error": "Installment number is required"})
            if not amount_paid:
                return JsonResponse({"success": False, "error": "Payment amount is required"})

            amount = Decimal(str(amount_paid))
            if amount <= 0:
                return JsonResponse({"success": False, "error": "Payment amount must be greater than zero"})

            # Retry loop for duplicate receipt numbers
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        # Lock the loan row
                        loan = Loan.objects.select_for_update().get(id=loan_id)

                        if loan.status != "active":
                            return JsonResponse({"success": False, "error": "Only active loans can receive payments"})

                        try:
                            repayment = LoanRepayment.objects.select_for_update().get(
                                loan=loan, installment_number=int(installment_number)
                            )
                        except LoanRepayment.DoesNotExist:
                            return JsonResponse({"success": False, "error": "Installment not found"})

                        if repayment.payment_status == "paid":
                            return JsonResponse({"success": False, "error": "This installment is already paid"})

                        # Calculate late penalty (2% per month on overdue amount)
                        penalty = Decimal("0.00")
                        if repayment.due_date < date.today():
                            days_late = (date.today() - repayment.due_date).days
                            months_late = max(1, days_late / 30)
                            penalty = (
                                repayment.amount_due * Decimal("2") * Decimal(str(months_late)) / Decimal("100")
                            ).quantize(Decimal("0.01"))

                        repayment.paid_date = date.today()
                        repayment.amount_paid = amount
                        repayment.penalty = penalty
                        repayment.payment_mode = payment_mode
                        repayment.payment_status = "paid" if amount >= repayment.amount_due else "partial"

                        # Create a receipt for the EMI payment
                        member_account = loan.disbursement_account
                        if not member_account:
                            # Fallback: use user's first active account
                            member_account = MemberAccount.objects.filter(user=loan.user, status="active").first()

                        if member_account:
                            # Lock the account for balance update
                            member_account = MemberAccount.objects.select_for_update().get(id=member_account.id)

                            # Auto-generate receipt number atomically
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
                            receipt_number = f"RCP-{year}-{next_seq:05d}"

                            # Update account balance with F() expression
                            new_balance = member_account.balance + amount
                            MemberAccount.objects.filter(id=member_account.id).update(
                                balance=F("balance") + amount,
                                last_transaction_date=date.today(),
                            )

                            receipt = Receipt.objects.create(
                                receipt_number=receipt_number,
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
                        loan.total_paid = loan.total_paid + amount
                        loan.outstanding_balance = loan.outstanding_balance - repayment.principal_component
                        if loan.outstanding_balance < 0:
                            loan.outstanding_balance = Decimal("0")
                        loan.emis_paid = LoanRepayment.objects.filter(loan=loan, payment_status="paid").count()

                        # Mark any upcoming EMIs past due date as overdue
                        LoanRepayment.objects.filter(
                            loan=loan, payment_status="upcoming", due_date__lt=date.today()
                        ).update(payment_status="overdue")

                        loan.emis_overdue = LoanRepayment.objects.filter(loan=loan, payment_status="overdue").count()

                        # Update overdue_amount dynamically
                        loan.overdue_amount = LoanRepayment.objects.filter(
                            loan=loan, payment_status="overdue"
                        ).aggregate(total=Sum("amount_due"))["total"] or Decimal("0")

                        # Check if all EMIs paid
                        unpaid = LoanRepayment.objects.filter(loan=loan).exclude(payment_status="paid").count()
                        if unpaid == 0:
                            loan.status = "closed"
                            loan.closure_date = date.today()
                            loan.outstanding_balance = Decimal("0")

                        loan.save()

                    # If we get here, the transaction succeeded
                    log_action(
                        request,
                        "update",
                        "loan",
                        loan_id,
                        f"Recorded EMI #{installment_number} payment of \u20b9{amount} for loan {loan.loan_number}",
                    )
                    return JsonResponse({"success": True})
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise
                    continue

        except Loan.DoesNotExist:
            return JsonResponse({"success": False, "error": "Loan not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


# ========================================
# Fund Management Views
# ========================================


@login_required
@admin_required
def funds_view(request):
    """Funds list view with pagination and search"""
    page = request.GET.get("page", 1)
    query = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    per_page = 25

    # Base queryset
    funds = FundAccount.objects.filter(is_deleted=False).order_by("name")

    # Apply search filter
    if query:
        funds = funds.filter(Q(name__icontains=query) | Q(account_number__icontains=query))
    if date_from:
        funds = funds.filter(created_at__date__gte=date_from)
    if date_to:
        funds = funds.filter(created_at__date__lte=date_to)

    # Paginate
    paginator = Paginator(funds, per_page)
    try:
        funds_page = paginator.page(page)
    except PageNotAnInteger:
        funds_page = paginator.page(1)
    except EmptyPage:
        funds_page = paginator.page(paginator.num_pages)

    # Summary stats
    total_funds = FundAccount.objects.filter(is_deleted=False).count()
    total_balance = FundAccount.objects.filter(is_deleted=False).aggregate(total=Sum("balance"))["total"] or 0
    pending_vouchers = Voucher.objects.filter(status="pending").select_related("user").order_by("-created_at")[:50]
    active_funds = FundAccount.objects.filter(is_deleted=False, is_active=True).order_by("name")

    return render(
        request,
        "admin/funds.html",
        {
            "funds": funds_page,
            "search_query": query,
            "page_obj": funds_page,
            "total_funds": total_funds,
            "total_balance": total_balance,
            "date_from": date_from,
            "date_to": date_to,
            "pending_vouchers": pending_vouchers,
            "active_funds": active_funds,
        },
    )


@login_required
@admin_required
def add_fund_view(request):
    """Create a new fund account"""
    if request.method == "POST":
        try:
            name = request.POST.get("name", "").strip()
            fund_type = request.POST.get("fund_type")
            description = request.POST.get("description", "").strip()

            # Validate required fields
            if not name:
                return JsonResponse({"success": False, "error": "Fund name is required"})
            if not fund_type:
                return JsonResponse({"success": False, "error": "Fund type is required"})

            # Auto-generate account number: FUND-YEAR-SEQUENCE
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        year = date.today().year
                        last_fund = (
                            FundAccount.objects.select_for_update()
                            .filter(account_number__startswith=f"FUND-{year}-")
                            .order_by("-account_number")
                            .first()
                        )
                        if last_fund:
                            try:
                                last_seq = int(last_fund.account_number.split("-")[-1])
                                next_seq = last_seq + 1
                            except (ValueError, IndexError):
                                next_seq = 1
                        else:
                            next_seq = 1

                        account_number = f"FUND-{year}-{next_seq:05d}"

                        fund = FundAccount.objects.create(
                            name=name,
                            fund_type=fund_type,
                            account_number=account_number,
                            description=description or None,
                            created_by=request.user,
                        )

                    log_action(
                        request,
                        "create",
                        "fund",
                        fund.id,
                        f"Created fund {name} ({account_number})",
                    )
                    return JsonResponse({"success": True, "fund_id": fund.id})
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise
                    continue

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def get_fund_view(request, fund_id):
    """Get fund details with recent transactions and allocation rules"""
    try:
        fund = FundAccount.objects.get(id=fund_id, is_deleted=False)

        # Get recent transactions
        transactions = fund.transactions.all().order_by("-created_at")[:10]
        transactions_data = [
            {
                "id": t.id,
                "transaction_type": t.transaction_type,
                "transaction_type_display": t.get_transaction_type_display(),
                "amount": str(t.amount),
                "description": t.description or "",
                "payment_mode_display": t.get_payment_mode_display(),
                "balance_after": str(t.balance_after),
                "created_at": t.created_at.strftime("%b %d, %Y") if t.created_at else "",
            }
            for t in transactions
        ]

        # Get allocation rules
        rules = fund.allocation_rules.filter(is_active=True).order_by("trigger_event")
        rules_data = [
            {
                "id": r.id,
                "trigger_event": r.trigger_event,
                "trigger_event_display": r.get_trigger_event_display(),
                "allocation_type": r.allocation_type,
                "allocation_type_display": r.get_allocation_type_display(),
                "amount": str(r.amount) if r.amount else "",
                "percentage": str(r.percentage) if r.percentage else "",
            }
            for r in rules
        ]

        return JsonResponse(
            {
                "success": True,
                "fund": {
                    "id": fund.id,
                    "name": fund.name,
                    "fund_type": fund.fund_type,
                    "fund_type_display": fund.get_fund_type_display(),
                    "account_number": fund.account_number,
                    "balance": str(fund.balance),
                    "description": fund.description or "",
                    "is_active": fund.is_active,
                    "created_at": fund.created_at.strftime("%b %d, %Y") if fund.created_at else "",
                    "transactions": transactions_data,
                    "rules": rules_data,
                },
            }
        )
    except FundAccount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Fund not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def edit_fund_view(request, fund_id):
    """Update fund details"""
    if request.method == "POST":
        try:
            fund = FundAccount.objects.get(id=fund_id, is_deleted=False)

            name = request.POST.get("name", "").strip()
            fund_type = request.POST.get("fund_type")
            description = request.POST.get("description", "").strip()
            is_active = request.POST.get("is_active") == "true"

            if not name:
                return JsonResponse({"success": False, "error": "Fund name is required"})
            if not fund_type:
                return JsonResponse({"success": False, "error": "Fund type is required"})

            fund.name = name
            fund.fund_type = fund_type
            fund.description = description or None
            fund.is_active = is_active
            fund.save()

            log_action(
                request,
                "update",
                "fund",
                fund.id,
                f"Updated fund {fund.name} ({fund.account_number})",
            )
            return JsonResponse({"success": True})
        except FundAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Fund not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def delete_fund_view(request, fund_id):
    """Soft-delete a fund account (only if balance is zero)"""
    if request.method == "POST":
        try:
            fund = FundAccount.objects.get(id=fund_id, is_deleted=False)

            # Protect funds with non-zero balance
            if fund.balance > 0:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Cannot delete fund with balance ₹{fund.balance}. Please transfer funds first.",
                    }
                )

            fund.is_deleted = True
            fund.deleted_at = timezone.now()
            fund.is_active = False
            fund.save()

            log_action(
                request,
                "delete",
                "fund",
                fund.id,
                f"Deleted fund {fund.name} ({fund.account_number})",
            )
            return JsonResponse({"success": True})
        except FundAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Fund not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def add_fund_transaction_view(request, fund_id):
    """Add a manual fund transaction"""
    if request.method == "POST":
        try:
            transaction_type = request.POST.get("transaction_type")
            amount = request.POST.get("amount")
            description = request.POST.get("description", "").strip()
            payment_mode = request.POST.get("payment_mode", "cash")
            reference_number = request.POST.get("reference_number", "").strip()

            # Validate required fields
            if not transaction_type:
                return JsonResponse({"success": False, "error": "Transaction type is required"})
            if not amount:
                return JsonResponse({"success": False, "error": "Amount is required"})
            if not description:
                return JsonResponse({"success": False, "error": "Description is required"})

            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                return JsonResponse({"success": False, "error": "Amount must be greater than zero"})

            with transaction.atomic():
                # Lock the fund account
                fund = FundAccount.objects.select_for_update().get(id=fund_id, is_deleted=False)

                # Calculate new balance
                if transaction_type == "credit":
                    new_balance = fund.balance + amount_decimal
                else:
                    # Check sufficient balance for debit
                    if amount_decimal > fund.balance:
                        return JsonResponse(
                            {
                                "success": False,
                                "error": f"Insufficient balance. Fund has ₹{fund.balance} but ₹{amount_decimal} was requested.",
                            }
                        )
                    new_balance = fund.balance - amount_decimal

                # Update balance using F() expression
                if transaction_type == "credit":
                    FundAccount.objects.filter(id=fund.id).update(balance=F("balance") + amount_decimal)
                else:
                    FundAccount.objects.filter(id=fund.id).update(balance=F("balance") - amount_decimal)

                # Create transaction record
                fund_txn = FundTransaction.objects.create(
                    fund=fund,
                    transaction_type=transaction_type,
                    amount=amount_decimal,
                    description=description,
                    payment_mode=payment_mode,
                    reference_number=reference_number or None,
                    balance_after=new_balance,
                    trigger_event="manual",
                    created_by=request.user,
                )

            log_action(
                request,
                "create",
                "fund",
                fund.id,
                f"Manual {transaction_type} of ₹{amount_decimal} to {fund.name}: {description}",
            )
            return JsonResponse({"success": True, "transaction_id": fund_txn.id})
        except FundAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Fund not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def fund_transactions_view(request, fund_id):
    """Get paginated transaction history for a fund"""
    try:
        fund = FundAccount.objects.get(id=fund_id, is_deleted=False)
        page = int(request.GET.get("page", 1))
        per_page = 25

        transactions = fund.transactions.all().order_by("-created_at")
        total = transactions.count()
        start = (page - 1) * per_page
        end = start + per_page
        page_transactions = transactions[start:end]

        results = [
            {
                "id": t.id,
                "transaction_type": t.transaction_type,
                "transaction_type_display": t.get_transaction_type_display(),
                "amount": str(t.amount),
                "description": t.description or "",
                "payment_mode_display": t.get_payment_mode_display(),
                "reference_number": t.reference_number or "",
                "balance_after": str(t.balance_after),
                "trigger_event_display": t.get_trigger_event_display() if t.trigger_event else "",
                "source_member": t.source_member.display_name if t.source_member else "",
                "created_by": t.created_by.display_name if t.created_by else "",
                "created_at": t.created_at.strftime("%b %d, %Y %I:%M %p") if t.created_at else "",
            }
            for t in page_transactions
        ]

        return JsonResponse(
            {
                "success": True,
                "fund_name": fund.name,
                "fund_account_number": fund.account_number,
                "transactions": results,
                "total": total,
                "page": page,
                "has_more": end < total,
            }
        )
    except FundAccount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Fund not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required
def allocation_rules_view(request):
    """Allocation rules list view with pagination"""
    page = request.GET.get("page", 1)
    per_page = 25

    # Base queryset
    rules = FundAllocationRule.objects.select_related("fund", "created_by").all().order_by("trigger_event", "fund")

    # Paginate
    paginator = Paginator(rules, per_page)
    try:
        rules_page = paginator.page(page)
    except PageNotAnInteger:
        rules_page = paginator.page(1)
    except EmptyPage:
        rules_page = paginator.page(paginator.num_pages)

    # Get all funds for dropdown
    funds = FundAccount.objects.filter(is_deleted=False, is_active=True).order_by("name")

    return render(
        request,
        "admin/allocation_rules.html",
        {
            "rules": rules_page,
            "page_obj": rules_page,
            "funds": funds,
        },
    )


@login_required
@admin_required
def add_allocation_rule_view(request):
    """Create a new allocation rule"""
    if request.method == "POST":
        try:
            trigger_event = request.POST.get("trigger_event")
            fund_id = request.POST.get("fund_id")
            allocation_type = request.POST.get("allocation_type")
            amount = request.POST.get("amount", "").strip()
            percentage = request.POST.get("percentage", "").strip()
            description = request.POST.get("description", "").strip()

            # Validate required fields
            if not trigger_event:
                return JsonResponse({"success": False, "error": "Trigger event is required"})
            if not fund_id:
                return JsonResponse({"success": False, "error": "Fund is required"})
            if not allocation_type:
                return JsonResponse({"success": False, "error": "Allocation type is required"})

            # Validate allocation amount/percentage
            if allocation_type == "fixed":
                if not amount:
                    return JsonResponse({"success": False, "error": "Amount is required for fixed allocation"})
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    return JsonResponse({"success": False, "error": "Amount must be greater than zero"})
                percentage_decimal = None
            else:
                if not percentage:
                    return JsonResponse({"success": False, "error": "Percentage is required for percentage allocation"})
                percentage_decimal = Decimal(str(percentage))
                if percentage_decimal <= 0 or percentage_decimal > 100:
                    return JsonResponse({"success": False, "error": "Percentage must be between 0 and 100"})
                amount_decimal = None

            # Validate fund exists
            try:
                fund = FundAccount.objects.get(id=fund_id, is_deleted=False)
            except FundAccount.DoesNotExist:
                return JsonResponse({"success": False, "error": "Fund not found"})

            rule = FundAllocationRule.objects.create(
                trigger_event=trigger_event,
                fund=fund,
                allocation_type=allocation_type,
                amount=amount_decimal,
                percentage=percentage_decimal,
                description=description or None,
                created_by=request.user,
            )

            log_action(
                request,
                "create",
                "fund",
                rule.id,
                f"Created allocation rule: {rule.get_trigger_event_display()} → {fund.name}",
            )
            return JsonResponse({"success": True, "rule_id": rule.id})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def edit_allocation_rule_view(request, rule_id):
    """Update an allocation rule"""
    if request.method == "POST":
        try:
            rule = FundAllocationRule.objects.get(id=rule_id)

            trigger_event = request.POST.get("trigger_event")
            fund_id = request.POST.get("fund_id")
            allocation_type = request.POST.get("allocation_type")
            amount = request.POST.get("amount", "").strip()
            percentage = request.POST.get("percentage", "").strip()
            description = request.POST.get("description", "").strip()
            is_active = request.POST.get("is_active") == "true"

            # Validate required fields
            if not trigger_event:
                return JsonResponse({"success": False, "error": "Trigger event is required"})
            if not fund_id:
                return JsonResponse({"success": False, "error": "Fund is required"})
            if not allocation_type:
                return JsonResponse({"success": False, "error": "Allocation type is required"})

            # Validate allocation amount/percentage
            if allocation_type == "fixed":
                if not amount:
                    return JsonResponse({"success": False, "error": "Amount is required for fixed allocation"})
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    return JsonResponse({"success": False, "error": "Amount must be greater than zero"})
                percentage_decimal = None
            else:
                if not percentage:
                    return JsonResponse({"success": False, "error": "Percentage is required for percentage allocation"})
                percentage_decimal = Decimal(str(percentage))
                if percentage_decimal <= 0 or percentage_decimal > 100:
                    return JsonResponse({"success": False, "error": "Percentage must be between 0 and 100"})
                amount_decimal = None

            # Validate fund exists
            try:
                fund = FundAccount.objects.get(id=fund_id, is_deleted=False)
            except FundAccount.DoesNotExist:
                return JsonResponse({"success": False, "error": "Fund not found"})

            rule.trigger_event = trigger_event
            rule.fund = fund
            rule.allocation_type = allocation_type
            rule.amount = amount_decimal
            rule.percentage = percentage_decimal
            rule.description = description or None
            rule.is_active = is_active
            rule.save()

            log_action(
                request,
                "update",
                "fund",
                rule.id,
                f"Updated allocation rule: {rule.get_trigger_event_display()} → {fund.name}",
            )
            return JsonResponse({"success": True})
        except FundAllocationRule.DoesNotExist:
            return JsonResponse({"success": False, "error": "Allocation rule not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def delete_allocation_rule_view(request, rule_id):
    """Delete an allocation rule"""
    if request.method == "POST":
        try:
            rule = FundAllocationRule.objects.get(id=rule_id)
            rule_desc = f"{rule.get_trigger_event_display()} → {rule.fund.name}"
            rule.delete()

            log_action(
                request,
                "delete",
                "fund",
                rule_id,
                f"Deleted allocation rule: {rule_desc}",
            )
            return JsonResponse({"success": True})
        except FundAllocationRule.DoesNotExist:
            return JsonResponse({"success": False, "error": "Allocation rule not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})
