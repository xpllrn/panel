"""
Create the first (and typically only) superuser for a fresh database.
Idempotent: does nothing if a superuser already exists.

Configure with env vars (e.g. in docker-compose):
  BOOTSTRAP_ADMIN_USERNAME (default: admin)
  BOOTSTRAP_ADMIN_EMAIL (default: admin@localhost)
  BOOTSTRAP_ADMIN_PASSWORD (required for non-interactive Docker; default: AdminDev123! for local dev only)
"""

import os

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Ensure one Django superuser exists (fresh DB). Skips if any superuser is already present."

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.NOTICE("Superuser already exists — bootstrap_admin skipped."))
            return

        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin").strip() or "admin"
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@localhost").strip() or "admin@localhost"
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "AdminDev123!")

        if User.objects.filter(username=username).exists():
            self.stderr.write(
                self.style.ERROR(f"User {username!r} exists but is not a superuser; fix in Django admin or shell.")
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="Admin",
            last_name="User",
        )
        user.role = "admin"
        user.save(update_fields=["role"])

        self.stdout.write(self.style.SUCCESS(f"Created superuser username={username!r} email={email!r}"))
        self.stdout.write(self.style.WARNING("Change BOOTSTRAP_ADMIN_PASSWORD / user password after first login in production."))
