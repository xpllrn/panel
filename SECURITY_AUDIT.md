# Django Banking System - Complete Security Audit

**Generated:** March 22, 2026  
**Purpose:** Security hook configuration for Kiro AI

---

## 1. DJANGO APPS

### accounts
- **Purpose:** User authentication, profile management, and core banking models
- **Models:** User, MemberAccount, Receipt, Loan, LoanRepayment, BankAccount, AuditLog
- **Views:** login_view, logout_view, signup_view (disabled), api_info
- **Key Features:** Custom User model, KYC management, audit logging

### admin_portal
- **Purpose:** Administrative interface for managing members, accounts, loans, and transactions
- **Models:** None (uses accounts models)
- **Views:** 40+ admin views for CRUD operations
- **Key Features:** Dashboard, member management, account management, loan processing, receipt generation, audit logs, Excel exports

### member_portal
- **Purpose:** Member-facing portal for viewing accounts, loans, and transactions
- **Models:** None (uses accounts models)
- **Views:** Dashboard, accounts, loans, transactions, profile
- **Key Features:** Read-only access to member's own data, password change

### config
- **Purpose:** Django project configuration
- **Contains:** settings.py, urls.py, wsgi.py, asgi.py

---

## 2. MODELS - COMPLETE FIELD INVENTORY


### User Model (accounts.User)
**Extends:** AbstractUser  
**Custom User Model:** AUTH_USER_MODEL = "accounts.User"

**Core Identity Fields:**
- member_id: CharField(50, unique=True, nullable) - indexed
- member_type: CharField(20, choices) - regular/nominal/associate/staff - indexed
- status: CharField(20, choices) - active/inactive/closed/deceased/blacklisted - indexed
- date_of_joining: DateField(nullable)
- exit_date: DateField(nullable)
- closure_reason: TextField(nullable)

**Personal Details:**
- date_of_birth: DateField(nullable)
- gender: CharField(10, choices) - male/female/other
- marital_status: CharField(20, choices) - single/married/divorced/widowed
- occupation: CharField(200, nullable)
- annual_income_bracket: CharField(100, nullable)
- education_qualification: CharField(200, nullable)

**Contact Information:**
- mobile_primary: CharField(15, nullable, validated) - phone_validator
- mobile_alternate: CharField(15, nullable, validated) - phone_validator
- preferred_comm_mode: CharField(20, choices) - sms/email/whatsapp/letter
- dnd_enabled: BooleanField(default=False)

**Address Fields (Current):**
- current_address_line1: CharField(255, nullable)
- current_address_line2: CharField(255, nullable)
- current_city: CharField(100, nullable)
- current_district: CharField(100, nullable)
- current_state: CharField(100, nullable)
- current_pincode: CharField(10, nullable, validated) - pincode_validator
- current_country: CharField(100, default="India")


**Address Fields (Permanent):**
- permanent_same_as_current: BooleanField(default=True)
- permanent_address_line1: CharField(255, nullable)
- permanent_address_line2: CharField(255, nullable)
- permanent_city: CharField(100, nullable)
- permanent_district: CharField(100, nullable)
- permanent_state: CharField(100, nullable)
- permanent_pincode: CharField(10, nullable, validated) - pincode_validator
- permanent_country: CharField(100, default="India")

**KYC & Identity Proofs:**
- kyc_status: CharField(20, choices) - pending/verified/rejected/expired
- kyc_verified_date: DateField(nullable)
- kyc_verified_by: CharField(200, nullable)
- aadhar_number: CharField(12, nullable, validated) - aadhar_validator
- pan_number: CharField(10, nullable, validated) - pan_validator
- voter_id: CharField(20, nullable)
- passport_number: CharField(20, nullable)
- driving_license: CharField(20, nullable)
- aadhar_copy: FileField(upload_to="kyc/aadhar/", nullable)
- pan_copy: FileField(upload_to="kyc/pan/", nullable)
- address_proof: FileField(upload_to="kyc/address/", nullable)
- photograph: ImageField(upload_to="kyc/photos/", nullable)
- signature_specimen: ImageField(upload_to="kyc/signatures/", nullable)

