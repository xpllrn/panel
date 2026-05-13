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
    from accounts.models import FundTransaction, LoanAccount, LoanRepayment, MemberAccount

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
    processing_fees = LoanAccount.objects.filter(
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
    active_loans = LoanAccount.objects.filter(status="active")
    total_loans_outstanding = active_loans.aggregate(total=Sum("outstanding_balance"))["total"] or Decimal("0.00")
    total_disbursed = LoanAccount.objects.filter(
        disbursement_date__range=(start_date, end_date),
        status__in=["active", "closed"],
    ).aggregate(total=Sum("principal_amount"))["total"] or Decimal("0.00")
    total_overdue = active_loans.aggregate(total=Sum("overdue_amount"))["total"] or Decimal("0.00")
    npa_loans = [la for la in active_loans if la.is_npa]

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


def persist_financial_snapshots(financial_period, calculated_by=None):
    """
    Persist ProfitAndLoss and SocietyAccount rows from get_financial_summary and related aggregates.

    Skips updating ProfitAndLoss when a snapshot for the period exists and is_locked (SocietyAccount
    is still refreshed). Returns (profit_and_loss, society_account, profit_and_loss_updated).
    """
    from django.db.models import Sum
    from django.utils import timezone

    from accounts.models import (
        FeeCharge,
        FundAccount,
        InterestReceivable,
        MemberAccount,
        ProfitAndLoss,
        SocietyAccount,
    )

    start = financial_period.start_date
    end = financial_period.end_date
    summary = get_financial_summary(start, end)

    fee_qs = FeeCharge.objects.filter(
        status="charged",
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    membership_fees = fee_qs.filter(fee_schedule__fee_type="membership").aggregate(s=Sum("amount"))["s"] or Decimal("0")
    fee_processing = fee_qs.filter(fee_schedule__fee_type="processing").aggregate(s=Sum("amount"))["s"] or Decimal("0")
    other_fees_income = fee_qs.filter(fee_schedule__fee_type__in=["annual_maintenance", "closure", "npa"]).aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")

    loan_interest_income = summary["loan_interest_income"]
    processing_fees_income = summary["processing_fees"] + fee_processing
    penalty_income = summary["penalty_income"]
    other_income = other_fees_income
    total_income = loan_interest_income + processing_fees_income + penalty_income + membership_fees + other_income

    deposit_interest_expense = summary["deposit_interest_expense"]
    bad_debt_expense = Decimal("0")
    other_expense = Decimal("0")
    total_expense = deposit_interest_expense + bad_debt_expense + other_expense

    gross_surplus = total_income - total_expense
    fund_allocations_total = summary["fund_allocations"]
    net_surplus = gross_surplus - fund_allocations_total

    now = timezone.now()

    existing_pl = ProfitAndLoss.objects.filter(financial_period=financial_period).order_by("-calculation_date").first()
    pl_updated = True
    if existing_pl and existing_pl.is_locked:
        pl_row = existing_pl
        pl_updated = False
    else:
        pl_defaults = {
            "loan_interest_income": loan_interest_income,
            "processing_fees_income": processing_fees_income,
            "penalty_income": penalty_income,
            "membership_fees_income": membership_fees,
            "other_income": other_income,
            "total_income": total_income,
            "deposit_interest_expense": deposit_interest_expense,
            "bad_debt_expense": bad_debt_expense,
            "other_expense": other_expense,
            "total_expense": total_expense,
            "gross_surplus": gross_surplus,
            "fund_allocations_total": fund_allocations_total,
            "net_surplus": net_surplus,
            "calculated_by": calculated_by,
            "calculation_date": now,
        }
        pl_row, _ = ProfitAndLoss.objects.update_or_create(
            financial_period=financial_period,
            defaults=pl_defaults,
        )

    deposit_accounts = MemberAccount.objects.filter(is_deleted=False, status="active").exclude(
        account_type__in=["share", "od"]
    )
    total_member_deposits = deposit_accounts.aggregate(s=Sum("balance"))["s"] or Decimal("0")
    total_interest_payable = deposit_accounts.aggregate(s=Sum("accrued_interest"))["s"] or Decimal("0")

    ir_outstanding = Decimal("0")
    for row in InterestReceivable.objects.filter(status="accrued").values("amount_accrued", "amount_collected"):
        ir_outstanding += row["amount_accrued"] - row["amount_collected"]

    fees_collected_period = fee_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_fund_balance = FundAccount.objects.filter(is_deleted=False).aggregate(s=Sum("balance"))["s"] or Decimal("0")

    society_defaults = {
        "total_member_deposits": total_member_deposits,
        "total_loan_outstanding": summary["total_loans_outstanding"],
        "total_interest_payable": total_interest_payable,
        "total_interest_receivable": ir_outstanding,
        "total_fees_collected": fees_collected_period,
        "total_fund_balance": total_fund_balance,
        "net_surplus": net_surplus,
    }
    society_row, _ = SocietyAccount.objects.update_or_create(
        financial_period=financial_period,
        defaults=society_defaults,
    )

    return pl_row, society_row, pl_updated


def sync_loan_interest_receivables(*, as_of_date=None, financial_period=None):
    """
    Ensure InterestReceivable rows exist for unpaid EMIs on active loans with due_date <= as_of_date.

    Returns the number of repayments considered (including those that already had a receivable).
    """
    from django.utils import timezone

    from accounts.models import InterestReceivable, LoanRepayment

    as_of = as_of_date or timezone.now().date()
    fp = financial_period if financial_period is not None else active_financial_period()

    qs = (
        LoanRepayment.objects.filter(loan_account__status="active", due_date__lte=as_of)
        .exclude(payment_status="paid")
        .select_related("loan_account")
    )

    count = 0
    for rep in qs:
        if rep.interest_component <= 0:
            continue
        obj, created = InterestReceivable.objects.get_or_create(
            loan_account=rep.loan_account,
            due_date=rep.due_date,
            defaults={
                "financial_period": fp,
                "amount_accrued": rep.interest_component,
                "amount_collected": Decimal("0"),
                "status": "accrued",
            },
        )
        if not created and obj.status == "accrued":
            obj.amount_accrued = rep.interest_component
            if fp is not None:
                obj.financial_period = fp
            obj.save(update_fields=["amount_accrued", "financial_period"])
        count += 1
    return count


def mark_interest_receivable_collected_for_repayment(repayment):
    """When an EMI is fully paid, mark the matching accrued interest receivable as collected."""
    from django.db.models import F

    from accounts.models import InterestReceivable

    if repayment.payment_status != "paid" or repayment.interest_component <= 0:
        return 0
    paid_date = repayment.paid_date
    return InterestReceivable.objects.filter(
        loan_account_id=repayment.loan_account_id,
        due_date=repayment.due_date,
        status="accrued",
    ).update(
        amount_collected=F("amount_accrued"),
        status="collected",
        collected_date=paid_date,
    )


def get_account_type_cashflow(months=6, account_type=None):
    """Return inflow/outflow grouped by account type for recent months."""
    from django.utils import timezone

    from accounts.models import MemberAccount, Transaction

    today = timezone.now().date()
    window_start = today - timedelta(days=months * 31)
    receipts = Transaction.objects.select_related("member_account").filter(created_at__date__gte=window_start)
    if account_type:
        receipts = receipts.filter(member_account__account_type=account_type)

    rows = []
    for acc_type, label in MemberAccount.ACCOUNT_TYPE_CHOICES:
        if account_type and acc_type != account_type:
            continue
        account_receipts = receipts.filter(member_account__account_type=acc_type)
        inflow = account_receipts.filter(
            transaction_type__in=["credit", "interest", "dividend", "share_capital"]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
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
        period = active_financial_period()

        rules = (
            FundAllocationRule.objects.filter(trigger_event=trigger_event, is_active=True)
            .select_related("fund")
            .order_by("priority_order", "id")
        )

        for rule in rules:
            try:
                if rule.min_threshold is not None and total_amount < rule.min_threshold:
                    continue

                # Calculate allocation amount
                if rule.allocation_type == "fixed":
                    allocation_amount = rule.amount
                elif rule.allocation_type == "percentage":
                    allocation_amount = (total_amount * rule.percentage) / Decimal("100")
                else:
                    continue

                if rule.max_cap is not None and allocation_amount is not None and allocation_amount > rule.max_cap:
                    allocation_amount = rule.max_cap

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
                        financial_period=period,
                        allocation_rule=rule,
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


# --- Phase 2: member sub-models (KYC, addresses, nominees, share capital) ---


def ensure_member_submodels(user):
    """Ensure KYC row and current/permanent address rows exist for a member."""
    from accounts.models import MemberAddress, MemberKYC

    MemberKYC.objects.get_or_create(user=user)
    MemberAddress.objects.get_or_create(
        user=user,
        address_type="current",
        defaults={"country": "India"},
    )
    MemberAddress.objects.get_or_create(
        user=user,
        address_type="permanent",
        defaults={"country": "India", "same_as_current": True},
    )


def user_kyc(user):
    """Return MemberKYC for user, or None if missing."""
    from accounts.models import MemberKYC

    try:
        return user.kyc
    except MemberKYC.DoesNotExist:
        return None


def user_address(user, address_type):
    """Return MemberAddress for the given type ('current' or 'permanent'), or None."""
    return user.addresses.filter(address_type=address_type).first()


def format_current_address_display(user):
    """Single-line display string for current address."""
    a = user_address(user, "current")
    if not a:
        return ""
    parts = [a.address_line1, a.address_line2, a.city, a.district, a.state, a.pincode]
    return ", ".join(p for p in parts if p)


def format_permanent_address_display(user):
    """Single-line display for permanent address."""
    p = user_address(user, "permanent")
    if not p:
        return ""
    if p.same_as_current:
        return "Same as current address"
    parts = [p.address_line1, p.address_line2, p.city, p.district, p.state, p.pincode]
    return ", ".join(x for x in parts if x)


def active_share_holdings_qs(user):
    """Issued share lots that are still active."""
    return user.share_holdings.filter(status="issued", redemption_date__isnull=True)


def user_active_share_capital_total(user):
    """Sum of total_value for active issued share lots."""
    total = active_share_holdings_qs(user).aggregate(s=Sum("total_value"))["s"]
    return total if total is not None else Decimal("0")


def user_active_share_count(user):
    """Total number of shares across active issued lots."""
    total = active_share_holdings_qs(user).aggregate(s=Sum("number_of_shares"))["s"]
    return int(total or 0)


def user_primary_share_lot(user):
    """Most recent active issued share lot (for certificate / face value display)."""
    return active_share_holdings_qs(user).order_by("-issue_date", "-id").first()


def nominee_primary(user):
    return user.nominees.filter(is_primary=True).order_by("id").first()


def nominee_secondary(user):
    return user.nominees.filter(is_primary=False).order_by("id").first()


def active_financial_period():
    """Backward-compat shim. Canonical impl: `accounts.services.financial_period.active`."""
    from accounts.services import financial_period as fp_service

    return fp_service.active()


def financial_period_overlapping(start_date, end_date):
    """Backward-compat shim. Canonical impl: `accounts.services.financial_period.overlapping`."""
    from accounts.services import financial_period as fp_service

    return fp_service.overlapping(start_date, end_date)


class LoanListItem:
    """Single row for loans table: either a pending/rejected application or a book account."""

    __slots__ = ("_application", "_account")

    def __init__(self, *, application=None, account=None):
        if bool(application) == bool(account):
            raise ValueError("LoanListItem: pass exactly one of application= or account=")
        self._application = application
        self._account = account

    @property
    def list_kind(self):
        return "account" if self._account else "application"

    @property
    def id(self):
        return self._account.id if self._account else self._application.id

    @property
    def user(self):
        return self._account.user if self._account else self._application.user

    @property
    def application(self):
        return self._account.application if self._account else self._application

    @property
    def loan_number(self):
        return self._account.loan_number if self._account else self._application.application_number

    @property
    def loan_type(self):
        return self.application.loan_type

    def get_loan_type_display(self):
        return self.application.get_loan_type_display()

    @property
    def principal_amount(self):
        return self.application.principal_amount

    @property
    def interest_rate(self):
        return self.application.interest_rate

    @property
    def tenure_months(self):
        return self.application.tenure_months

    @property
    def emi_amount(self):
        if self._account:
            return self._account.emi_amount
        return self._application.calculate_emi()

    @property
    def outstanding_balance(self):
        if self._account:
            return self._account.outstanding_balance
        return self.application.principal_amount

    @property
    def overdue_amount(self):
        if self._account:
            return self._account.overdue_amount
        return Decimal("0.00")

    @property
    def completion_percentage(self):
        if self._account:
            return self._account.completion_percentage
        return 0.0

    @property
    def is_npa(self):
        if self._account:
            return self._account.is_npa
        return False

    @property
    def application_date(self):
        return self.application.application_date

    @property
    def disbursement_date(self):
        return self._account.disbursement_date if self._account else None

    @property
    def status(self):
        return self._account.status if self._account else self._application.status

    def get_status_display(self):
        return self._account.get_status_display() if self._account else self._application.get_status_display()

    @property
    def created_at(self):
        return self._account.created_at if self._account else self._application.created_at
