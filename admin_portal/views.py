import functools
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import AuditLog, Loan, LoanRepayment, MemberAccount, Receipt, Ticket, TicketMessage, User
from accounts.utils import log_action, split_full_name, validate_password_strength


def admin_required(view_func):
    """Decorator to check if user is staff"""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Check if it's an AJAX request
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
                return JsonResponse({"success": False, "error": "Authentication required. Please log in."}, status=401)
            return redirect("/portal/login/")
        
        if not request.user.is_staff:
            # Check if it's an AJAX request
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
                return JsonResponse({"success": False, "error": "Access denied. Administrators only."}, status=403)
            return HttpResponseForbidden("Access denied. Administrators only.")
        
        return view_func(request, *args, **kwargs)

    return wrapper


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

    # Account type distribution (for pie chart)
    account_type_data = list(
        MemberAccount.objects.filter(is_deleted=False)
        .values("account_type")
        .annotate(count=Count("id"))
        .order_by("account_type")
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

    # Transaction trend - last 7 days (for bar chart)
    trend_data = []
    for i in range(6, -1, -1):
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
        trend_data.append(
            {
                "date": day.strftime("%b %d"),
                "day": day.strftime("%a"),
                "credits": float(day_credits),
                "debits": float(day_debits),
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
        },
    )


@login_required
@admin_required
def members_view(request):
    """Members management view with pagination and search"""
    page = request.GET.get("page", 1)
    query = request.GET.get("q", "").strip()
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

    return render(
        request,
        "admin/members.html",
        {
            "users": users_page,
            "search_query": query,
            "page_obj": users_page,
            "total_members": total_members,
            "active_members": active_members,
        },
    )


@login_required
@admin_required
def add_member_view(request):
    """Create a new member with auto-generated password from DOB"""
    if request.method == "POST":
        try:
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

            user.save()

            log_action(
                request,
                "create",
                "member",
                user.id,
                f"Created member {username} ({user.display_name})",
            )

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
        accounts = MemberAccount.objects.filter(user=user, is_deleted=False).order_by("-created_at")
        accounts_data = [
            {
                "id": a.id,
                "account_number": a.account_number,
                "account_type_display": a.get_account_type_display(),
                "status": a.status,
                "status_display": a.get_status_display(),
                "balance": str(a.balance),
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
            full_name = request.POST.get("full_name", "").strip()
            mobile_primary = request.POST.get("mobile_primary", "")
            role = request.POST.get("role", "member")
            password = request.POST.get("password", "").strip()

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

            # Update password if provided (with validation)
            if password:
                is_valid, errors = validate_password_strength(password)
                if not is_valid:
                    return JsonResponse({"success": False, "error": errors[0]})
                user.set_password(password)

            user.save()

            log_action(
                request,
                "update",
                "member",
                user.id,
                f"Updated member {user.username} ({user.display_name})",
            )

            return JsonResponse({"success": True})
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
        request.user.phone = request.POST.get("phone", "")
        request.user.save()
        messages.success(request, "Profile updated successfully!")
        return redirect("/profile/")

    return render(request, "admin/profile.html")


@login_required
@admin_required
def delete_account_view(request, account_id):
    """Delete a bank account"""
    if request.method == "POST":
        try:
            from accounts.models import BankAccount

            account = BankAccount.objects.get(id=account_id, user=request.user)
            account.delete()
            return JsonResponse({"success": True})
        except BankAccount.DoesNotExist:
            return JsonResponse({"success": False, "error": "Account not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
@admin_required
def accounts_view(request):
    """Member accounts management view with pagination and filters"""
    page = request.GET.get("page", 1)
    query = request.GET.get("q", "").strip()
    account_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    per_page = 25

    # Base queryset with related user data
    accounts = MemberAccount.objects.select_related("user").filter(is_deleted=False).order_by("-created_at")

    # Apply search filter
    if query:
        accounts = accounts.filter(
            Q(account_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__member_id__icontains=query)
            | Q(user__username__icontains=query)
        )

    # Apply account type filter
    if account_type:
        accounts = accounts.filter(account_type=account_type)

    # Apply status filter
    if status:
        accounts = accounts.filter(status=status)

    # Paginate
    paginator = Paginator(accounts, per_page)
    try:
        accounts_page = paginator.page(page)
    except PageNotAnInteger:
        accounts_page = paginator.page(1)
    except EmptyPage:
        accounts_page = paginator.page(paginator.num_pages)

    # Get account type and status choices for filter dropdowns
    account_type_choices = MemberAccount.ACCOUNT_TYPE_CHOICES
    status_choices = MemberAccount.STATUS_CHOICES

    # Summary stats
    total_accounts = MemberAccount.objects.filter(is_deleted=False).count()
    active_accounts = MemberAccount.objects.filter(is_deleted=False, status="active").count()

    return render(
        request,
        "admin/accounts.html",
        {
            "accounts": accounts_page,
            "search_query": query,
            "selected_type": account_type,
            "selected_status": status,
            "account_type_choices": account_type_choices,
            "status_choices": status_choices,
            "page_obj": accounts_page,
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
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
            "transaction_type_choices": Receipt.TRANSACTION_TYPE_CHOICES,
            "payment_mode_choices": Receipt.PAYMENT_MODE_CHOICES,
            "page_obj": receipts_page,
            "total_receipts": total_receipts,
            "today_receipts": today_receipts,
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
    """Create a new receipt"""
    if request.method == "POST":
        try:
            user_id = request.POST.get("user_id")
            account_id = request.POST.get("account_id")
            transaction_type = request.POST.get("transaction_type")
            amount = request.POST.get("amount")
            description = request.POST.get("description", "").strip()
            payment_mode = request.POST.get("payment_mode", "cash")
            reference_number = request.POST.get("reference_number", "").strip()
            remarks = request.POST.get("remarks", "").strip()

            # Validate required fields
            if not user_id:
                return JsonResponse({"success": False, "error": "Member is required"})
            if not account_id:
                return JsonResponse({"success": False, "error": "Account is required"})
            if not transaction_type:
                return JsonResponse({"success": False, "error": "Transaction type is required"})
            if not amount:
                return JsonResponse({"success": False, "error": "Amount is required"})

            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                return JsonResponse({"success": False, "error": "Amount must be greater than zero"})

            # Validate user exists
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({"success": False, "error": "Member not found"})

            # Retry loop for duplicate receipt numbers
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        # Lock the account row to prevent concurrent balance modifications
                        try:
                            account = MemberAccount.objects.select_for_update().get(id=account_id, user=user)
                        except MemberAccount.DoesNotExist:
                            return JsonResponse({"success": False, "error": "Account not found for this member"})

                        # Calculate balance after transaction
                        if transaction_type in (
                            "credit",
                            "interest",
                            "dividend",
                            "share_capital",
                        ):
                            balance_after = account.balance + amount_decimal
                        else:
                            # Check sufficient balance for debit/transfer
                            if amount_decimal > account.balance:
                                return JsonResponse(
                                    {
                                        "success": False,
                                        "error": f"Insufficient balance. Account has \u20b9{account.balance} "
                                        f"but \u20b9{amount_decimal} was requested.",
                                    }
                                )
                            balance_after = account.balance - amount_decimal

                        # Update account balance atomically using F() expression
                        if transaction_type in (
                            "credit",
                            "interest",
                            "dividend",
                            "share_capital",
                        ):
                            MemberAccount.objects.filter(id=account.id).update(
                                balance=F("balance") + amount_decimal,
                                last_transaction_date=date.today(),
                            )
                        else:
                            MemberAccount.objects.filter(id=account.id).update(
                                balance=F("balance") - amount_decimal,
                                last_transaction_date=date.today(),
                            )

                        # Generate receipt number atomically (locked read)
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

                        receipt = Receipt.objects.create(
                            receipt_number=receipt_number,
                            user=user,
                            member_account=account,
                            transaction_type=transaction_type,
                            amount=amount_decimal,
                            description=description or None,
                            payment_mode=payment_mode,
                            reference_number=reference_number or None,
                            balance_after=balance_after,
                            created_by=request.user,
                            remarks=remarks or None,
                        )

                    # If we get here, the transaction succeeded
                    log_action(
                        request,
                        "create",
                        "receipt",
                        receipt.id,
                        f"Created receipt {receipt.receipt_number} - {transaction_type} of "
                        f"\u20b9{amount_decimal} for {user.display_name}",
                    )
                    return JsonResponse({"success": True, "receipt_id": receipt.id})
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise
                    continue

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


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

        return JsonResponse({"success": True, "accounts": results})
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
                m.mobile_primary or m.phone or "",
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
                f"Approved loan {loan.loan_number} - \u20b9{loan.principal_amount} " f"for {loan.user.display_name}",
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

                        repayment.paid_date = date.today()
                        repayment.amount_paid = amount
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
                        loan.emis_overdue = LoanRepayment.objects.filter(
                            loan=loan, payment_status="upcoming", due_date__lt=date.today()
                        ).count()

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
                        f"Recorded EMI #{installment_number} payment of " f"\u20b9{amount} for loan {loan.loan_number}",
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
# Ticket Views
# ========================================


@login_required
@admin_required
def admin_tickets_view(request):
    """List all support tickets."""
    tickets_qs = Ticket.objects.select_related("user").all()

    # Filters
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    q = request.GET.get("q", "").strip()

    if status:
        tickets_qs = tickets_qs.filter(status=status)
    if priority:
        tickets_qs = tickets_qs.filter(priority=priority)
    if q:
        tickets_qs = tickets_qs.filter(
            Q(subject__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__member_id__icontains=q)
        )

    paginator = Paginator(tickets_qs, 20)
    page = request.GET.get("page", 1)
    try:
        tickets = paginator.page(page)
    except PageNotAnInteger:
        tickets = paginator.page(1)
    except EmptyPage:
        tickets = paginator.page(paginator.num_pages)

    # Stats
    total = Ticket.objects.count()
    open_count = Ticket.objects.filter(status="open").count()

    context = {
        "tickets": tickets,
        "status_choices": Ticket.STATUS_CHOICES,
        "priority_choices": Ticket.PRIORITY_CHOICES,
        "current_status": status,
        "current_priority": priority,
        "search_query": q,
        "total_tickets": total,
        "open_tickets": open_count,
    }
    return render(request, "admin/tickets.html", context)


@login_required
@admin_required
def admin_ticket_detail_view(request, ticket_id):
    """View ticket detail, reply, and change status."""
    ticket = Ticket.objects.select_related("user").get(id=ticket_id)

    if request.method == "POST":
        action = request.POST.get("action", "reply")

        if action == "reply":
            body = request.POST.get("body", "").strip()
            attachment = request.FILES.get("attachment")
            if body:
                TicketMessage.objects.create(ticket=ticket, sender=request.user, body=body, attachment=attachment)
                ticket.save(update_fields=["updated_at"])

        elif action == "status":
            new_status = request.POST.get("status", "")
            if new_status and new_status in dict(Ticket.STATUS_CHOICES):
                ticket.status = new_status
                ticket.save(update_fields=["status", "updated_at"])

        return redirect("admin_ticket_detail", ticket_id=ticket.id)

    messages_qs = ticket.messages.select_related("sender").all()

    context = {
        "ticket": ticket,
        "ticket_messages": messages_qs,
        "status_choices": Ticket.STATUS_CHOICES,
    }
    return render(request, "admin/ticket_detail.html", context)

