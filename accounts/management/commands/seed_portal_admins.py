from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User

# Initial staff for /login/ portal (is_staff required by admin_required).
# Passwords are hashed in the DB; running this command (re)applies the same passwords.
SEED_ADMINS = [
    {
        "username": "xpllrn",
        "email": "xpllrn@icloud.com",
        "first_name": "Tanmay",
        "last_name": "",
        "password": "9R@u2KqL",
    },
    {
        "username": "bijendrabs",
        "email": "bijendrabs.bs@gmail.com",
        "first_name": "Bijendra",
        "last_name": "Sharma",
        "password": "2029@Acbd",
    },
    {
        "username": "danbank",
        "email": "contact@delhiaamnagrik.org",
        "first_name": "Dans",
        "last_name": "",
        "password": "noqpen-2hysfA-patheh",
    },
]


class Command(BaseCommand):
    help = "Create or update fixed portal admin accounts (is_staff, role=admin) with configured passwords."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Each run sets passwords from seed data. If this repo is public, change these passwords after deploy."
            )
        )

        for row in SEED_ADMINS:
            username = row["username"]
            email = row["email"].lower()
            first_name = row["first_name"]
            last_name = row["last_name"]
            password = row["password"]

            other = User.objects.filter(email__iexact=email).exclude(username=username).first()
            if other:
                self.stderr.write(
                    self.style.ERROR(f"Skip {username}: email {email} already belongs to {other.username}")
                )
                continue

            user = User.objects.filter(username=username).first()

            with transaction.atomic():
                if user:
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.role = "admin"
                    user.is_staff = True
                    user.is_active = True
                    user.set_password(password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"{username} ({email}) — updated (password set)"))
                else:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    user.role = "admin"
                    user.is_staff = True
                    user.is_active = True
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"{username} ({email}) — created"))
