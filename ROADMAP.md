# Panel ERP — Roadmap

**Single source of truth** for where Panel ERP stands today and the phased plan to bring it in line with the cooperative-society ERP architecture (the "diagram"), then expose the whole system as an **MCP server** for AI agents and third-party apps.

> File: `ROADMAP.md`. Supersedes the earlier `PROJECT_STATE.md` (now removed).

This document is the working plan. Edit it as work lands. Companion docs:
- `CLAUDE.md` — coding conventions
- `DATABASE.md` — current schema reference (needs refresh after Phase 2 of the DB refactor)
- `DATABASE_REFACTOR_PLAN.md` — the original DB refactor (Phases 1–4 are **complete**)
- `API_DOCUMENTATION.md` — REST surface documentation

---

## 1. Target architecture (the diagram)

The cooperative society banking flow has five layers. Every box below must be backed by a model, a service function, a UI/API surface, and an audit trail.

```
L1 — Period & people
   Financial Period (open / close / continue)
   Share Capital · Member (KYC + nominees) · Guarantor

L2 — Member products
   CD · FD · OD · RD/Savings
                 │
                 ▼
   Interest Calculation Engine ──────────────────┐
                 │                               │
L3 — Loan stack  │                               │
   Loan Application → Loan Account → Repayment Schedule
                 │
L4 — Posting plumbing
   Transaction (acct, date, CR/DR, ref)
        │
        ▼
   Voucher (receipt · payment · contra · journal)
        │
        ▼
   Instrument (cash · cheque · DD · NEFT · UPI · IMPS)

L5 — Society books
   SOCIETY MAIN ACCOUNT  ←  every Transaction rolls up here
        │
        ├── Interest Payable (to depositors)        — subtract
        ├── Interest Receivable (from loans)        — add
        ├── Fees & Charges                          — add
        ▼
   Net Surplus
        │
        ├── Statutory Reserve    25%
        ├── Education Fund      1–2%
        ├── Build/Service Fund  configurable
        ├── Bad-debt Provision  configurable
        └── Dividend            remainder
```

---

## 2. Deployment architecture (already in place)

The frontend and the API are deployed as **two independent processes** sharing one PostgreSQL database. This is a security and reuse boundary — an HTML bug or auto-login shortcut on the panel cannot reach the API surface, and the API can be consumed by the Android app, future client apps, and the upcoming MCP server.

| Service | Container | Port | Settings | URLconf | Notes |
|---|---|---|---|---|---|
| **panel** | `panel` | 8000 | `config.settings` | `config.urls_panel` | Staff HTML portal, Django admin, setup wizard. Owns migrations. |
| **api** | `api` | 8001 | `config.settings_api` | `config.urls_api` | Pure REST (`/api/v1/`). `AutoStaffLoginMiddleware` stripped. No HTML. Used by Android, MCP, third-party apps. |
| **db** | `db` | 5433→5432 | — | — | PostgreSQL 15. Shared. |

What is still **wrong** today: business logic lives inside `admin_portal/views.py` (4,677 lines of HTML view functions) and is partially duplicated inside `accounts/api_views.py` (2,582 lines). The two surfaces drift. **Phase 0 fixes this** by introducing a services layer that both surfaces call into.

---

## 3. Current state — diagram coverage

The DB refactor (Phases 1–4 in `DATABASE_REFACTOR_PLAN.md`) is **complete**. All 28 models exist, the old monolithic `Loan` is gone, `Receipt` is now `Transaction`, and `FinancialPeriod` / `Instrument` / `InterestReceivable` / `ProfitAndLoss` / `SocietyAccount` / `FeeSchedule` / `FeeCharge` are in place.

The remaining gap is **wiring**: many models exist with no UI, no API, or with services that ignore them. Scorecard:

