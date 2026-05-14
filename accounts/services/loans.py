"""
Loan lifecycle services — application → approval → EMI tracking.

This module is the single source of truth for all loan business logic. Both
adapters (`admin_portal.views` HTML and `accounts.api_views` REST) MUST call
these functions instead of duplicating the rules.

Functions in this module:

    create_loan_application(...)      — staff records a new LoanApplication
    approve_loan_application(...)     — second admin approves, books LoanAccount + schedule
    record_emi_payment(...)           — installment is paid; updates schedule + posts Transaction
    has_unpaid_emi(user)              — guard used by member-status workflows
    next_application_number()         — atomic LA-YYYY-NNNNN generator
    next_loan_account_number()        — atomic LN-YYYY-NNNNN generator

Design notes:

* All HTTP / template concerns stay in the adapter layer.
* Services accept `actor` (a `User`) and optional `ip_address` (str) instead
  of a `request`. Adapters pass `request.user` and `_get_client_ip(request)`.
* Services raise from `accounts.services.exceptions`; adapters translate.
* This is a pure 0.3 refactor — behaviour is byte-identical to the prior
  view-internal logic. Phase A1 (disbursement-as-Transaction) and Phase B4
  (auto-fees) will land *inside this module* in subsequent commits.
"""

import calendar
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum

from accounts.models import (
    AuditLog,
    Guarantor,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    LoanTypeConfiguration,
    MemberAccount,
    SocietyConfiguration,
    Transaction,
    User,
)
from accounts.services.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

DEFAULT_INTEREST_TYPE = "reducing"
MAX_NUMBER_GENERATION_RETRIES = 5

# ---------------------------------------------------------------------------
# Audit helper (local to the service layer — no HTTP coupling)
# ---------------------------------------------------------------------------


def _write_audit(*, actor, action, entity_type, entity_id, description, ip_address=None):
    """Write an AuditLog row from a service. Mirrors `accounts.utils.log_action`
    but takes `actor` / `ip_address` directly so services do not import `request`.
    """
    AuditLog.objects.create(
        user=actor if (actor is not None and actor.is_authenticated) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )


# ---------------------------------------------------------------------------
# Number generators
# ---------------------------------------------------------------------------


