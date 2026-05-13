# Database Refactor Plan — Panel ERP

## Context

The current database has 15 models in a single `accounts/models.py` (1018 lines). The User model alone has 200+ fields mixing auth, personal info, KYC, nominees, addresses, and share capital. The Loan model mixes application state with active loan tracking. Financial period, instruments, interest receivable, fees, society-level accounting, and P&L are not modeled.

This plan restructures the database to match the cooperative society ERP architecture (per the ERP diagram), using a phased approach to minimize risk.

**Decisions made:**
- Keep User (AbstractUser), extract sub-models with FKs back to User
- Full Loan split: LoanApplication + LoanAccount
- Rename Receipt → Transaction across the codebase
- 4-phase rollout

---

## Current vs Target — Summary

| # | Entity | Current State | Action |
|---|--------|--------------|--------|
| 1 | Financial Period | ❌ Missing | **CREATE** `FinancialPeriod` |
| 2 | Share Capital | ⚠️ Embedded in User (7 fields) | **EXTRACT** to `ShareCapital` model |
| 3 | Member (User) | ⚠️ Bloated (200+ fields) | **EXTRACT** KYC, Nominee, Address to sub-models |
| 4 | Guarantor | ⚠️ CharFields on Loan | **CREATE** `Guarantor` model with FK to User |
| 5 | Account Types | ✅ MemberAccount | **KEEP** as-is (add suputra/sukanya as-is) |
| 6 | Interest Engine | ⚠️ Scattered across 3 files | **CENTRALIZE** into service class |
| 7 | Loan Application | ❌ Mixed in Loan | **CREATE** `LoanApplication` (split from Loan) |
| 8 | Loan Account | ❌ Mixed in Loan | **CREATE** `LoanAccount` (split from Loan) |
| 9 | Repayment Schedule | ✅ LoanRepayment | **UPDATE** FK from Loan → LoanAccount |
| 10 | Transaction | ✅ Receipt (misnamed) | **RENAME** Receipt → Transaction |
| 11 | Vouchers | ⚠️ Only 2 types | **EXPAND** to 4 types (receipt/payment/contra/journal) |
| 12 | Instruments | ❌ Missing | **CREATE** `Instrument` model |
| 13 | Society Main Account | ❌ Missing | **CREATE** `SocietyAccount` |
| 14 | Interest Payable | ⚠️ Basic InterestPayout | **ENHANCE** with status + transaction link |
| 15 | Interest Receivable | ❌ Missing | **CREATE** `InterestReceivable` |
| 16 | Fees & Charges | ⚠️ Scattered fields | **CREATE** `FeeSchedule` + `FeeCharge` |
| 17 | Net Surplus / P&L | ⚠️ Calculated dynamically | **CREATE** `ProfitAndLoss` to persist |
| 18 | Fund Distribution | ✅ Mostly good | **ENHANCE** with FinancialPeriod + priority |

---

## Phase 1: Foundation Layer

**Goal:** Add core infrastructure models that other phases depend on. No existing models changed.

### 1.1 — CREATE `FinancialPeriod`

```
Table: accounts_financialperiod

Fields:
  label              CharField(20)     e.g. "FY 2025-26"
  start_date         DateField         e.g. 2025-04-01
  end_date           DateField         e.g. 2026-03-31
  status             CharField(20)     choices: open / closed / continuing
  is_active          BooleanField      default=True (only one active at a time)
  created_by         FK(User)          SET_NULL, nullable
  created_at         DateTimeField     auto_now_add
  updated_at         DateTimeField     auto_now

Meta: ordering=["-start_date"], unique_together=["start_date", "end_date"]
```

### 1.2 — CREATE `Instrument`

