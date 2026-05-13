# Legacy code

Code retired from the active build but kept for reference / future revival. Nothing in this directory is referenced from active code paths; the Django app does not import or route to anything here.

## Contents

| Path | What it is | How to revive |
|---|---|---|
| `legacy/android-app/` | Member-facing Android app (Kotlin / Jetpack Compose). Consumed the now-disabled member REST API. | Move back to `android-app/` at repo root and re-enable the member REST endpoints (see "OTP / member REST" below). |
| `legacy/member_portal/` | Member self-service Django app (read-only views: dashboard, accounts, loans, transactions, profile, statement). | Move back to `member_portal/` at repo root, re-add `"member_portal"` to `INSTALLED_APPS` in `config/settings.py`, and re-introduce `path("member/", include("member_portal.urls"))` in `config/urls_panel.py`. |
| `legacy/templates/member/` | Bootstrap templates consumed by `member_portal/views.py`. | Moves with the app. |
| `legacy/templates/accounts_member_portal_disabled.html` | Stub page rendered when a member tried to access the disabled portal. | Restore to `templates/accounts/member_portal_disabled.html` and re-add `member_portal_disabled_view` to `accounts/views.py` and `accounts/urls.py`. |
| `legacy/templates/emails/login_otp.{html,txt}` | Email templates for the OTP login flow. | Move back to `templates/emails/` and re-register the OTP URL routes. |
| `legacy/templates/emails/email_change_otp.{html,txt}` | Email templates for the email-change OTP flow. | Same as above. |

## OTP / member REST endpoints

The OTP-login + device-registration + member-REST endpoints are **NOT** in this folder. They are kept as dormant code inside `accounts/api_views.py`:

- `auth_login_start_view` — `POST /api/v1/auth/login/`
- `auth_verify_otp_view` — `POST /api/v1/auth/login/verify-otp/`
- `auth_resend_otp_view` — `POST /api/v1/auth/login/resend-otp/`
- `register_device_token_view` / `unregister_device_token_view`
- `member_dashboard` / `member_accounts_*` / `member_loans_*` / `member_transactions_*`
- `member_notifications_*` / `member_push_preferences_view` / `member_notifications_test_push_view`

These functions still compile and pass `manage.py check`, but **their URL routes are not registered** in `accounts/api_urls.py`. To revive: copy the removed `path(...)` lines back from `git log -- accounts/api_urls.py` (the commit retiring them).

The supporting helpers `accounts/email_utils.send_login_otp_email` and `accounts/notification_service.send_member_test_push` also remain in place — they are imported by the dormant view functions but only invoked when the routes are alive.

## Dormant database tables

These two tables stay in the schema but are unreachable:

- `accounts_loginotpchallenge` (`LoginOTPChallenge` model)
- `accounts_userdevice` (`UserDevice` model)
- `User.push_notifications_enabled` column (added in migration `0024_push_notifications_enabled`)

We did **not** generate "drop table" migrations because:

1. The tables hold no rows in production.
2. Removing them would force a schema migration on every deployment for code that may come back online.
3. They cost effectively zero storage when empty.

If you want to fully drop them, run `python manage.py makemigrations accounts` after deleting the model classes from `accounts/models.py`.

## Tests removed

- `accounts.tests.OtpLoginFlowTests` (4 tests) — covered `auth_login_start`, `auth_verify_otp`, OTP bypass, and device register/unregister.
- `member_portal.tests.*` — moved with the app.
