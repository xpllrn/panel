import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User


class Command(BaseCommand):
    help = (
        "Create or update a staff user for the custom admin portal (/login/, /home/). "
        "The portal checks is_staff; role is set to admin for consistency."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default="tanmay", help="Login name at /login/")
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", default="", dest="first_name")
        parser.add_argument("--last-name", default="", dest="last_name")
        parser.add_argument(
            "--password",
            default="",
            help="If omitted, a random password is generated and printed once.",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Also grant Django /admin/ access (is_superuser).",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip().lower()
        first_name = options["first_name"].strip()
        last_name = options["last_name"].strip()
        password = options["password"]
        want_super = options["superuser"]

        if not username or not email:
            self.stderr.write(self.style.ERROR("username and email are required."))
            return

        if not password:
            password = secrets.token_urlsafe(14)

        other = User.objects.filter(email__iexact=email).exclude(username=username).first()
        if other:
            self.stderr.write(
                self.style.ERROR(
                    f"Email {email} is already used by username {other.username}. "
                    "Resolve the conflict or pick another email."
                )
            )
            return

        with transaction.atomic():
            user = User.objects.filter(username=username).first()
            if user:
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.set_password(password)
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
            user.is_superuser = want_super
            user.is_active = True
            user.save()

        self.stdout.write(
            self.style.SUCCESS(f"Portal admin ready: username={username}, email={email}, name={user.display_name}")
        )
        self.stdout.write("Log in at /login/ with this username and password.")
        if options["password"]:
            self.stdout.write(self.style.WARNING("Password was taken from --password (visible in shell history; change after login)."))
        else:
            self.stdout.write(self.style.WARNING("Generated password (save it; not stored in logs hereafter):"))
            self.stdout.write(self.style.SUCCESS(password))