| Diagram element | Model | UI | API | Service / Logic |
|---|---|---|---|---|
| Financial Period | ✅ | ⚠️ Settings tab only — no open/close lifecycle | ❌ No REST | ⚠️ `portal_fy.py` resolves "working FY" but no transitions |
| Member / KYC / Nominee / Address / Share Capital | ✅ | ✅ | ✅ | ✅ |
| Guarantor | ✅ | ⚠️ Single row, captured at approval | ⚠️ Partial fields | ❌ No multi-guarantor support |
| CD/FD/OD/RD accounts | ✅ | ✅ | ✅ | ✅ |
| Interest Engine — deposits | ✅ math (`accounts/interest.py`) | ✅ `post_interest_view` button | ✅ `admin_post_interest` | ⚠️ **OD excluded**; no scheduled job; ignores `transaction_date` |
| Interest Engine — loans | ✅ `InterestReceivable` | ⚠️ Manual "sync receivables" button | ⚠️ Manual sync endpoint | ❌ No daily accrual; no unified engine |
| Loan Application | ✅ | ✅ | ✅ | ✅ |
| Loan Account | ✅ | ✅ | ✅ | ⚠️ **Approval doesn't disburse** — no `Transaction` posted, `disbursement_account` stays null, `processing_fee` silently dropped by API |
| Repayment Schedule | ✅ | ✅ | ✅ | ⚠️ `calculate_emi()` always uses reducing formula, even for flat loans |
| Transaction | ✅ | ✅ | ✅ | ✅ |
| Voucher (4 types) | ✅ | ✅ | ✅ | ⚠️ Cash payments **forced** through voucher staging |
| Instrument (cheque/DD/NEFT/UPI/IMPS) | ✅ | ❌ **Never created from any flow** | ❌ Not on serializer | ❌ Model lives unused |
| Society Main Account | ✅ snapshot | ✅ | ✅ | ⚠️ Aggregates only; no running ledger |
| Interest Payable / Receivable / Fees | ✅ | ⚠️ Payable yes; receivable manual; fees almost untouched | ⚠️ | ❌ `FeeSchedule` defined; **`FeeCharge` never created automatically** |
| Net Surplus | ✅ `ProfitAndLoss` | ✅ saved snapshot | ✅ | ❌ **`distribute_profit` reads live summary, NOT the saved P&L row** — locking is meaningless |
| 5-bucket distribution (25% / 1–2% / build / bad-debt / dividend) | ✅ `FundAllocationRule.annual_profit` | ⚠️ Manual rule creation | ⚠️ | ❌ Setup wizard **doesn't seed statutory funds or default rules** |
| MCP server | ❌ Nothing exists | ❌ | ❌ | ❌ |

### Other lingering issues
- `templates/admin/receipts.html` still rendered by `transactions_view` (cosmetic rename incomplete).
- `templates/admin/financial_periods.html` is an **orphan** — never linked, never routed.
- Setup wizard does not create the **first FinancialPeriod** or seed any **statutory FundAccounts**.
- API `LoanCreateSerializer` accepts `processing_fee` and `disbursement_account`, but `admin_loans_create` drops them.
- Only one finance test class (`PersistFinancialSnapshotsTests`); no coverage for interest, fund allocation, loan approval, FY lifecycle.
- `android-app/DATABASE_REFACTOR_ANDROID_PENDING.md` flags the Android app hasn't been updated for the rename/split.

---

## 4. Architectural principle going forward

**Single source of truth for every business action is a service function.** The panel HTML views, the REST API, and the future MCP server are all thin adapters.

```
                          ┌────────────────────────┐
                          │  Django ORM + Models   │
                          └────────────▲───────────┘
                                       │
                          ┌────────────┴───────────┐
                          │  accounts/services/    │  ← single source of truth
                          │   • financial_period   │
                          │   • interest_engine    │
                          │   • loans              │
                          │   • transactions       │
                          │   • vouchers           │
                          │   • instruments        │
                          │   • fees               │
                          │   • surplus            │
                          │   • exposure           │
                          │   • eligibility        │
                          └─┬────────┬───────────┬─┘
                            │        │           │
            ┌───────────────┘        │           └────────────────┐
            ▼                        ▼                            ▼
    ┌──────────────┐         ┌──────────────┐            ┌──────────────┐
    │ admin_portal │         │ accounts/    │            │ mcp_server   │
    │   views.py   │         │  api_views   │            │  (Phase C)   │
    │   (HTML)     │         │   (JSON)     │            │  (tools)     │
    └──────────────┘         └──────────────┘            └──────────────┘
       panel:8000               api:8001                   mcp:stdio/sse
```

Every change from Phase A onwards lands the new logic in `accounts/services/` and updates both adapters in lock-step.

---

## 5. The phased plan

### Phase 0 — Foundation (services layer) · complete

**Goal:** introduce `accounts/services/` and migrate the existing logic out of `admin_portal/views.py` and `accounts/api_views.py` into pure functions that both adapters call. No behaviour change.