```
Table: accounts_instrument

Fields:
  INSTRUMENT_TYPE_CHOICES:
    cash, cheque, dd, neft, rtgs, upi, imps

  CHEQUE_STATUS_CHOICES:
    not_submitted, submitted, cleared, bounced, cancelled

  instrument_type       CharField(20)     choices, indexed
  amount                DecimalField(15,2)

  # Cheque / DD fields (all nullable)
  cheque_number         CharField(30)
  drawer_name           CharField(200)
  drawer_bank           CharField(200)
  drawer_ifsc           CharField(11)     validators=[ifsc_validator]
  cheque_date           DateField
  cheque_status         CharField(20)     choices, default="not_submitted"

  # Electronic transfer fields (all nullable)
  reference_number      CharField(100)    UTR / RRN / transaction ID
  upi_vpa               CharField(100)    e.g. name@upi

  # Clearing
  is_cleared            BooleanField      default=False
  clearing_date         DateField         nullable
  bounce_reason         TextField         nullable

  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now

Meta: ordering=["-created_at"]
```

### 1.3 — RENAME Receipt → Transaction + link to Instrument

```
Rename: Receipt → Transaction (model, table, all references)

ADD fields to Transaction:
  transaction_date      DateField         default=today (when it happened, vs created_at)
  instrument            FK(Instrument)    SET_NULL, nullable, related_name="transactions"

RENAME field: receipt_number → transaction_number (keep same format RCP-YYYY-NNNNN)
```

**Files to update for rename:**
- `accounts/models.py` — model class + all related_name references
- `accounts/serializers.py` — ReceiptSerializer → TransactionSerializer, ReceiptCreateSerializer → TransactionCreateSerializer
- `accounts/api_views.py` — all receipt endpoint functions
- `accounts/api_urls.py` — URL patterns
- `admin_portal/views.py` — `_next_receipt_number`, `add_receipt_view`, `receipts_view`, `get_receipt_view`, `export_receipts_view` + all Receipt.objects references
- `admin_portal/urls.py` — route names
- `member_portal/views.py` + `urls.py`
- `templates/admin/receipts.html` — template references
- `static/js/receipts.js` — JS references
- `accounts/admin.py` — if registered
- `android-app/` — API endpoint paths (receipts → transactions)

### 1.4 — EXPAND Voucher types

```
Change VOUCHER_TYPE_CHOICES on Voucher model:
  OLD: voucher, contra_voucher
  NEW: receipt, payment, contra, journal

ADD field:
  journal_narration     TextField         nullable, blank (for journal voucher entries)
```

### Phase 1 Migration count: 1 migration (all additive + rename)

---

## Phase 2: Member Refactoring

**Goal:** Slim down the User model by extracting KYC, nominees, addresses, and share capital into proper sub-models.

### 2.1 — CREATE `MemberKYC`

```
Table: accounts_memberkyc

Fields:
  user                  OneToOneField(User)  CASCADE, related_name="kyc"
  kyc_status            CharField(20)     choices: pending/verified/rejected/expired, default="pending"
  kyc_verified_date     DateField         nullable
  kyc_verified_by       CharField(200)    nullable
  aadhaar_number        CharField(12)     nullable, validators=[aadhaar_validator]
  pan_number            CharField(10)     nullable, validators=[pan_validator]
  voter_id              CharField(20)     nullable
  passport_number       CharField(20)     nullable
  driving_licence       CharField(20)     nullable
  aadhaar_copy          FileField         upload_to="kyc/aadhaar/", nullable
  pan_copy              FileField         upload_to="kyc/pan/", nullable
  address_proof         FileField         upload_to="kyc/address/", nullable
  photograph            ImageField        upload_to="kyc/photos/", nullable
  signature_specimen    ImageField        upload_to="kyc/signatures/", nullable
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now
```

**Remove from User:** kyc_status, kyc_verified_date, kyc_verified_by, aadhaar_number, pan_number, voter_id, passport_number, driving_licence, aadhaar_copy, pan_copy, address_proof, photograph, signature_specimen (13 fields)

### 2.2 — CREATE `MemberNominee`

