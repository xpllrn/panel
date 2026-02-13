"""
Utility functions for the accounts app.
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


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
