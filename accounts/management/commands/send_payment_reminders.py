from datetime import date, timedelta

from django.core.management.base import BaseCommand

from accounts.models import LoanRepayment
from accounts.notification_service import dispatch_user_notification


class Command(BaseCommand):
    help = "Send payment reminders for upcoming or overdue loan EMIs."

    def handle(self, *args, **options):
        today = date.today()
        upcoming_date = today + timedelta(days=3)

        upcoming = LoanRepayment.objects.select_related("loan", "loan__user").filter(
            payment_status="upcoming",
            due_date__lte=upcoming_date,
            due_date__gte=today,
        )
        overdue = LoanRepayment.objects.select_related("loan", "loan__user").filter(
            payment_status="overdue",
            due_date__lt=today,
        )

        sent = 0

        for repayment in upcoming:
            user = repayment.loan.user
            dispatch_user_notification(
                user=user,
                title="EMI Reminder",
                message=f"EMI #{repayment.installment_number} of ₹{repayment.amount_due} is due on {repayment.due_date}.",
                notification_type="loan",
                metadata={
                    "loan_id": repayment.loan.id,
                    "loan_number": repayment.loan.loan_number,
                    "installment_number": repayment.installment_number,
                    "due_amount": str(repayment.amount_due),
                    "due_date": str(repayment.due_date),
                },
                email_template="payment_reminder",
            )
            sent += 1

        for repayment in overdue:
            user = repayment.loan.user
            dispatch_user_notification(
                user=user,
                title="Overdue EMI Alert",
                message=f"EMI #{repayment.installment_number} of ₹{repayment.amount_due} is overdue since {repayment.due_date}.",
                notification_type="loan",
                metadata={
                    "loan_id": repayment.loan.id,
                    "loan_number": repayment.loan.loan_number,
                    "installment_number": repayment.installment_number,
                    "due_amount": str(repayment.amount_due),
                    "due_date": str(repayment.due_date),
                    "overdue": "true",
                },
                email_template="payment_reminder",
            )
            sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} payment reminders."))
