from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AuditLog, MemberAccount, User


class Command(BaseCommand):
    help = """
    Create missing accounts for existing members who don't have all 7 account types.

    Security Note: This command runs with system privileges and creates accounts
    without user authentication. It should only be run by authorized administrators
    with direct server access. All operations are logged to the audit trail.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        account_types = [
            ("fd", "Fixed Deposit", 7.5),
            ("cd", "Certificate of Deposit", 7.0),
            ("rd", "Recurring Deposit", 7.0),
            ("od", "Overdraft", 12.0),
            ("share", "Share Account", 0.0),
            ("sukanya", "Sukanya Yojana", 8.0),
            ("suputra", "Suputra Yojana", 8.5),
        ]

        # Get all members (not staff/admin)
        members = User.objects.filter(role="member")
        total_members = members.count()
        members_updated = 0
        accounts_created = 0

        self.stdout.write(f"Found {total_members} members")

        for user in members:
            # Check which account types are missing
            existing_types = set(
                MemberAccount.objects.filter(user=user, is_deleted=False).values_list("account_type", flat=True)
            )

            missing_types = []
            for account_type, account_name, default_rate in account_types:
                if account_type not in existing_types:
                    missing_types.append((account_type, account_name, default_rate))

            if missing_types:
                members_updated += 1
                self.stdout.write(f"\nUser: {user.username} (ID: {user.id})")
                self.stdout.write(f"  Missing {len(missing_types)} account(s)")

                if dry_run:
                    for account_type, account_name, _ in missing_types:
                        account_number = f"{account_type.upper()}-{user.id:05d}-001"
                        self.stdout.write(f"  [DRY RUN] Would create: {account_number} - {account_name}")
                else:
                    # Wrap account creation in transaction for atomicity
                    with transaction.atomic():
                        for account_type, account_name, default_rate in missing_types:
                            account_number = f"{account_type.upper()}-{user.id:05d}-001"
                            account = MemberAccount.objects.create(
                                user=user,
                                account_number=account_number,
                                account_type=account_type,
                                status="active",
                                balance=0.00,
                                interest_rate=default_rate,
                                opening_date=date.today(),
                            )
                            accounts_created += 1
                            self.stdout.write(self.style.SUCCESS(f"  Created: {account_number} - {account_name}"))

                            # Create audit log for system-generated account
                            AuditLog.objects.create(
                                user=None,  # System action
                                action="create",
                                entity_type="account",
                                entity_id=account.id,
                                description=f"System auto-created {account_name} account {account_number} for member {user.username}",
                                ip_address="127.0.0.1",
                            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would update {members_updated} members and create {len(missing_types) * members_updated if members_updated > 0 else 0} accounts"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCompleted! Updated {members_updated} members, created {accounts_created} accounts"
                )
            )