```
Table: accounts_membernominee

Fields:
  user                  FK(User)          CASCADE, related_name="nominees"
  is_primary            BooleanField      default=True
  name                  CharField(200)
  relationship          CharField(100)    nullable
  dob                   DateField         nullable
  contact               CharField(15)     nullable
  address               TextField         nullable
  id_type               CharField(50)     nullable
  id_number             CharField(50)     nullable
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now

Meta: ordering=["user", "-is_primary"]
```

**Remove from User:** nominee_name, nominee_relationship, nominee_dob, nominee_contact, nominee_address, nominee_id_type, nominee_id_number, alt_nominee_name, alt_nominee_relationship, alt_nominee_dob, alt_nominee_contact (11 fields)

### 2.3 — CREATE `MemberAddress`

```
Table: accounts_memberaddress

Fields:
  user                  FK(User)          CASCADE, related_name="addresses"
  address_type          CharField(20)     choices: current / permanent
  address_line1         CharField(255)    nullable
  address_line2         CharField(255)    nullable
  city                  CharField(100)    nullable
  district              CharField(100)    nullable
  state                 CharField(100)    nullable
  pincode               CharField(10)     nullable, validators=[pincode_validator]
  country               CharField(100)    default="India"
  same_as_current       BooleanField      default=False (for permanent address)
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now

Meta: ordering=["user", "address_type"], unique_together=["user", "address_type"]
```

**Remove from User:** current_address_line1, current_address_line2, current_city, current_district, current_state, current_pincode, current_country, permanent_same_as_current, permanent_address_line1 through permanent_country (15 fields)

### 2.4 — CREATE `ShareCapital`

```
Table: accounts_sharecapital

Fields:
  user                  FK(User)          CASCADE, related_name="share_holdings"
  number_of_shares      IntegerField
  face_value_per_share  DecimalField(10,2)
  total_value           DecimalField(12,2)  (computed: shares * face_value)
  certificate_number    CharField(50)     nullable
  issue_date            DateField
  redemption_date       DateField         nullable (null = still held)
  status                CharField(20)     choices: issued / redeemed / transferred
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now

Meta: ordering=["-issue_date"]
```

**Remove from User:** share_capital_amount, number_of_shares, face_value_per_share, share_certificate_number, share_issue_date (5 fields)
**Keep on User (for now):** dividend_payable_balance, last_dividend_paid_date (move in Phase 4)

### 2.5 — Remove denormalized summary fields from User

**Remove from User:** total_accounts_count, active_savings_accounts, active_fd_accounts, active_rd_accounts, active_loan_accounts, total_deposit_balance, total_loan_outstanding (7 fields — these are `editable=False` and never actually updated)

### Phase 2 total fields removed from User: ~51 fields
### Phase 2 Migration: 1 migration (create 4 models + remove fields from User)

**Data migration needed:** Copy existing User field values into new sub-models before removing columns.

---

## Phase 3: Loan Restructuring

**Goal:** Split monolithic Loan into LoanApplication + LoanAccount. Extract Guarantor.

### 3.1 — CREATE `LoanApplication`

```
Table: accounts_loanapplication

Fields:
  application_number    CharField(20)     unique, indexed (format: LA-YYYY-NNNNN)
  user                  FK(User)          CASCADE, related_name="loan_applications"
  loan_type             CharField(20)     choices: same 8 types as current Loan
  principal_amount      DecimalField(15,2)
  interest_rate         DecimalField(5,2)
  interest_type         CharField(20)     choices: flat / reducing, default="reducing"
  tenure_months         IntegerField
  purpose               TextField         nullable
  status                CharField(20)     choices: pending / approved / rejected
  application_date      DateField
  approval_date         DateField         nullable
  rejected_reason       TextField         nullable
  approved_by           FK(User)          SET_NULL, nullable, related_name="applications_approved"
  created_by            FK(User)          SET_NULL, nullable, related_name="applications_created"
  remarks               TextField         nullable
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now

Meta: ordering=["-created_at"]
```

### 3.2 — CREATE `LoanAccount`

