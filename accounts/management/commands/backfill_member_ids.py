"""
Management command to backfill member_id for existing members.
Assigns MBR{YEAR}{SEQUENTIAL} IDs to members who don't have one.
"""

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Backfill member_id for existing members who have no member_id assigned"

    def handle(self, *args, **options):
        members_without_id = User.objects.filter(
            role="member", member_id__isnull=True
        ) | User.objects.filter(role="member", member_id="")

        count = members_without_id.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("All members already have a member_id."))
            return

        self.stdout.write(f"Found {count} members without a member_id. Backfilling...")

        updated = 0
        for member in members_without_id:
            member.save()  # triggers auto-gen in the model's save() method
            updated += 1
            self.stdout.write(f"  {member.display_name} -> {member.member_id}")

        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated} members."))
