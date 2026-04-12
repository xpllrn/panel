from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0026_alter_voucherentry_transaction_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="voucher",
            name="voucher_type",
            field=models.CharField(
                choices=[("voucher", "Voucher"), ("contra_voucher", "Contra Voucher")],
                db_index=True,
                default="voucher",
                max_length=20,
            ),
        ),
    ]
