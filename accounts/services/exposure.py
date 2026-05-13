"""Member-exposure service — what every member has at stake with the society.

Pure read service. No state mutation. No audit logging (read-only).

Public surface
--------------

    get_member_exposure(user)        — snapshot dict, given a User instance.
    get_member_exposure_by_id(user_id) — id-based wrapper, raises NotFoundError
                                         if the user does not exist.

The snapshot dict has these Decimal keys (every value quantised to 0.01):

    share_capital         Sum of `ShareCapital.total_value` for the member.
    deposits              Sum of `MemberAccount.balance` over the member's
                          active CD / FD / RD / Sukanya / Suputra accounts.
                          NOTE: Share-type `MemberAccount` rows are NOT included
                          here — share capital lives in its own `ShareCapital`
                          table and is summarised in `share_capital`.
    od_drawn              Amount the member has drawn against any active OD
                          account, defined as `Sum(max(0, -balance))`. OD
                          accounts store the drawn amount as a negative balance.
    loan_outstanding      Sum of `LoanAccount.outstanding_balance` over the
                          member's active loans.
    guarantee_contingent  Sum of `LoanAccount.outstanding_balance` over every
                          active loan the member guarantees (linked via
                          `Guarantor.user`). Represents the contingent
                          liability the society could recall from this member
                          if the underlying borrower defaults.
    fees_outstanding      Sum of `FeeCharge.amount` for charges that are still
                          owed by the member (status `pending` or `charged`).
                          The current model only defines `charged` / `waived`
                          / `refunded`; `pending` is included defensively for
                          forward compatibility (see ROADMAP Phase B4).
    net_exposure          deposits + share_capital
                          − od_drawn − loan_outstanding
                          − guarantee_contingent − fees_outstanding.
                          Positive means the society owes the member;
                          negative means the member owes the society.

This service consciously avoids any HTTP / template coupling so it can be
called by:

    * `admin_portal.views`            — the member-detail "Total exposure" panel.
    * `accounts.services.loans`       — Phase B8 loan-eligibility check.
    * the MCP server                  — Phase C resource
                                        `panelerp://members/{id}/exposure`.
    * `accounts.api_views`            — future `GET /api/v1/admin/members/{id}/exposure`.
"""

from decimal import Decimal

from django.db.models import Sum

from accounts.models import (
    FeeCharge,
    LoanAccount,
    MemberAccount,
    ShareCapital,
    User,
)
from accounts.services.exceptions import NotFoundError

ZERO = Decimal("0.00")

DEPOSIT_ACCOUNT_TYPES = ("cd", "fd", "rd", "sukanya", "suputra")

# `FeeCharge.STATUS_CHOICES` is currently `charged / waived / refunded` only
# (see `accounts/models.py`). We still match `pending` defensively in case a
# future migration adds a charged-but-unposted state (ROADMAP Phase B4).
FEE_OUTSTANDING_STATUSES = ("pending", "charged")


def _q(value):
    """Return `value` as a Decimal quantised to two decimal places.

    `None` (the typical empty-aggregate result) collapses to `Decimal('0.00')`.
    """
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def get_member_exposure(user):
    """Return a dict snapshot of every position `user` has against the society.

    `user` must be a `User` model instance. The function is intentionally
    forgiving — a user with no accounts / loans / fees gets back a fully
    zero-filled dict, never an exception. To look up by primary key and get
    a `NotFoundError` for unknown ids, call `get_member_exposure_by_id`.

    All values in the returned dict are 2-dp `Decimal` instances:

        {
            "share_capital":        Decimal(...),
            "deposits":             Decimal(...),
            "od_drawn":             Decimal(...),
            "loan_outstanding":     Decimal(...),
            "guarantee_contingent": Decimal(...),
            "fees_outstanding":     Decimal(...),
            "net_exposure":         Decimal(...),
        }
    """
    share_capital = ShareCapital.objects.filter(user=user).aggregate(
        total=Sum("total_value", default=ZERO),
    )["total"]

    deposits = MemberAccount.objects.filter(
        user=user,
        status="active",
        account_type__in=DEPOSIT_ACCOUNT_TYPES,
    ).aggregate(total=Sum("balance", default=ZERO))["total"]

    # OD balance is stored as a (typically negative) number: a balance of -3000
    # means the member has drawn 3000 against the facility. Filter to drawn
    # accounts only (balance < 0), sum, then negate — the database does the
    # heavy lifting and Python only flips the sign of the final scalar.
    od_negative_total = MemberAccount.objects.filter(
        user=user,
        status="active",
        account_type="od",
        balance__lt=0,
    ).aggregate(total=Sum("balance", default=ZERO))["total"]
    od_drawn = -od_negative_total if od_negative_total else ZERO

    loan_outstanding = LoanAccount.objects.filter(
        user=user,
        status="active",
    ).aggregate(total=Sum("outstanding_balance", default=ZERO))["total"]

    # `Guarantor.user` is the FK back to the user who is guaranteeing the
    # loan (related_name="guarantees"). We sum the outstanding of every
    # *active* loan they back. A guarantor row whose `user` is NULL (an
    # external, non-member guarantor) is naturally excluded by the join.
    guarantee_contingent = LoanAccount.objects.filter(
        guarantors__user=user,
        status="active",
    ).aggregate(total=Sum("outstanding_balance", default=ZERO))["total"]

    fees_outstanding = FeeCharge.objects.filter(
        user=user,
        status__in=FEE_OUTSTANDING_STATUSES,
    ).aggregate(total=Sum("amount", default=ZERO))["total"]

    share_capital = _q(share_capital)
    deposits = _q(deposits)
    od_drawn = _q(od_drawn)
    loan_outstanding = _q(loan_outstanding)
    guarantee_contingent = _q(guarantee_contingent)
    fees_outstanding = _q(fees_outstanding)

    net_exposure = _q(deposits + share_capital - od_drawn - loan_outstanding - guarantee_contingent - fees_outstanding)

    return {
        "share_capital": share_capital,
        "deposits": deposits,
        "od_drawn": od_drawn,
        "loan_outstanding": loan_outstanding,
        "guarantee_contingent": guarantee_contingent,
        "fees_outstanding": fees_outstanding,
        "net_exposure": net_exposure,
    }


def get_member_exposure_by_id(user_id):
    """Look up the member by primary key and return their exposure snapshot.

    Raises:
        NotFoundError — no `User` with that id exists.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Member not found.") from exc
    return get_member_exposure(user)
