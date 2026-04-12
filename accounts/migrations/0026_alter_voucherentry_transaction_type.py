from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0025_voucher_and_member_resign"),
    ]

    operations = [
        migrations.AlterField(
            model_name="voucherentry",
            name="transaction_type",
            field=models.CharField(
                choices=[
                    ("credit", "Credit"),
                    ("debit", "Debit"),
                    ("transfer", "Transfer"),
                    ("interest", "Interest Payment"),
                    ("dividend", "Dividend"),
                    ("share_capital", "Share Capital"),
                ],
                max_length=20,
            ),
        ),
    ]
