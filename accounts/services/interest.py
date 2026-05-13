"""
Pure-math interest and EMI helpers.

This module is the single source of truth for the formulas used across the
deposit interest engine, EMI generation, and reporting. It is intentionally
ORM-free so it is trivially unit-testable and safe to import from anywhere
(models, services, views, MCP tools, management commands).

For the higher-level "run the engine across all accounts / loans for a period
and post Transactions" workflow, see `accounts/services/interest_engine.py`
(Phase B in `ROADMAP.md`).
"""

from decimal import Decimal


class InterestCalculatorService:
    """Pure calculation helpers; no ORM."""

    @staticmethod
    def daily_simple_interest(balance, annual_rate_percent, days):
        """Simple interest: balance * (annual_rate / 100) * (days / 365).

        All inputs may be Decimal or int; output is Decimal quantised to paise.
        """
        if days <= 0 or balance <= 0 or annual_rate_percent <= 0:
            return Decimal("0.00")
        raw = balance * annual_rate_percent * Decimal(str(days)) / Decimal("36500")
        return raw.quantize(Decimal("0.01"))

    @staticmethod
    def calculate_emi(principal, annual_rate_percent, months):
        """Reducing-balance monthly EMI. Zero rate splits principal evenly."""
        if months <= 0:
            return Decimal("0.00")
        if principal <= 0:
            return Decimal("0.00")
        r = annual_rate_percent / Decimal("1200")
        if r == 0:
            return (principal / Decimal(str(months))).quantize(Decimal("0.01"))
        n = months
        factor = (1 + r) ** n
        emi = principal * r * factor / (factor - 1)
        return emi.quantize(Decimal("0.01"))

    @staticmethod
    def calculate_flat_emi(principal, annual_rate_percent, months):
        """Flat-interest monthly EMI.

        ``total_interest = principal * rate% * months / 12``
        ``total_payable  = principal + total_interest``
        ``emi            = total_payable / months``  (quantised to paise)

        Mirrors :meth:`calculate_emi` for the flat-vs-reducing branch used by
        :class:`accounts.models.LoanApplication` and
        :class:`accounts.models.LoanAccount`.
        """
        if months <= 0:
            return Decimal("0.00")
        if principal <= 0:
            return Decimal("0.00")
        principal = Decimal(str(principal))
        rate = Decimal(str(annual_rate_percent))
        n = Decimal(str(months))
        total_interest = principal * rate * n / Decimal("1200")
        total_payable = principal + total_interest
        return (total_payable / n).quantize(Decimal("0.01"))

    @staticmethod
    def maturity_amount_simple(principal, annual_rate_percent, months):
        """Principal + simple interest over the full term (months)."""
        if months <= 0 or principal <= 0:
            return principal.quantize(Decimal("0.01")) if principal else Decimal("0.00")
        interest = principal * annual_rate_percent * Decimal(str(months)) / Decimal("1200")
        return (principal + interest).quantize(Decimal("0.01"))
