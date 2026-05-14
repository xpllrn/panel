"""Run the unified interest engine — Phase B2.

Thin wrapper around ``accounts.services.interest_engine.run_full_engine`` so
the engine can be scheduled from cron (or a Kubernetes CronJob, systemd
timer, etc.) without an operator clicking the panel's "Post Interest" button.

Typical usage::

    # Nightly (after midnight, before the daily reports). Uses the active FY
    # and today's date.
    python manage.py run_interest_engine

    # Explicit financial period + as-of (for back-fills / catch-up runs).
    python manage.py run_interest_engine --period 7 --as-of 2026-03-31

    # Only the deposit side (skip loan receivables).
    python manage.py run_interest_engine --deposits-only

    # Only the loan side (no deposit credits — useful right before FY close).
    python manage.py run_interest_engine --loans-only

The engine itself is idempotent for a given ``as-of`` date, so re-running on
the same day is a no-op on deposits and only refreshes loan receivables when
an EMI's ``interest_component`` was edited.

Sample crontab line (run at 00:30 every day)::

    30 0 * * * cd /app && /usr/local/bin/python manage.py run_interest_engine >> /var/log/panel/interest_engine.log 2>&1
"""

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from accounts.models import FinancialPeriod
from accounts.services import interest_engine


class Command(BaseCommand):
    help = "Run the unified interest engine (deposit accrual + loan receivable accrual)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            dest="as_of",
            default=None,
            help="Run as if today is this YYYY-MM-DD date (default: today). Used for catch-up runs and back-fills.",
        )
        parser.add_argument(
            "--period",
            dest="period_id",
            type=int,
            default=None,
            help="FinancialPeriod id to attribute postings to. Default: the active FY.",
        )
        parser.add_argument(
            "--deposits-only",
            dest="deposits_only",
            action="store_true",
            help="Skip loan-side accrual; post only deposit interest credits.",
        )
        parser.add_argument(
            "--loans-only",
            dest="loans_only",
            action="store_true",
            help="Skip deposit-side accrual; only materialise loan InterestReceivable rows.",
        )

    def handle(self, *args, **options):
        if options["deposits_only"] and options["loans_only"]:
            raise CommandError("--deposits-only and --loans-only are mutually exclusive.")

        as_of = self._parse_as_of(options["as_of"])
        fp = self._resolve_financial_period(options["period_id"])

        if options["deposits_only"]:
            result = interest_engine.accrue_deposits(as_of=as_of, financial_period=fp, audit_via="cron")
            self._print_deposits(result)
            return

        if options["loans_only"]:
            result = interest_engine.accrue_loans(as_of=as_of, financial_period=fp, audit_via="cron")
            self._print_loans(result)
            return

        out = interest_engine.run_full_engine(as_of=as_of, financial_period=fp, audit_via="cron")
        self._print_deposits(out["deposits"])
        self._print_loans(out["loans"])

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
            return None  # interest_engine will resolve the active FY itself.
        try:
            return FinancialPeriod.objects.get(id=period_id)
        except FinancialPeriod.DoesNotExist as exc:
            raise CommandError(f"FinancialPeriod id={period_id} not found.") from exc

    def _print_deposits(self, result):
        self.stdout.write(
            self.style.SUCCESS(
                f"[deposits] {result['accounts_updated']} account(s) credited \u2014 "
                f"total \u20b9{result['total_posted']} as of {result['period_end']}."
            )
        )

    def _print_loans(self, result):
        self.stdout.write(
            self.style.SUCCESS(
                f"[loans]    {result['rows_created']} new + {result['rows_updated']} updated receivable(s) "
                f"({result['installments_considered']} installment(s) considered) as of {result['as_of']}."
            )
        )
