# Database Reference

Complete schema documentation for the Cooperative Society Banking System.
Source of truth: `accounts/models.py` (1018 lines, 15 models).

**Database:** PostgreSQL 15 | **ORM:** Django 4.2+ | **Auto PK:** BigAutoField (64-bit)

**Web vs API auth:** The cooperative staff HTML UI may run without a login form when `WEB_LOGIN_DISABLED=True` (first staff user is assumed). Database tables such as `LoginOTPChallenge` and `UserDevice` still support **API** member login (`/api/v1/auth/…`); they are not removed when the browser panel skips passwords.

---

## Entity-Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                      │
│                            ┌──────────────────┐                                      │
│                 ┌─────────>│   Notification    │                                      │
│                 │          └──────────────────┘                                      │
│                 │          ┌──────────────────┐                                      │
│                 ├─────────>│ LoginOTPChallenge │                                      │
│                 │          └──────────────────┘                                      │
│                 │          ┌──────────────────┐                                      │
│                 ├─────────>│    UserDevice     │                                      │
│                 │          └──────────────────┘                                      │
│                 │                                                                    │
│   ┌─────────────────────┐      ┌──────────────────┐      ┌──────────────────┐       │
│   │                     │─────>│  MemberAccount    │─────>│    Receipt       │       │
│   │                     │      │                   │      │                  │       │
│   │                     │      │  ┌─interest_      │      └───────┬──────────┘       │
│   │                     │      │  │ payouts         │              │                  │
│   │                     │      │  v                 │              │                  │
│   │        User         │      │ InterestPayout    │              │                  │
│   │   (AbstractUser)    │      │                   │              │                  │
│   │                     │      └──────┬───────────┘              │                  │
│   │  introducer_member──┤             │                          │                  │
│   │  (self FK)          │             │ disbursement_account     │                  │
│   │                     │      ┌──────v───────────┐              │                  │
│   │                     │─────>│      Loan         │              │                  │
│   │                     │      │                   │              │                  │
│   │                     │      └──────┬───────────┘              │                  │
│   │                     │             │                          │                  │
│   │                     │      ┌──────v───────────┐              │                  │
│   │                     │      │  LoanRepayment   │──────────────┘                  │
│   │                     │      │                   │   (receipt FK)                   │
│   │                     │      └──────────────────┘                                  │
│   │                     │                                                            │
│   │                     │      ┌──────────────────┐      ┌──────────────────┐       │
│   │                     │─────>│     Voucher       │─────>│  VoucherEntry    │       │
│   │                     │      │                   │      │                  │       │
│   │                     │      └────────┬─────────┘      └──────────────────┘       │
│   │                     │               │ transferred_to_fund                        │
│   │                     │      ┌────────v─────────┐      ┌──────────────────┐       │
│   │                     │─────>│   FundAccount     │─────>│ FundTransaction  │       │
│   │                     │      │                   │      └──────────────────┘       │
│   │                     │      │                   │      ┌──────────────────┐       │
│   │                     │      │                   │─────>│FundAllocationRule│       │
│   └─────────────────────┘      └──────────────────┘      └──────────────────┘       │
│                                                                                      │
│   ┌─────────────────────┐                                                            │
│   │      AuditLog       │<──── User (FK, SET_NULL)                                   │
│   └─────────────────────┘                                                            │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### FK Summary (30+ foreign keys)

| From | Field | To | on_delete | related_name |
|------|-------|----|-----------|-------------|
| User | introducer_member | User (self) | SET_NULL | `introduced_members` |
| Notification | user | User | CASCADE | `notifications` |
| LoginOTPChallenge | user | User | CASCADE | `login_otp_challenges` |
| UserDevice | user | User | CASCADE | `devices` |
| MemberAccount | user | User | CASCADE | `member_accounts` |
| Receipt | user | User | CASCADE | `receipts` |
| Receipt | member_account | MemberAccount | CASCADE | `receipts` |
| Receipt | created_by | User | SET_NULL | `receipts_created` |
| Voucher | user | User | CASCADE | `vouchers` |
| Voucher | created_by | User | SET_NULL | `vouchers_created` |
| Voucher | transferred_to_fund | FundAccount | SET_NULL | `vouchers_transferred` |
| VoucherEntry | voucher | Voucher | CASCADE | `entries` |
| VoucherEntry | member_account | MemberAccount | CASCADE | `voucher_entries` |
| VoucherEntry | linked_loan_repayment | LoanRepayment | SET_NULL | `voucher_entries` |
| VoucherEntry | created_receipt | Receipt | SET_NULL | `voucher_entries` |
| Loan | user | User | CASCADE | `loans` |
| Loan | approved_by | User | SET_NULL | `loans_approved` |
| Loan | created_by | User | SET_NULL | `loans_created` |
| Loan | disbursement_account | MemberAccount | SET_NULL | `loans_disbursed` |
| LoanRepayment | loan | Loan | CASCADE | `repayments` |
| LoanRepayment | receipt | Receipt | SET_NULL | `loan_repayments` |
| AuditLog | user | User | SET_NULL | `audit_logs` |
| FundAccount | created_by | User | SET_NULL | `funds_created` |
| FundTransaction | fund | FundAccount | CASCADE | `transactions` |
| FundTransaction | source_member | User | SET_NULL | `fund_transactions` |
| FundTransaction | created_by | User | SET_NULL | `fund_transactions_created` |
| FundAllocationRule | fund | FundAccount | CASCADE | `allocation_rules` |
| FundAllocationRule | created_by | User | SET_NULL | `allocation_rules_created` |
| InterestPayout | account | MemberAccount | CASCADE | `interest_payouts` |
| InterestPayout | created_by | User | SET_NULL | `interest_payouts_created` |

