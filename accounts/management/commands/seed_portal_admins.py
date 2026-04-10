import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User

# Initial staff for /login/ portal (is_staff required by admin_required).
SEED_ADMINS = [
    {"username": "xpllrn", "email": "xpllrn@icloud.com", "first_name": "Tanmay", "last_name": ""},
    {"username": "bijendrabs", "email": "bijendrabs.bs@gmail.com", "first_name": "Bijendra", "last_name": "Sharma"},
    {"username": "danbank", "email": "contact@delhiaamnagrik.org", "first_name": "Dans", "last_name": ""},
]


class Command(BaseCommand):
    help = "Create or update fixed portal admin accounts (is_staff, role=admin). Prints one-time passwords for new/reset users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Regenerate password for every listed user (even if they already exist).",
        )

    def handle(self, *args, **options):
        reset_all = options["reset_passwords"]
        self.stdout.write(self.style.WARNING("Save these passwords; they are not stored in the database in plain text."))

        for row in SEED_ADMINS:
            username = row["username"]
            email = row["email"].lower()
            first_name = row["first_name"]
            last_name = row["last_name"]

            other = User.objects.filter(email__iexact=email).exclude(username=username).first()
            if other:
                self.stderr.write(
                    self.style.ERROR(f"Skip {username}: email {email} already belongs to {other.username}")
                )
                continue

            user = User.objects.filter(username=username).first()
            new_password = secrets.token_urlsafe(14)

            with transaction.atomic():
                if user:
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.role = "admin"
                    user.is_staff = True
                    user.is_active = True
                    if reset_all:
                        user.set_password(new_password)
                    user.save()
                    if reset_all:
                        self.stdout.write(
                            self.style.SUCCESS(f"{username} ({email}) — password reset")
                        )
                        self.stdout.write(f"  Password: {new_password}")
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"{username} ({email}) — already existed; updated profile/flags, password unchanged. "
                                "Use --reset-passwords to set a new password."
                            )
                        )
                else:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=new_password,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    user.role = "admin"
                    user.is_staff = True
                    user.is_active = True
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"{username} ({email}) — created"))
                    self.stdout.write(f"  Password: {new_password}")
