# Generated manually for Fund Management system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_remove_dead_code'),
    ]

    operations = [
        # Update AuditLog ENTITY_CHOICES to include 'fund'
        migrations.AlterField(
            model_name='auditlog',
            name='entity_type',
            field=models.CharField(
                choices=[
                    ('member', 'Member'),
                    ('account', 'Account'),
                    ('receipt', 'Receipt'),
                    ('loan', 'Loan'),
                    ('fund', 'Fund'),
                    ('system', 'System'),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        # Create FundAccount model
        migrations.CreateModel(
            name='FundAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Fund Name')),
                ('fund_type', models.CharField(
                    choices=[
                        ('welfare', 'Welfare Fund'),
                        ('library', 'Library Fund'),
                        ('education', 'Education Fund'),
                        ('emergency', 'Emergency Fund'),
                        ('dividend', 'Dividend Fund'),
                        ('statutory', 'Statutory Fund'),
                        ('reserve', 'Reserve Fund'),
                        ('other', 'Other'),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ('account_number', models.CharField(db_index=True, max_length=20, unique=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='funds_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Fund Account',
                'verbose_name_plural': 'Fund Accounts',
                'ordering': ['name'],
            },
        ),
        # Create FundTransaction model
        migrations.CreateModel(
            name='FundTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(
                    choices=[('credit', 'Credit'), ('debit', 'Debit')],
                    db_index=True,
                    max_length=20,
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('description', models.TextField()),
                ('payment_mode', models.CharField(
                    choices=[
                        ('cash', 'Cash'),
                        ('cheque', 'Cheque'),
                        ('online', 'Online Transfer'),
                        ('neft', 'NEFT'),
                        ('rtgs', 'RTGS'),
                        ('upi', 'UPI'),
                        ('internal', 'Internal Transfer'),
                    ],
                    default='internal',
                    max_length=20,
                )),
                ('reference_number', models.CharField(blank=True, max_length=100, null=True)),
                ('balance_after', models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ('trigger_event', models.CharField(blank=True, max_length=50, null=True)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fund_transactions_created',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('fund', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transactions',
                    to='accounts.fundaccount',
                )),
                ('source_member', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='fund_transactions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Fund Transaction',
                'verbose_name_plural': 'Fund Transactions',
                'ordering': ['-created_at'],
            },
        ),
        # Create FundAllocationRule model
        migrations.CreateModel(
            name='FundAllocationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trigger_event', models.CharField(
                    choices=[
                        ('member_registration', 'Member Registration'),
                        ('loan_interest', 'Loan Interest'),
                        ('loan_penalty', 'Loan Penalty'),
                        ('account_interest', 'Account Interest'),
                        ('annual_profit', 'Annual Profit'),
                        ('manual', 'Manual'),
                    ],
                    db_index=True,
                    max_length=50,
                )),
                ('allocation_type', models.CharField(
                    choices=[('fixed', 'Fixed Amount'), ('percentage', 'Percentage')],
                    max_length=20,
                )),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('percentage', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='allocation_rules_created',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('fund', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='allocation_rules',
                    to='accounts.fundaccount',
                )),
            ],
            options={
                'verbose_name': 'Fund Allocation Rule',
                'verbose_name_plural': 'Fund Allocation Rules',
                'ordering': ['trigger_event', 'fund'],
            },
        ),
    ]
