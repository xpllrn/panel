"""
Management command to backfill member accounts for existing members.
Creates all account types for members who don't have them yet.
"""

from datetime import date

from django.core.management.base import BaseCommand

from accounts.models import MemberAccount, User


class Command(BaseCommand):
    help = "Backfill member accounts for existing members who don't have all account types"

    def handle(self, *args, **options):
        members = User.objects.filter(role="member").exclude(member_id__isnull=True).exclude(member_id="")

        total_members = members.count()

        if total_members == 0:
            self.stdout.write(self.style.WARNING("No members found with member_id."))
            return

        self.stdout.write(f"Found {total_members} members. Checking accounts...")

        account_types = [choice[0] for choice in MemberAccount.ACCOUNT_TYPE_CHOICES]
        total_created = 0

        for member in members:
            created_count = 0

            for account_type in account_types:
                type_prefix = account_type.upper()
                account_number = f"{type_prefix}-{member.member_id}"

                # Check if account already exists
                if MemberAccount.objects.filter(account_number=account_number).exists():
                    continue

                # Create the account
                try:
                    MemberAccount.objects.create(
                        user=member,
                        account_number=account_number,
                        account_type=account_type,
                        status="active",
                        balance=0.00,
                        interest_rate=0.00,
                        principal_amount=0.00,
                        accrued_interest=0.00,
                        opening_date=date.today(),
                        remarks=f"Backfilled {account_type.upper()} account for member {member.display_name}",
                    )
                    created_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Failed to create {account_type} for {member.display_name}: {str(e)}")
                    )

            if created_count > 0:
                total_created += created_count
                self.stdout.write(f"  {member.display_name} ({member.member_id}): Created {created_count} accounts")

        if total_created > 0:
            self.stdout.write(self.style.SUCCESS(f"Done. Created {total_created} accounts across all members."))
        else:
            self.stdout.write(self.style.SUCCESS("All members already have all account types."))
