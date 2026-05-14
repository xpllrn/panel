# Panel ERP — Roadmap

> Single source of truth for what's done, what's next, and what blocks what.
> Edit this file as work lands.

---

## ⚡ TL;DR

| Phase | What it ships | Status |
|---|---|---|
| 0 | Services layer (`accounts/services/`) shared by panel + API | ✅ Done |
| A | Stabilize the diagram — instruments, FY lifecycle, locked-P&L distribute | ✅ Done |
| **B** | **Running engine — interest, fees, society live totals, surplus posting** | **🟡 In progress — B1, B2, B3, B4, B5, B6, B7, B8 done** |
| C | MCP server (Panel ERP as tools for AI agents) | ⚪ Not started |
| D | Polish — docs, smoke script, perf | 🟡 D1 done |

**👉 Next up: Phase B9 — Surplus distribution service.** `services/surplus.py` posts journal voucher debiting Surplus / crediting funds.

---

## Status legend

| Symbol | Meaning |
|---|---|
| ✅ | Done — shipped, tested |
| 🟡 | In progress / partial |
| ⚪ | Not started |
| ❌ | Blocked / awaiting decision |

Last updated: 2026-05-14.

---

## 🗺️ What's left, in plain language

1. **B9, B10** — surplus voucher posting, cross-product tests.
2. **B7/B8 follow-ups** — REST endpoints + UI panels for the already-shipped exposure & eligibility services.
3. **Phase C — MCP server** — only after B1–B5 are real (MCP tools shouldn't lie about half-wired services). ✅ B5 done — MCP unblocked.
4. **Phase D — Polish** — refresh `DATABASE.md` / `README.md`, smoke script, pagination + caching.

---

## 📐 1. Target architecture

Five layers from the cooperative-society banking diagram. Every box must be backed by a model, a service function, a UI/API surface, and an audit trail.

```
L1 — Period & people
   Financial Period (open / close / continue)
   Share Capital · Member (KYC + nominees) · Guarantor

L2 — Member products
   CD · FD · OD · RD / Savings
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
        ├── Interest Payable (to depositors)   — subtract
        ├── Interest Receivable (from loans)   — add
        ├── Fees & Charges                     — add
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

## 🏗️ 2. Deployment architecture (already in place)

Two independent processes share one PostgreSQL database. Security and reuse boundary: an HTML bug on the panel cannot reach the API, and the API serves Android, future clients, and the upcoming MCP server.

| Service | Container | Port | Settings | URLconf | Notes |
|---|---|---|---|---|---|
| **panel** | `panel` | 8000 | `config.settings` | `config.urls_panel` | Staff HTML, Django admin, setup wizard. Owns migrations. |
| **api** | `api` | 8001 | `config.settings_api` | `config.urls_api` | Pure REST `/api/v1/`. No HTML, no auto-login. |
| **db** | `db` | 5433→5432 | — | — | PostgreSQL 15. Shared. |

---

## 🧱 3. Where we are vs the diagram (scorecard)

DB refactor (Phases 1–4 of `DATABASE_REFACTOR_PLAN.md`) is ✅ complete. All 28 models exist. The remaining gap is **wiring** — services + UI + API + audit — for the engine and MCP.

| Diagram element | Model | UI | API | Service | Status |
|---|---|---|---|---|---|
| Financial Period (open/close/continue) | ✅ | ✅ `/finance/periods/` | ✅ | ✅ | ✅ A5 |
| Member · KYC · Nominee · Address · Share Capital | ✅ | ✅ | ✅ | ✅ | ✅ |
| Guarantor | ✅ | 🟡 single row | 🟡 partial | ❌ multi-guarantor | 🟡 |
| Deposits (CD/FD/RD/OD/share) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Interest Engine — deposits | ✅ math | ✅ button | ✅ POST endpoint | ✅ B1 `interest_engine.accrue_deposits` (shared by panel + API) | ✅ |
| Interest Engine — loans | ✅ `InterestReceivable` | ✅ sync button → engine | ✅ sync endpoint → engine | ✅ B1 `interest_engine.accrue_loans` (`sync_loan_interest_receivables` shim) | ✅ |
| Loan Application → Account → Schedule | ✅ | ✅ | ✅ | ✅ A1 disbursement posts | ✅ |
| Transaction | ✅ | ✅ | ✅ | ✅ | ✅ |
| Voucher (4 types) | ✅ | ✅ | ✅ | ✅ A4 cash optional | ✅ |
| Instrument (cheque/DD/NEFT/UPI/IMPS) | ✅ | ✅ panel + voucher + modal | ✅ nested serializer | ✅ A2 shared across bulk + voucher transfer | ✅ |
| Society Main Account | ✅ snapshot + live | ✅ | ✅ `GET /…/society/main-account` | ✅ `services/society.py` | ✅ B5 |
| Interest Payable / Receivable / Fees | ✅ | 🟡 receivable manual, fees register | 🟡 | ✅ `FeeCharge` auto via `services/fees.py` | **B5** (society totals) |
| Net Surplus (P&L) | ✅ | ✅ saved snapshot | ✅ | ✅ A6 distribute reads locked snapshot | ✅ |
| 5-bucket distribution | ✅ rules | 🟡 manual rule creation | 🟡 | ❌ wizard doesn't seed funds | **B6** |
| Member exposure / loan eligibility | ✅ | ❌ no panels | ❌ no REST | ✅ B7 / B8 services + tests | 🟡 needs surfaces |
| MCP server | ❌ | ❌ | ❌ | ❌ | **Phase C** |

### Other lingering issues
- Setup wizard does not create the **first FinancialPeriod** or seed **statutory FundAccounts** (Phase B6).
- `DATABASE.md` / `API_DOCUMENTATION.md` lag the schema and routes (Phase D4).
- Member portal, Android app, OTP + member REST routes archived under `legacy/` — see `legacy/README.md`.

---

## 🧭 4. Architectural principle

**Single source of truth for every business action is a service function.** The panel HTML views, the REST API, and the future MCP server are all thin adapters.

```
                          ┌────────────────────────┐
                          │  Django ORM + Models   │
                          └────────────▲───────────┘
                                       │
                          ┌────────────┴───────────┐
                          │  accounts/services/    │  ← single source of truth
                          │   • financial_period   │
                          │   • interest           │  pure math
                          │   • interest_engine    │  ← Phase B1
                          │   • loans              │
                          │   • transactions       │  (handles vouchers + instruments)
                          │   • exposure           │
                          │   • eligibility        │
                          │   • fees               │  ← Phase B4
                          │   • surplus            │  ← Phase B9
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

## 🚦 5. Phases at a glance

### Phase B (current) — Build the missing engine

| ID | Title | Status | Why it matters |
|---|---|---|---|
| **B1** | Unified Interest Engine | ✅ | `accounts/services/interest_engine.py` (`accrue_deposits` / `accrue_loans` / `run_full_engine`). Panel + REST adapters delegate. 15 new tests, all green. New `internal` payment mode + migration 0037. |
| **B2** | Management command + cron hook | ✅ | `python manage.py run_interest_engine [--period <fy>] [--as-of <date>] [--deposits-only \| --loans-only]`. 9 new tests. Cron line documented. |
| **B3** | EMI ↔ Receivable reconciliation | ✅ | `interest_engine.reconcile_emi_to_receivable(repayment, transaction=...)`. Both `record_emi_payment` and `_settle_loan_repayment` (the `post_transaction(loan_repayment_id=...)` path) reconcile now. Handles "paid before accrual" by creating the receivable already-collected. New `InterestReceivable.transaction` FK + migration 0038. 15 new tests. |
| **B4** | Fees become automatic | ✅ | Approval / overdue / opening / rollover post `FeeCharge` via `FeeSchedule`. |
| B5 | Society Main Account becomes derived | ✅ | `GET /api/v1/admin/society/main-account` computes live totals + compares snapshot. |
| B6 | Setup-wizard seeding | ✅ | `_finalize_setup` idempotently seeds the current Indian FY's `FinancialPeriod`, 5 statutory `FundAccount` rows, and 5 `annual_profit` `FundAllocationRule` rows (totalling 100%). Operator edits to pre-existing rows are preserved. 5 new tests. |
| B7 | Member-exposure service | ✅ | `services/exposure.py` + 7 tests. **REST + UI panel still pending.** |
| B8 | Loan-eligibility pre-check service | ✅ | `services/eligibility.py` + 11 tests. **REST + UI panel still pending.** |
| B9 | Surplus distribution service | ⚪ | `services/surplus.py` posts journal voucher debiting Surplus / crediting funds. |
| B10 | Cross-product engine + fee + surplus tests | ⚪ | Idempotency, CD+FD+OD+RD+Loan in one run, locked-P&L distribute, auto-fees. |

**Exit:** `python manage.py run_interest_engine` produces deterministic, audit-logged Transactions across all account types; FY close → P&L lock → distribute → fund credit happens via service calls (not view-internal logic).

### Phase C — MCP server

After Phase B lands. Skeleton steps (see §6 for details):
C1 stack/skeleton · C2 resources (`panelerp://…`) · C3 tools · C4 prompts · C5 auth + audit · C6 docs + tests.

**Exit:** an agent can answer *"What's member MEM-2026-0027's total exposure?"* and execute *"Distribute FY 2025-26 surplus"* with full audit trail.

### Phase D — Polish

| ID | Title | Status |
|---|---|---|
| D1 | Archive Android app + member portal + OTP/device endpoints | ✅ Done — see `legacy/README.md` |
| D2 | Pagination + caching on `panelerp://society/main-account` | ⚪ |
| D3 | Replace `accounts/utils.get_financial_summary`'s computed deposit liability with real `InterestPayout` sums | ⚪ |
| D4 | Refresh `DATABASE.md`, `API_DOCUMENTATION.md`, `README.md` | ⚪ |
| D5 | End-to-end smoke script: open FY → onboard → accounts → disburse → engine → close → distribute | ⚪ |

---

## 🧪 6. Phase C (MCP) — detailed plan

- [ ] **C1. Stack + skeleton.** New top-level Django app `mcp_server/` using the official Python `mcp` SDK (FastMCP-style). Runs as a separate process importing the Django app via `DJANGO_SETTINGS_MODULE=config.settings_api`. `docker-compose.yml` adds `mcp` service sharing the same Postgres.
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

- [ ] **C5. Auth + audit.** API key (env `PANELERP_MCP_API_KEY`). Per-key Django user binding. Every tool call → `AuditLog(description="via MCP …")`.

- [ ] **C6. Docs + tests.** `mcp_server/tests/` runs each tool against the Django test DB. `MCP.md` documents how to point Cursor / Claude Desktop at the server (stdio + URL).

---

## 🔁 7. Execution order

```
Phase 0  ─►  Phase A  ─►  Phase B  ─►  Phase C  ─►  Phase D
   ✅          ✅       (in progress)   (unblocked) (queued)

Phase B sequencing:
  B1 ─► B2 ─► B3 ─► B4 ─► B5 ─► (B6, B9) ─► B10
  ✅    ✅    ✅    ✅    ✅    ✅ ▲
                                     │
                                     └── you are here  B9 still open
                                                       B7, B8 services landed early; REST + UI later
```

Why this order:
- **B1 first** — every later track (B3, B5, B9, MCP) needs the engine to be the source of truth.
- **B4 before B5** — society totals should include auto-posted fees, not be patched after.
- **B6 before B9** — surplus distribution needs the 5 funds + rules to exist out of the box.
- **C waits for B** — MCP tools must not lie about half-wired services.

---

## 📜 8. Phase history (completed work)

<details>
<summary><strong>Phase 0 — Foundation (services layer) · ✅ complete</strong></summary>

Goal: introduce `accounts/services/` and migrate existing logic into pure functions both adapters call. No behaviour change.

- [x] 0.1 Create `accounts/services/__init__.py` package skeleton.
- [x] 0.2 Move `accounts/interest.py` → `accounts/services/interest.py` (deprecation shim kept).
- [x] 0.3 Extract loan flows → `accounts/services/loans.py` (`create_loan_application`, `approve_loan_application`, `record_emi_payment`, `has_unpaid_emi`).
- [x] 0.4 Extract transaction posting → `accounts/services/transactions.py` (`post_transaction` single line + `loan_repayment_id` + `instrument`, `post_transactions_bulk`, `post_voucher`).
- [x] 0.5 Extract financial-period helpers → `accounts/services/financial_period.py` (`active`, `overlapping`, FY bounds + month/quarter window helpers; request-scoped helpers stay in `admin_portal/portal_fy.py`).
- [x] 0.6 Refactor `admin_portal/views.py` to call the new services.
- [x] 0.7 Refactor `accounts/api_views.py` to call the same services.
- [x] 0.8 Service-level test coverage: `tests_services_loans.py` (14) + `tests_services_transactions.py` (18) — happy + sad paths.

**Stretch (not a gate, ongoing):** migrate *all* remaining business logic out of `admin_portal/views.py` / `accounts/api_views.py` so both shrink to thin dispatch layers (~200 lines each). Reports, setup wizard, exports still live in views.
</details>

<details>
<summary><strong>Phase A — Stabilize the diagram · ✅ complete</strong></summary>

Every diagram element with a model gained a working end-to-end path. Half-wires fixed.

- [x] **A1. Loan disbursement is a real accounting event.** `approve_loan_application` accepts `disbursement_account_id` + `processing_fee`, validates ownership + active status, persists on `LoanAccount`, and posts a `Transaction(transaction_type="credit", amount=principal)` to the disbursement account via `transaction_service.post_transaction` — all inside one `transaction.atomic()`. Cross-member / inactive → `ValidationError`. `InterestCalculatorService.calculate_flat_emi(...)` added; flat-vs-reducing branch wired on both `LoanApplication.calculate_emi()` and `LoanAccount.calculate_emi()`. Optional `FeeCharge` for processing fee deferred to B4. 6 new tests (20 total).
- [x] **A1.5. Approve adapters forward `disbursement_account_id` + `processing_fee`.** `admin_loans_approve` reads JSON body; `approve_loan_view` reads POST. Invalid id → 400. Approve dialog includes optional fields. Values are re-entered (no LoanApplication columns).
- [x] **A2. Instrument wired into every Transaction.** `post_transaction` / `post_transactions_bulk` / `post_voucher` create an `Instrument` when `payment_mode != "cash"`. Bulk + voucher share **one** instrument (`amount` = sum of lines). `transfer_voucher_to_fund_view` reuses voucher instrument on each posted row. Panel: cheque / DD / UPI / NEFT-RTGS-online / IMPS fields; `get_transaction_view` includes `instrument`. REST: nested `instrument` on `TransactionCreateSerializer` (write) and `TransactionSerializer` (read); admin list/detail `select_related("instrument")`. `Transaction.PAYMENT_MODE_CHOICES` includes `dd` and `imps`.
- [x] **A3. Receipt → Transaction rename.** `templates/admin/transactions.html`, `static/js/transactions.js`, `static/css/pages/transactions.css`; `transactions_view` renders the new template. Optional cosmetic follow-ups: `total_receipts` label / modal copy / JS `receiptModal` ID renames.
- [x] **A4. Voucher requirement loosened.** Removed "cash → forced voucher" branch in `add_transaction_view`. Vouchers opt-in via the `use_voucher` checkbox. REST `admin_transactions_create` had no analogous branch — unchanged. 2 new tests. Cheque/DD staging via `Instrument.is_cleared` still pending (clearing UI).
- [x] **A5. FinancialPeriod lifecycle UI + REST.** `services.financial_period.open_period / continue_period / close_period`; `close_period` `get_or_create`s a `ProfitAndLoss`, sets `is_locked=True / locked_by / locked_date`, creates a zero-default `SocietyAccount` snapshot (B engine populates aggregates), flips period to `status="closed", is_active=False`, writes `AuditLog`. REST: `GET / POST /api/v1/admin/financial-periods/`, `GET /…/current/`, `POST /…/<pk>/continue/`, `POST /…/<pk>/close/`. Panel: `/finance/periods/`. 11 service tests; 51/51 green. Auto-activate-next-FY-on-close still pending.
- [x] **A6. Distribute-profit uses the saved P&L.** `distribute_profit_view` and `admin_reports_distribute_profit` require a `ProfitAndLoss` row for the resolved `FinancialPeriod`, reject when missing or `is_locked=False`, and pass `net_surplus` into `apply_fund_allocations(..., "annual_profit", ...)`. Panel posts `financial_period_id`; button enabled only when snapshot exists, is locked, and `net_surplus > 0`. API body prefers `financial_period_id`; else `year` resolves overlap.
- [x] **A7. Tests for Phase A.** `tests_phase_a_integration.py` — locked vs unlocked distribute. `admin_portal.tests.VoucherFlowTests` — NEFT voucher creates `Voucher.instrument`; transfer attaches same instrument to posted rows. `tests_services_transactions.py` — voucher instrument coverage.

</details>

<details>
<summary><strong>Phase B partial — B1 / B2 / B3 / B4 / B5 / B6 / B7 / B8 · ✅ complete</strong></summary>

- [x] **B1. Unified Interest Engine.** New `accounts/services/interest_engine.py` with three public entry points:
  - `accrue_deposits(*, as_of=, financial_period=, actor=, ip_address=, audit_via=)` — iterates active deposit accounts (CD/FD/RD/Sukanya/Suputra; `share` + `od` excluded), calls `InterestCalculatorService.daily_simple_interest`, posts via `transaction_service.post_transaction(transaction_type="interest", payment_mode="internal", transaction_date=as_of)` (one TXN number, balance bump, no `Instrument`), bumps `accrued_interest` + `last_interest_calc_date`, creates `InterestPayout(status="credited")`, writes one aggregated `AuditLog`.
  - `accrue_loans(*, as_of=, financial_period=, actor=, audit_via=)` — `get_or_create`s `InterestReceivable` rows for unpaid `LoanRepayment.due_date <= as_of`. Refreshes `amount_accrued` if the EMI's `interest_component` changes. Returns `{installments_considered, rows_created, rows_updated, as_of}`.
  - `run_full_engine(...)` — both sides in one `transaction.atomic()`. Idempotent for a given `as_of`.

  **Engine plumbing:** `_instrument_type_for_payment_mode` now treats `internal` as no-instrument (alongside `cash`). New `("internal", "Internal Transfer")` added to `Transaction.PAYMENT_MODE_CHOICES`. Migration **0037** re-syncs the choice list for `Transaction.payment_mode`, `Voucher.payment_mode`, and `LoanRepayment.payment_mode` (the last two were still on the pre-0036 snapshot).

  **Adapters refactored to delegate:**
  - `admin_portal.views.post_interest_view` → `interest_engine.accrue_deposits(...)` (panel).
  - `accounts.api_views.admin_post_interest` → same service; per-payout push/email notifications fired by the adapter after the engine returns.
  - `accounts.utils.sync_loan_interest_receivables` → thin shim around `interest_engine.accrue_loans` (panel "Sync receivables" button + REST endpoint unchanged externally).

  **Tests:** 15 new tests in `accounts/tests_services_interest_engine.py` — deposit happy path / audit summary / exclusions (share, OD, zero rate, frozen, soft-deleted, zero balance) / window from `last_interest_calc_date` / idempotency; loan create / idempotency / skip-paid / skip-future / refresh-on-change; full-engine runs both sides and is idempotent.

- [x] **B2. Management command + cron hook.** `accounts/management/commands/run_interest_engine.py` — thin wrapper around `interest_engine.run_full_engine` with `--as-of YYYY-MM-DD`, `--period <fy_id>`, `--deposits-only`, `--loans-only` (mutually exclusive). Validates date format and FY id; raises `CommandError` for both bad inputs. Stdout prints one summary line per side (`[deposits]` / `[loans]`) so the cron log is grep-friendly. Documented cron line in the module docstring. 9 new tests in `accounts/tests_management_run_interest_engine.py` — default invocation, each flag combo, as-of in past, bad as-of, explicit period, missing period, idempotency.

- [x] **B3. EMI ↔ Receivable reconciliation.** New engine helper `interest_engine.reconcile_emi_to_receivable(repayment, *, transaction=None, financial_period=None)`. Both EMI-settlement paths now reconcile:
  - `accounts/services/loans.py::record_emi_payment` (explicit "Record EMI payment" admin flow).
  - `accounts/services/transactions.py::_settle_loan_repayment` (the `post_transaction(loan_repayment_id=...)` path; previously did NOT reconcile — fixed).

  Behaviour matrix:

  | Pre-existing receivable | After full EMI payment |
  |---|---|
  | none | New row, `status="collected"`, `amount_accrued = amount_collected = interest_component`, transaction linked. |
  | `status="accrued"` | Flipped to `collected`, `amount_collected = amount_accrued`, transaction linked. |
  | `status="collected"` (no txn) | Idempotent; back-fills `transaction` if it was missing. |
  | `status="collected"` (with txn) | No-op. |
  | `status="written_off"` | Left untouched. |

  Partial payments and `interest_component <= 0` repayments are no-ops. New `InterestReceivable.transaction` FK (migration 0038, `on_delete=SET_NULL`, `related_name="interest_receivables_settled"`) lets reports / future MCP tools trace which `Transaction` collected which accrual. `accounts/utils.mark_interest_receivable_collected_for_repayment` kept as a thin shim that delegates to the engine. 15 new tests in `accounts/tests_phase_b3_emi_receivable.py` covering the full behaviour matrix on both EMI paths and the legacy shim.

- [x] **B4. Fees become automatic.** New `accounts/services/fees.py` with six public entry points:
  - `resolve_active_fee_schedule(fee_type, applies_to, as_of)` — picks the most recent active `FeeSchedule` whose `effective_date <= as_of`.
  - `compute_fee_amount(schedule, base=None)` — resolves flat `amount` or `percentage * base / 100`.
  - `apply_processing_fee(loan_account, *, actor, ip_address, audit_via)` — posts `FeeCharge` + debit `Transaction` on loan approval. Uses the operator-typed `processing_fee` if set, else falls back to the schedule. Idempotent per `LoanAccount`.
  - `apply_membership_fee(user, *, member_account, actor, ...)` — posts a membership fee once per user per FY. Idempotent per `(user, fee_type, financial_period)`.
  - `apply_late_payment_fees(*, as_of, grace_days, financial_period, ...)` — daily sweep: one `late_payment` `FeeCharge` per overdue EMI past grace. Idempotent via `FeeCharge.loan_repayment` FK.
  - `apply_annual_maintenance_fees(*, financial_period, ...)` — yearly sweep: one `annual_maintenance` `FeeCharge` per active member per FY. Idempotent per `(user, fee_type, financial_period)`.

  **Schema (migration 0039):** `FeeCharge.loan_repayment` FK (late-fee idempotency key), `FeeCharge.financial_period` FK (annual-fee idempotency key), `FeeCharge.STATUS_CHOICES += ("pending",)` (for charges without a debit account), `SocietyConfiguration.late_fee_grace_days` (operator-tunable grace period), `AuditLog.ENTITY_CHOICES += ("fee",)`.

  **Wiring:**
  - `approve_loan_application` calls `fee_service.apply_processing_fee(acct, ...)` inside the existing atomic block after the disbursement Transaction.
  - `admin_portal.views.add_account_view` and `accounts.api_views.admin_accounts_create` call `fee_service.apply_membership_fee(user, ...)` after account creation.
  - New management command `python manage.py apply_fees --late [--annual] [--as-of YYYY-MM-DD] [--grace-days N] [--period ID]` for cron scheduling.

  **Tests:** 28 new tests in `accounts/tests_services_fees.py` (schedule resolution, processing fee, membership fee, late-payment sweep, annual maintenance sweep — happy paths + idempotency + edge cases) + 9 tests in `accounts/tests_management_apply_fees.py` (command flags, error handling, idempotency).

- [x] **B5. Society Main Account becomes derived.** New `accounts/services/society.py` with two public entry points:
  - `compute_live_position(financial_period=None)` — aggregates live totals from the database: `total_member_deposits` (active non-share/OD accounts), `total_loan_outstanding` (active loans), `total_interest_payable` (accrued_interest on deposits), `total_interest_receivable` (accrued IR rows: accrued - collected), `total_fees_collected` (charged FeeCharge in FY), `total_fund_balance` (all FundAccount balances), `net_surplus` (receivable + fees - payable).
  - `get_main_account(financial_period=None)` — returns `{live, snapshot, drift, financial_period, snapshot_stale}`. Drift is field-by-field `live - snapshot`. `snapshot_stale=True` when any drift is non-zero.

  **REST endpoint:** `GET /api/v1/admin/society/main-account[?financial_period_id=N]` — returns the live position, stored `SocietyAccount` snapshot, and drift comparison. Serializes Decimal values to strings for JSON safety.

  **Tests:** 10 new tests in `accounts/tests_services_society.py` — empty DB zeros, deposit aggregation, loan outstanding, interest receivable, fees collected, fund balances, no-snapshot stale, snapshot-matches-live, drift detection, financial period metadata.

- [x] **B6. Setup-wizard seeding** (parallel subagent). Extended `accounts/views.py::_finalize_setup` inside the existing `transaction.atomic()` block to seed, idempotently:
  - **1 `FinancialPeriod`** — current Indian FY (April–March), label `"FY YYYY-YY"`, `status="open"`, `is_active=True`. Resolves `fy_start_year` from `timezone.localdate()` (current year if month ≥ 4, else previous year). Uses `get_or_create` on `(start_date, end_date)` so it honours the existing `unique_together` and never flips a pre-existing period.
  - **5 statutory `FundAccount` rows** — Statutory Reserve (`fund_type="statutory"`), Education (`education`), Build/Service (`welfare`), Bad-debt Provision (`reserve`), Dividend (`dividend`). Account numbers are deterministic and year-stamped (`FND-<fy_start_year>-{SR,ED,BS,BD,DV}001`). `get_or_create(account_number=..., defaults=...)` so operator-edited rows are preserved.
  - **5 `FundAllocationRule(trigger_event="annual_profit")`** — Statutory Reserve 25%, Education 1.5%, Build/Service 10%, Bad-debt Provision 2%, Dividend 61.5% (total 100%); all `allocation_type="percentage"`, ascending `priority_order`. `get_or_create(trigger_event=..., fund=...)` so operator-tuned rules survive re-finalize.

  Two module-level constants (`STATUTORY_FUNDS`, `STATUTORY_ALLOCATIONS`) keep the defaults editable in one spot. **No wizard UX change** — the 7-step screen flow is untouched; seeding is silent on finalize. 5 new tests in `accounts/tests_setup_wizard_seeding.py` — FY shape / fund details / rule totals / idempotency / operator-edit preservation. **186/186 total tests green.**

- [x] **B7. Member-exposure service.** `accounts/services/exposure.py::get_member_exposure(user)` and `get_member_exposure_by_id(user_id)` ship the snapshot dict: `share_capital`, `deposits`, `od_drawn`, `loan_outstanding`, `guarantee_contingent`, `fees_outstanding`, `net_exposure` — all 2-dp `Decimal`. 7 tests. Field corrections vs the original brief: `MemberAccount.status="active"` (not `is_active`); `Guarantor.user` FK (not `member_user`); `LoanAccount.outstanding_balance` is the column; `FeeCharge.status` lacks a `pending` choice (filter defensively includes it for B4). REST `GET /api/v1/admin/members/{id}/exposure` + member-detail UI panel still pending.
- [x] **B8. Loan-eligibility pre-check service.** `accounts/services/eligibility.py::check_loan_eligibility(user=, loan_type=, principal_amount=)` and `check_loan_eligibility_by_id(...)` return `{approvable, reasons, exposure}`. Checks: member role + not soft-deleted; `eligible_for_loans`; KYC verified; no overdue EMI; active `LoanTypeConfiguration`; `principal_amount > 0`; active FinancialPeriod; projected exposure ≤ ceiling (deposits + share_capital, or 50L fallback). All 7 checks accumulate (operator sees full list of failed conditions). 11 tests. `LoanTypeConfiguration` has no `min_amount/max_amount` columns; bounds check is a forward-compat hook. REST + UI surfaces still pending.

</details>

---

## 🧾 9. Companion docs

| File | What's in it |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | Coding conventions (no type hints, FBVs only, ruff, validators, JSON shape) |
| `DATABASE.md` | Current schema reference — **needs refresh** (Phase D4) |
| `DATABASE_REFACTOR_PLAN.md` | The original DB refactor (Phases 1–4 ✅ complete) |
| `API_DOCUMENTATION.md` | REST surface — keep in lock-step with new endpoints |

---
