"""Phase B4 — fees become automatic.

Schema additions to make fee posting safe to retry from cron:

* `FeeCharge.loan_repayment` — FK to the EMI that triggered a `late_payment`
  fee. Combined with `fee_schedule__fee_type` it gives a unique-per-EMI key
  that the daily sweep uses to avoid raising the same fee twice.
* `FeeCharge.financial_period` — FK to the FY a `membership` /
  `annual_maintenance` fee belongs to. The annual sweep uses
  `(user, fee_type, financial_period)` to stay idempotent across reruns.
* `FeeCharge.STATUS_CHOICES += ("pending",)` — exposure / receivables reports
  already filter defensively for it (see `accounts/services/exposure.py`).
* `SocietyConfiguration.late_fee_grace_days` — operator-tunable grace before a
  late fee is automatically raised. Defaults to 0 (immediate).
* `AuditLog.ENTITY_CHOICES += ("fee",)` — gives fee-related audit rows their
  own entity bucket so the audit-log filter dropdowns work.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0038_interestreceivable_settlement_transaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="feecharge",
            name="loan_repayment",
            field=models.ForeignKey(
                blank=True,
                help_text="The overdue installment that triggered this late_payment fee (Phase B4).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="fee_charges",
                to="accounts.loanrepayment",
                verbose_name="Linked EMI",
            ),
        ),
        migrations.AddField(
            model_name="feecharge",
            name="financial_period",
            field=models.ForeignKey(
                blank=True,
                help_text="The FY this fee is attributed to (Phase B4).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fee_charges",
                to="accounts.financialperiod",
                verbose_name="Financial Period",
            ),
        ),
        migrations.AlterField(
            model_name="feecharge",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("charged", "Charged"),
                    ("waived", "Waived"),
                    ("refunded", "Refunded"),
                ],
                db_index=True,
                default="charged",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="societyconfiguration",
            name="late_fee_grace_days",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Days past EMI due date before a late_payment fee is auto-charged (Phase B4).",
                verbose_name="Late Fee Grace Days",
            ),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="entity_type",
            field=models.CharField(
                choices=[
                    ("member", "Member"),
                    ("account", "Account"),
                    ("transaction", "Transaction"),
                    ("voucher", "Voucher"),
                    ("loan", "Loan"),
                    ("fund", "Fund"),
                    ("fee", "Fee"),
                    ("system", "System"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
