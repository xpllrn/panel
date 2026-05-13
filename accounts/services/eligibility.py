"""Loan-eligibility pre-check service.

Pure read service. Returns a deterministic verdict + reasons. Never mutates
data. Never raises (except :class:`NotFoundError` for an unknown user via the
``check_loan_eligibility_by_id`` helper).

The service powers three downstream surfaces (Phase B8 builds the engine; the
adapters land in later phases):

* Admin loan-application form — "Eligibility check" live panel.
* REST endpoint ``GET /api/v1/admin/members/{id}/loan-eligibility?...``.
* MCP server tool ``is_loan_approvable(application_id)``.

DESIGN
------
Each rule is an internal ``_check_*`` helper that returns either ``None`` (the
check passes) or a single human-readable reason string (the check fails). The
top-level ``check_loan_eligibility`` runs **every** check regardless of earlier
failures so the operator sees the *full* list of blockers in one round-trip.

All monetary maths use :class:`decimal.Decimal`. No HTTP, no templates, no
mutation. Pattern mirrors :mod:`accounts.services.loans`.
"""

import logging
from decimal import Decimal, InvalidOperation

from accounts.models import LoanTypeConfiguration, User
from accounts.services import financial_period as financial_period_service
from accounts.services.exceptions import NotFoundError
from accounts.services.loans import has_unpaid_emi

logger = logging.getLogger(__name__)

try:
    from accounts.services import exposure as _exposure_service

    _EXPOSURE_AVAILABLE = True
except ImportError:
    _exposure_service = None
    _EXPOSURE_AVAILABLE = False
    logger.info("eligibility: exposure_check_unavailable (accounts.services.exposure not importable)")


POSITIVE_KYC_STATUSES = {"verified", "approved"}

DEFAULT_EXPOSURE_CEILING = Decimal("5000000")


# ---------------------------------------------------------------------------
# Individual checks — each returns None (pass) or a reason string (fail).
# ---------------------------------------------------------------------------


def _check_user_is_member(user):
    """Pass when ``user.role == 'member'`` and the row is not soft-deleted."""
    if user is None:
        return "Selected user is not a member."
    role = getattr(user, "role", None)
    if role != "member":
        return "Selected user is not a member."
    if getattr(user, "is_deleted", False):
        return "Selected user is not a member."
    return None


def _check_eligible_for_loans(user):
    """Pass when ``user.eligible_for_loans`` is truthy.

    The check is skipped silently if the column is not present on the User
    model (older installs without the Phase 2 banking-flag block).
    """
    if user is None:
        return None
    if not _has_field(User, "eligible_for_loans"):
        return None
    if getattr(user, "eligible_for_loans", True):
        return None
    return "Member is marked as ineligible for loans."


def _check_kyc_verified(user):
    """Pass when the member's KYC status is one of :data:`POSITIVE_KYC_STATUSES`.

    Prefers the Phase-2 :class:`accounts.models.MemberKYC` row when present;
    falls back to the legacy ``User.kyc_status`` column otherwise.
    """
    if user is None:
        return "KYC is not verified."

    status = None
    kyc_row = None
    try:
        kyc_row = getattr(user, "kyc", None)
    except Exception:
        kyc_row = None
    if kyc_row is not None:
        status = getattr(kyc_row, "kyc_status", None)

    if status is None:
        status = getattr(user, "kyc_status", None)

    if status and str(status).lower() in POSITIVE_KYC_STATUSES:
        return None
    return "KYC is not verified."


def _check_no_overdue_emi(user):
    """Pass when :func:`accounts.services.loans.has_unpaid_emi` is False."""
    if user is None:
        return None
    if has_unpaid_emi(user):
        return "Member has overdue EMI on an existing loan."
    return None


def _check_loan_type_active(loan_type):
    """Pass when an active :class:`LoanTypeConfiguration` row exists for ``loan_type``."""
    if not loan_type:
        return "Loan type is required."
    exists = LoanTypeConfiguration.objects.filter(loan_type=loan_type, is_active=True).exists()
    if exists:
        return None
    return f"Loan type '{loan_type}' is currently disabled."


def _check_principal_within_limits(loan_type, principal):
    """Pass when ``principal`` is positive and (if configured) inside loan-type bounds.

    The min/max checks are skipped silently when the LoanTypeConfiguration
    model does not define ``min_amount`` / ``max_amount`` columns.
    """
    if principal is None:
        return "Principal must be greater than zero."
    try:
        amount = Decimal(str(principal))
    except (InvalidOperation, TypeError, ValueError):
        return "Principal must be greater than zero."
    if amount <= 0:
        return "Principal must be greater than zero."

    if not loan_type:
        return None

    config = LoanTypeConfiguration.objects.filter(loan_type=loan_type).first()
    if config is None:
        return None

    if _has_field(LoanTypeConfiguration, "min_amount"):
        min_amount = getattr(config, "min_amount", None)
        if min_amount is not None and amount < Decimal(str(min_amount)):
            return f"Principal {amount} is below the minimum {Decimal(str(min_amount))}."

    if _has_field(LoanTypeConfiguration, "max_amount"):
        max_amount = getattr(config, "max_amount", None)
        if max_amount is not None and amount > Decimal(str(max_amount)):
            return f"Principal {amount} is above the maximum {Decimal(str(max_amount))}."

    return None


