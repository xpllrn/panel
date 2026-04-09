from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0022_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginOTPChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("challenge_token", models.CharField(db_index=True, max_length=64, unique=True)),
                ("otp_hash", models.CharField(max_length=255)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("attempt_count", models.IntegerField(default=0)),
                ("max_attempts", models.IntegerField(default=5)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("request_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="login_otp_challenges",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Login OTP Challenge",
                "verbose_name_plural": "Login OTP Challenges",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="UserDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, max_length=255, unique=True)),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS"), ("web", "Web")], default="android", max_length=20)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="devices",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "User Device",
                "verbose_name_plural": "User Devices",
                "ordering": ["-last_seen"],
            },
        ),
    ]