- [ ] **0.1** Create `accounts/services/__init__.py` package skeleton.
- [ ] **0.2** Move `accounts/interest.py` → `accounts/services/interest.py` (preserve a deprecation shim).
- [x] **0.3** Extract loan flows into `accounts/services/loans.py`:
  - `create_loan_application(...)`
  - `approve_loan_application(...)` (creates `LoanAccount` + schedule)
  - `record_emi_payment(...)`
  - `has_unpaid_emi(...)` (moved from `admin_portal/views.py`; `_has_unpaid_emi` kept as alias).
- [x] **0.4** Extract transaction posting into `accounts/services/transactions.py`:
  - `post_transaction(...)` (single line, supports `loan_repayment_id` + `instrument`)
  - `post_transactions_bulk(...)` (multi-line direct posting + optional fund credit)
  - `post_voucher(...)` (multi-line via voucher staging)
- [x] **0.5** Extract financial-period helpers into `accounts/services/financial_period.py`:
  - `active()`, `overlapping(start, end)` (moved from `accounts/utils.py`; old names kept as backward-compat shims).
  - `default_indian_fy_bounds()`, `month_options_in_window()`, `quarter_ranges_in_window()`, `parse_month_key_in_window()` (moved from `admin_portal/portal_fy.py`; re-exported there for legacy importers).
  - Request-scoped FY helpers (session override, `report_dates_from_request`) stay in `admin_portal/portal_fy.py`.
- [x] **0.6** Refactor `admin_portal/views.py` to call the new services.
- [x] **0.7** Refactor `accounts/api_views.py` to call the same services.
- [x] **0.8** Service-level test coverage: `accounts/tests_services_loans.py` (14 tests) + `accounts/tests_services_transactions.py` (18 tests) — happy + sad paths for every public service function. Both files ruff-clean, all 32 pass.

**Exit criteria:** zero business logic lives in `views.py` files; both adapters compile to ~200-line dispatch layers.

---

### Phase A — Stabilize the diagram (after Phase 0)

**Goal:** every diagram element with a model gets a working end-to-end path. Fix the half-wires.

- [x] **A1. Loan disbursement is a real accounting event** (with A1.5 follow-up)
  - `approve_loan_application` now accepts `disbursement_account_id` + `processing_fee`, validates the account belongs to the borrower and is active, persists both fields on the new `LoanAccount`, and posts a `Transaction(transaction_type="credit", amount=principal)` to the disbursement account via `transaction_service.post_transaction` — all inside one `transaction.atomic()` block.
  - Cross-member or inactive disbursement account → `ValidationError("Disbursement account does not belong to the borrower.")`.
  - `LoanApplication` has **no** `processing_fee` / `disbursement_account` columns (only `LoanAccount` does). `create_loan_application` captures them in the audit description; **the caller must re-supply them at approval time**. The current `admin_loans_create` / `add_loan_view` forward at creation but the parallel `admin_loans_approve` / `approve_loan_view` adapters do NOT yet read them on the approve request — the disbursement Transaction therefore only posts when the panel/API approval payload carries them. Tracked as the **A1.5** follow-up below.
  - `InterestCalculatorService.calculate_flat_emi(principal, rate, months)` added (paise-quantised); both `LoanApplication.calculate_emi()` and `LoanAccount.calculate_emi()` now branch on `interest_type` and use the new helper for `"flat"`.
  - Optional `FeeCharge` for the processing fee deferred to Phase B4 (will route through the fee schedule there).
  - 6 new tests in `accounts/tests_services_loans.py` (20 total, all OK).
- [ ] **A1.5. Wire the approve adapters to forward `disbursement_account_id` + `processing_fee`**
  - Either (a) add the two columns to `LoanApplication` via a migration so they survive create→approve, or (b) make `admin_loans_approve` (REST) and `approve_loan_view` (panel) read them from the approval request and forward to `approve_loan_application(...)`. Pick (b) first — no schema churn.
- [ ] **A2. Instrument wired into every Transaction**
  - Add cheque / DD / NEFT / UPI / IMPS sub-fields to the transaction form, shown conditionally on `payment_mode`.
  - `services.transactions.post_transaction` creates an `Instrument` row when `payment_mode != "cash"`, links it to the Transaction.
  - Add `instrument` to `TransactionCreateSerializer` (nested write) and `TransactionSerializer` (read).
  - Surface instrument info on `get_transaction_view` JSON and the detail panel.
