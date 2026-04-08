# Generated manually to remove dead code

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_auditlog'),
    ]

    operations = [
        # Remove deprecated fields from User model
        migrations.RemoveField(
            model_name='user',
            name='phone',
        ),
        migrations.RemoveField(
            model_name='user',
            name='avatar',
        ),
        # Delete BankAccount model entirely
        migrations.DeleteModel(
            name='BankAccount',
        ),
    ]
