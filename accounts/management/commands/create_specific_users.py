import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AuditLog, MemberAccount, User


class Command(BaseCommand):
    help = "Create specific named users for demo purposes"

    def handle(self, *args, **options):
        # Specific users to create
        users_data = [
            {"first_name": "Ashok", "last_name": "Kumar"},
            {"first_name": "Veer", "last_name": "Singh"},
            {"first_name": "Vijay", "last_name": "Sharma"},
            {"first_name": "Bijendra", "last_name": "Patel"},
        ]

        account_balance_ranges = {
            "fd": (10000, 500000),
            "cd": (5000, 300000),
            "rd": (1000, 100000),
            "od": (0, 50000),
            "share": (5000, 200000),
            "sukanya": (10000, 150000),
            "suputra": (5000, 100000),
        }

        account_types = [
            ("fd", "Fixed Deposit", 7.5),
            ("cd", "Certificate of Deposit", 7.0),
            ("rd", "Recurring Deposit", 7.0),
            ("od", "Overdraft", 12.0),
            ("share", "Share Account", 0.0),
            ("sukanya", "Sukanya Yojana", 8.0),
            ("suputra", "Suputra Yojana", 8.5),
        ]

        users_created = 0
        accounts_created = 0

        for user_data in users_data:
            first_name = user_data["first_name"]
            last_name = user_data["last_name"]
            full_name = f"{first_name} {last_name}"

            # Generate username
            base_username = f"{first_name.lower()}"
            username = base_username

            # Check if username exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f"User {username} already exists, skipping..."))
                continue

            # Generate random DOB (age between 30 and 60)
            days_ago = random.randint(30 * 365, 60 * 365)
            dob = date.today() - timedelta(days=days_ago)

            # Generate password
            name_chars = full_name.replace(" ", "").upper()[:4]
            password = f"{dob.day:02d}{dob.month:02d}{name_chars}"

            # Generate email
            email = f"{username}@example.com"

            # Generate mobile
            mobile = f"9{random.randint(100000000, 999999999)}"

            try:
                with transaction.atomic():
                    # Create user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        role="member",
                    )
                    user.first_name = first_name
                    user.last_name = last_name
                    user.date_of_birth = dob
                    user.mobile_primary = mobile
                    user.status = "active"
                    user.save()

                    self.stdout.write(f"\n✓ Created user: {username} ({full_name})")
                    self.stdout.write(f"  Email: {email}")
                    self.stdout.write(f"  Mobile: {mobile}")
                    self.stdout.write(f"  Password: {password}")

                    # Create all 7 accounts with random balances
                    for account_type, account_name, default_rate in account_types:
                        account_number = f"{account_type.upper()}-{user.id:05d}-001"
                        min_balance, max_balance = account_balance_ranges[account_type]
                        balance = Decimal(str(random.randint(min_balance, max_balance)))

                        account = MemberAccount.objects.create(
                            user=user,
                            account_number=account_number,
                            account_type=account_type,
                            status="active",
                            balance=balance,
                            interest_rate=default_rate,
                            opening_date=date.today() - timedelta(days=random.randint(30, 365)),
                        )

                        self.stdout.write(f"  ✓ {account_name}: {account_number} - ₹{balance:,.2f}")

                        AuditLog.objects.create(
                            user=None,
                            action="create",
                            entity_type="account",
                            entity_id=account.id,
                            description=f"Demo: Created {account_name} account {account_number} with ₹{balance} for {username}",
                            ip_address="127.0.0.1",
                        )

                        accounts_created += 1

                    AuditLog.objects.create(
                        user=None,
                        action="create",
                        entity_type="member",
                        entity_id=user.id,
                        description=f"Demo: Created member {username} ({full_name}) with 7 accounts",
                        ip_address="127.0.0.1",
                    )

                    users_created += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Error creating {username}: {str(e)}"))

        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Successfully created {users_created} users and {accounts_created} accounts!")
        )
