"""
Email utilities for the cooperative society system.
Handles email notifications and verification.
"""

import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone


def generate_verification_token():
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


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
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send verification email to {user.email}: {str(e)}")
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

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
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
