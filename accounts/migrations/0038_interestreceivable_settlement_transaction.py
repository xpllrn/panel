import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Phase B3: link an InterestReceivable to the EMI Transaction that
    settled it. Lets reports / MCP tools trace which payment closed which
    loan-side accrual."""

    dependencies = [
        ("accounts", "0037_internal_payment_mode_for_engine"),
    ]

    operations = [
        migrations.AddField(
            model_name="interestreceivable",
            name="transaction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="interest_receivables_settled",
                to="accounts.transaction",
                verbose_name="Settlement transaction",
                help_text="The EMI Transaction that collected this receivable (Phase B3).",
            ),
        ),
    ]