```
Table: accounts_loanaccount

Fields:
  loan_number           CharField(20)     unique, indexed (format: LN-YYYY-NNNNN)
  application           FK(LoanApplication) CASCADE, related_name="loan_account"
  user                  FK(User)          CASCADE, related_name="loan_accounts"
  status                CharField(20)     choices: active / closed / defaulted / written_off
  principal_amount      DecimalField(15,2)
  interest_rate         DecimalField(5,2)
  interest_type         CharField(20)     choices: flat / reducing
  tenure_months         IntegerField
  emi_amount            DecimalField(12,2) default=0.00
  total_payable         DecimalField(15,2) default=0.00
  total_paid            DecimalField(15,2) default=0.00
  outstanding_balance   DecimalField(15,2) default=0.00
  overdue_amount        DecimalField(15,2) default=0.00
  disbursement_date     DateField
  disbursement_account  FK(MemberAccount) SET_NULL, nullable, related_name="loans_disbursed"
  processing_fee        DecimalField(10,2) default=0.00
  first_emi_date        DateField         nullable
  last_emi_date         DateField         nullable
  closure_date          DateField         nullable
  total_emis            IntegerField      default=0
  emis_paid             IntegerField      default=0
  emis_overdue          IntegerField      default=0
  npa_date              DateField         nullable
  collateral_type       CharField(200)    nullable
  collateral_value      DecimalField(15,2) nullable
  collateral_description TextField        nullable
  remarks               TextField         nullable
  created_by            FK(User)          SET_NULL, nullable
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now

Properties (same as current Loan):
  completion_percentage, is_npa, npa_category, days_overdue, calculated_overdue_amount

Methods:
  calculate_emi() — move from current Loan model

Meta: ordering=["-created_at"]
```

### 3.3 — CREATE `Guarantor`

```
Table: accounts_guarantor

Fields:
  loan_account          FK(LoanAccount)   CASCADE, related_name="guarantors"
  user                  FK(User)          SET_NULL, nullable, related_name="guarantees"
  name                  CharField(200)    (for non-member guarantors)
  relationship          CharField(100)    nullable
  contact               CharField(15)     nullable, validators=[phone_validator]
  is_member             BooleanField      default=False
  is_verified           BooleanField      default=False
  created_at            DateTimeField     auto_now_add

Meta: ordering=["loan_account", "created_at"]
```

### 3.4 — UPDATE `LoanRepayment`

```
Change FK:
  OLD: loan = FK(Loan)
  NEW: loan_account = FK(LoanAccount, related_name="repayments")
```

### 3.5 — DELETE old `Loan` model

After data migration is complete and all references updated.

### Phase 3 Data Migration:
1. For each Loan with status in (pending, rejected): create LoanApplication
2. For each Loan with status in (approved, active, closed, defaulted, written_off): create LoanApplication (approved) + LoanAccount
3. For each Loan: create Guarantor record from guarantor_* fields (if populated)
4. Update LoanRepayment FKs from Loan → LoanAccount
5. Update VoucherEntry.linked_loan_repayment references
6. Drop old Loan model

### Phase 3 Files to update:
- `accounts/models.py` — new models, remove Loan
- `accounts/serializers.py` — LoanListSerializer, LoanDetailSerializer, LoanCreateSerializer → split
- `accounts/api_views.py` — all loan endpoints
- `admin_portal/views.py` — add_loan_view, loans_view, approve_loan_view, record_emi_payment_view, get_loan_view
- `templates/admin/loans.html`
- `static/js/loans.js`
- `android-app/` — loan API models

---

## Phase 4: Financial Tracking & Society Account

**Goal:** Add the financial infrastructure layer: interest tracking, fees, P&L, society account.

### 4.1 — CREATE `InterestReceivable`

