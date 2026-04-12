from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0024_push_notifications_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="inactive_since",
            field=models.DateField(blank=True, null=True, verbose_name="Inactive Since"),
        ),
        migrations.AlterField(
            model_name="user",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                    ("resign", "Resigned"),
                    ("closed", "Closed"),
                    ("deceased", "Deceased"),
                    ("blacklisted", "Blacklisted"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="entity_type",
            field=models.CharField(
                choices=[
                    ("member", "Member"),
                    ("account", "Account"),
                    ("receipt", "Receipt"),
                    ("voucher", "Voucher"),
                    ("loan", "Loan"),
                    ("fund", "Fund"),
                    ("system", "System"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="Voucher",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("voucher_number", models.CharField(db_index=True, max_length=20, unique=True)),
                ("total_amount", models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                (
                    "payment_mode",
                    models.CharField(
                        choices=[
                            ("cash", "Cash"),
                            ("cheque", "Cheque"),
                            ("online", "Online Transfer"),
                            ("neft", "NEFT"),
                            ("rtgs", "RTGS"),
                            ("upi", "UPI"),
                        ],
                        default="cash",
                        max_length=20,
                    ),
                ),
                ("reference_number", models.CharField(blank=True, max_length=100, null=True)),
                ("remarks", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("transferred", "Transferred"), ("cancelled", "Cancelled")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("transferred_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vouchers_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "transferred_to_fund",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vouchers_transferred",
                        to="accounts.fundaccount",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="vouchers", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "verbose_name": "Voucher",
                "verbose_name_plural": "Vouchers",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="VoucherEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_type", models.CharField(max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=15)),
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_receipt",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="voucher_entries",
                        to="accounts.receipt",
                    ),
                ),
                (
                    "linked_loan_repayment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="voucher_entries",
                        to="accounts.loanrepayment",
                    ),
                ),
                (
                    "member_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="voucher_entries",
                        to="accounts.memberaccount",
                    ),
                ),
                (
                    "voucher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="accounts.voucher"
                    ),
                ),
            ],
            options={
                "verbose_name": "Voucher Entry",
                "verbose_name_plural": "Voucher Entries",
                "ordering": ["created_at"],
            },
        ),
    ]