---

## Module-Level Validators

Defined at top of `accounts/models.py`, used across the User model for Indian identity formats:

| Validator | Regex | Format | Example |
|-----------|-------|--------|---------|
| `pan_validator` | `^[A-Z]{5}[0-9]{4}[A-Z]$` | 5 letters + 4 digits + 1 letter | `ABCDE1234F` |
| `aadhaar_validator` | `^[2-9][0-9]{11}$` | 12 digits, cannot start with 0/1 | `234567890123` |
| `phone_validator` | `^[6-9][0-9]{9}$` | 10 digits starting with 6-9 | `9876543210` |
| `ifsc_validator` | `^[A-Z]{4}0[A-Z0-9]{6}$` | 4 letters + 0 + 6 alphanum | `SBIN0001234` |
| `pincode_validator` | `^[1-9][0-9]{5}$` | 6 digits, cannot start with 0 | `400001` |

---

## Auto-Generated Number Formats

These are generated atomically in views/serializers using `select_for_update()` to prevent duplicates:

| Entity | Format | Example | Generated In |
|--------|--------|---------|-------------|
| Member ID | `MEM-{year}-{seq:04d}` | `MEM-2026-0027` | `serializers.py` (UserCreateSerializer.create) |
| Account Number | auto-incremented unique | varies | `admin_portal/views.py` (add_account_view) |
| Receipt Number | `RCP-{year}-{seq:05d}` | `RCP-2026-00940` | `admin_portal/views.py` (_next_receipt_number) |
| Voucher Number | `VCH-{year}-{seq:05d}` | `VCH-2026-00015` | `admin_portal/views.py` (_next_voucher_number) |
| Loan Number | `LN-{year}-{seq:05d}` | `LN-2026-00030` | `admin_portal/views.py` (add_loan_view) |
| Fund Account Number | `FND-{year}-{seq:04d}` | `FND-2026-0005` | `admin_portal/views.py` (add_fund_view) |

---

## Soft-Delete Pattern

Three models use soft-delete instead of actual DB deletion:

| Model | Fields | Query Filter |
|-------|--------|-------------|
| User | `is_deleted` (Boolean, default=False, indexed), `deleted_at` (DateTime, nullable) | `.filter(is_deleted=False)` |
| MemberAccount | `is_deleted` (Boolean, default=False, indexed), `deleted_at` (DateTime, nullable) | `.filter(is_deleted=False)` |
| FundAccount | `is_deleted` (Boolean, default=False, indexed), `deleted_at` (DateTime, nullable) | `.filter(is_deleted=False)` |

---

## Model 1: User

**Purpose:** Central hub model for both admin staff and cooperative society members.
**Table:** `accounts_user`
**Extends:** `django.contrib.auth.models.AbstractUser` (inherits: id, username, password, first_name, last_name, email, is_staff, is_active, is_superuser, date_joined, last_login, groups, user_permissions)

### Choice Constants

**MEMBER_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `regular` | Regular |
| `nominal` | Nominal |
| `associate` | Associate |
| `staff` | Staff |

**STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `active` | Active |
| `inactive` | Inactive |
| `resign` | Resigned |
| `closed` | Closed |
| `deceased` | Deceased |
| `blacklisted` | Blacklisted |

**GENDER_CHOICES:**
| Value | Display |
|-------|---------|
| `male` | Male |
| `female` | Female |
| `other` | Other |

**MARITAL_STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `single` | Single |
| `married` | Married |
| `divorced` | Divorced |
| `widowed` | Widowed |

**COMM_MODE_CHOICES:**
| Value | Display |
|-------|---------|
| `sms` | SMS |
| `email` | Email |
| `whatsapp` | WhatsApp |
| `letter` | Letter |

**KYC_STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `pending` | Pending |
| `verified` | Verified |
| `rejected` | Rejected |
| `expired` | Expired |

**RISK_CATEGORY_CHOICES:**
| Value | Display |
|-------|---------|
| `low` | Low |
| `medium` | Medium |
| `high` | High |

### Fields

#### Core Identity
| Field | Type | Constraints |
|-------|------|-------------|
| `member_id` | CharField(50) | unique, nullable, blank, indexed |
| `member_type` | CharField(20) | choices=MEMBER_TYPE_CHOICES, default="regular", indexed |
| `status` | CharField(20) | choices=STATUS_CHOICES, default="active", indexed |
| `date_of_joining` | DateField | nullable, blank |
| `inactive_since` | DateField | nullable, blank |
| `exit_date` | DateField | nullable, blank |
| `closure_reason` | TextField | nullable, blank |