**Banking Relationship Flags:**
- eligible_for_accounts: BooleanField(default=True)
- eligible_for_loans: BooleanField(default=True)
- eligible_for_dividend: BooleanField(default=True)
- eligible_for_voting: BooleanField(default=True)
- risk_category: CharField(20, choices) - low/medium/high

**Shareholding & Membership Capital:**
- share_capital_amount: DecimalField(12, 2, default=0.00)
- number_of_shares: IntegerField(default=0)
- face_value_per_share: DecimalField(10, 2, default=0.00)
- share_certificate_number: CharField(50, nullable)
- share_issue_date: DateField(nullable)
- dividend_payable_balance: DecimalField(12, 2, default=0.00)
- last_dividend_paid_date: DateField(nullable)


**Nominee Details:**
- nominee_name: CharField(200, nullable)
- nominee_relationship: CharField(100, nullable)
- nominee_dob: DateField(nullable)
- nominee_contact: CharField(15, nullable)
- nominee_address: TextField(nullable)
- nominee_id_type: CharField(50, nullable)
- nominee_id_number: CharField(50, nullable)
- alt_nominee_name: CharField(200, nullable)
- alt_nominee_relationship: CharField(100, nullable)
- alt_nominee_dob: DateField(nullable)
- alt_nominee_contact: CharField(15, nullable)

**Account & Loan Summary (Read-Only):**
- total_accounts_count: IntegerField(default=0, editable=False)
- active_savings_accounts: IntegerField(default=0, editable=False)
- active_fd_accounts: IntegerField(default=0, editable=False)
- active_rd_accounts: IntegerField(default=0, editable=False)
- active_loan_accounts: IntegerField(default=0, editable=False)
- total_deposit_balance: DecimalField(15, 2, default=0.00, editable=False)
- total_loan_outstanding: DecimalField(15, 2, default=0.00, editable=False)

**Internal Controls & Compliance:**
- introducer_member: ForeignKey(User, nullable)
- introducer_approval_date: DateField(nullable)
- board_approval_reference: CharField(100, nullable)
- aml_check_status: CharField(50, nullable)
- last_compliance_review_date: DateField(nullable)
- internal_remarks: TextField(nullable)

**User/System Mapping:**
- portal_access_enabled: BooleanField(default=True)

**Soft-Delete Support:**
- is_deleted: BooleanField(default=False) - indexed
- deleted_at: DateTimeField(nullable)

**Legacy Fields:**
- role: CharField(20, default="member") - indexed (admin/member/viewer)
- phone: CharField(20, nullable) - DEPRECATED, use mobile_primary
- avatar: ImageField(upload_to="avatars/", nullable) - DEPRECATED, use photograph

**Inherited from AbstractUser:**
- username: CharField(150, unique=True)
- first_name: CharField(150)
- last_name: CharField(150)
- email: EmailField
- is_staff: BooleanField(default=False)
- is_active: BooleanField(default=True)
- is_superuser: BooleanField(default=False)
- date_joined: DateTimeField(auto_now_add=True)
- last_login: DateTimeField(nullable)
- password: CharField(128) - hashed


**User Model Methods:**
- display_name: @property - returns "first_name last_name" or username
- age: @property - calculates age from date_of_birth
- generate_password_from_dob(): Returns DDMMFIRSTFOUR format password
- reset_password_to_dob(): Resets password to DOB-based format
- get_role_display_name(): Returns capitalized role
- is_admin_role(): Returns True if role=="admin" or is_superuser
- can_manage_users(): Returns True if is_superuser or role=="admin"

---

### MemberAccount Model (accounts.MemberAccount)
**Purpose:** Internal society accounts for member deposits

**Core Fields:**
- user: ForeignKey(User, CASCADE) - related_name="member_accounts"
- account_number: CharField(20, unique=True) - indexed
- account_type: CharField(20, choices) - fd/cd/rd/od/share/sukanya/suputra - indexed
- status: CharField(20, choices) - active/closed/frozen/matured/dormant - indexed

