# Android app — database refactor backlog

The Django backend completed **Phase 3** (loan split: `LoanApplication`, `LoanAccount`, `Guarantor`, `LoanRepayment.loan_account`). The native member app was intentionally **not** updated yet. Track gaps here before shipping against production APIs.

## Loans API mismatch

### List (`GET member/loans/`)

- **Backend:** Paginated results are **merged rows**: each item has `list_kind` (`"application"` | `"account"`), string amounts, and `id` that is either a **LoanApplication** id or a **LoanAccount** id (same numeric space can collide across tables — use `list_kind` always).
- **App:** `Models.kt` uses a single `Loan` data class and assumes one loan model. Update to carry `list_kind` (or separate DTOs) and parse string decimals if needed.

### Detail (`GET member/loans/{id}/`)

- **Backend:** Optional query `?kind=application|account` disambiguates; without `kind`, server tries **LoanAccount** first, then **LoanApplication**.
- **App:** `ApiService.getLoanDetail(@Path("id") id: Int)` has no `kind`. Add `@Query("kind")` (or path segment) and pass through from the list row.
- **Navigation:** `loan_detail/{id}` should include kind, e.g. `loan_detail/{kind}/{id}`, or pass kind as a navigation argument.

### Dashboard / other calls

- **Backend:** `active_loans` in member dashboard are **LoanAccount** rows only (`list_kind` implied `"account"`).
- **App:** Ensure any hard-coded assumptions about old `Loan.status` values (`approved` on book) match **account** statuses (`active`, `closed`, …).

## Transactions (Phase 1 rename)

- Endpoints and JSON fields use **`transaction`** / `transaction_number` instead of **receipt** / `receipt_number` if the app still calls legacy paths; confirm `ApiService` paths match `API_DOCUMENTATION.md` / live `config/urls.py`.

## Phase 4 (financial layer)

- New entities (`InterestReceivable`, `FeeSchedule`, `FeeCharge`, `ProfitAndLoss`, `SocietyAccount`) will appear on **admin/API** first. Add mobile scope only when product requires it.

## Suggested implementation order

1. Regenerate or hand-update Kotlin models from OpenAPI / sample JSON for **member loans** list + detail.
2. Thread `list_kind` from list → detail → API query.
3. Regression-test login, dashboard, loans list/detail, transactions list.

When this file is empty of actionable items, delete it or replace with “In sync with backend”.
