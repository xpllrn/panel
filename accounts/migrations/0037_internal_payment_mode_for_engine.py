from django.db import migrations, models

PAYMENT_MODE_CHOICES = [
    ("cash", "Cash"),
    ("cheque", "Cheque"),
    ("dd", "Demand Draft"),
    ("online", "Online Transfer"),
    ("neft", "NEFT"),
    ("rtgs", "RTGS"),
    ("upi", "UPI"),
    ("imps", "IMPS"),
    ("internal", "Internal Transfer"),
]


class Migration(migrations.Migration):
    """Phase B1 prep:

    Adds ``internal`` to ``Transaction.PAYMENT_MODE_CHOICES`` so the unified
    interest engine and other system-generated postings show up correctly in
    admin / forms.

    Also re-syncs ``Voucher.payment_mode`` and ``LoanRepayment.payment_mode``,
    which both ``choices=Transaction.PAYMENT_MODE_CHOICES`` but were never
    re-snapshotted after migration 0036 added ``dd`` and ``imps``.
    """

    dependencies = [
        ("accounts", "0036_voucher_instrument_and_payment_modes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="payment_mode",
            field=models.CharField(
                choices=PAYMENT_MODE_CHOICES,
                default="cash",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="voucher",
            name="payment_mode",
            field=models.CharField(
                choices=PAYMENT_MODE_CHOICES,
                default="cash",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="loanrepayment",
            name="payment_mode",
            field=models.CharField(
                choices=PAYMENT_MODE_CHOICES,
                default="cash",
                max_length=20,
            ),
        ),
    ]
