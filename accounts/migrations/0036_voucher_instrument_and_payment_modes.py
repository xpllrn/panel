import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0035_expand_custom_product_name_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="voucher",
            name="instrument",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="vouchers",
                to="accounts.instrument",
                verbose_name="Payment instrument",
            ),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="payment_mode",
            field=models.CharField(
                choices=[
                    ("cash", "Cash"),
                    ("cheque", "Cheque"),
                    ("dd", "Demand Draft"),
                    ("online", "Online Transfer"),
                    ("neft", "NEFT"),
                    ("rtgs", "RTGS"),
                    ("upi", "UPI"),
                    ("imps", "IMPS"),
                ],
                default="cash",
                max_length=20,
            ),
        ),
    ]