**Financial Details:**
- balance: DecimalField(15, 2, default=0.00)
- interest_rate: DecimalField(5, 2, default=0.00)
- principal_amount: DecimalField(15, 2, default=0.00)
- accrued_interest: DecimalField(15, 2, default=0.00)

**RD-Specific Fields:**
- rd_monthly_amount: DecimalField(12, 2, nullable)
- rd_installments_paid: IntegerField(default=0)
- rd_total_installments: IntegerField(nullable)

**Dates:**
- opening_date: DateField
- maturity_date: DateField(nullable)
- closure_date: DateField(nullable)
- last_transaction_date: DateField(nullable)
- last_interest_calc_date: DateField(nullable)

**Tenure:**
- tenure_months: IntegerField(nullable)

**Nominee (Account-Level Override):**
- nominee_name: CharField(200, nullable)
- nominee_relationship: CharField(100, nullable)

**Internal Tracking:**
- remarks: TextField(nullable)
- created_at: DateTimeField(auto_now_add=True)
- updated_at: DateTimeField(auto_now=True)

**Soft-Delete:**
- is_deleted: BooleanField(default=False) - indexed
- deleted_at: DateTimeField(nullable)

**Properties:**
- is_term_deposit: @property - True if fd/rd/cd/sukanya/suputra
- maturity_amount: @property - Calculates estimated maturity with simple interest


---

### Receipt Model (accounts.Receipt)
**Purpose:** Financial transaction tracking and receipt generation

**Core Fields:**
- receipt_number: CharField(20, unique=True) - indexed
- user: ForeignKey(User, CASCADE) - related_name="receipts"
- member_account: ForeignKey(MemberAccount, CASCADE) - related_name="receipts"

**Transaction Details:**
- transaction_type: CharField(20, choices) - credit/debit/transfer/interest/dividend/share_capital - indexed
- amount: DecimalField(15, 2)
- description: TextField(nullable)

**Payment Details:**
- payment_mode: CharField(20, choices) - cash/cheque/online/neft/rtgs/upi
- reference_number: CharField(100, nullable)
- balance_after: DecimalField(15, 2, default=0.00)

**Internal Tracking:**
- created_by: ForeignKey(User, SET_NULL, nullable) - related_name="receipts_created"
- remarks: TextField(nullable)
- created_at: DateTimeField(auto_now_add=True)

---

### Loan Model (accounts.Loan)
**Purpose:** Member loan tracking with EMI management

**Core Fields:**
- loan_number: CharField(20, unique=True) - indexed
- user: ForeignKey(User, CASCADE) - related_name="loans"
- loan_type: CharField(20, choices) - personal/home/vehicle/gold/education/business/emergency/agriculture - indexed
- status: CharField(20, choices) - pending/approved/active/closed/defaulted/written_off/rejected - indexed

**Financial Details:**
- principal_amount: DecimalField(15, 2)
- interest_rate: DecimalField(5, 2)
- interest_type: CharField(20, choices) - flat/reducing
- tenure_months: IntegerField
- emi_amount: DecimalField(12, 2, default=0.00)

**Balance Tracking:**
- total_payable: DecimalField(15, 2, default=0.00)
- total_paid: DecimalField(15, 2, default=0.00)
- outstanding_balance: DecimalField(15, 2, default=0.00)
- overdue_amount: DecimalField(15, 2, default=0.00)

**Dates:**
- application_date: DateField
- approval_date: DateField(nullable)
- disbursement_date: DateField(nullable)
- first_emi_date: DateField(nullable)
- last_emi_date: DateField(nullable)
- closure_date: DateField(nullable)

**EMI Tracking:**
- total_emis: IntegerField(default=0)
- emis_paid: IntegerField(default=0)
- emis_overdue: IntegerField(default=0)

**Guarantor Details:**
- guarantor_name: CharField(200, nullable)
- guarantor_member_id: CharField(50, nullable)
- guarantor_relationship: CharField(100, nullable)
- guarantor_contact: CharField(15, nullable)

