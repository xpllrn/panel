"""
Email utilities for the cooperative society system.
Handles email notifications and verification.
"""

import base64
import logging
import json
import secrets

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

import requests

logger = logging.getLogger(__name__)

_DEFAULT_LEGAL = "Delhi Aam Nagrik Co-operative Credit Society Ltd."


def _society_legal_name():
    """Name shown in email bodies, subjects, and From display (full legal name)."""
    return getattr(settings, "SOCIETY_LEGAL_NAME", getattr(settings, "SOCIETY_NAME", _DEFAULT_LEGAL))


def generate_verification_token():
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


def get_email_branding_context():
    """Shared context for HTML/text templates (matches public site: forest greens, DM Sans in HTML)."""
    origin = getattr(settings, "MARKETING_SITE_ORIGIN", "https://xpllrn.github.io/panel").rstrip("/")
    phone = getattr(settings, "SUPPORT_CONTACT_PHONE", "+91-9305050596")
    phone_tel = "".join(c for c in phone if c.isdigit() or c == "+") or phone
    return {
        "society_name": _society_legal_name(),
        "society_tagline": getattr(settings, "SOCIETY_TAGLINE", "Member services · Delhi, India"),
        "site_url": origin,
        "logo_mark_url": f"{origin}/assets/logo-mark.png",
        "logo_social_url": f"{origin}/assets/logo-social.png",
        "support_email": getattr(settings, "SUPPORT_CONTACT_EMAIL", "contact@delhiaamnagrik.org"),
        "support_phone": phone,
        "support_phone_tel": phone_tel,
    }


def merge_email_context(extra=None):
    """Merge caller context with branding keys."""
    ctx = get_email_branding_context()
    if extra:
        ctx.update(extra)
    return ctx


def _get_brevo_api_key():
    """Resolve Brevo API key from direct env or MCP_BREVO encoded payload."""
    if getattr(settings, "BREVO_API_KEY", ""):
        return settings.BREVO_API_KEY

    encoded = getattr(settings, "MCP_BREVO", "")
    if not encoded:
        return ""

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        data = json.loads(decoded)
        return data.get("api_key", "")
    except Exception:
        return ""


def _send_via_brevo_api(subject, text_message, html_message, recipient_email, recipient_name="User"):
    """Send transactional email via Brevo HTTP API."""
    api_key = _get_brevo_api_key()
    if not api_key:
        return False

    from_email = settings.DEFAULT_FROM_EMAIL
    from_name = _society_legal_name()

    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": recipient_email, "name": recipient_name or recipient_email}],
        "subject": subject,
        "htmlContent": html_message,
        "textContent": text_message,
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }

    try:
        response = requests.post("https://api.brevo.com/v3/smtp/email", headers=headers, json=payload, timeout=20)
        if response.status_code in [200, 201, 202]:
            try:
                mid = response.json().get("messageId")
                logger.info("Brevo accepted email messageId=%s to=%s subject=%s", mid, recipient_email, subject)
            except Exception:
                logger.info("Brevo accepted email to=%s subject=%s", recipient_email, subject)
            return True
        logger.error(
            "Brevo SMTP API rejected send status=%s to=%s body=%s",
            response.status_code,
            recipient_email,
            (response.text or "")[:800],
        )
        return False
    except Exception as exc:
        logger.exception("Brevo SMTP API request failed for %s: %s", recipient_email, exc)
        return False


def _render_and_send(subject, template_base, recipient_email, recipient_name, context):
    """Render emails/{template_base}.txt and .html with merged branding context."""
    ctx = merge_email_context(context)
    message = render_to_string(f"emails/{template_base}.txt", ctx)
    html_message = render_to_string(f"emails/{template_base}.html", ctx)
    try:
        return _send_via_brevo_api(subject, message, html_message, recipient_email, recipient_name)
    except Exception as e:
        print(f"Failed to send email to {recipient_email}: {str(e)}")
        return False


def send_verification_email(user):
    """Send email verification link to user."""
    if not user.email:
        return False

    user.email_verification_token = generate_verification_token()
    user.email_verification_sent_at = timezone.now()
    user.save(update_fields=["email_verification_token", "email_verification_sent_at"])

    verification_url = f"{settings.FRONTEND_URL}/verify-email/{user.email_verification_token}/"
    society = _society_legal_name()
    subject = f"Verify your email — {society}"
    ctx = {
        "user": user,
        "verification_url": verification_url,
    }
    return _render_and_send(subject, "verify_email", user.email, user.display_name, ctx)


def send_login_otp_email(user, otp_code, expires_minutes=15):
    """Send login OTP email."""
    if not user.email:
        return False

    if getattr(settings, "LOGIN_OTP_LOG_PLAINTEXT", False):
        logger.warning(
            "LOGIN_OTP_LOG_PLAINTEXT: username=%s email=%s otp=%s (disable in production)",
            user.username,
            user.email,
            otp_code,
        )

    society = _society_legal_name()
    subject = f"Your sign-in code — {society}"
    ctx = {
        "user": user,
        "otp_code": otp_code,
        "expires_minutes": expires_minutes,
    }
    return _render_and_send(subject, "login_otp", user.email, user.display_name, ctx)


