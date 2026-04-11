from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = "Create or update a Play review member account for app access testing."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="playreview", help="Review account username.")
        parser.add_argument("--password", required=True, help="Review account password.")
        parser.add_argument("--email", default="", help="Optional email (not required for bypass mode).")
        parser.add_argument("--member-id", default="PLAY-REVIEW-001", help="Optional member ID label.")

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        password = options["password"]
        email = (options["email"] or "").strip().lower()
        member_id = (options["member_id"] or "").strip()

        if not username or not password:
            self.stderr.write(self.style.ERROR("username and password are required."))
            return

        defaults = {
            "email": email,
            "first_name": "Play",
            "last_name": "Reviewer",
            "role": "member",
            "status": "active",
            "is_active": True,
            "member_id": member_id or None,
            "date_of_joining": timezone.now().date(),
        }

        user, created = User.objects.get_or_create(username=username, defaults=defaults)
        if not created:
            for field, value in defaults.items():
                setattr(user, field, value)

        user.set_password(password)
        user.save()

        state = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Play review user {state}: username={user.username}"))
