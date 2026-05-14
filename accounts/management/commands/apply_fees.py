"""Apply automatic fees — Phase B4.

Thin wrapper around ``accounts.services.fees`` so fee sweeps can be scheduled
from cron (or a Kubernetes CronJob, systemd timer, etc.).

Typical usage::

    # Daily: post late-payment fees for overdue EMIs past grace period.
    python manage.py apply_fees --late

    # Yearly (or on FY open): post annual maintenance fees for all members.
    python manage.py apply_fees --annual

    # Both in one invocation.
    python manage.py apply_fees --late --annual

    # Override the as-of date (for back-fills / catch-up runs).
    python manage.py apply_fees --late --as-of 2026-03-31

    # Override grace days (ignores SocietyConfiguration value).
    python manage.py apply_fees --late --grace-days 7

    # Target a specific financial period.
    python manage.py apply_fees --annual --period 3

Sample crontab line (run daily at 01:00)::

    0 1 * * * cd /app && /usr/local/bin/python manage.py apply_fees --late >> /var/log/panel/fees.log 2>&1
"""

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from accounts.models import FinancialPeriod
from accounts.services import fees as fee_service


class Command(BaseCommand):
    help = "Apply automatic fees (late-payment sweep and/or annual maintenance)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--late",
            dest="late",
            action="store_true",
            help="Run the late-payment fee sweep for overdue EMIs.",
        )
        parser.add_argument(
            "--annual",
            dest="annual",
            action="store_true",
            help="Run the annual maintenance fee sweep for all active members.",
        )
        parser.add_argument(
            "--as-of",
            dest="as_of",
            default=None,
            help="Run as if today is this YYYY-MM-DD date (default: today). Applies to --late.",
        )
        parser.add_argument(
            "--grace-days",
            dest="grace_days",
            type=int,
            default=None,
            help="Override the grace days from SocietyConfiguration. Applies to --late.",
        )
        parser.add_argument(
            "--period",
            dest="period_id",
            type=int,
            default=None,
            help="FinancialPeriod id to attribute fees to. Default: the active FY.",
        )

    def handle(self, *args, **options):
        if not options["late"] and not options["annual"]:
            raise CommandError("Specify at least one of --late or --annual.")

        as_of = self._parse_as_of(options["as_of"])
        fp = self._resolve_financial_period(options["period_id"])

        if options["late"]:
            result = fee_service.apply_late_payment_fees(
                as_of=as_of,
                grace_days=options["grace_days"],
                financial_period=fp,
                audit_via="cron",
            )
            self.stdout.write(
                f"[late_payment] created={result['charges_created']} "
                f"skipped={result['charges_skipped']} as_of={result['as_of']}"
            )

        if options["annual"]:
            result = fee_service.apply_annual_maintenance_fees(
                financial_period=fp,
                audit_via="cron",
            )
            self.stdout.write(
                f"[annual_maintenance] created={result['charges_created']} skipped={result['charges_skipped']}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_as_of(self, raw):
        if not raw:
            return date.today()
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(f"--as-of must be YYYY-MM-DD, got {raw!r}.") from exc

    def _resolve_financial_period(self, period_id):
        if period_id is None:
            return None
        try:
            return FinancialPeriod.objects.get(id=period_id)
        except FinancialPeriod.DoesNotExist as exc:
            raise CommandError(f"FinancialPeriod with id={period_id} does not exist.") from exc
