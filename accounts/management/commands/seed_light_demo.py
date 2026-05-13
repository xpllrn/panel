import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import LoanAccount, LoanApplication, LoanRepayment, MemberAccount, Transaction, User


class Command(BaseCommand):
    help = "Seed light demo data for playreview account."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="playreview", help="Member username to seed.")
        parser.add_argument("--receipts", type=int, default=50, help="Approximate number of receipts to create.")
        parser.add_argument("--reset", action="store_true", help="Delete existing receipts and loans for the user first.")

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        receipt_target = max(10, int(options["receipts"]))

        try:
            user = User.objects.get(username=username, is_deleted=False)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User '{username}' not found."))
            return

        with transaction.atomic():
            if options["reset"]:
                Transaction.objects.filter(user=user).delete()
                LoanRepayment.objects.filter(loan_account__user=user).delete()
                LoanAccount.objects.filter(user=user).delete()
                LoanApplication.objects.filter(user=user).delete()

            accounts = list(MemberAccount.objects.filter(user=user, is_deleted=False, status="active"))
            if not accounts:
                defaults = [
                    ("fd", 7.5),
                    ("rd", 7.0),
                    ("share", 0.0),
                    ("sukanya", 8.0),
                ]
                for acc_type, rate in defaults:
                    account = MemberAccount.objects.create(
                        user=user,
                        account_number=f"{acc_type.upper()}-{user.id:05d}-001",
                        account_type=acc_type,
                        status="active",
                        opening_date=date.today() - timedelta(days=400),
                        interest_rate=Decimal(str(rate)),
                        balance=Decimal("0.00"),
                    )
                    accounts.append(account)

            self._create_receipts(user, accounts, receipt_target)
            self._create_loans_with_pending_emi(user, accounts)

        self.stdout.write(self.style.SUCCESS(f"Seeded light demo data for {user.username} ({receipt_target} receipts target)."))

    def _next_transaction_number(self):
        year = date.today().year
        last = (
            Transaction.objects.filter(transaction_number__startswith=f"RCP-{year}-")
            .order_by("-transaction_number")
            .first()
        )
        if not last:
            return f"RCP-{year}-00001"
        try:
            seq = int(last.transaction_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
        return f"RCP-{year}-{seq:05d}"

    def _create_receipts(self, user, accounts, receipt_target):
        running = {account.id: Decimal(str(account.balance or "0")) for account in accounts}
        receipt_types = ["credit", "credit", "credit", "debit", "interest", "share_capital"]
        for _ in range(receipt_target):
            account = random.choice(accounts)
            tx_type = random.choice(receipt_types)
            amount = Decimal(str(random.randint(200, 5000)))
            if tx_type in ("debit", "transfer") and running[account.id] <= Decimal("500"):
                tx_type = "credit"
            if tx_type in ("debit", "transfer"):
                amount = min(amount, running[account.id])
                running[account.id] -= amount
            else:
                running[account.id] += amount
            receipt = Transaction.objects.create(
                transaction_number=self._next_transaction_number(),
                user=user,
                member_account=account,
                transaction_type=tx_type,
                amount=amount,
                description=f"Demo {tx_type} entry",
                payment_mode=random.choice(["cash", "upi", "online"]),
                balance_after=running[account.id],
            )
            random_days = random.randint(1, 180)
            Transaction.objects.filter(id=receipt.id).update(created_at=date.today() - timedelta(days=random_days))
        for account in accounts:
            account.balance = running[account.id]
            account.last_transaction_date = date.today()
            account.save(update_fields=["balance", "last_transaction_date"])

    def _create_loans_with_pending_emi(self, user, accounts):
        if LoanAccount.objects.filter(user=user).exists():
            return
        disb_account = accounts[0]
        year = date.today().year
        for idx in range(2):
            principal = Decimal("120000.00") + Decimal(str(idx * 30000))
            emi_amt = Decimal("11000.00") + Decimal(str(idx * 1000))
            app = LoanApplication.objects.create(
                application_number=f"LA-{year}-{user.id:03d}{idx + 1}",
                user=user,
                loan_type="personal",
                principal_amount=principal,
                interest_rate=Decimal("12.00"),
                interest_type="reducing",
                tenure_months=12,
                application_date=date.today() - timedelta(days=200),
                status="approved",
                approval_date=date.today() - timedelta(days=190),
            )
            loan = LoanAccount.objects.create(
                loan_number=f"LN-{year}-{user.id:03d}{idx + 1}",
                application=app,
                user=user,
                status="active",
                principal_amount=principal,
                interest_rate=Decimal("12.00"),
                interest_type="reducing",
                tenure_months=12,
                emi_amount=emi_amt,
                total_payable=Decimal("132000.00") + Decimal(str(idx * 12000)),
                total_paid=Decimal("33000.00"),
                outstanding_balance=principal - Decimal("33000.00"),
                overdue_amount=Decimal("11000.00"),
                disbursement_date=date.today() - timedelta(days=185),
                disbursement_account=disb_account,
                total_emis=12,
                emis_paid=3,
                emis_overdue=1,
            )
            for installment in range(1, 13):
                due_date = date.today() - timedelta(days=(12 - installment) * 30)
                st = "paid" if installment <= 3 else ("overdue" if installment == 4 else "upcoming")
                paid_date = due_date if st == "paid" else None
                paid_amount = loan.emi_amount if st == "paid" else Decimal("0.00")
                LoanRepayment.objects.create(
                    loan_account=loan,
                    installment_number=installment,
                    due_date=due_date,
                    paid_date=paid_date,
                    amount_due=loan.emi_amount,
                    amount_paid=paid_amount,
                    principal_component=Decimal("9000.00"),
                    interest_component=Decimal("2000.00"),
                    balance_after=max(Decimal("0.00"), loan.outstanding_balance - (installment * Decimal("9000.00"))),
                    payment_status=st,
                )