#### Personal Details
| Field | Type | Constraints |
|-------|------|-------------|
| `date_of_birth` | DateField | nullable, blank |
| `gender` | CharField(10) | choices=GENDER_CHOICES, nullable, blank |
| `marital_status` | CharField(20) | choices=MARITAL_STATUS_CHOICES, nullable, blank |
| `occupation` | CharField(200) | nullable, blank |
| `annual_income_bracket` | CharField(100) | nullable, blank |
| `education_qualification` | CharField(200) | nullable, blank |

#### Contact Information
| Field | Type | Constraints |
|-------|------|-------------|
| `mobile_primary` | CharField(15) | nullable, blank, validators=[phone_validator] |
| `mobile_alternate` | CharField(15) | nullable, blank, validators=[phone_validator] |
| `preferred_comm_mode` | CharField(20) | choices=COMM_MODE_CHOICES, default="email" |
| `dnd_enabled` | BooleanField | default=False |

#### Current Address
| Field | Type | Constraints |
|-------|------|-------------|
| `current_address_line1` | CharField(255) | nullable, blank |
| `current_address_line2` | CharField(255) | nullable, blank |
| `current_city` | CharField(100) | nullable, blank |
| `current_district` | CharField(100) | nullable, blank |
| `current_state` | CharField(100) | nullable, blank |
| `current_pincode` | CharField(10) | nullable, blank, validators=[pincode_validator] |
| `current_country` | CharField(100) | default="India" |

#### Permanent Address
| Field | Type | Constraints |
|-------|------|-------------|
| `permanent_same_as_current` | BooleanField | default=True |
| `permanent_address_line1` | CharField(255) | nullable, blank |
| `permanent_address_line2` | CharField(255) | nullable, blank |
| `permanent_city` | CharField(100) | nullable, blank |
| `permanent_district` | CharField(100) | nullable, blank |
| `permanent_state` | CharField(100) | nullable, blank |
| `permanent_pincode` | CharField(10) | nullable, blank, validators=[pincode_validator] |
| `permanent_country` | CharField(100) | default="India" |

#### KYC & Identity Proofs
| Field | Type | Constraints |
|-------|------|-------------|
| `kyc_status` | CharField(20) | choices=KYC_STATUS_CHOICES, default="pending" |
| `kyc_verified_date` | DateField | nullable, blank |
| `kyc_verified_by` | CharField(200) | nullable, blank |
| `aadhaar_number` | CharField(12) | nullable, blank, validators=[aadhaar_validator] |
| `pan_number` | CharField(10) | nullable, blank, validators=[pan_validator] |
| `voter_id` | CharField(20) | nullable, blank |
| `passport_number` | CharField(20) | nullable, blank |
| `driving_licence` | CharField(20) | nullable, blank |
| `aadhaar_copy` | FileField | upload_to="kyc/aadhaar/", nullable, blank |
| `pan_copy` | FileField | upload_to="kyc/pan/", nullable, blank |
| `address_proof` | FileField | upload_to="kyc/address/", nullable, blank |
| `photograph` | ImageField | upload_to="kyc/photos/", nullable, blank |
| `signature_specimen` | ImageField | upload_to="kyc/signatures/", nullable, blank |

#### Banking Relationship Flags
| Field | Type | Constraints |
|-------|------|-------------|
| `eligible_for_accounts` | BooleanField | default=True |
| `eligible_for_loans` | BooleanField | default=True |
| `eligible_for_dividend` | BooleanField | default=True |
| `eligible_for_voting` | BooleanField | default=True |
| `risk_category` | CharField(20) | choices=RISK_CATEGORY_CHOICES, default="low" |

#### Shareholding & Membership Capital
| Field | Type | Constraints |
|-------|------|-------------|
| `share_capital_amount` | DecimalField(12,2) | default=0.00 |
| `number_of_shares` | IntegerField | default=0 |
| `face_value_per_share` | DecimalField(10,2) | default=0.00 |
| `share_certificate_number` | CharField(50) | nullable, blank |
| `share_issue_date` | DateField | nullable, blank |
| `dividend_payable_balance` | DecimalField(12,2) | default=0.00 |
| `last_dividend_paid_date` | DateField | nullable, blank |

#### Nominee Details
| Field | Type | Constraints |
|-------|------|-------------|
| `nominee_name` | CharField(200) | nullable, blank |
| `nominee_relationship` | CharField(100) | nullable, blank |
| `nominee_dob` | DateField | nullable, blank |
| `nominee_contact` | CharField(15) | nullable, blank |
| `nominee_address` | TextField | nullable, blank |
| `nominee_id_type` | CharField(50) | nullable, blank |
| `nominee_id_number` | CharField(50) | nullable, blank |

