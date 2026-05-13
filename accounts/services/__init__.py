"""
Service layer for Panel ERP business logic.

WHY THIS PACKAGE EXISTS
-----------------------
Panel ERP is deployed as two independent processes that share one database:

- `panel`  (container, port 8000, urls=`config.urls_panel`) — staff HTML portal
- `api`    (container, port 8001, urls=`config.urls_api`)   — REST `/api/v1/`

Both processes need the SAME business rules (create a loan application, post a
transaction, run the interest engine, distribute surplus, etc.). If those rules
live inside `admin_portal/views.py` (HTML request/response code) and are copy-
pasted into `accounts/api_views.py` (JSON request/response code), the two
surfaces drift and bugs become endemic.

The fix is a thin service layer: every business action is implemented ONCE
inside `accounts/services/<topic>.py` as a pure Python function that accepts
plain values (or model instances) and returns a result dict / model instance.
The HTML views and API views become small adapters that:

    1. parse the incoming request,
    2. call a service function,
    3. format the response (HTML / JSON / SSE).

The upcoming MCP server (Phase C in `ROADMAP.md`) is the third adapter
and will also call these services directly — that is why this layer exists.

DESIGN RULES
------------
1. Services depend on Django ORM and `accounts.models` but MUST NOT import
   anything from `admin_portal`, `member_portal`, `rest_framework`, or any
   HTTP layer. If a service needs the acting user it accepts a `User` object,
   not a `request`.
2. Services wrap their own `transaction.atomic()` blocks where appropriate.
3. Services call `AuditLog.objects.create(...)` themselves so every adapter
   gets the same audit trail for free. They accept an optional `actor` user
   (the staff member acting) and an optional `ip_address` string.
4. Services raise `accounts.services.exceptions.ServiceError` (or subclasses)
   on business-rule violations. Adapters translate those into HTTP responses.
5. Services NEVER call `messages.success` / `messages.error` — adapter concern.
6. Services NEVER render templates — adapter concern.

ADDING A NEW SERVICE
--------------------
Create a new module here, e.g. `accounts/services/interest_engine.py`:

    from accounts.models import LoanAccount, InterestReceivable
    from accounts.services.exceptions import ServiceError

    def accrue_loans(period_start, period_end, financial_period, *, actor=None):
        \"\"\"Idempotent loan-side interest accrual.\"\"\"
        # ... business logic, no HTTP, no templates ...
        return {"accrued_count": n, "total_amount": total}

Then expose it from both adapters by `from accounts.services import interest_engine`
and call `interest_engine.accrue_loans(...)`.
"""

from accounts.services import exceptions  # noqa: F401  re-exported for convenience

__all__ = ["exceptions"]
