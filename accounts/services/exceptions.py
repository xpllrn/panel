"""
Service-layer exceptions.

Adapters (HTML views, API views, MCP tools) catch these and translate them
into surface-appropriate responses (HTTP 400/403/404/409 JSON, Django messages
+ redirect, MCP error envelope, etc.).

Business code SHOULD raise these. Business code SHOULD NOT raise raw
`ValueError` / `Exception` / `Http404` — those leak adapter assumptions into
the service layer.
"""


class ServiceError(Exception):
    """Base class for all service-layer exceptions.

    Attributes:
        message: Human-readable description (shown to user).
        code:    Short machine-readable slug, e.g. "kyc_not_verified". Optional.
    """

    default_message = "Service error."

    def __init__(self, message=None, *, code=None):
        self.message = message or self.default_message
        self.code = code or self.__class__.__name__
        super().__init__(self.message)


class ValidationError(ServiceError):
    """Input is invalid (missing field, bad type, negative amount, etc.).

    Adapters render this as HTTP 400 / form error.
    """

    default_message = "Invalid input."


class NotFoundError(ServiceError):
    """Referenced entity does not exist or is soft-deleted.

    Adapters render this as HTTP 404.
    """

    default_message = "Not found."


class PermissionDeniedError(ServiceError):
    """Caller is not allowed to perform this action (e.g. self-approving a loan).

    Adapters render this as HTTP 403.
    """

    default_message = "Permission denied."


class ConflictError(ServiceError):
    """Action would violate a business invariant (duplicate, locked period, etc.).

    Adapters render this as HTTP 409.
    """

    default_message = "Operation conflicts with current state."


class FinancialPeriodError(ConflictError):
    """The active / target FinancialPeriod is in the wrong state for this action.

    Examples: posting a transaction into a closed FY, distributing surplus
    when the P&L row is not yet locked, opening a new FY that overlaps an
    existing one.
    """

    default_message = "Financial period is in the wrong state for this action."