```
Table: accounts_interestreceivable

Fields:
  loan_account          FK(LoanAccount)   CASCADE, related_name="interest_receivables"
  financial_period      FK(FinancialPeriod) SET_NULL, nullable
  amount_accrued        DecimalField(12,2)
  amount_collected      DecimalField(12,2) default=0.00
  status                CharField(20)     choices: accrued / collected / written_off
  due_date              DateField
  collected_date        DateField         nullable
  created_at            DateTimeField     auto_now_add
```

### 4.2 — ENHANCE `InterestPayout`

```
ADD fields:
  transaction           FK(Transaction)   SET_NULL, nullable (link when credited)
  financial_period      FK(FinancialPeriod) SET_NULL, nullable
  status                CharField(20)     choices: accrued / credited, default="accrued"
```

### 4.3 — CREATE `FeeSchedule` + `FeeCharge`

```
Table: accounts_feeschedule
  fee_type              CharField(30)     choices: membership/processing/late_payment/annual_maintenance/closure/npa
  name                  CharField(200)
  amount                DecimalField(10,2) nullable (fixed amount)
  percentage            DecimalField(5,2)  nullable (% of principal)
  applies_to            CharField(20)     choices: loan / account / membership
  is_active             BooleanField      default=True
  effective_date        DateField
  description           TextField         nullable
  created_at            DateTimeField     auto_now_add

Table: accounts_feecharge
  fee_schedule          FK(FeeSchedule)   CASCADE
  user                  FK(User)          CASCADE, related_name="fee_charges"
  loan_account          FK(LoanAccount)   SET_NULL, nullable
  member_account        FK(MemberAccount) SET_NULL, nullable
  amount                DecimalField(10,2)
  status                CharField(20)     choices: charged / waived / refunded
  transaction           FK(Transaction)   SET_NULL, nullable
  waived_by             FK(User)          SET_NULL, nullable
  waived_reason         TextField         nullable
  created_at            DateTimeField     auto_now_add
```

### 4.4 — CREATE `ProfitAndLoss`

```
Table: accounts_profitandloss
  financial_period      FK(FinancialPeriod) CASCADE

  # Income
  loan_interest_income      DecimalField(15,2) default=0
  processing_fees_income    DecimalField(15,2) default=0
  penalty_income            DecimalField(15,2) default=0
  membership_fees_income    DecimalField(15,2) default=0
  other_income              DecimalField(15,2) default=0
  total_income              DecimalField(15,2) default=0

  # Expenses
  deposit_interest_expense  DecimalField(15,2) default=0
  bad_debt_expense          DecimalField(15,2) default=0
  other_expense             DecimalField(15,2) default=0
  total_expense             DecimalField(15,2) default=0

  # Summary
  gross_surplus             DecimalField(15,2) default=0
  fund_allocations_total    DecimalField(15,2) default=0
  net_surplus               DecimalField(15,2) default=0

  # Audit
  calculated_by         FK(User)          SET_NULL, nullable
  calculation_date      DateTimeField
  is_locked             BooleanField      default=False
  locked_by             FK(User)          SET_NULL, nullable
  locked_date           DateTimeField     nullable
  created_at            DateTimeField     auto_now_add
  updated_at            DateTimeField     auto_now
```

### 4.5 — CREATE `SocietyAccount`

```
Table: accounts_societyaccount
  financial_period          FK(FinancialPeriod) CASCADE

  total_member_deposits     DecimalField(15,2) default=0
  total_loan_outstanding    DecimalField(15,2) default=0
  total_interest_payable    DecimalField(15,2) default=0
  total_interest_receivable DecimalField(15,2) default=0
  total_fees_collected      DecimalField(15,2) default=0
  total_fund_balance        DecimalField(15,2) default=0
  net_surplus               DecimalField(15,2) default=0

  last_updated              DateTimeField     auto_now
  created_at                DateTimeField     auto_now_add
```

### 4.6 — ENHANCE Fund models