**Collateral/Security:**
- collateral_type: CharField(200, nullable)
- collateral_value: DecimalField(15, 2, nullable)
- collateral_description: TextField(nullable)

**Linked Account:**
- disbursement_account: ForeignKey(MemberAccount, SET_NULL, nullable) - related_name="loans_disbursed"

**Internal Tracking:**
- purpose: TextField(nullable)
- remarks: TextField(nullable)
- approved_by: ForeignKey(User, SET_NULL, nullable) - related_name="loans_approved"
- created_by: ForeignKey(User, SET_NULL, nullable) - related_name="loans_created"
- created_at: DateTimeField(auto_now_add=True)
- updated_at: DateTimeField(auto_now=True)

**Properties:**
- completion_percentage: @property - (emis_paid / total_emis) * 100

**Methods:**
- calculate_emi(): Calculates EMI using reducing balance formula


---

### LoanRepayment Model (accounts.LoanRepayment)
**Purpose:** Individual EMI payment tracking

**Core Fields:**
- loan: ForeignKey(Loan, CASCADE) - related_name="repayments"
- installment_number: IntegerField
- due_date: DateField
- paid_date: DateField(nullable)

**Payment Details:**
- amount_due: DecimalField(12, 2)
- amount_paid: DecimalField(12, 2, default=0.00)
- principal_component: DecimalField(12, 2, default=0.00)
- interest_component: DecimalField(12, 2, default=0.00)
- penalty: DecimalField(10, 2, default=0.00)
- balance_after: DecimalField(15, 2, default=0.00)
- payment_status: CharField(20, choices) - paid/partial/overdue/upcoming

**Payment Mode:**
- payment_mode: CharField(20, choices) - cash/cheque/online/neft/rtgs/upi
- reference_number: CharField(100, nullable)

**Linked Receipt:**
- receipt: ForeignKey(Receipt, SET_NULL, nullable) - related_name="loan_repayments"

**Internal:**
- remarks: TextField(nullable)
- created_at: DateTimeField(auto_now_add=True)

**Unique Constraint:** (loan, installment_number)

---

### BankAccount Model (accounts.BankAccount)
**Purpose:** External bank accounts for member payouts

**Fields:**
- user: ForeignKey(User, CASCADE) - related_name="bank_accounts"
- account_name: CharField(200)
- bank_name: CharField(200)
- account_number: CharField(50)
- ifsc_code: CharField(11, nullable, validated) - ifsc_validator
- branch: CharField(200, nullable)
- account_type: CharField(50, nullable)
- created_at: DateTimeField(auto_now_add=True)
- updated_at: DateTimeField(auto_now=True)

---

### AuditLog Model (accounts.AuditLog)
**Purpose:** Comprehensive audit trail for all admin actions

**Fields:**
- user: ForeignKey(User, SET_NULL, nullable) - related_name="audit_logs"
- action: CharField(20, choices) - create/update/delete/login/logout/approve/reject/reset_password/export - indexed
- entity_type: CharField(20, choices) - member/account/receipt/loan/system - indexed
- entity_id: IntegerField(nullable)
- description: TextField
- ip_address: GenericIPAddressField(nullable)
- created_at: DateTimeField(auto_now_add=True) - indexed

---

## 3. AUTHENTICATION & AUTHORIZATION

### Authentication Method
- **Type:** Django Session Authentication
- **Custom User Model:** accounts.User (extends AbstractUser)
- **Login URL:** /login/
- **Login Redirect:** /home/ (admin) or /member/ (member)
- **Logout Redirect:** /login/

### Password Management
- **Validators:** UserAttributeSimilarity, MinimumLength(8), CommonPassword, NumericPassword
- **Auto-Generated Format:** DDMMFIRSTFOUR (e.g., "0211TANM" for DOB 02/11 and name starting with TANM)
- **Reset Method:** User.reset_password_to_dob() - resets to DOB-based password
- **Hashing:** Django default (PBKDF2)


### Groups & Permissions
**NO DJANGO GROUPS OR PERMISSIONS ARE USED**

The system uses a custom role-based access control (RBAC) system:

**Role Field:** User.role (CharField)
- **admin:** Full access to admin portal
- **member:** Access to member portal only
- **viewer:** Read-only access (not fully implemented)

**Staff Flag:** User.is_staff (BooleanField)
- Set to True when role="admin"
- Required for admin portal access

**Superuser Flag:** User.is_superuser (BooleanField)
- Django admin panel access
- Bypasses all permission checks

**Portal Access Flag:** User.portal_access_enabled (BooleanField)
- Can disable member portal access without deleting account
- Checked in member_required decorator

### Custom Decorators

**@admin_required** (admin_portal/views.py)
```python
def admin_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Access denied. Administrators only.")
        return view_func(request, *args, **kwargs)
    return wrapper
```
- Checks: request.user.is_staff == True
- Returns: 403 Forbidden if not staff

**@member_required** (member_portal/views.py)
```python
def member_required(view_func):
    @functools.wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_admin_role():
            return redirect("/home/")
        if not request.user.portal_access_enabled:
            return HttpResponseForbidden("Your portal access has been disabled. Contact admin.")
        return view_func(request, *args, **kwargs)
    return wrapper
```
- Checks: 
  1. User is authenticated (@login_required)
  2. User is NOT staff/admin (redirects to /home/)
  3. portal_access_enabled == True
- Returns: 403 Forbidden if portal access disabled

---

## 4. VIEWS - COMPLETE INVENTORY

### accounts/views.py (Authentication Views)

**signup_view(request)**
- **Type:** Function-based view
- **Method:** GET, POST
- **Auth:** None (public)
- **Permission:** None
- **Action:** DISABLED - redirects to /login/
- **Note:** Signup is disabled; members created by admins only

**login_view(request)**
- **Type:** Function-based view
- **Method:** GET, POST
- **Auth:** None (public)
- **Permission:** None
- **Form:** LoginForm (username, password)
- **Action:** Authenticates user, redirects based on role
- **Redirect Logic:**
  - is_staff or is_admin_role() → /home/
  - else → /member/

**logout_view(request)**
- **Type:** Function-based view
- **Method:** POST only
- **Auth:** @login_required
- **Permission:** None
- **Action:** Logs out user, redirects to /login/
- **Security:** POST-only to prevent CSRF


### accounts/api_views.py (API Views)

**api_info(request)**
- **Type:** DRF @api_view(["GET"])
- **Method:** GET
- **Auth:** SessionAuthentication (DRF default)
- **Permission:** IsAuthenticated (DRF default)
- **Action:** Returns API metadata
- **Data Exposed:** API version, endpoint list

---

### admin_portal/views.py (Admin Views - 40+ views)

**ALL ADMIN VIEWS USE:** @login_required + @admin_required
**Permission Check:** request.user.is_staff must be True

#### Dashboard & Home

**home_view(request)**
- **Methods:** GET
- **Data Exposed:** 
  - Member stats (total, active)
  - Account stats (total, active, total deposits)
  - Account type distribution
  - Receipt stats (total, today's count, today's credit/debit)
  - 7-day transaction trend
  - Recent 10 transactions
  - Overdue loan payments (top 10)
- **Queries:** Aggregates on User, MemberAccount, Receipt, LoanRepayment

#### Member Management

**members_view(request)**
- **Methods:** GET
- **Params:** page, q (search query)
- **Data Exposed:** Paginated member list (25 per page)
- **Search Fields:** username, email, first_name, last_name, member_id, mobile_primary
- **Filters:** is_deleted=False

**add_member_view(request)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Input:** username, email, full_name, date_of_birth, mobile_primary, role
- **Action:** 
  - Creates User with auto-generated password (DDMMFIRSTFOUR)
  - Auto-creates 7 account types (fd, cd, rd, od, share, sukanya, suputra)
  - Logs action to AuditLog
- **Returns:** JSON with user_id and generated password
- **Validation:** Duplicate username check
- **Security Risk:** Password returned in response