#### Alternate Nominee
| Field | Type | Constraints |
|-------|------|-------------|
| `alt_nominee_name` | CharField(200) | nullable, blank |
| `alt_nominee_relationship` | CharField(100) | nullable, blank |
| `alt_nominee_dob` | DateField | nullable, blank |
| `alt_nominee_contact` | CharField(15) | nullable, blank |

#### Account & Loan Summary (Denormalized, Read-Only)
| Field | Type | Constraints |
|-------|------|-------------|
| `total_accounts_count` | IntegerField | default=0, editable=False |
| `active_savings_accounts` | IntegerField | default=0, editable=False |
| `active_fd_accounts` | IntegerField | default=0, editable=False |
| `active_rd_accounts` | IntegerField | default=0, editable=False |
| `active_loan_accounts` | IntegerField | default=0, editable=False |
| `total_deposit_balance` | DecimalField(15,2) | default=0.00, editable=False |
| `total_loan_outstanding` | DecimalField(15,2) | default=0.00, editable=False |

#### Internal Controls & Compliance
| Field | Type | Constraints |
|-------|------|-------------|
| `introducer_member` | ForeignKey(self) | on_delete=SET_NULL, nullable, blank, related_name="introduced_members" |
| `introducer_approval_date` | DateField | nullable, blank |
| `board_approval_reference` | CharField(100) | nullable, blank |
| `aml_check_status` | CharField(50) | nullable, blank |
| `last_compliance_review_date` | DateField | nullable, blank |
| `internal_remarks` | TextField | nullable, blank |

#### System & Access
| Field | Type | Constraints |
|-------|------|-------------|
| `portal_access_enabled` | BooleanField | default=True |
| `is_deleted` | BooleanField | default=False, indexed |
| `deleted_at` | DateTimeField | nullable, blank |
| `role` | CharField(20) | default="member", indexed |

#### Notification & Verification Settings
| Field | Type | Constraints |
|-------|------|-------------|
| `email_notifications` | BooleanField | default=True |
| `sms_notifications` | BooleanField | default=False |
| `push_notifications_enabled` | BooleanField | default=True |
| `email_verified` | BooleanField | default=False |
| `email_verification_token` | CharField(100) | nullable, blank |
| `email_verification_sent_at` | DateTimeField | nullable, blank |

### Properties & Methods

| Name | Type | Description |
|------|------|-------------|
| `display_name` | @property | Returns `"{first_name} {last_name}"` or falls back to `username` |
| `age` | @property | Calculates age from `date_of_birth`, returns None if not set |
| `__str__` | method | Returns `"{member_id or username} - {display_name}"` |
| `generate_password_from_dob()` | method | Format: `DDMM` + first 4 chars of first_name uppercase (e.g., `0211TANM`) |
| `reset_password_to_dob()` | method | Resets password using DOB-based generation |
| `get_role_display_name()` | method | Returns capitalized role |
| `is_admin_role()` | method | True if role=="admin" or is_superuser |
| `can_manage_users()` | method | True if is_superuser or role=="admin" |
| `send_verification_email()` | method | Triggers email verification |
| `verify_email(token)` | method | Verifies email with token, sets email_verified=True |

---

## Model 2: Notification

**Purpose:** In-app and push notification records for members.
**Table:** `accounts_notification`

### Choice Constants

**TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `general` | General |
| `transaction` | Transaction |
| `loan` | Loan |
| `system` | System |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="notifications" |
| `title` | CharField(200) | required |
| `message` | TextField | required |
| `notification_type` | CharField(20) | choices=TYPE_CHOICES, default="general", indexed |
| `is_read` | BooleanField | default=False, indexed |
| `read_at` | DateTimeField | nullable, blank |
| `metadata` | JSONField | default=dict, blank |
| `created_at` | DateTimeField | auto_now_add=True, indexed |

### Meta
- `ordering = ["-created_at"]`

---

## Model 3: LoginOTPChallenge

**Purpose:** Stores OTP challenges for two-factor login authentication.
**Table:** `accounts_loginotpchallenge`

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="login_otp_challenges" |
| `challenge_token` | CharField(64) | unique, indexed |
| `otp_hash` | CharField(255) | required (hashed OTP) |
| `expires_at` | DateTimeField | indexed |
| `attempt_count` | IntegerField | default=0 |
| `max_attempts` | IntegerField | default=5 |
| `consumed_at` | DateTimeField | nullable, blank |
| `request_ip` | GenericIPAddressField | nullable, blank |
| `user_agent` | CharField(255) | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True, indexed |

### Properties

| Name | Type | Description |
|------|------|-------------|
| `is_expired` | @property | Returns `self.expires_at <= timezone.now()` |

### Meta
- `ordering = ["-created_at"]`

---

## Model 4: UserDevice

**Purpose:** Stores FCM device tokens for push notifications.
**Table:** `accounts_userdevice`

### Choice Constants