- [ ] **A3. Finish the Receipt → Transaction rename**
  - Rename `templates/admin/receipts.html` → `transactions.html`; rename `static/js/receipts.js` → `transactions.js`; update includes.
  - Drop the `_credit_transaction("receipt")` shim in `admin_portal/views.py`.
- [x] **A4. Loosen the voucher requirement**
  - Removed the "cash → forced voucher" branch in `admin_portal/views.py::add_transaction_view`. Vouchers are now opt-in (operator chooses via the `use_voucher` checkbox).
  - REST `admin_transactions_create` had no analogous branch — unchanged.
  - 2 new service-layer tests (cash without voucher; cash with explicit voucher); 20 tests in `tests_services_transactions` all OK.
  - Cheque/DD staging via `Instrument.is_cleared` still pending — picked up in A2.
- [x] **A5. FinancialPeriod lifecycle UI + REST**
  - `services.financial_period.open_period / continue_period / close_period` shipped — `close_period` `get_or_create`s a `ProfitAndLoss` for the period, sets `is_locked=True / locked_by=actor / locked_date=now()`, creates a `SocietyAccount` snapshot row (zero-default — Phase B engine will populate aggregates), flips the period to `status="closed", is_active=False`, and writes an `AuditLog`.
  - Status choices on `FinancialPeriod` are `open / closed / continuing` (no `archived`). `AuditLog` lacks `financial_period` entity / `close` action choices — using `entity_type="system" + action="approve"` as a documented fallback (small migration would unlock richer audit later).
  - REST: `GET / POST /api/v1/admin/financial-periods/`, `GET /…/current/`, `POST /…/<pk>/continue/`, `POST /…/<pk>/close/`. List + create share one URL via a thin `admin_financial_periods_dispatch` view.
  - Panel: `/finance/periods/` (orphan template promoted to a real page with open/continue/close action buttons).
  - 11 service tests in `accounts/tests_services_financial_period.py` (all OK); 51/51 service tests across loans + transactions + FY all green.
  - Auto-activate-next-FY-on-close still pending — operator currently picks the next FY explicitly via Continue.
- [ ] **A6. Distribute-profit uses the saved P&L**
  - `distribute_profit_view` + `admin_reports_distribute_profit` read `ProfitAndLoss.net_surplus` for the selected FY.
  - Allowed only when `is_locked=True`.
  - Reject on unlocked / missing snapshot.
- [ ] **A7. Tests for Phase A**
  - Disbursement creates a Transaction; Instrument captured; FY close locks P&L; distribute rejects unlocked.

**Exit criteria:** every diagram box has an end-to-end CRUD path; `python manage.py test` green; manual QA checklist refreshed.

---

### Phase B — Build the missing engine

**Goal:** turn the static models into a **running** system. Every accrual produces deterministic Transaction rows so the MCP layer in Phase C will be honest.

- [ ] **B1. Unified Interest Engine** — new `accounts/services/interest_engine.py`.
  - `accrue_deposits(period_start, period_end, financial_period)` — iterate active deposit accounts (CD, FD, **OD**, RD, share); call `InterestCalculatorService.daily_simple_interest`; create `Transaction(type="interest", transaction_date=period_end)` and `InterestPayout(status="credited", transaction=...)`.
  - `accrue_loans(period_start, period_end, financial_period)` — for each active `LoanAccount`, for each `LoanRepayment` due in the period, ensure an `InterestReceivable(status="accrued")` exists with `amount_accrued = repayment.interest_component`.
  - `run_full_engine(financial_period, as_of=today)` — one call, both sides, idempotent.
- [ ] **B2. Management command + cron hook**
  - `python manage.py run_interest_engine --period <fy_id> --as-of YYYY-MM-DD`.
  - Document a cron line for daily accrual.
- [ ] **B3. EMI ↔ Receivable reconciliation**
  - `record_emi_payment` flips matching `InterestReceivable.status="collected"`, sets `collected_date`, links the Transaction.
  - Replace ad-hoc `mark_interest_receivable_collected_for_repayment` with the engine-aware version.
- [ ] **B4. Fees become automatic**
  - Approval applies active `FeeSchedule(fee_type="processing")` → `FeeCharge` → Transaction.
  - Overdue EMI past N days applies `late_payment` schedule.
  - Account opening / annual rollover applies `membership` / `annual_maintenance`.
- [ ] **B5. Society Main Account becomes derived**
  - `GET /api/v1/admin/society/main-account` computes live totals from Transactions + InterestPayable + InterestReceivable + FeeCharge, plus the latest `SocietyAccount` snapshot for comparison.
