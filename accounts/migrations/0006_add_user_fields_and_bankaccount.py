# Generated migration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='pan_card',
            field=models.CharField(blank=True, max_length=10, null=True, verbose_name='PAN Card'),
        ),
        migrations.AddField(
            model_name='user',
            name='aadhar_card',
            field=models.CharField(blank=True, max_length=12, null=True, verbose_name='Aadhar Card'),
        ),
        migrations.AddField(
            model_name='user',
            name='work',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Work/Occupation'),
        ),
        migrations.AddField(
            model_name='user',
            name='work_address',
            field=models.TextField(blank=True, null=True, verbose_name='Work Address'),
        ),
        migrations.CreateModel(
            name='BankAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_name', models.CharField(max_length=200, verbose_name='Account Holder Name')),
                ('bank_name', models.CharField(max_length=200, verbose_name='Bank Name')),
                ('account_number', models.CharField(max_length=50, verbose_name='Account Number')),
                ('ifsc_code', models.CharField(blank=True, max_length=11, null=True, verbose_name='IFSC Code')),
                ('branch', models.CharField(blank=True, max_length=200, null=True, verbose_name='Branch')),
                ('account_type', models.CharField(blank=True, max_length=50, null=True, verbose_name='Account Type')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