def next_application_number(*, today=None):
    """Generate the next LA-YYYY-NNNNN application number.

    Caller MUST be inside a `transaction.atomic()` block that holds a
    `select_for_update()` on the LoanApplication row with the previous max
    sequence, OR retry on IntegrityError. This helper performs the lookup
    under SELECT FOR UPDATE; the caller's atomic block protects the create.
    """
    today = today or date.today()
    year = today.year
    last_app = (
        LoanApplication.objects.select_for_update()
        .filter(application_number__startswith=f"LA-{year}-")
        .order_by("-application_number")
        .first()
    )
    if last_app:
        try:
            last_seq = int(last_app.application_number.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1
    return f"LA-{year}-{next_seq:05d}"


def next_loan_account_number(*, today=None):
    """Generate the next LN-YYYY-NNNNN loan account number. See atomic note above."""
    today = today or date.today()
    year = today.year
    last_ac = (
        LoanAccount.objects.select_for_update()
        .filter(loan_number__startswith=f"LN-{year}-")
        .order_by("-loan_number")
        .first()
    )
    if last_ac:
        try:
            last_seq = int(last_ac.loan_number.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1
    return f"LN-{year}-{next_seq:05d}"


def _next_transaction_number(*, today=None):
    """Delegate to `accounts.services.transactions.next_transaction_number`
    so there is exactly one number-generation implementation in the service
    layer. (Phase 0.4 consolidation.)
    """
    from accounts.services.transactions import next_transaction_number

    return next_transaction_number(today=today)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def has_unpaid_emi(user):
    """True if the user has any non-paid installment on any active loan.

    Used by member-status workflows to prevent inactivating a member who
    still owes the society money.
    """
    return (
        LoanRepayment.objects.filter(
            loan_account__user=user,
            loan_account__status="active",
        )
        .exclude(payment_status="paid")
        .exists()
    )


# ---------------------------------------------------------------------------
# EMI math (kept here for now; Phase A1 will reconcile with InterestCalculatorService)
# ---------------------------------------------------------------------------


def _compute_emi_and_total_payable(principal, rate, tenure, interest_type):
    """Return (emi, total_payable) quantised to paise.

    Preserves the exact arithmetic of the prior view-internal code so this
    0.3 refactor is byte-identical. Phase A1 will route through
    `accounts.services.interest.InterestCalculatorService` and add proper
    flat-vs-reducing handling on the model side.
    """
    principal = Decimal(str(principal))
    rate = Decimal(str(rate))
    tenure = int(tenure)

    if rate > 0:
        monthly_rate = rate / Decimal("1200")
        if interest_type == "flat":
            total_interest = principal * rate * Decimal(str(tenure)) / Decimal("1200")
            emi = (principal + total_interest) / Decimal(str(tenure))
            total_payable = principal + total_interest
        else:
            factor = (1 + monthly_rate) ** tenure
            emi = (principal * monthly_rate * factor) / (factor - 1)
            total_payable = emi * Decimal(str(tenure))
    else:
        emi = principal / Decimal(str(tenure))
        total_payable = principal

    return emi.quantize(Decimal("0.01")), total_payable.quantize(Decimal("0.01"))


def _advance_one_month(d, anchor_day):
    """Return d advanced by one month, clamped to the anchor's day-of-month."""
    if d.month == 12:
        next_month = 1
        next_year = d.year + 1
    else:
        next_month = d.month + 1
        next_year = d.year
    max_d = calendar.monthrange(next_year, next_month)[1]
    return date(next_year, next_month, min(anchor_day, max_d))


def _build_repayment_schedule(loan_account, principal, rate, emi, tenure, first_emi_date):
    """Build (but do not save) the list of LoanRepayment rows for a fresh loan."""
    remaining = Decimal(str(principal))
    monthly_rate = Decimal(str(rate)) / Decimal("1200")
    current_date = first_emi_date
    repayments = []
    for i in range(1, tenure + 1):
        interest = (remaining * monthly_rate).quantize(Decimal("0.01"))
        principal_component = emi - interest
        if i == tenure:
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
                loan_account=loan_account,
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
        current_date = _advance_one_month(current_date, first_emi_date.day)

    return repayments


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def create_loan_application(
    *,
    user_id,
    loan_type,
    principal_amount,
    interest_rate,
    tenure_months,
    interest_type=DEFAULT_INTEREST_TYPE,
    purpose="",
    remarks="",
    guarantor_name="",
    guarantor_member_id="",
    guarantor_relationship="",
    guarantor_contact="",
    collateral_type="",
    collateral_value=None,
    collateral_description="",
    processing_fee=None,
    disbursement_account_id=None,
    actor=None,
    ip_address=None,
    audit_via="panel",
):
    """Create a new LoanApplication. Returns the created instance.

    ``processing_fee`` and ``disbursement_account_id`` are part of the loan
    *account* schema, not the application schema (no columns on
    :class:`LoanApplication`). They are accepted here so adapters can pass the
    full payload through a single service entry point — both are captured in
    the audit description and must be re-supplied to
    :func:`approve_loan_application` for the disbursement Transaction to post.

    Raises:
        ValidationError — missing/invalid field, disabled loan type, missing rate.
        NotFoundError   — referenced member does not exist.
    """
    if not user_id:
        raise ValidationError("Member is required.")
    if not loan_type:
        raise ValidationError("Loan type is required.")
    if not principal_amount:
        raise ValidationError("Loan amount is required.")
    if not tenure_months:
        raise ValidationError("Tenure is required.")

    active_loan_types = set(LoanTypeConfiguration.objects.filter(is_active=True).values_list("loan_type", flat=True))
    configured_rate = (
        LoanTypeConfiguration.objects.filter(loan_type=loan_type, is_active=True)
        .values_list("interest_rate", flat=True)
        .first()
    )
    if active_loan_types and loan_type not in active_loan_types:
        raise ValidationError("This loan type is disabled in Settings.")
    if not interest_rate and configured_rate is not None:
        interest_rate = str(configured_rate)
    if not interest_rate:
        raise ValidationError("Interest rate is required.")

    try:
        member = User.objects.get(id=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Member not found.") from exc

    principal = Decimal(str(principal_amount))
    rate = Decimal(str(interest_rate))
    tenure = int(tenure_months)
    interest_type = interest_type or DEFAULT_INTEREST_TYPE

    try:
        fee_decimal = Decimal(str(processing_fee)) if processing_fee not in (None, "") else Decimal("0")
    except Exception as exc:
        raise ValidationError("Processing fee is invalid.") from exc
    disbursement_account_id = int(disbursement_account_id) if disbursement_account_id else None

    emi, _total_payable = _compute_emi_and_total_payable(principal, rate, tenure, interest_type)

    for attempt in range(MAX_NUMBER_GENERATION_RETRIES):
        try:
            with transaction.atomic():
                application_number = next_application_number()
                app = LoanApplication.objects.create(
                    application_number=application_number,
                    user=member,
                    loan_type=loan_type,
                    principal_amount=principal,
                    interest_rate=rate,
                    interest_type=interest_type,
                    tenure_months=tenure,
                    application_date=date.today(),
                    status="pending",
                    purpose=(purpose or "").strip() or None,
                    remarks=(remarks or "").strip() or None,
                    guarantor_name=(guarantor_name or "").strip() or None,
                    guarantor_member_id=(guarantor_member_id or "").strip() or None,
                    guarantor_relationship=(guarantor_relationship or "").strip() or None,
                    guarantor_contact=(guarantor_contact or "").strip() or None,
                    collateral_type=(collateral_type or "").strip() or None,
                    collateral_value=Decimal(str(collateral_value)) if collateral_value else None,
                    collateral_description=(collateral_description or "").strip() or None,
                    created_by=actor,
                )

            via = "via API: " if audit_via == "api" else ""
            extras = []
            if fee_decimal and fee_decimal > 0:
                extras.append(f"processing_fee=\u20b9{fee_decimal}")
            if disbursement_account_id:
                extras.append(f"disbursement_account_id={disbursement_account_id}")
            extras_suffix = f" [{', '.join(extras)}]" if extras else ""
            _write_audit(
                actor=actor,
                ip_address=ip_address,
                action="create",
                entity_type="loan",
                entity_id=app.id,
                description=(
                    f"Created loan application {via}{application_number} for {member.display_name} — "
                    f"{app.get_loan_type_display()} \u20b9{principal} (EMI ~\u20b9{emi}){extras_suffix}"
                ),
            )
            return app
        except IntegrityError:
            if attempt == MAX_NUMBER_GENERATION_RETRIES - 1:
                raise
            continue


def approve_loan_application(
    *,
    application_id,
    disbursement_date,
    actor,
    disbursement_account_id=None,
    processing_fee=None,
    ip_address=None,
    audit_via="panel",
):
    """Approve a pending LoanApplication: create LoanAccount, EMI schedule, Guarantor.

    When ``disbursement_account_id`` resolves to an active :class:`MemberAccount`
    belonging to the borrower, a credit :class:`Transaction` is posted for the
    full principal via :func:`accounts.services.transactions.post_transaction`
    inside the same atomic block (Phase A1 — disbursement-as-Transaction).

    Returns the new ``LoanAccount`` instance.

    Raises:
        NotFoundError         — application missing.
        ValidationError       — application not pending / already has an account
                                / no disbursement_date / processing_fee bad /
                                disbursement account missing / not owned by borrower.
        PermissionDeniedError — actor created the application (segregation of duties).
    """
    from accounts.services import transactions as transaction_service

    if not disbursement_date:
        raise ValidationError("Disbursement date is required.")

    if isinstance(disbursement_date, str):
        from datetime import datetime  # local import keeps top of file tidy

        disbursement_date = datetime.strptime(disbursement_date, "%Y-%m-%d").date()

    try:
        app = LoanApplication.objects.get(id=application_id)
    except LoanApplication.DoesNotExist as exc:
        raise NotFoundError("Loan application not found.") from exc

    if app.status != "pending":
        raise ValidationError("Only pending applications can be approved.")

    if actor is not None and app.created_by_id == getattr(actor, "id", None):
        raise PermissionDeniedError("You cannot approve a loan you created. Another admin must approve it.")

    if LoanAccount.objects.filter(application=app).exists():
        raise ConflictError("This application already has a loan account.")

    # Resolve disbursement account / processing fee. LoanApplication has no
    # columns for these (verified Phase A1) — caller passes the values that
    # were captured at create time. Falls back to whatever the application
    # carries if a future migration adds the columns.
    resolved_account_id = disbursement_account_id
    if resolved_account_id is None:
        resolved_account_id = getattr(app, "disbursement_account_id", None)
    resolved_account_id = int(resolved_account_id) if resolved_account_id else None

    if processing_fee in (None, ""):
        processing_fee = getattr(app, "processing_fee", None)
    try:
        resolved_fee = Decimal(str(processing_fee)) if processing_fee not in (None, "") else Decimal("0")
    except Exception as exc:
        raise ValidationError("Processing fee is invalid.") from exc

    disbursement_account = None
    if resolved_account_id:
        try:
            disbursement_account = MemberAccount.objects.get(id=resolved_account_id, is_deleted=False)
        except MemberAccount.DoesNotExist as exc:
            raise ValidationError("Disbursement account does not belong to the borrower.") from exc
        if disbursement_account.user_id != app.user_id:
            raise ValidationError("Disbursement account does not belong to the borrower.")
        if disbursement_account.status != "active":
            raise ValidationError("Disbursement account does not belong to the borrower.")

    if disbursement_date.month == 12:
        first_emi_month = 1
        first_emi_year = disbursement_date.year + 1
    else:
        first_emi_month = disbursement_date.month + 1
        first_emi_year = disbursement_date.year
    max_day = calendar.monthrange(first_emi_year, first_emi_month)[1]
    first_emi_date = date(first_emi_year, first_emi_month, min(disbursement_date.day, max_day))

    principal = app.principal_amount
    rate = app.interest_rate
    tenure = app.tenure_months
    emi = app.calculate_emi()
    if rate > 0 and app.interest_type == "flat":
        total_interest = principal * rate * Decimal(str(tenure)) / Decimal("1200")
        total_payable = (principal + total_interest).quantize(Decimal("0.01"))
    elif rate > 0:
        total_payable = (emi * Decimal(str(tenure))).quantize(Decimal("0.01"))
    else:
        total_payable = principal

    disbursement_txn = None
    with transaction.atomic():
        app.status = "approved"
        app.approval_date = date.today()
        app.approved_by = actor
        app.save()

        ln_number = next_loan_account_number()
        acct = LoanAccount.objects.create(
            loan_number=ln_number,
            application=app,
            user_id=app.user_id,
            status="active",
            principal_amount=principal,
            interest_rate=rate,
            interest_type=app.interest_type,
            tenure_months=tenure,
            emi_amount=emi,
            total_payable=total_payable,
            total_paid=Decimal("0"),
            outstanding_balance=principal,
            overdue_amount=Decimal("0"),
            disbursement_date=disbursement_date,
            first_emi_date=first_emi_date,
            total_emis=tenure,
            emis_paid=0,
            emis_overdue=0,
            collateral_type=app.collateral_type,
            collateral_value=app.collateral_value,
            collateral_description=app.collateral_description,
            disbursement_account=disbursement_account,
            processing_fee=resolved_fee,
            created_by=app.created_by,
        )

        repayments = _build_repayment_schedule(
            loan_account=acct,
            principal=principal,
            rate=rate,
            emi=emi,
            tenure=tenure,
            first_emi_date=first_emi_date,
        )
        if repayments:
            acct.last_emi_date = repayments[-1].due_date
            acct.save()
        LoanRepayment.objects.bulk_create(repayments)

        if app.guarantor_name:
            g = Guarantor(
                loan_account=acct,
                name=app.guarantor_name,
                relationship=app.guarantor_relationship,
                contact=app.guarantor_contact or None,
                is_member=bool(app.guarantor_member_id),
                is_verified=False,
            )
            if app.guarantor_member_id:
                gu = User.objects.filter(member_id=app.guarantor_member_id).first()
                if gu:
                    g.user_id = gu.id
            g.save()

        if disbursement_account is not None:
            disbursement_txn = transaction_service.post_transaction(
                member_account_id=disbursement_account.id,
                transaction_type="credit",
                amount=principal,
                description=f"Loan disbursement: {ln_number}",
                actor=actor,
                ip_address=ip_address,
                audit=False,
                audit_via=audit_via,
            )

        # Phase B4: auto-post processing fee via the fee service.
        from accounts.services import fees as fee_service

        fee_service.apply_processing_fee(
            acct,
            actor=actor,
            ip_address=ip_address,
            audit_via=audit_via,
        )

    acct.refresh_from_db()

    via = "via API: " if audit_via == "api" else ""
    extras = []
    if resolved_fee and resolved_fee > 0:
        extras.append(f"processing_fee=\u20b9{resolved_fee}")
    if disbursement_txn is not None:
        extras.append(f"disbursement_txn={disbursement_txn.transaction_number}")
    extras_suffix = f" [{', '.join(extras)}]" if extras else ""
    _write_audit(
        actor=actor,
        ip_address=ip_address,
        action="approve",
        entity_type="loan",
        entity_id=acct.id,
        description=(f"Approved loan {via}{ln_number} — \u20b9{principal} for {app.user.display_name}{extras_suffix}"),
    )

    return acct


def record_emi_payment(
    *,
    loan_account_id,
    installment_number,
    amount_paid,
    payment_mode="cash",
    actor=None,
    ip_address=None,
    audit_via="panel",
):
    """Record an EMI payment. Returns a dict with `repayment`, `loan_account`,
    `transaction` (the Transaction or None), and `penalty` (Decimal).

    Raises:
        NotFoundError   — loan or installment missing.
        ValidationError — loan not active / installment paid / non-positive amount.
    """
    from accounts.services import interest_engine

    if not installment_number:
        raise ValidationError("Installment number is required.")
    if amount_paid is None or amount_paid == "":
        raise ValidationError("Payment amount is required.")
    try:
        amount = Decimal(str(amount_paid))
    except Exception as exc:
        raise ValidationError("Payment amount is invalid.") from exc
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    for attempt in range(MAX_NUMBER_GENERATION_RETRIES):
        try:
            with transaction.atomic():
                try:
                    loan_ac = LoanAccount.objects.select_for_update().get(id=loan_account_id)
                except LoanAccount.DoesNotExist as exc:
                    raise NotFoundError("Loan not found.") from exc

                if loan_ac.status != "active":
                    raise ValidationError("Only active loans can receive payments.")

                try:
                    repayment = LoanRepayment.objects.select_for_update().get(
                        loan_account=loan_ac, installment_number=int(installment_number)
                    )
                except LoanRepayment.DoesNotExist as exc:
                    raise NotFoundError("Installment not found.") from exc

                if repayment.payment_status == "paid":
                    raise ValidationError("This installment is already paid.")

                penalty = Decimal("0.00")
                if repayment.due_date < date.today():
                    days_late = (date.today() - repayment.due_date).days
                    penalty_per_day = SocietyConfiguration.objects.order_by("id").values_list(
                        "late_payment_penalty_per_day", flat=True
                    ).first() or Decimal("0.00")
                    penalty = (Decimal(days_late) * penalty_per_day).quantize(Decimal("0.01"))

                repayment.paid_date = date.today()
                repayment.amount_paid = amount
                repayment.penalty = penalty
                repayment.payment_mode = payment_mode
                repayment.payment_status = "paid" if amount >= repayment.amount_due else "partial"

                member_account = loan_ac.disbursement_account
                if not member_account:
                    member_account = MemberAccount.objects.filter(user=loan_ac.user, status="active").first()

                txn = None
                if member_account:
                    member_account = MemberAccount.objects.select_for_update().get(id=member_account.id)
                    txn_number = _next_transaction_number()
                    new_balance = member_account.balance + amount
                    MemberAccount.objects.filter(id=member_account.id).update(
                        balance=F("balance") + amount,
                        last_transaction_date=date.today(),
                    )
                    txn = Transaction.objects.create(
                        transaction_number=txn_number,
                        user=loan_ac.user,
                        member_account=member_account,
                        transaction_type="credit",
                        amount=amount,
                        description=f"Loan EMI #{installment_number} - {loan_ac.loan_number}",
                        payment_mode=payment_mode,
                        balance_after=new_balance,
                        created_by=actor,
                    )
                    repayment.transaction = txn

                repayment.save()

                if repayment.payment_status == "paid":
                    interest_engine.reconcile_emi_to_receivable(repayment, transaction=txn)

                loan_ac.total_paid = loan_ac.total_paid + amount
                loan_ac.outstanding_balance = loan_ac.outstanding_balance - repayment.principal_component
                if loan_ac.outstanding_balance < 0:
                    loan_ac.outstanding_balance = Decimal("0")
                loan_ac.emis_paid = LoanRepayment.objects.filter(loan_account=loan_ac, payment_status="paid").count()

                LoanRepayment.objects.filter(
                    loan_account=loan_ac, payment_status="upcoming", due_date__lt=date.today()
                ).update(payment_status="overdue")

                loan_ac.emis_overdue = LoanRepayment.objects.filter(
                    loan_account=loan_ac, payment_status="overdue"
                ).count()
                loan_ac.overdue_amount = LoanRepayment.objects.filter(
                    loan_account=loan_ac, payment_status="overdue"
                ).aggregate(total=Sum("amount_due"))["total"] or Decimal("0")

                unpaid = LoanRepayment.objects.filter(loan_account=loan_ac).exclude(payment_status="paid").count()
                if unpaid == 0:
                    loan_ac.status = "closed"
                    loan_ac.closure_date = date.today()
                    loan_ac.outstanding_balance = Decimal("0")

                loan_ac.save()

            via = "via API: " if audit_via == "api" else ""
            _write_audit(
                actor=actor,
                ip_address=ip_address,
                action="update",
                entity_type="loan",
                entity_id=loan_ac.id,
                description=(
                    f"Recorded EMI #{installment_number} payment {via}of \u20b9{amount} for loan {loan_ac.loan_number}"
                ),
            )

            return {
                "repayment": repayment,
                "loan_account": loan_ac,
                "transaction": txn,
                "penalty": penalty,
            }
        except IntegrityError:
            if attempt == MAX_NUMBER_GENERATION_RETRIES - 1:
                raise
            continue