- [ ] **B6. Setup-wizard seeding**
  - Two new steps: **Open first FinancialPeriod**, **Seed statutory funds + allocation rules** (Statutory Reserve 25%, Education 1.5%, Build/Service, Bad-debt Provision, Dividend).
  - On finalize: create 1 `FinancialPeriod`, 5 `FundAccount`s, 5 `FundAllocationRule(trigger_event="annual_profit")` rows.
- [x] **B7. Member-exposure service**
  - `accounts/services/exposure.py::get_member_exposure(user)` and `get_member_exposure_by_id(user_id)` ship the snapshot dict: `share_capital`, `deposits`, `od_drawn`, `loan_outstanding`, `guarantee_contingent`, `fees_outstanding`, `net_exposure` — all 2-dp `Decimal`.
  - 7 tests in `accounts/tests_services_exposure.py` (all OK); existing 40 service tests green.
  - Field-name corrections vs roadmap brief: `MemberAccount.status="active"` (not `is_active`); `Guarantor.user` FK (not `member_user`); `LoanAccount.outstanding_balance` exists; `FeeCharge.status` has `charged/waived/refunded` only — filter defensively includes `pending` for Phase B4.
  - REST endpoint `GET /api/v1/admin/members/{id}/exposure` and member-detail UI panel still pending — picked up after A5's API-routing work lands.
- [x] **B8. Loan-eligibility pre-check service**
  - `accounts/services/eligibility.py::check_loan_eligibility(user=, loan_type=, principal_amount=)` and `check_loan_eligibility_by_id(...)` return `{approvable, reasons, exposure}`.
  - Checks: member role + not soft-deleted; `eligible_for_loans`; KYC verified (via `MemberKYC.kyc_status`, fallback to legacy `User.kyc_status`); no overdue EMI (`loan_service.has_unpaid_emi`); `LoanTypeConfiguration` active; `principal_amount > 0`; active FinancialPeriod exists; projected exposure ≤ ceiling (deposits + share_capital, or 50L fallback) — pulls `exposure.get_member_exposure` via `try/except ImportError`.
  - All 7 checks accumulate (no short-circuit), so the operator sees the full list of failed conditions.
  - 11 tests in `accounts/tests_services_eligibility.py`, all OK; existing 40 service tests still green (51 total).
  - Note: `LoanTypeConfiguration` has no `min_amount/max_amount` columns today; bounds check is a forward-compat hook.
  - REST endpoint + live "Eligibility check" panel still pending — picked up after A5's API-routing patterns are settled.
- [ ] **B9. Surplus distribution service**
  - `accounts/services/surplus.py::distribute_surplus(fy, surplus_amount, dry_run=False)` → per-fund breakdown from `FundAllocationRule(trigger_event="annual_profit")` with priority & caps.
  - When committed: posts a journal Voucher debiting Surplus and crediting each fund.
- [ ] **B10. Tests**
  - Engine idempotency; cross-product coverage (CD + FD + OD + RD + Loan in one run); surplus distribution against locked P&L; fee auto-charging.

**Exit criteria:** `python manage.py run_interest_engine` produces deterministic, audit-logged Transactions across all account types; FY close → P&L lock → distribute → fund credit happens via service calls (not view-internal logic).

---

### Phase C — Expose Panel ERP as an MCP server

Now that every business action sits behind a service, MCP becomes a thin protocol layer. Lives in a **new top-level package** so it can be containerised independently from the panel and the API.

- [ ] **C1. Stack + skeleton**
  - New top-level Django app `mcp_server/` using the official Python `mcp` SDK (FastMCP-style).
  - Runs as a **separate process** importing the Django app via `DJANGO_SETTINGS_MODULE=config.settings_api`.
  - `docker-compose.yml` adds `mcp` service sharing the same Postgres.