def send_email_change_otp_email(user, new_email, otp_code, expires_minutes=10):
    """Send email change OTP to the new email address."""
    if not new_email:
        return False

    society = _society_legal_name()
    subject = f"Confirm your new email — {society}"
    ctx = {
        "user": user,
        "otp_code": otp_code,
        "expires_minutes": expires_minutes,
    }
    return _render_and_send(subject, "email_change_otp", new_email, user.display_name, ctx)


def send_notification_email(user, subject, template_name, context=None):
    """Send a notification email to user if email notifications are enabled."""
    if not user.email or not user.email_notifications or not user.email_verified:
        return False

    if context is None:
        context = {}

    context["user"] = user
    try:
        return _render_and_send(subject, template_name, user.email, user.display_name, context)
    except Exception as e:
        print(f"Failed to send notification email to {user.email}: {str(e)}")
        return False


def send_password_change_alert(user):
    """Send password change alert (transactional; does not require email_verified)."""
    if not user.email:
        return False

    society = _society_legal_name()
    subject = f"Password updated — {society}"
    ctx = {
        "user": user,
        "timestamp": timezone.now(),
    }
    return _render_and_send(subject, "password_change_alert", user.email, user.display_name, ctx)


def send_login_alert(user, ip_address=None):
    """Send login from new device/location alert (transactional)."""
    if not user.email:
        return False

    society = _society_legal_name()
    subject = f"New sign-in — {society}"
    ctx = {
        "user": user,
        "timestamp": timezone.now(),
        "ip_address": ip_address or "Unknown",
    }
    return _render_and_send(subject, "login_alert", user.email, user.display_name, ctx)


def send_email_moved_security_notice(old_email, display_name, new_email):
    """Notify the previous inbox that the account email was changed (security)."""
    if not old_email or not str(old_email).strip():
        return False

    society = _society_legal_name()
    subject = f"Your sign-in email was changed — {society}"
    ctx = {
        "display_name": display_name or "Member",
        "new_email": new_email,
    }
    return _render_and_send(subject, "email_moved_notice", old_email.strip(), display_name or "Member", ctx)


def send_email_change_confirmed(user):
    """Short confirmation to the new address after a successful change."""
    if not user.email:
        return False

    society = _society_legal_name()
    subject = f"Email confirmed — {society}"
    ctx = {"user": user}
    return _render_and_send(subject, "email_change_confirmed", user.email, user.display_name, ctx)


def send_phone_changed_alert(user, old_mobile, new_mobile):
    """Notify member that profile phone was updated (transactional)."""
    if not user.email:
        return False

    society = _society_legal_name()
    subject = f"Phone number updated — {society}"
    ctx = {
        "user": user,
        "old_mobile": old_mobile or "",
        "new_mobile": new_mobile or "",
    }
    return _render_and_send(subject, "phone_changed_alert", user.email, user.display_name, ctx)


def send_deposit_confirmation(user, receipt):
    """Send deposit confirmation email."""
    context = {
        "receipt": receipt,
        "account": receipt.account,
        "amount": receipt.amount,
    }
    return send_notification_email(
        user=user,
        subject=f"Deposit confirmation — ₹{receipt.amount}",
        template_name="deposit_confirmation",
        context=context,
    )


def send_loan_approval_notification(user, loan):
    """Send loan approval notification email."""
    context = {
        "loan": loan,
        "amount": loan.principal_amount,
    }
    return send_notification_email(
        user=user, subject=f"Loan approved — ₹{loan.principal_amount}", template_name="loan_approval", context=context
    )


def send_emi_reminder(user, loan, days_until_due=3):
    """Send EMI due reminder email."""
    context = {
        "loan": loan,
        "days_until_due": days_until_due,
        "emi_amount": loan.emi_amount,
    }
    return send_notification_email(
        user=user, subject=f"EMI reminder — ₹{loan.emi_amount}", template_name="emi_reminder", context=context
    )


def send_interest_credit_notification(user, account, amount):
    """Send interest credit notification email."""
    context = {
        "account": account,
        "interest_amount": amount,
    }
    return send_notification_email(
        user=user, subject=f"Interest credited — ₹{amount}", template_name="interest_credit", context=context
    )


def send_payment_success_email(user, amount, reference, payment_type):
    """Send successful payment email."""
    context = {
        "amount": amount,
        "reference": reference,
        "payment_type": payment_type,
    }
    return send_notification_email(
        user=user,
        subject=f"Payment received — ₹{amount}",
        template_name="payment_success",
        context=context,
    )


def send_payment_reminder_email(user, due_amount, due_date, payment_type):
    """Send payment reminder email."""
    context = {
        "due_amount": due_amount,
        "due_date": due_date,
        "payment_type": payment_type,
    }
    return send_notification_email(
        user=user,
        subject=f"Payment reminder — ₹{due_amount}",
        template_name="payment_reminder",
        context=context,
    )