def _check_exposure_within_ceiling(user, principal, exposure_snapshot):
    """Pass when projected outstanding ≤ ceiling.

    Projected outstanding = ``current_loan_outstanding + principal``.
    Ceiling = ``share_capital + deposits`` when that sum is > 0,
    otherwise :data:`DEFAULT_EXPOSURE_CEILING` (Rs 50L).

    Returns ``None`` (and does NOT block approval) when the exposure service
    is not yet bolted into the codebase — the caller surfaces that via the
    informational ``"exposure_check_unavailable"`` marker on the reasons list.
    """
    if exposure_snapshot is None:
        return None
    if user is None or principal is None:
        return None

    try:
        amount = Decimal(str(principal))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    current = _decimal_from(exposure_snapshot.get("loan_outstanding", 0))
    share = _decimal_from(exposure_snapshot.get("share_capital", 0))
    deposits = _decimal_from(exposure_snapshot.get("deposits", 0))

    ceiling = share + deposits
    if ceiling <= 0:
        ceiling = DEFAULT_EXPOSURE_CEILING

    projected = current + amount
    if projected > ceiling:
        return f"Projected loan outstanding {projected} exceeds exposure ceiling {ceiling}."
    return None


def _check_active_financial_period():
    """Pass when an active :class:`FinancialPeriod` row exists."""
    if financial_period_service.active() is None:
        return "No active financial period \u2014 loans cannot be approved."
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_field(model_cls, name):
    """Return True when ``model_cls`` defines a concrete field called ``name``."""
    try:
        model_cls._meta.get_field(name)
    except Exception:
        return False
    return True


def _decimal_from(value):
    """Best-effort Decimal conversion. Returns Decimal('0') on failure."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _load_exposure_snapshot(user):
    """Call the exposure service if it is importable. Returns the dict or None.

    Failures inside the exposure service are swallowed — the eligibility
    service refuses to crash on a downstream bug; instead the caller records
    ``"exposure_check_unavailable"`` on the reasons list.
    """
    if not _EXPOSURE_AVAILABLE or _exposure_service is None or user is None:
        return None
    try:
        snapshot = _exposure_service.get_member_exposure(user)
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    return snapshot


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def check_loan_eligibility(*, user, loan_type, principal_amount):
    """Return ``{"approvable": bool, "reasons": [...], "exposure": dict|None}``.

    ``approvable`` is True iff every check passes. ``reasons`` is a list of
    human-readable strings — empty when ``approvable`` is True. ``exposure``
    is the :func:`accounts.services.exposure.get_member_exposure` dict when
    the exposure service is available, else ``None``.

    Every check runs regardless of earlier failures so the operator sees the
    FULL list of blockers. The service never raises and never writes data.
    """
    reasons = []

    reasons.append(_check_user_is_member(user))
    reasons.append(_check_eligible_for_loans(user))
    reasons.append(_check_kyc_verified(user))
    reasons.append(_check_no_overdue_emi(user))
    reasons.append(_check_loan_type_active(loan_type))
    reasons.append(_check_principal_within_limits(loan_type, principal_amount))
    reasons.append(_check_active_financial_period())

    exposure_snapshot = _load_exposure_snapshot(user)
    if _EXPOSURE_AVAILABLE:
        reasons.append(_check_exposure_within_ceiling(user, principal_amount, exposure_snapshot))
    else:
        # Exposure service not yet in the tree (Phase B7 lands separately).
        # The check is a graceful no-op: nothing is added to ``reasons`` so the
        # eligibility engine ships unblocked. The absence is signalled to the
        # caller via ``exposure=None`` and to operators via a module-level
        # ``logger.info("exposure_check_unavailable")`` at import time.
        pass

    reasons = [r for r in reasons if r]

    return {
        "approvable": not reasons,
        "reasons": reasons,
        "exposure": exposure_snapshot,
    }


def check_loan_eligibility_by_id(*, user_id, loan_type, principal_amount):
    """Lookup helper. Same return shape as :func:`check_loan_eligibility`.

    Raises:
        NotFoundError — ``user_id`` does not correspond to an existing user row.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Member not found.") from exc
    return check_loan_eligibility(
        user=user,
        loan_type=loan_type,
        principal_amount=principal_amount,
    )