**PLATFORM_CHOICES:**
| Value | Display |
|-------|---------|
| `android` | Android |
| `ios` | iOS |
| `web` | Web |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="devices" |
| `token` | CharField(255) | unique, indexed |
| `platform` | CharField(20) | choices=PLATFORM_CHOICES, default="android" |
| `is_active` | BooleanField | default=True, indexed |
| `last_seen` | DateTimeField | auto_now=True |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["-last_seen"]`

---

## Model 5: MemberAccount

**Purpose:** Financial accounts held by members. One member can have multiple accounts of different types.
**Table:** `accounts_memberaccount`

### Choice Constants

**ACCOUNT_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `fd` | Fixed Deposit |
| `cd` | Certificate of Deposit |
| `rd` | Recurring Deposit |
| `od` | Overdraft |
| `share` | Share Account |
| `sukanyu` | Sukanyu Yojana |
| `suputra` | Suputra Yojana |

**STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `active` | Active |
| `closed` | Closed |
| `frozen` | Frozen |
| `matured` | Matured |
| `dormant` | Dormant |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="member_accounts" |
| `account_number` | CharField(20) | unique, indexed |
| `account_type` | CharField(20) | choices=ACCOUNT_TYPE_CHOICES, indexed |
| `status` | CharField(20) | choices=STATUS_CHOICES, default="active", indexed |
| `balance` | DecimalField(15,2) | default=0.00 |
| `interest_rate` | DecimalField(5,2) | default=0.00 |
| `principal_amount` | DecimalField(15,2) | default=0.00 |
| `accrued_interest` | DecimalField(15,2) | default=0.00 |
| `rd_monthly_amount` | DecimalField(12,2) | nullable, blank |
| `rd_installments_paid` | IntegerField | default=0 |
| `rd_total_installments` | IntegerField | nullable, blank |
| `opening_date` | DateField | required |
| `maturity_date` | DateField | nullable, blank |
| `closure_date` | DateField | nullable, blank |
| `last_transaction_date` | DateField | nullable, blank |
| `last_interest_calc_date` | DateField | nullable, blank |
| `tenure_months` | IntegerField | nullable, blank |
| `nominee_name` | CharField(200) | nullable, blank |
| `nominee_relationship` | CharField(100) | nullable, blank |
| `remarks` | TextField | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True |
| `updated_at` | DateTimeField | auto_now=True |
| `is_deleted` | BooleanField | default=False, indexed |
| `deleted_at` | DateTimeField | nullable, blank |

### Properties

| Name | Type | Description |
|------|------|-------------|
| `is_term_deposit` | @property | True if account_type in (fd, rd, cd, sukanyu, suputra) |
| `maturity_amount` | @property | Simple interest: `principal + (principal * rate * tenure) / (12 * 100)` |

### Meta
- `ordering = ["-created_at"]`

---

## Model 6: Receipt

**Purpose:** Records every financial transaction (deposit, withdrawal, transfer, interest, dividend).
**Table:** `accounts_receipt`

### Choice Constants

**TRANSACTION_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `credit` | Credit |
| `debit` | Debit |
| `transfer` | Transfer |
| `interest` | Interest Payment |
| `dividend` | Dividend |
| `share_capital` | Share Capital |

**PAYMENT_MODE_CHOICES:**
| Value | Display |
|-------|---------|
| `cash` | Cash |
| `cheque` | Cheque |
| `online` | Online Transfer |
| `neft` | NEFT |
| `rtgs` | RTGS |
| `upi` | UPI |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `receipt_number` | CharField(20) | unique, indexed |
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="receipts" |
| `member_account` | ForeignKey(MemberAccount) | on_delete=CASCADE, related_name="receipts" |
| `transaction_type` | CharField(20) | choices=TRANSACTION_TYPE_CHOICES, indexed |
| `amount` | DecimalField(15,2) | required |
| `description` | TextField | nullable, blank |
| `payment_mode` | CharField(20) | choices=PAYMENT_MODE_CHOICES, default="cash" |
| `reference_number` | CharField(100) | nullable, blank |
| `balance_after` | DecimalField(15,2) | default=0.00 |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="receipts_created" |
| `remarks` | TextField | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["-created_at"]`

---

## Model 7: Voucher

**Purpose:** Staged cash collection record. Created as "pending", then transferred to a fund when verified.
**Table:** `accounts_voucher`

### Choice Constants

**VOUCHER_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `voucher` | Voucher |
| `contra_voucher` | Contra Voucher |

**STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `pending` | Pending |
| `transferred` | Transferred |
| `cancelled` | Cancelled |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `voucher_number` | CharField(20) | unique, indexed |
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="vouchers" |
| `voucher_type` | CharField(20) | choices=VOUCHER_TYPE_CHOICES, default="voucher", indexed |
| `total_amount` | DecimalField(15,2) | default=0.00 |
| `payment_mode` | CharField(20) | choices=Receipt.PAYMENT_MODE_CHOICES, default="cash" |
| `reference_number` | CharField(100) | nullable, blank |
| `remarks` | TextField | nullable, blank |
| `status` | CharField(20) | choices=STATUS_CHOICES, default="pending", indexed |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="vouchers_created" |
| `transferred_to_fund` | ForeignKey(FundAccount) | on_delete=SET_NULL, nullable, blank, related_name="vouchers_transferred" |
| `transferred_at` | DateTimeField | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["-created_at"]`

---

## Model 8: VoucherEntry

**Purpose:** Individual line items within a voucher (one voucher can cover multiple accounts/loans).
**Table:** `accounts_voucherentry`

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `voucher` | ForeignKey(Voucher) | on_delete=CASCADE, related_name="entries" |
| `member_account` | ForeignKey(MemberAccount) | on_delete=CASCADE, related_name="voucher_entries" |
| `transaction_type` | CharField(20) | choices=Receipt.TRANSACTION_TYPE_CHOICES |
| `amount` | DecimalField(15,2) | required |
| `description` | TextField | nullable, blank |
| `linked_loan_repayment` | ForeignKey(LoanRepayment) | on_delete=SET_NULL, nullable, blank, related_name="voucher_entries" |
| `created_receipt` | ForeignKey(Receipt) | on_delete=SET_NULL, nullable, blank, related_name="voucher_entries" |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["created_at"]`

---

## Model 9: Loan

**Purpose:** Full loan lifecycle from application to closure, with EMI tracking and NPA classification.
**Table:** `accounts_loan`

### Choice Constants

**LOAN_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `personal` | Personal Loan |
| `home` | Home Loan |
| `vehicle` | Vehicle Loan |
| `gold` | Gold Loan |
| `education` | Education Loan |
| `business` | Business Loan |
| `emergency` | Emergency Loan |
| `agriculture` | Agriculture Loan |

**STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `pending` | Pending Approval |
| `approved` | Approved |
| `active` | Active |
| `closed` | Closed |
| `defaulted` | Defaulted |
| `written_off` | Written Off |
| `rejected` | Rejected |

**INTEREST_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `flat` | Flat Rate |
| `reducing` | Reducing Balance |

### Fields

#### Core
| Field | Type | Constraints |
|-------|------|-------------|
| `loan_number` | CharField(20) | unique, indexed |
| `user` | ForeignKey(User) | on_delete=CASCADE, related_name="loans" |
| `loan_type` | CharField(20) | choices=LOAN_TYPE_CHOICES, indexed |
| `status` | CharField(20) | choices=STATUS_CHOICES, default="pending", indexed |

#### Financial
| Field | Type | Constraints |
|-------|------|-------------|
| `principal_amount` | DecimalField(15,2) | required |
| `interest_rate` | DecimalField(5,2) | required |
| `interest_type` | CharField(20) | choices=INTEREST_TYPE_CHOICES, default="reducing" |
| `tenure_months` | IntegerField | required |
| `emi_amount` | DecimalField(12,2) | default=0.00 |

#### Balance Tracking
| Field | Type | Constraints |
|-------|------|-------------|
| `total_payable` | DecimalField(15,2) | default=0.00 |
| `total_paid` | DecimalField(15,2) | default=0.00 |
| `outstanding_balance` | DecimalField(15,2) | default=0.00 |
| `overdue_amount` | DecimalField(15,2) | default=0.00 |

#### Dates
| Field | Type | Constraints |
|-------|------|-------------|
| `application_date` | DateField | required |
| `approval_date` | DateField | nullable, blank |
| `disbursement_date` | DateField | nullable, blank |
| `first_emi_date` | DateField | nullable, blank |
| `last_emi_date` | DateField | nullable, blank |
| `closure_date` | DateField | nullable, blank |

#### EMI Tracking
| Field | Type | Constraints |
|-------|------|-------------|
| `total_emis` | IntegerField | default=0 |
| `emis_paid` | IntegerField | default=0 |
| `emis_overdue` | IntegerField | default=0 |

#### Guarantor
| Field | Type | Constraints |
|-------|------|-------------|
| `guarantor_name` | CharField(200) | nullable, blank |
| `guarantor_member_id` | CharField(50) | nullable, blank |
| `guarantor_relationship` | CharField(100) | nullable, blank |
| `guarantor_contact` | CharField(15) | nullable, blank |

#### Collateral
| Field | Type | Constraints |
|-------|------|-------------|
| `collateral_type` | CharField(200) | nullable, blank |
| `collateral_value` | DecimalField(15,2) | nullable, blank |
| `collateral_description` | TextField | nullable, blank |

#### Processing & Disbursement
| Field | Type | Constraints |
|-------|------|-------------|
| `disbursement_account` | ForeignKey(MemberAccount) | on_delete=SET_NULL, nullable, blank, related_name="loans_disbursed" |
| `processing_fee` | DecimalField(10,2) | default=0.00 |

#### NPA
| Field | Type | Constraints |
|-------|------|-------------|
| `npa_date` | DateField | nullable, blank |