**get_member_view(request, user_id)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Data Exposed:** Complete member profile including:
  - All personal details
  - KYC information (aadhar_number, pan_number, etc.)
  - Financial data (share capital, dividend balance)
  - Nominee details
  - All member accounts summary
  - Internal remarks
- **Security Risk:** Exposes sensitive PII

**edit_member_view(request, user_id)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Input:** username, email, full_name, mobile_primary, role, password (optional)
- **Action:** Updates member, optionally changes password
- **Validation:** Duplicate username/email check, password strength validation
- **Logs:** AuditLog entry
- **Security Risk:** Can change any member's password

**delete_member_view(request, user_id)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Action:** Soft-deletes member (sets is_deleted=True, status='closed')
- **Protection:** Cannot delete self
- **Cascade:** Soft-deletes all member accounts
- **Logs:** AuditLog entry

**reset_member_password_view(request, user_id)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Action:** Resets password to DOB-based format
- **Returns:** JSON with new password
- **Logs:** AuditLog entry
- **Security Risk:** Password returned in response

**search_members_view(request)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Params:** q (min 2 chars)
- **Search Fields:** username, first_name, last_name, member_id
- **Returns:** JSON array (max 10 results)
- **Data Exposed:** id, username, full_name, member_id


#### Account Management

**accounts_view(request)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Params:** page, q (search query)
- **Data Exposed:** Account book grid showing all members and their account balances
- **Aggregates:** Total balance per account type, grand total
- **Pagination:** 50 members per page

**add_account_view(request)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Input:** user_id, account_type, balance, interest_rate, principal_amount, opening_date, maturity_date, tenure_months, nominee_name, nominee_relationship, remarks
- **Action:** Creates MemberAccount with auto-generated account_number
- **Format:** PREFIX-YEAR-SEQUENCE (e.g., FD-2026-00001)
- **Concurrency:** Uses select_for_update() with retry loop (max 5)
- **Logs:** AuditLog entry

**get_account_view(request, account_id)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Data Exposed:** Complete account details including user info
- **Security:** No ownership check - can view any account

**edit_account_view(request, account_id)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Input:** account_type, status, balance, interest_rate, principal_amount, opening_date, maturity_date, tenure_months, nominee details, remarks
- **Action:** Updates MemberAccount
- **Security:** No ownership check - can edit any account
- **Logs:** AuditLog entry

**delete_member_account_view(request, account_id)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Action:** Soft-deletes account (is_deleted=True, status='closed')
- **Security:** No ownership check - can delete any account
- **Logs:** AuditLog entry

**get_account_transactions_view(request, account_id)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Params:** page
- **Data Exposed:** Paginated transaction history (20 per page)
- **Security:** No ownership check - can view any account's transactions

**get_member_accounts_view(request, user_id)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Returns:** JSON array of active accounts for a member
- **Used For:** Cascading dropdown in forms

**get_member_transactions_view(request, user_id)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Params:** page
- **Returns:** JSON array of recent transactions (15 per page)
- **Security:** No ownership check

#### Receipt/Transaction Management

**receipts_view(request)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Params:** page, q (search), type (transaction_type), mode (payment_mode)
- **Data Exposed:** Paginated receipts (25 per page)
- **Search Fields:** receipt_number, user names, member_id, account_number, reference_number
- **Stats:** Total receipts, today's receipts

**get_receipt_view(request, receipt_id)**
- **Methods:** GET
- **Auth Check:** is_staff
- **Data Exposed:** Complete receipt details including:
  - Member info (name, ID, mobile, address)
  - Account info
  - Admin who created it
- **Security:** No ownership check

**add_receipt_view(request)**
- **Methods:** POST
- **Auth Check:** is_staff
- **Input:** user_id, account_id, transaction_type, amount, description, payment_mode, reference_number, remarks
- **Action:** 
  - Creates Receipt with auto-generated receipt_number
  - Updates account balance atomically using F() expressions
  - Uses select_for_update() with retry loop
- **Validation:** Sufficient balance check for debits
- **Format:** RCP-YEAR-SEQUENCE
- **Logs:** AuditLog entry
- **Security Risk:** Can create transactions for any member

