# Phase 3: split Loan into LoanApplication + LoanAccount + Guarantor; LoanRepayment -> loan_account

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_from_legacy_loan(apps, schema_editor):
    OldLoan = apps.get_model("accounts", "Loan")
    LoanApplication = apps.get_model("accounts", "LoanApplication")
    LoanAccount = apps.get_model("accounts", "LoanAccount")
    Guarantor = apps.get_model("accounts", "Guarantor")
    LoanRepayment = apps.get_model("accounts", "LoanRepayment")
    User = apps.get_model("accounts", "User")

    old_to_account = {}

    for loan in OldLoan.objects.all().order_by("id"):
        if loan.loan_number.startswith("LN-"):
            app_num = loan.loan_number.replace("LN-", "LA-", 1)
        else:
            app_num = f"LA-{loan.id}"

        if loan.status in ("pending", "rejected"):
            app_status = "rejected" if loan.status == "rejected" else "pending"
            rejected_reason = loan.remarks if app_status == "rejected" else None
            LoanApplication.objects.create(
                application_number=app_num,
                user_id=loan.user_id,
                loan_type=loan.loan_type,
                principal_amount=loan.principal_amount,
                interest_rate=loan.interest_rate,
                interest_type=loan.interest_type,
                tenure_months=loan.tenure_months,
                purpose=loan.purpose,
                guarantor_name=loan.guarantor_name,
                guarantor_member_id=loan.guarantor_member_id,
                guarantor_relationship=loan.guarantor_relationship,
                guarantor_contact=loan.guarantor_contact,
                collateral_type=loan.collateral_type,
                collateral_value=loan.collateral_value,
                collateral_description=loan.collateral_description,
                status=app_status,
                application_date=loan.application_date,
                approval_date=loan.approval_date,
                rejected_reason=rejected_reason,
                approved_by_id=loan.approved_by_id,
                created_by_id=loan.created_by_id,
                remarks=loan.remarks,
            )
            continue

        account_status_map = {
            "approved": "active",
            "active": "active",
            "closed": "closed",
            "defaulted": "defaulted",
            "written_off": "written_off",
        }
        acc_status = account_status_map.get(loan.status, "active")

        app = LoanApplication.objects.create(
            application_number=app_num,
            user_id=loan.user_id,
            loan_type=loan.loan_type,
            principal_amount=loan.principal_amount,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            tenure_months=loan.tenure_months,
            purpose=loan.purpose,
            guarantor_name=loan.guarantor_name,
            guarantor_member_id=loan.guarantor_member_id,
            guarantor_relationship=loan.guarantor_relationship,
            guarantor_contact=loan.guarantor_contact,
            collateral_type=loan.collateral_type,
            collateral_value=loan.collateral_value,
            collateral_description=loan.collateral_description,
            status="approved",
            application_date=loan.application_date,
            approval_date=loan.approval_date or loan.application_date,
            rejected_reason=None,
            approved_by_id=loan.approved_by_id,
            created_by_id=loan.created_by_id,
            remarks=loan.remarks,
        )
        acct = LoanAccount.objects.create(
            loan_number=loan.loan_number,
            application=app,
            user_id=loan.user_id,
            status=acc_status,
            principal_amount=loan.principal_amount,
            interest_rate=loan.interest_rate,
            interest_type=loan.interest_type,
            tenure_months=loan.tenure_months,
            emi_amount=loan.emi_amount,
            total_payable=loan.total_payable,
            total_paid=loan.total_paid,
            outstanding_balance=loan.outstanding_balance,
            overdue_amount=loan.overdue_amount,
            disbursement_date=loan.disbursement_date,
            first_emi_date=loan.first_emi_date,
            last_emi_date=loan.last_emi_date,
            closure_date=loan.closure_date,
            total_emis=loan.total_emis,
            emis_paid=loan.emis_paid,
            emis_overdue=loan.emis_overdue,
            collateral_type=loan.collateral_type,
            collateral_value=loan.collateral_value,
            collateral_description=loan.collateral_description,
            disbursement_account_id=loan.disbursement_account_id,
            processing_fee=loan.processing_fee,
            npa_date=loan.npa_date,
            remarks=loan.remarks,
            created_by_id=loan.created_by_id,
        )
        old_to_account[loan.id] = acct.id

        if loan.guarantor_name:
            g = Guarantor(
                loan_account_id=acct.id,
                name=loan.guarantor_name,
                relationship=loan.guarantor_relationship,
                contact=loan.guarantor_contact,
                is_member=bool(loan.guarantor_member_id),
                is_verified=False,
            )
            if loan.guarantor_member_id:
                u = User.objects.filter(member_id=loan.guarantor_member_id).first()
                if u:
                    g.user_id = u.id
            g.save()

    for rep in LoanRepayment.objects.all():
        acct_id = old_to_account.get(rep.loan_id)
        if acct_id:
            rep.loan_account_id = acct_id
            rep.save(update_fields=["loan_account_id"])
        else:
            rep.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0029_member_submodels_phase2"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoanApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("application_number", models.CharField(db_index=True, max_length=20, unique=True)),
                (
                    "loan_type",
                    models.CharField(
                        choices=[
                            ("personal", "Personal Loan"),
                            ("home", "Home Loan"),
                            ("vehicle", "Vehicle Loan"),
                            ("gold", "Gold Loan"),
                            ("education", "Education Loan"),
                            ("business", "Business Loan"),
                            ("emergency", "Emergency Loan"),
                            ("agriculture", "Agriculture Loan"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("principal_amount", models.DecimalField(decimal_places=2, max_digits=15)),
                ("interest_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                (
                    "interest_type",
                    models.CharField(
                        choices=[("flat", "Flat Rate"), ("reducing", "Reducing Balance")],
                        default="reducing",
                        max_length=20,
                    ),
                ),
                ("tenure_months", models.IntegerField()),
                ("purpose", models.TextField(blank=True, null=True)),
                ("guarantor_name", models.CharField(blank=True, max_length=200, null=True)),
                ("guarantor_member_id", models.CharField(blank=True, max_length=50, null=True)),
                ("guarantor_relationship", models.CharField(blank=True, max_length=100, null=True)),
                ("guarantor_contact", models.CharField(blank=True, max_length=15, null=True)),
                ("collateral_type", models.CharField(blank=True, max_length=200, null=True)),
                ("collateral_value", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("collateral_description", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("application_date", models.DateField()),
                ("approval_date", models.DateField(blank=True, null=True)),
                ("rejected_reason", models.TextField(blank=True, null=True)),
                ("remarks", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="applications_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="applications_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loan_applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Loan Application",
                "verbose_name_plural": "Loan Applications",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LoanAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("loan_number", models.CharField(db_index=True, max_length=20, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("closed", "Closed"),
                            ("defaulted", "Defaulted"),
                            ("written_off", "Written Off"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                ("principal_amount", models.DecimalField(decimal_places=2, max_digits=15, verbose_name="Loan Amount")),
                (
                    "interest_rate",
                    models.DecimalField(decimal_places=2, max_digits=5, verbose_name="Interest Rate (% p.a.)"),
                ),
                (
                    "interest_type",
                    models.CharField(
                        choices=[("flat", "Flat Rate"), ("reducing", "Reducing Balance")],
                        default="reducing",
                        max_length=20,
                    ),
                ),
                ("tenure_months", models.IntegerField(verbose_name="Tenure (Months)")),
                ("emi_amount", models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name="EMI Amount")),
                ("total_payable", models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ("total_paid", models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ("outstanding_balance", models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ("overdue_amount", models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ("disbursement_date", models.DateField(blank=True, null=True, verbose_name="Disbursement Date")),
                ("first_emi_date", models.DateField(blank=True, null=True, verbose_name="First EMI Date")),
                ("last_emi_date", models.DateField(blank=True, null=True, verbose_name="Last EMI Date")),
                ("closure_date", models.DateField(blank=True, null=True, verbose_name="Closure Date")),
                ("total_emis", models.IntegerField(default=0, verbose_name="Total EMIs")),
                ("emis_paid", models.IntegerField(default=0, verbose_name="EMIs Paid")),
                ("emis_overdue", models.IntegerField(default=0, verbose_name="EMIs Overdue")),
                ("collateral_type", models.CharField(blank=True, max_length=200, null=True, verbose_name="Collateral Type")),
                (
                    "collateral_value",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, verbose_name="Collateral Value"),
                ),
                ("collateral_description", models.TextField(blank=True, null=True, verbose_name="Collateral Description")),
                ("processing_fee", models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name="Processing Fee")),
                ("npa_date", models.DateField(blank=True, null=True, verbose_name="NPA Classification Date")),
                ("remarks", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "application",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loan_account",
                        to="accounts.loanapplication",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="loan_accounts_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "disbursement_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="loans_disbursed",
                        to="accounts.memberaccount",
                        verbose_name="Disbursement Account",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loan_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Loan Account",
                "verbose_name_plural": "Loan Accounts",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Guarantor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("relationship", models.CharField(blank=True, max_length=100, null=True)),
                ("contact", models.CharField(blank=True, max_length=15, null=True)),
                ("is_member", models.BooleanField(default=False)),
                ("is_verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "loan_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="guarantors",
                        to="accounts.loanaccount",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guarantees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Guarantor",
                "verbose_name_plural": "Guarantors",
                "ordering": ["loan_account", "created_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="loanrepayment",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="loanrepayment",
            name="loan_account",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="repayments",
                to="accounts.loanaccount",
            ),
        ),
        migrations.RunPython(migrate_from_legacy_loan, noop_reverse),
        migrations.RemoveField(
            model_name="loanrepayment",
            name="loan",
        ),
        migrations.AlterField(
            model_name="loanrepayment",
            name="loan_account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="repayments",
                to="accounts.loanaccount",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="loanrepayment",
            unique_together={("loan_account", "installment_number")},
        ),
        migrations.DeleteModel(
            name="Loan",
        ),
    ]
