"""
Notification dispatcher for in-app, email, and push channels.
"""

import logging

from django.conf import settings
from django.utils import timezone

from accounts.email_utils import send_notification_email
from accounts.models import Notification, UserDevice

logger = logging.getLogger(__name__)


def _send_push_notification(user, title, message, metadata=None):
    """Send push notifications via Firebase Admin SDK to active user devices."""
    if metadata is None:
        metadata = {}

    if not getattr(user, "push_notifications_enabled", True):
        return {"success": False, "reason": "push_disabled"}

    if not getattr(settings, "FCM_ENABLED", False):
        return {"success": False, "reason": "fcm_disabled"}

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except Exception:
        logger.exception("Firebase Admin SDK is not installed.")
        return {"success": False, "reason": "sdk_missing"}

    try:
        if not firebase_admin._apps:
            cred_path = getattr(settings, "FCM_CREDENTIALS_PATH", "")
            if cred_path:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
    except Exception:
        logger.exception("Failed to initialize Firebase app.")
        return {"success": False, "reason": "init_failed"}

    devices = UserDevice.objects.filter(user=user, is_active=True)
    if not devices.exists():
        return {"success": False, "reason": "no_devices"}

    delivered = 0
    invalid_tokens = []

    for device in devices:
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=message),
            data={k: str(v) for k, v in metadata.items()},
            token=device.token,
        )
        try:
            messaging.send(msg)
            delivered += 1
        except Exception:
            invalid_tokens.append(device.token)

    if invalid_tokens:
        UserDevice.objects.filter(token__in=invalid_tokens).update(is_active=False, last_seen=timezone.now())

    return {"success": delivered > 0, "delivered": delivered}


def send_member_test_push(user):
    """Send a single demo push for settings/testing (no extra in-app row)."""
    if not getattr(user, "push_notifications_enabled", True):
        return {"success": False, "reason": "push_disabled"}
    return _send_push_notification(
        user,
        "Panels — demo",
        "This is a test notification from your settings.",
        {"type": "demo", "source": "member_test"},
    )


def dispatch_user_notification(user, title, message, notification_type="system", metadata=None, email_template=None):
    """Create in-app notification and dispatch email/push channels."""
    if metadata is None:
        metadata = {}

    record = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        metadata=metadata,
    )

    email_sent = False
    if email_template:
        email_context = metadata.copy()
        email_context.update({"title": title, "message": message})
        email_sent = send_notification_email(user, title, email_template, email_context)

    push_result = _send_push_notification(user, title, message, metadata)

    return {
        "notification_id": record.id,
        "email_sent": email_sent,
        "push_sent": push_result.get("success", False),
    }
