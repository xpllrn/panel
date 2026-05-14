# Playreview Manual QA Checklist

## Preconditions
- Run migrations: `docker compose exec web python manage.py migrate`
- Seed review account + light data: `docker compose exec web python manage.py create_play_review_user --username playreview --password "YourPassword" --seed-light`
- Staff HTML UI: with **`WEB_LOGIN_DISABLED=True`** (Docker default), open **`/`** or **`/home/`** after **`/setup/`** — no browser login step.
- Login as admin and as `playreview` in Android app (API JWT unchanged).

## Admin Portal
- Members page filters: verify `status`, `member type`, and search together.
- Accounts page filters: verify `member status`, `account type`, `account status`, and pagination retain filters.
- Member modal account tab: confirm account rows do not show/edit per-account status.
- Member modal `Edit Member`: set inactive/resign and verify validation behavior.
- Receipts modal:
  - add 2+ account lines and create receipt.
  - select `Save as voucher first` and verify voucher appears in list.
  - transfer voucher to a fund and confirm receipts are created.
- Member account details from members modal opens `/accounts/<id>/details/` page (not JSON).
- Reports page: verify account-type inflow/outflow table updates when account type filter changes.

## Member Lifecycle Rules
- With pending EMI, setting member to inactive should fail.
- After inactive for 30+ days and no pending EMI, setting member to resign should succeed.
- On resign, settlement debit receipts should be generated and account balances reduced.

## Android App Pull-to-Refresh
- Home tab: pull down refresh keeps existing content visible and updates values.
- Accounts tab: pull down refresh reloads list without full-screen loader flash.
- Loans tab: pull down refresh reloads list without full-screen loader flash.
- Profile tab: pull down refresh reloads profile data while staying on screen.

## Smoke Checks
- Django tests: `docker compose exec web python manage.py test admin_portal.tests`
- Kotlin compile: `cd android-app && ./gradlew :app:compileDebugKotlin`