- [ ] **C2. Resources — `panelerp://`**

  | URI | Backed by |
  |---|---|
  | `panelerp://financial-period/current` | `services.financial_period.active()` |
  | `panelerp://members/{id}` | `UserDetailSerializer` |
  | `panelerp://members/{id}/share-capital` | `ShareCapital.objects.filter(user_id=…)` |
  | `panelerp://members/{id}/guarantors` | `Guarantor.objects.filter(user_id=…)` |
  | `panelerp://accounts/{id}/{cd\|fd\|od\|rd}` | `MemberAccount` filtered by type |
  | `panelerp://loans/{id}/application` | `LoanApplicationDetailSerializer` |
  | `panelerp://loans/{id}/account` | `LoanDetailSerializer` |
  | `panelerp://loans/{id}/schedule` | `LoanRepayment` list |
  | `panelerp://transactions/{id}` | `TransactionSerializer` |
  | `panelerp://vouchers/{id}` | `VoucherSerializer` |
  | `panelerp://instruments/{id}` | `Instrument` |
  | `panelerp://society/main-account` | live aggregation + latest snapshot |

- [ ] **C3. Tools — thin wrappers over Phase B services**
  ```
  calculate_interest(account_id, period_start, period_end)
  open_financial_year(label, start_date, end_date)
  close_financial_year(fy_id)
  create_loan_application(member_id, amount, type, tenure)
  approve_loan(application_id, approver_id)
  disburse_loan(loan_account_id, disbursement_account_id)
  generate_repayment_schedule(loan_account_id)
  mark_emi_paid(schedule_id, emi_no, instrument_payload)
  post_transaction(account_id, voucher_type, amount, instrument_payload)
  compute_net_surplus(fy_id)
  distribute_surplus(fy_id)
  ```
  Each tool returns `{success, data, audit_log_id}`.

- [ ] **C4. Prompts**
  ```
  member_total_exposure(member_id)
  is_loan_approvable(application_id)
  monthly_interest_payouts(period)
  society_net_position(fy_id)
  ```
  Compose Resources + Tools — no new business logic.

- [ ] **C5. Auth + audit**
  - API key (env `PANELERP_MCP_API_KEY`).
  - Per-key Django user binding.
  - Every tool call → `AuditLog(description="via MCP …")`.

- [ ] **C6. Docs + tests**
  - `mcp_server/tests/` runs each tool against the Django test DB.
  - `MCP.md` documents how to point Cursor / Claude Desktop at the server (stdio + URL).

**Exit criteria:** an agent can answer *"What's member MEM-2026-0027's total exposure?"* and execute *"Distribute FY 2025-26 surplus"* with full audit trail.

---

### Phase D — Polish

- [x] **D1.** ~~Update `android-app/`~~ → Android app archived to `legacy/android-app/` (with `member_portal`, OTP/device endpoints, and OTP email templates). Revival instructions in `legacy/README.md`.
- [ ] **D2.** Pagination + caching on `panelerp://society/main-account` (it scans everything).
- [ ] **D3.** Replace `accounts/utils.get_financial_summary`'s computed deposit liability with real sums from `InterestPayout` once the engine is the source of truth.
- [ ] **D4.** Refresh `DATABASE.md` (still describes 15 pre-refactor models), `API_DOCUMENTATION.md`, `README.md`.
- [ ] **D5.** End-to-end smoke script: open FY → onboard member → open accounts → disburse loan → run engine → close FY → distribute surplus.

---

## 6. Execution order

```
Phase 0  →  Phase A  →  Phase B  →  Phase C  →  Phase D
foundation  stabilize    engine     MCP        polish

0.1-0.8     A1, A2, A3   B1 → B2 → B3 → B4 → B5
            A4, A5, A6                    │
            A7                            ▼
                                B6, B7, B8, B9, B10  (parallel)
                                          │
                                          ▼
                                 C1 → C2 → C3 → C4 → C5 → C6
                                          │
                                          ▼
                                          D
```

Why this order:
- **Phase 0 first** — otherwise A1 puts loan disbursement logic inside `admin_portal/views.py` again and we'd refactor it twice.
- **A1 before B1** — engine creates Transactions; Transactions need real Instruments and disbursement plumbing first.
- **A6 before B9** — surplus distribution must read the saved P&L, not live aggregates.
- **B6–B9 parallel** — independent once B1–B5 are stable.
- **C waits for B** — MCP tools should not lie about half-wired services.

---

## 7. Status

Last updated: 2026-05-13. Update this line and tick boxes above as work lands.

- Database refactor (Phases 1–4 of `DATABASE_REFACTOR_PLAN.md`) — ✅ done
- Deployment split (panel + api containers) — ✅ done
- Phase 0 (services layer) — 🟡 in progress
- Phase A (stabilize) — ⚪ not started
- Phase B (engine) — ⚪ not started
- Phase C (MCP) — ⚪ not started
- Phase D (polish) — ⚪ not started