#### Internal
| Field | Type | Constraints |
|-------|------|-------------|
| `purpose` | TextField | nullable, blank |
| `remarks` | TextField | nullable, blank |
| `approved_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, blank, related_name="loans_approved" |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="loans_created" |
| `created_at` | DateTimeField | auto_now_add=True |
| `updated_at` | DateTimeField | auto_now=True |

### Properties & Methods

| Name | Type | Description |
|------|------|-------------|
| `completion_percentage` | @property | `(emis_paid / total_emis) * 100`, rounded to 1 decimal |
| `is_npa` | @property | True if status in (active, defaulted) AND oldest overdue EMI >= 90 days (RBI norm) |
| `npa_category` | @property | "loss" (>=1095d), "doubtful" (>=365d), "substandard" (<365d) |
| `days_overdue` | @property | Days since oldest unresolved overdue EMI |
| `calculated_overdue_amount` | @property | Sum of all overdue EMI amounts |
| `calculate_emi()` | method | Reducing balance: `P * r * (1+r)^n / ((1+r)^n - 1)` where r = annual_rate/1200 |

### Meta
- `ordering = ["-created_at"]`

---

## Model 10: LoanRepayment

**Purpose:** Individual EMI installments within a loan. Generated on approval, updated when paid.
**Table:** `accounts_loanrepayment`

### Choice Constants

**PAYMENT_STATUS_CHOICES:**
| Value | Display |
|-------|---------|
| `paid` | Paid |
| `partial` | Partial |
| `overdue` | Overdue |
| `upcoming` | Upcoming |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `loan` | ForeignKey(Loan) | on_delete=CASCADE, related_name="repayments" |
| `installment_number` | IntegerField | required |
| `due_date` | DateField | required |
| `paid_date` | DateField | nullable, blank |
| `amount_due` | DecimalField(12,2) | required |
| `amount_paid` | DecimalField(12,2) | default=0.00 |
| `principal_component` | DecimalField(12,2) | default=0.00 |
| `interest_component` | DecimalField(12,2) | default=0.00 |
| `penalty` | DecimalField(10,2) | default=0.00 |
| `balance_after` | DecimalField(15,2) | default=0.00 |
| `payment_status` | CharField(20) | choices=PAYMENT_STATUS_CHOICES, default="upcoming" |
| `payment_mode` | CharField(20) | choices=Receipt.PAYMENT_MODE_CHOICES, default="cash" |
| `reference_number` | CharField(100) | nullable, blank |
| `receipt` | ForeignKey(Receipt) | on_delete=SET_NULL, nullable, blank, related_name="loan_repayments" |
| `remarks` | TextField | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["installment_number"]`
- `unique_together = ["loan", "installment_number"]`

---

## Model 11: AuditLog

**Purpose:** Immutable audit trail for every significant action in the system.
**Table:** `accounts_auditlog`

### Choice Constants

**ACTION_CHOICES:**
| Value | Display |
|-------|---------|
| `create` | Create |
| `update` | Update |
| `delete` | Delete |
| `login` | Login |
| `logout` | Logout |
| `approve` | Approve |
| `reject` | Reject |
| `reset_password` | Reset Password |
| `export` | Export |

**ENTITY_CHOICES:**
| Value | Display |
|-------|---------|
| `member` | Member |
| `account` | Account |
| `receipt` | Receipt |
| `voucher` | Voucher |
| `loan` | Loan |
| `fund` | Fund |
| `system` | System |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `user` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="audit_logs" |
| `action` | CharField(20) | choices=ACTION_CHOICES, indexed |
| `entity_type` | CharField(20) | choices=ENTITY_CHOICES, indexed |
| `entity_id` | IntegerField | nullable, blank |
| `description` | TextField | required |
| `ip_address` | GenericIPAddressField | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True, indexed |

### Meta
- `ordering = ["-created_at"]`

---

## Model 12: FundAccount

**Purpose:** Organizational fund accounts (welfare, reserve, statutory, etc.) as mandated by RCS Act.
**Table:** `accounts_fundaccount`

### Choice Constants

**FUND_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `welfare` | Welfare Fund |
| `library` | Library Fund |
| `education` | Education Fund |
| `emergency` | Emergency Fund |
| `dividend` | Dividend Fund |
| `statutory` | Statutory Fund |
| `reserve` | Reserve Fund |
| `other` | Other |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | CharField(200) | required |
| `fund_type` | CharField(20) | choices=FUND_TYPE_CHOICES, indexed |
| `account_number` | CharField(20) | unique, indexed |
| `balance` | DecimalField(15,2) | default=0.00 |
| `description` | TextField | nullable, blank |
| `is_active` | BooleanField | default=True |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="funds_created" |
| `created_at` | DateTimeField | auto_now_add=True |
| `updated_at` | DateTimeField | auto_now=True |
| `is_deleted` | BooleanField | default=False, indexed |
| `deleted_at` | DateTimeField | nullable, blank |

### Meta
- `ordering = ["name"]`

---

## Model 13: FundTransaction

**Purpose:** Every credit/debit movement within a fund account.
**Table:** `accounts_fundtransaction`

### Choice Constants

**TRANSACTION_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `credit` | Credit |
| `debit` | Debit |

