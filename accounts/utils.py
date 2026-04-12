"""
Utility functions for the accounts app.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Sum

logger = logging.getLogger(__name__)


def split_full_name(full_name):
    """
    Split a full name into first_name and last_name.

    Args:
        full_name: A string containing the full name

    Returns:
        tuple: (first_name, last_name)

    Examples:
        >>> split_full_name("John Doe")
        ('John', 'Doe')
        >>> split_full_name("John")
        ('John', '')
        >>> split_full_name("John Michael Doe")
        ('John', 'Michael Doe')
        >>> split_full_name("")
        ('', '')
    """
    if not full_name:
        return ("", "")

    full_name = full_name.strip()
    if not full_name:
        return ("", "")

    parts = full_name.split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    return (first_name, last_name)


def combine_name(first_name, last_name):
    """
    Combine first_name and last_name into a full name.

    Args:
        first_name: First name string (can be None or empty)
        last_name: Last name string (can be None or empty)

    Returns:
        str: Combined full name, trimmed

    Examples:
        >>> combine_name("John", "Doe")
        'John Doe'
        >>> combine_name("John", "")
        'John'
        >>> combine_name("", "Doe")
        'Doe'
        >>> combine_name(None, None)
        ''
    """
    first = (first_name or "").strip()
    last = (last_name or "").strip()

    return f"{first} {last}".strip()


def mask_email_for_display(email):
    """
    Mask an email for UI hints (e.g. login OTP screen).

    Uses first local character + *** + second-to-last local character so
    short addresses stay readable (e.g. xpllrn@icloud.com -> x***r@icloud.com).
    """
    raw = (email or "").strip()
    if not raw or "@" not in raw:
        return "your email"
    local, _, domain = raw.partition("@")
    local = local.strip()
    domain = domain.strip()
    if not local or not domain:
        return "your email"
    n = len(local)
    if n == 1:
        masked_local = local[0] + "***"
    elif n == 2:
        masked_local = local[0] + "***" + local[1]
    else:
        masked_local = local[0] + "***" + local[-2]
    return f"{masked_local}@{domain}"


def validate_password_strength(password, user=None):
    """
    Validate password against Django's password validators.

    Args:
        password: The password string to validate
        user: Optional user instance for user-specific validation

    Returns:
        tuple: (is_valid, error_messages)
            - is_valid: Boolean indicating if password is valid
            - error_messages: List of error message strings (empty if valid)

    Examples:
        >>> is_valid, errors = validate_password_strength("short")
        >>> is_valid
        False
        >>> "too short" in str(errors).lower()
        True
    """
    if not password:
        return (False, ["Password is required"])

    try:
        validate_password(password, user=user)
        return (True, [])
    except ValidationError as e:
        return (False, list(e.messages))


def get_financial_summary(start_date, end_date):
    """Calculate revenue, expenses, and profit for a given period."""
    from accounts.models import FundTransaction, Loan, LoanRepayment, MemberAccount

    # REVENUE: Interest earned from loan repayments
    loan_interest = LoanRepayment.objects.filter(
        payment_status="paid",
        paid_date__range=(start_date, end_date),
    ).aggregate(total=Sum("interest_component"))["total"] or Decimal("0.00")

    # REVENUE: Principal collected (cash inflow, not profit)
    principal_collected = LoanRepayment.objects.filter(
        payment_status="paid",
        paid_date__range=(start_date, end_date),
    ).aggregate(total=Sum("principal_component"))["total"] or Decimal("0.00")

    # REVENUE: Penalty income
    penalty_income = LoanRepayment.objects.filter(
        payment_status="paid",
        paid_date__range=(start_date, end_date),
    ).aggregate(total=Sum("penalty"))["total"] or Decimal("0.00")

    # REVENUE: Processing fees from loans disbursed in period
    processing_fees = Loan.objects.filter(
        disbursement_date__range=(start_date, end_date),
        status__in=["active", "closed"],
    ).aggregate(total=Sum("processing_fee"))["total"] or Decimal("0.00")

    # EXPENSE: Monthly interest liability on member deposits
    deposit_accounts = MemberAccount.objects.filter(is_deleted=False, status="active").exclude(
        account_type__in=["share", "od"]
    )
    monthly_interest_liability = sum(
        (acc.balance * acc.interest_rate / Decimal("100") / Decimal("12")) for acc in deposit_accounts
    )
    # Scale to the period
    months_in_period = max(1, (end_date - start_date).days / 30)
    deposit_interest_expense = (monthly_interest_liability * Decimal(str(round(months_in_period, 1)))).quantize(
        Decimal("0.01")
    )

    # Fund allocations in period
    fund_credits = FundTransaction.objects.filter(
        transaction_type="credit",
        created_at__date__range=(start_date, end_date),
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    # Loan portfolio stats
    active_loans = Loan.objects.filter(status="active")
    total_loans_outstanding = active_loans.aggregate(total=Sum("outstanding_balance"))["total"] or Decimal("0.00")
    total_disbursed = Loan.objects.filter(
        disbursement_date__range=(start_date, end_date),
        status__in=["active", "closed"],
    ).aggregate(total=Sum("principal_amount"))["total"] or Decimal("0.00")
    total_overdue = active_loans.aggregate(total=Sum("overdue_amount"))["total"] or Decimal("0.00")
    npa_loans = [loan for loan in active_loans if loan.is_npa]

    # Recovery rate
    total_due_in_period = LoanRepayment.objects.filter(due_date__range=(start_date, end_date)).aggregate(
        total=Sum("amount_due")
    )["total"] or Decimal("0.00")
    total_collected_in_period = LoanRepayment.objects.filter(
        due_date__range=(start_date, end_date), payment_status="paid"
    ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0.00")
    recovery_rate = (
        round(float(total_collected_in_period / total_due_in_period) * 100, 1) if total_due_in_period > 0 else 100.0
    )

    # Deposit portfolio
    deposit_by_type = {}
    for acc_type, acc_label in MemberAccount.ACCOUNT_TYPE_CHOICES:
        accs = MemberAccount.objects.filter(is_deleted=False, status="active", account_type=acc_type)
        total_bal = accs.aggregate(total=Sum("balance"))["total"] or Decimal("0.00")
        avg_rate = Decimal("0.00")
        if accs.exists():
            from django.db.models import Avg

            avg_rate = accs.aggregate(avg=Avg("interest_rate"))["avg"] or Decimal("0.00")
        if total_bal > 0:
            deposit_by_type[acc_label] = {
                "balance": total_bal,
                "avg_rate": round(avg_rate, 2),
                "count": accs.count(),
            }

    gross_revenue = loan_interest + penalty_income + processing_fees
    net_profit = gross_revenue - deposit_interest_expense

    return {
        "loan_interest_income": loan_interest,
        "principal_collected": principal_collected,
        "penalty_income": penalty_income,
        "processing_fees": processing_fees,
        "deposit_interest_expense": deposit_interest_expense,
        "fund_allocations": fund_credits,
        "gross_revenue": gross_revenue,
        "total_expenses": deposit_interest_expense,
        "net_profit": net_profit,
        # Loan portfolio
        "active_loans_count": active_loans.count(),
        "total_disbursed": total_disbursed,
        "total_loans_outstanding": total_loans_outstanding,
        "total_overdue": total_overdue,
        "npa_count": len(npa_loans),
        "recovery_rate": recovery_rate,
        # Deposit portfolio
        "deposit_by_type": deposit_by_type,
        "monthly_interest_liability": monthly_interest_liability.quantize(Decimal("0.01"))
        if isinstance(monthly_interest_liability, Decimal)
        else Decimal(str(round(monthly_interest_liability, 2))),
    }


def get_account_type_cashflow(months=6, account_type=None):
    """Return inflow/outflow grouped by account type for recent months."""
    from django.utils import timezone

    from accounts.models import MemberAccount, Receipt

    today = timezone.now().date()
    window_start = today - timedelta(days=months * 31)
    receipts = Receipt.objects.select_related("member_account").filter(created_at__date__gte=window_start)
    if account_type:
        receipts = receipts.filter(member_account__account_type=account_type)

    rows = []
    for acc_type, label in MemberAccount.ACCOUNT_TYPE_CHOICES:
        if account_type and acc_type != account_type:
            continue
        account_receipts = receipts.filter(member_account__account_type=acc_type)
        inflow = (
            account_receipts.filter(transaction_type__in=["credit", "interest", "dividend", "share_capital"]).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        outflow = account_receipts.filter(transaction_type__in=["debit", "transfer"]).aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        rows.append(
            {
                "account_type": acc_type,
                "label": label,
                "inflow": inflow,
                "outflow": outflow,
                "net": inflow - outflow,
            }
        )
    return rows


def log_action(request, action, entity_type, entity_id, description):
    """
    Create an audit log entry.

    Args:
        request: The HTTP request (used to get user and IP)
        action: Action type (create, update, delete, login, logout, approve, reject, reset_password, export)
        entity_type: Entity type (member, account, receipt, loan, system)
        entity_id: ID of the entity being acted on (can be None)
        description: Human-readable description of the action
    """
    from accounts.models import AuditLog

    ip_address = _get_client_ip(request)

    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )


def _get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def apply_fund_allocations(request, trigger_event, total_amount, source_description, source_member=None):
    """
    Automatically allocate amounts to funds based on active rules for the given trigger event.

    Args:
        request: The HTTP request (used to get user and for logging)
        trigger_event: The event that triggered this allocation (e.g., 'member_registration')
        total_amount: The total amount to be allocated (Decimal)
        source_description: Description of the source transaction
        source_member: Optional User instance who triggered this allocation

    Returns:
        list: List of FundTransaction objects created

    Examples:
        >>> apply_fund_allocations(request, 'member_registration', Decimal('200.00'),
        ...                        'Member registration fee: John Doe', source_member=user)
        [<FundTransaction: Welfare Fund - Credit - 50.00>, ...]
    """
    from decimal import Decimal

    from django.db import transaction
    from django.db.models import F

    from accounts.models import FundAccount, FundAllocationRule, FundTransaction

    created_transactions = []

    try:
        # Query all active allocation rules for this trigger event
        rules = FundAllocationRule.objects.filter(trigger_event=trigger_event, is_active=True).select_related("fund")

        for rule in rules:
            try:
                # Calculate allocation amount
                if rule.allocation_type == "fixed":
                    allocation_amount = rule.amount
                elif rule.allocation_type == "percentage":
                    allocation_amount = (total_amount * rule.percentage) / Decimal("100")
                else:
                    continue

                if not allocation_amount or allocation_amount <= 0:
                    continue

                # Wrap in atomic transaction
                with transaction.atomic():
                    # Lock the fund account for update
                    fund = FundAccount.objects.select_for_update().get(id=rule.fund.id, is_deleted=False)

                    # Calculate new balance
                    new_balance = fund.balance + allocation_amount

                    # Update balance using F() expression
                    FundAccount.objects.filter(id=fund.id).update(balance=F("balance") + allocation_amount)

                    # Create fund transaction
                    fund_txn = FundTransaction.objects.create(
                        fund=fund,
                        transaction_type="credit",
                        amount=allocation_amount,
                        description=source_description,
                        payment_mode="internal",
                        balance_after=new_balance,
                        trigger_event=trigger_event,
                        source_member=source_member,
                        created_by=request.user if request.user.is_authenticated else None,
                    )

                    created_transactions.append(fund_txn)

                    # Log the action
                    log_action(
                        request,
                        "create",
                        "fund",
                        fund.id,
                        f"Auto-allocated ₹{allocation_amount} to {fund.name} via {trigger_event}: {source_description}",
                    )

            except Exception as e:
                # Log error but don't break the parent transaction
                logger.error(
                    "Fund allocation failed for rule %s (fund: %s): %s",
                    rule.id,
                    rule.fund.name,
                    str(e),
                )
                continue

    except Exception as e:
        # Log error but don't break parent operations
        logger.error("Fund allocation process failed: %s", str(e))

    return created_transactions


def create_member_notification(user, title, message, notification_type="general", metadata=None):
    """Create an in-app notification for a member."""
    from accounts.models import Notification

    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        metadata=metadata or {},
    )
