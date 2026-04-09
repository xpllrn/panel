"""
Email utilities for the cooperative society system.
Handles email notifications and verification.
"""

import base64
import json
import secrets

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

import requests


def generate_verification_token():
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


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
    from_name = getattr(settings, "SOCIETY_NAME", "Cooperative Society")

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
        return response.status_code in [200, 201, 202]
    except Exception:
        return False


def send_verification_email(user):
    """Send email verification link to user."""
    if not user.email:
        return False

    # Generate new token
    user.email_verification_token = generate_verification_token()
    user.email_verification_sent_at = timezone.now()
    user.save(update_fields=["email_verification_token", "email_verification_sent_at"])

    # Build verification URL
    verification_url = f"{settings.FRONTEND_URL}/verify-email/{user.email_verification_token}/"

    # Render email content
    context = {
        "user": user,
        "verification_url": verification_url,
        "society_name": getattr(settings, "SOCIETY_NAME", "Cooperative Society"),
    }

    subject = f"Email Verification - {context['society_name']}"
    message = render_to_string("emails/verify_email.txt", context)
    html_message = render_to_string("emails/verify_email.html", context)

    try:
        return _send_via_brevo_api(subject, message, html_message, user.email, user.display_name)
    except Exception as e:
        print(f"Failed to send verification email to {user.email}: {str(e)}")
        return False


def send_login_otp_email(user, otp_code, expires_minutes=15):
    """Send login OTP email."""
    if not user.email:
        return False

    context = {
        "user": user,
        "otp_code": otp_code,
        "expires_minutes": expires_minutes,
        "society_name": getattr(settings, "SOCIETY_NAME", "Cooperative Society"),
    }
    subject = f"Your Login OTP - {context['society_name']}"
    message = render_to_string("emails/login_otp.txt", context)
    html_message = render_to_string("emails/login_otp.html", context)

    try:
        return _send_via_brevo_api(subject, message, html_message, user.email, user.display_name)
    except Exception as e:
        print(f"Failed to send OTP email to {user.email}: {str(e)}")
        return False


def send_email_change_otp_email(user, new_email, otp_code, expires_minutes=10):
    """Send email change OTP to the new email address."""
    if not new_email:
        return False

    society_name = getattr(settings, "SOCIETY_NAME", "Cooperative Society")
    subject = f"Verify your new email - {society_name}"
    message = (
        f"Hello {user.display_name},\n\n"
        f"Use this OTP to verify your new email address:\n\n"
        f"{otp_code}\n\n"
        f"This OTP expires in {expires_minutes} minutes.\n"
        "If you did not request this change, ignore this email."
    )
    html_message = (
        f"<p>Hello {user.display_name},</p>"
        "<p>Use this OTP to verify your new email address:</p>"
        f"<h2 style='letter-spacing:3px'>{otp_code}</h2>"
        f"<p>This OTP expires in {expires_minutes} minutes.</p>"
        "<p>If you did not request this change, ignore this email.</p>"
    )

    try:
        return _send_via_brevo_api(subject, message, html_message, new_email, user.display_name)
    except Exception:
        return False


def send_notification_email(user, subject, template_name, context=None):
    """Send a notification email to user if email notifications are enabled."""
    if not user.email or not user.email_notifications or not user.email_verified:
        return False

    if context is None:
        context = {}

    context.update(
        {
            "user": user,
            "society_name": getattr(settings, "SOCIETY_NAME", "Cooperative Society"),
        }
    )

    try:
        message = render_to_string(f"emails/{template_name}.txt", context)
        html_message = render_to_string(f"emails/{template_name}.html", context)
        return _send_via_brevo_api(subject, message, html_message, user.email, user.display_name)
    except Exception as e:
        print(f"Failed to send notification email to {user.email}: {str(e)}")
        return False


def send_deposit_confirmation(user, receipt):
    """Send deposit confirmation email."""
    context = {
        "receipt": receipt,
        "account": receipt.account,
        "amount": receipt.amount,
    }
    return send_notification_email(
        user=user,
        subject=f"Deposit Confirmation - ₹{receipt.amount}",
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
        user=user, subject=f"Loan Approved - ₹{loan.principal_amount}", template_name="loan_approval", context=context
    )


def send_emi_reminder(user, loan, days_until_due=3):
    """Send EMI due reminder email."""
    context = {
        "loan": loan,
        "days_until_due": days_until_due,
        "emi_amount": loan.emi_amount,
    }
    return send_notification_email(
        user=user, subject=f"EMI Due Reminder - ₹{loan.emi_amount}", template_name="emi_reminder", context=context
    )


def send_password_change_alert(user):
    """Send password change alert email."""
    context = {
        "timestamp": timezone.now(),
    }
    return send_notification_email(
        user=user, subject="Password Changed Successfully", template_name="password_change_alert", context=context
    )


def send_login_alert(user, ip_address=None):
    """Send login from new device/location alert."""
    context = {
        "timestamp": timezone.now(),
        "ip_address": ip_address or "Unknown",
    }
    return send_notification_email(
        user=user, subject="New Login to Your Account", template_name="login_alert", context=context
    )


def send_interest_credit_notification(user, account, amount):
    """Send interest credit notification email."""
    context = {
        "account": account,
        "interest_amount": amount,
    }
    return send_notification_email(
        user=user, subject=f"Interest Credited - ₹{amount}", template_name="interest_credit", context=context
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
        subject=f"Payment Successful - ₹{amount}",
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
        subject=f"Payment Reminder - ₹{due_amount}",
        template_name="payment_reminder",
        context=context,
    )