**PAYMENT_MODE_CHOICES:**
| Value | Display |
|-------|---------|
| `cash` | Cash |
| `cheque` | Cheque |
| `online` | Online Transfer |
| `neft` | NEFT |
| `rtgs` | RTGS |
| `upi` | UPI |
| `internal` | Internal Transfer |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `fund` | ForeignKey(FundAccount) | on_delete=CASCADE, related_name="transactions" |
| `transaction_type` | CharField(20) | choices=TRANSACTION_TYPE_CHOICES, indexed |
| `amount` | DecimalField(15,2) | required |
| `description` | TextField | required |
| `payment_mode` | CharField(20) | choices=PAYMENT_MODE_CHOICES, default="internal" |
| `reference_number` | CharField(100) | nullable, blank |
| `balance_after` | DecimalField(15,2) | default=0.00 |
| `trigger_event` | CharField(50) | nullable, blank |
| `source_member` | ForeignKey(User) | on_delete=SET_NULL, nullable, blank, related_name="fund_transactions" |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="fund_transactions_created" |
| `remarks` | TextField | nullable, blank |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["-created_at"]`

---

## Model 14: FundAllocationRule

**Purpose:** Configurable rules that automatically allocate money to funds on specific trigger events.
**Table:** `accounts_fundallocationrule`

### Choice Constants

**TRIGGER_EVENT_CHOICES:**
| Value | Display |
|-------|---------|
| `member_registration` | Member Registration |
| `loan_interest` | Loan Interest |
| `loan_penalty` | Loan Penalty |
| `account_interest` | Account Interest |
| `annual_profit` | Annual Profit |
| `manual` | Manual |

**ALLOCATION_TYPE_CHOICES:**
| Value | Display |
|-------|---------|
| `fixed` | Fixed Amount |
| `percentage` | Percentage |

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `trigger_event` | CharField(50) | choices=TRIGGER_EVENT_CHOICES, indexed |
| `fund` | ForeignKey(FundAccount) | on_delete=CASCADE, related_name="allocation_rules" |
| `allocation_type` | CharField(20) | choices=ALLOCATION_TYPE_CHOICES |
| `amount` | DecimalField(10,2) | nullable, blank |
| `percentage` | DecimalField(5,2) | nullable, blank |
| `is_active` | BooleanField | default=True |
| `description` | TextField | nullable, blank |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="allocation_rules_created" |
| `created_at` | DateTimeField | auto_now_add=True |
| `updated_at` | DateTimeField | auto_now=True |

### Meta
- `ordering = ["trigger_event", "fund"]`

---

## Model 15: InterestPayout

**Purpose:** Records interest posted to member deposit accounts during periodic interest calculation.
**Table:** `accounts_interestpayout`

### Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `account` | ForeignKey(MemberAccount) | on_delete=CASCADE, related_name="interest_payouts" |
| `amount` | DecimalField(12,2) | required |
| `period_start` | DateField | required |
| `period_end` | DateField | required |
| `created_by` | ForeignKey(User) | on_delete=SET_NULL, nullable, related_name="interest_payouts_created" |
| `created_at` | DateTimeField | auto_now_add=True |

### Meta
- `ordering = ["-created_at"]`

---

## Migration History

27 migrations in `accounts/migrations/`:

| Phase | Migrations | What Was Added |
|-------|-----------|----------------|
| **Core User & Auth** | 0001-0005 | Initial schema, notification fields, bio removal, user managers, role field |
| **User Expansion** | 0006-0010 | Full Indian-format user fields, validators, bank account model (later removed), member_id/type/status |
| **Financial Products** | 0011-0014 | MemberAccount, Receipt, Loan + LoanRepayment, account_type modifications |
| **Data Integrity** | 0015-0016 | Soft-delete (is_deleted, deleted_at), removed full_name field |
| **Audit & Funds** | 0017-0019 | AuditLog, dead code cleanup, FundAccount + FundTransaction + FundAllocationRule |
| **Advanced Finance** | 0020 | NPA date on Loan, processing_fee on Loan, InterestPayout model |
| **Notifications** | 0021-0024 | Email notification settings, Notification model, LoginOTPChallenge + UserDevice, push_notifications_enabled |
| **Vouchers** | 0025-0027 | Voucher + VoucherEntry, member resignation status, voucher_type (voucher/contra_voucher) |

---

## Database Configuration

**Engine:** PostgreSQL 15 (Alpine)

```
DB_NAME=adminpanel
DB_USER=admin
DB_PASSWORD=<from .env>
DB_HOST=db (Docker) / localhost (local dev)
DB_PORT=5432
```

**Django Settings:**
- `AUTH_USER_MODEL = "accounts.User"`
- `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`
- `TIME_ZONE = "Asia/Kolkata"`
- `USE_TZ = True`

**Docker:** PostgreSQL 15-alpine with persistent named volume `postgres_data`. Auto-migrates on container start.

---

## Statistics

| Metric | Count |
|--------|-------|
| Total models | 15 |
| Total fields (custom, excluding inherited) | ~200 |
| Total ForeignKey relationships | 30 |
| Choice constant sets | 27 |
| Module-level validators | 5 |
| Soft-delete models | 3 |
| Models with auto-generated numbers | 6 |
| Migrations | 27 |
