import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AuditLog, MemberAccount, Receipt, User


class Command(BaseCommand):
    help = """
    Create demo users with random account balances for testing.

    This command creates multiple member accounts with realistic Indian names
    and adds random balances to their accounts.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of demo users to create (default: 10)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        count = options["count"]

        # Indian names for demo users
        first_names = [
            "Ashok",
            "Veer",
            "Vijay",
            "Bijendra",
            "Rajesh",
            "Suresh",
            "Ramesh",
            "Mahesh",
            "Dinesh",
            "Ganesh",
            "Prakash",
            "Anil",
            "Sunil",
            "Mukesh",
            "Rakesh",
            "Naresh",
            "Yogesh",
            "Ritesh",
            "Umesh",
            "Kamlesh",
            "Pradeep",
            "Sandeep",
            "Kuldeep",
            "Mandeep",
            "Amarjeet",
            "Ranjeet",
            "Harjeet",
            "Gurpreet",
            "Amit",
            "Sumit",
            "Rohit",
            "Mohit",
            "Lalit",
            "Ajit",
            "Sanjay",
            "Vijay",
            "Jai",
            "Raj",
            "Dev",
            "Arjun",
        ]

        last_names = [
            "Kumar",
            "Singh",
            "Sharma",
            "Verma",
            "Gupta",
            "Yadav",
            "Patel",
            "Reddy",
            "Nair",
            "Iyer",
            "Joshi",
            "Desai",
            "Mehta",
            "Shah",
            "Agarwal",
            "Bansal",
            "Malhotra",
            "Kapoor",
            "Chopra",
            "Bhatia",
        ]

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
        receipts_created = 0

        self.stdout.write(f"Creating {count} demo users...")

        for _ in range(count):
            # Generate random name
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            full_name = f"{first_name} {last_name}"

            # Generate username (lowercase, no spaces, add number if needed)
            base_username = f"{first_name.lower()}{last_name.lower()}"
            username = base_username

            # Check if username exists, add number if needed
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            # Generate random DOB (age between 25 and 65)
            days_ago = random.randint(25 * 365, 65 * 365)
            dob = date.today() - timedelta(days=days_ago)

            # Generate password: DDMM + first 4 chars of name
            name_chars = full_name.replace(" ", "").upper()[:4]
            password = f"{dob.day:02d}{dob.month:02d}{name_chars}"

            # Generate email
            email = f"{username}@example.com"

            # Generate mobile
            mobile = f"9{random.randint(100000000, 999999999)}"

            if dry_run:
                self.stdout.write(f"\n[DRY RUN] Would create user: {username} ({full_name})")
                self.stdout.write(f"  Email: {email}")
                self.stdout.write(f"  Mobile: {mobile}")
                self.stdout.write(f"  DOB: {dob}")
                self.stdout.write(f"  Password: {password}")
                self.stdout.write("  Would create 7 accounts with random balances")
                self.stdout.write("  Would create 3-8 transactions per account")
                users_created += 1
                accounts_created += 7
                receipts_created += 7 * random.randint(3, 8)
            else:
                try:
                    with transaction.atomic():
                        # Auto-generate member_id: MBR-YEAR-SEQUENCE
                        year = date.today().year
                        last_member = (
                            User.objects.select_for_update()
                            .filter(member_id__startswith=f"MBR-{year}-")
                            .order_by("-member_id")
                            .first()
                        )
                        if last_member:
                            try:
                                last_seq = int(last_member.member_id.split("-")[-1])
                                next_seq = last_seq + 1
                            except (ValueError, IndexError):
                                next_seq = 1
                        else:
                            next_seq = 1

                        member_id = f"MBR-{year}-{next_seq:05d}"

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
                        user.member_id = member_id
                        user.save()

                        self.stdout.write(f"\n✓ Created user: {username} ({full_name})")
                        self.stdout.write(f"  Member ID: {member_id}")
                        self.stdout.write(f"  Email: {email}")
                        self.stdout.write(f"  Mobile: {mobile}")
                        self.stdout.write(f"  Password: {password}")

                        # Create all 7 accounts with random balances and transactions
                        for account_type, account_name, default_rate in account_types:
                            # Generate account number
                            account_number = f"{account_type.upper()}-{user.id:05d}-001"

                            # Create account with initial balance of 0
                            account = MemberAccount.objects.create(
                                user=user,
                                account_number=account_number,
                                account_type=account_type,
                                status="active",
                                balance=0.00,
                                interest_rate=default_rate,
                                opening_date=date.today() - timedelta(days=random.randint(30, 365)),
                            )

                            # Create random transactions for each account (3-8 transactions)
                            num_transactions = random.randint(3, 8)
                            running_balance = Decimal("0.00")

                            for _ in range(num_transactions):
                                # Generate transaction date (within last 365 days)
                                days_ago = random.randint(1, 365)
                                txn_date = date.today() - timedelta(days=days_ago)

                                # Determine transaction type (70% credit, 30% debit)
                                if random.random() < 0.7 or running_balance == 0:
                                    # Credit transaction
                                    txn_type = random.choice(["credit", "interest", "dividend"])
                                    amount = Decimal(str(random.randint(500, 50000)))
                                    running_balance += amount
                                else:
                                    # Debit transaction (only if balance exists)
                                    txn_type = "debit"
                                    max_debit = min(running_balance, Decimal("50000"))
                                    amount = Decimal(str(random.randint(100, int(max_debit))))
                                    running_balance -= amount

                                # Generate receipt number
                                receipt_year = txn_date.year
                                last_receipt = (
                                    Receipt.objects.filter(receipt_number__startswith=f"RCP-{receipt_year}-")
                                    .order_by("-receipt_number")
                                    .first()
                                )
                                if last_receipt:
                                    try:
                                        last_seq = int(last_receipt.receipt_number.split("-")[-1])
                                        next_seq = last_seq + 1
                                    except (ValueError, IndexError):
                                        next_seq = 1
                                else:
                                    next_seq = 1

                                receipt_number = f"RCP-{receipt_year}-{next_seq:05d}"

                                # Payment mode
                                payment_mode = random.choice(["cash", "cheque", "online", "upi"])

                                # Create receipt
                                receipt = Receipt.objects.create(
                                    receipt_number=receipt_number,
                                    user=user,
                                    member_account=account,
                                    transaction_type=txn_type,
                                    amount=amount,
                                    description=f"Demo {txn_type} transaction",
                                    payment_mode=payment_mode,
                                    balance_after=running_balance,
                                    created_by=None,  # System generated
                                )
                                # Backdate the receipt
                                Receipt.objects.filter(id=receipt.id).update(created_at=txn_date)

                                receipts_created += 1

                            # Update account balance to match final running balance
                            account.balance = running_balance
                            account.save()

                            self.stdout.write(
                                f"  ✓ {account_name}: {account_number} - ₹{running_balance:,.2f} ({num_transactions} txns)"
                            )

                            # Create audit log
                            AuditLog.objects.create(
                                user=None,
                                action="create",
                                entity_type="account",
                                entity_id=account.id,
                                description=f"Demo: Created {account_name} account {account_number} with ₹{running_balance} and {num_transactions} transactions for {username}",
                                ip_address="127.0.0.1",
                            )

                            accounts_created += 1

                        # Create audit log for user
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
                    self.stdout.write(self.style.ERROR(f"  ✗ Error creating {username}: {str(e)}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would create {users_created} users, {accounts_created} accounts, and {receipts_created} transactions"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully created {users_created} users, {accounts_created} accounts, and {receipts_created} transactions!"
                )
            )
            self.stdout.write(
                "\nYou can now login with any of these users using their username and password shown above."
            )
