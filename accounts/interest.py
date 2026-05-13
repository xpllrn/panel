"""
Backwards-compatibility shim for `accounts.interest`.

The pure-math interest helpers moved to `accounts.services.interest` in
Phase 0 of `ROADMAP.md`. Existing imports of
`from accounts.interest import InterestCalculatorService` keep working via
this re-export. New code should import from `accounts.services.interest`
directly.
"""

from accounts.services.interest import InterestCalculatorService

__all__ = ["InterestCalculatorService"]