```
ADD to FundAllocationRule:
  priority_order        IntegerField      default=0
  min_threshold         DecimalField(10,2) nullable
  max_cap               DecimalField(10,2) nullable

ADD to FundTransaction:
  financial_period      FK(FinancialPeriod) SET_NULL, nullable
  allocation_rule       FK(FundAllocationRule) SET_NULL, nullable
```

### 4.7 — CREATE `InterestCalculatorService`

New file: `accounts/interest.py` (not a model — a service class)

```python
class InterestCalculatorService:
    @staticmethod
    def daily_simple_interest(balance, annual_rate, days):
        """balance * rate * days / 36500"""

    @staticmethod
    def calculate_emi(principal, annual_rate, months):
        """P * r * (1+r)^n / ((1+r)^n - 1)"""

    @staticmethod
    def maturity_amount(principal, annual_rate, months, method="simple"):
        """For FD/RD maturity calculation"""
```

Refactor: `utils.py`, `admin_portal/views.py` (post_interest_view, etc.) to use this service.

---

## New Model Count Summary

| Phase | New Models | Models Modified | Models Removed |
|-------|-----------|----------------|---------------|
| Phase 1 | 2 (FinancialPeriod, Instrument) | 2 (Receipt→Transaction, Voucher) | 0 |
| Phase 2 | 4 (MemberKYC, MemberNominee, MemberAddress, ShareCapital) | 1 (User — remove ~51 fields) | 0 |
| Phase 3 | 3 (LoanApplication, LoanAccount, Guarantor) | 1 (LoanRepayment) | 1 (Loan) |
| Phase 4 | 5 (InterestReceivable, FeeSchedule, FeeCharge, ProfitAndLoss, SocietyAccount) | 3 (InterestPayout, FundAllocationRule, FundTransaction) | 0 |
| **Total** | **14 new** | **7 modified** | **1 removed** |

Final model count: 15 current - 1 removed + 14 new = **28 models**

---

## Files Modified Per Phase

### Phase 1
- `accounts/models.py` — add FinancialPeriod, Instrument; rename Receipt→Transaction; expand Voucher types
- `accounts/serializers.py` — rename Receipt serializers → Transaction
- `accounts/api_views.py` — rename receipt endpoints → transaction
- `accounts/api_urls.py` — update URL patterns
- `admin_portal/views.py` — rename all receipt references
- `admin_portal/urls.py` — update route names
- `member_portal/views.py` + `urls.py`
- `templates/admin/receipts.html` — rename or create `transactions.html`
- `static/js/receipts.js` — rename or create `transactions.js`

### Phase 2
- `accounts/models.py` — add 4 sub-models, remove 51 fields from User
- `accounts/serializers.py` — update UserDetailSerializer, UserCreateSerializer
- `accounts/api_views.py` — update member endpoints
- `admin_portal/views.py` — update add_member_view, edit_member_view, get_member_view
- `templates/admin/members.html` — update form fields
- Data migration script to copy User fields → sub-models

### Phase 3
- `accounts/models.py` — add LoanApplication, LoanAccount, Guarantor; remove Loan
- `accounts/serializers.py` — split loan serializers
- `accounts/api_views.py` — update all loan endpoints
- `admin_portal/views.py` — update loan views (add, approve, emi, list)
- `templates/admin/loans.html`
- `static/js/loans.js`
- Data migration: split existing Loan records → LoanApplication + LoanAccount

### Phase 4
- `accounts/models.py` — add 5 models, enhance 3
- `accounts/interest.py` — new service file
- `accounts/utils.py` — refactor get_financial_summary to use new models
- `admin_portal/views.py` — update reports, distribute_profit, post_interest, distribute_dividend

---

## Verification

After each phase:
1. `python manage.py makemigrations` — verify migrations generate correctly
2. `python manage.py migrate` — apply to dev database
3. `python manage.py test` — run existing test suite
4. `ruff check . --fix && ruff format .` — lint/format
5. Manual smoke test: open staff panel (`/home/` or `/` after setup) → members → accounts → receipts/transactions → loans
6. API test: `curl` commands from API_DOCUMENTATION.md
