# Cooperative Society REST API Documentation

## Overview

The Cooperative Society API provides programmatic access to all banking operations. It is built with Django REST Framework and supports JWT authentication, making it suitable for mobile apps, third-party integrations, and frontend SPAs.

**Base URL:** `http://localhost:8000/api/v1/`
**Interactive Docs (Swagger):** `http://localhost:8000/api/v1/docs/`
**API Schema (OpenAPI 3.0):** `http://localhost:8000/api/v1/schema/`

---

## Authentication

The API uses **JWT (JSON Web Tokens)** for authentication. All endpoints (except `/api/v1/` and `/api/v1/auth/login/`) require a valid access token.

### Login (Get Tokens)

```
POST /api/v1/auth/login/
Content-Type: application/json

{
    "username": "admin",
    "password": "admin123"
}
```

**Response:**
```json
{
    "access": "eyJhbGciOiJIUzI1NiI...",
    "refresh": "eyJhbGciOiJIUzI1NiI..."
}
```

| Token | Lifetime | Purpose |
|-------|----------|---------|
| `access` | 12 hours | Used in Authorization header for API calls |
| `refresh` | 7 days | Used to get a new access token without re-login |

### Using the Access Token

Include the access token in the `Authorization` header of every API request:

```
GET /api/v1/admin/members/
Authorization: Bearer eyJhbGciOiJIUzI1NiI...
```

### Refresh Token (Get New Access Token)

When the access token expires, use the refresh token to get a new one:

```
POST /api/v1/auth/refresh/
Content-Type: application/json

{
    "refresh": "eyJhbGciOiJIUzI1NiI..."
}
```

**Response:**
```json
{
    "access": "eyJhbGciOiJIUzI1NiI..."
}
```

### Get Current User Profile

```
GET /api/v1/auth/profile/
Authorization: Bearer <token>
```

**Response:**
```json
{
    "id": 1,
    "username": "admin",
    "member_id": null,
    "display_name": "Admin",
    "first_name": "Admin",
    "last_name": "",
    "email": "admin@example.com",
    "member_type": "regular",
    "status": "active",
    "share_capital_amount": "0.00",
    "number_of_shares": 0,
    "dividend_payable_balance": "0.00"
}
```

---

## Two Access Levels

| Role | Prefix | Access |
|------|--------|--------|
| **Admin** (staff users) | `/api/v1/admin/` | Full CRUD on all resources |
| **Member** (regular users) | `/api/v1/member/` | Read-only access to own data |

The API automatically determines the user's role from the JWT token. An admin user cannot access `/api/v1/member/` endpoints and vice versa.

---

## Response Format

### Success (Single Object)
```json
{
    "id": 1,
    "member_id": "MBR-2026-00001",
    "display_name": "Suresh Desai",
    ...
}
```

### Success (Paginated List)
```json
{
    "count": 26,
    "next": "http://localhost:8000/api/v1/admin/members/?page=2",
    "previous": null,
    "results": [
        { "id": 1, ... },
        { "id": 2, ... }
    ]
}
```

### Error
```json
{
    "error": "Member not found"
}
```
or
```json
{
    "errors": {
        "email": ["This field is required."],
        "mobile_primary": ["Phone must be 10 digits starting with 6, 7, 8, or 9"]
    }
}
```

---

## Admin API Endpoints

### Members

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/members/` | List all members (paginated) |
| `POST` | `/api/v1/admin/members/create/` | Create a new member |
| `GET` | `/api/v1/admin/members/{id}/` | Get member detail + accounts + loans |
| `PUT/PATCH` | `/api/v1/admin/members/{id}/update/` | Update member details |
| `DELETE` | `/api/v1/admin/members/{id}/delete/` | Soft-delete a member |

**Query Parameters for List:**
- `search` — Search by name, member_id, or phone
- `status` — Filter: `active`, `inactive`, `closed`, `deceased`, `blacklisted`
- `member_type` — Filter: `regular`, `nominal`, `associate`, `staff`
- `page` — Page number (default: 1)
- `page_size` — Items per page (default: 20)

**Create Member Example:**
```
POST /api/v1/admin/members/create/
Content-Type: application/json

{
    "full_name": "Rajesh Kumar",
    "email": "rajesh@example.com",
    "member_type": "regular",
    "date_of_birth": "1990-05-15",
    "gender": "male",
    "mobile_primary": "9876543210",
    "aadhar_number": "234567890123",
    "pan_number": "ABCDE1234F",
    "current_address_line1": "123 Main St",
    "current_city": "Mumbai",
    "current_state": "Maharashtra",
    "current_pincode": "400001"
}
```

The system automatically:
- Generates a `member_id` (e.g., `MEM-2026-0027`)
- Generates a username from the member_id
- Sets the password from DOB (DDMM + first 4 chars of name uppercase)
- Applies fund allocation rules for `member_registration`

### Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/accounts/` | List all accounts |
| `POST` | `/api/v1/admin/accounts/create/` | Create a new account |
| `GET` | `/api/v1/admin/accounts/{id}/` | Get account detail + recent transactions |
| `PUT/PATCH` | `/api/v1/admin/accounts/{id}/update/` | Update account |
| `DELETE` | `/api/v1/admin/accounts/{id}/delete/` | Soft-delete (only if zero balance) |

**Query Parameters:**
- `type` — Filter: `fd`, `cd`, `rd`, `od`, `share`, `sukanya`, `suputra`
- `status` — Filter: `active`, `closed`, `frozen`, `matured`, `dormant`
- `user` — Filter by member user ID

**Create Account Example:**
```json
{
    "user": 132,
    "account_type": "fd",
    "interest_rate": 7.5,
    "principal_amount": 100000,
    "opening_date": "2026-04-01",
    "maturity_date": "2027-04-01",
    "tenure_months": 12
}
```

### Receipts (Transactions)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/receipts/` | List all receipts |
| `POST` | `/api/v1/admin/receipts/create/` | Create a receipt (deposit/withdrawal) |
| `GET` | `/api/v1/admin/receipts/{id}/` | Get receipt detail |

**Create Receipt (Deposit) Example:**
```json
{
    "member_account": 45,
    "transaction_type": "credit",
    "amount": 5000.00,
    "payment_mode": "cash",
    "description": "Monthly deposit"
}
```

The system automatically:
- Generates a unique receipt number (e.g., `RCP-2026-00940`)
- Updates account balance atomically using `F()` expressions
- Records the `balance_after` snapshot
- Creates an audit log entry

**Transaction types:** `credit`, `debit`, `transfer`, `interest`, `dividend`, `share_capital`
**Payment modes:** `cash`, `cheque`, `online`, `neft`, `rtgs`, `upi`

### Loans

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/loans/` | List all loans |
| `POST` | `/api/v1/admin/loans/create/` | Create a loan application |
| `GET` | `/api/v1/admin/loans/{id}/` | Get loan detail + repayment schedule |
| `POST` | `/api/v1/admin/loans/{id}/approve/` | Approve loan + generate EMI schedule |
| `POST` | `/api/v1/admin/loans/{id}/record-emi/` | Record an EMI payment |

**Query Parameters:**
- `status` — Filter: `pending`, `approved`, `active`, `closed`, `defaulted`, `written_off`, `rejected`
- `type` — Filter: `personal`, `home`, `vehicle`, `gold`, `education`, `business`, `emergency`, `agriculture`
- `user` — Filter by member user ID

**Create Loan Example:**
```json
{
    "user": 132,
    "loan_type": "personal",
    "principal_amount": 100000,
    "interest_rate": 12.0,
    "tenure_months": 24,
    "processing_fee": 1000,
    "purpose": "Home renovation",
    "guarantor_name": "Vijay Kumar",
    "guarantor_contact": "9876543210"
}
```

The system automatically:
- Generates a loan number (e.g., `LN-2026-00030`)
- Calculates EMI using reducing balance method
- Sets status to `pending` (requires approval by a **different** admin)

**Approve Loan:**
```
POST /api/v1/admin/loans/15/approve/
Content-Type: application/json

{
    "disbursement_date": "2026-04-10"
}
```

This generates the full repayment schedule with principal/interest split for each EMI.

**Important:** The admin who created the loan **cannot** approve it (segregation of duties). Another admin must approve.

**Record EMI Payment:**
```
POST /api/v1/admin/loans/15/record-emi/
Content-Type: application/json

{
    "installment_number": 1,
    "amount_paid": 4707.35,
    "payment_mode": "cash"
}
```

The system automatically:
- Calculates late penalty (2% per month on overdue amount)
- Creates a receipt for the payment
- Updates loan outstanding balance
- Marks overdue EMIs
- Closes the loan when all EMIs are paid

### Funds

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/funds/` | List all funds |
| `POST` | `/api/v1/admin/funds/create/` | Create a new fund |
| `GET` | `/api/v1/admin/funds/{id}/` | Get fund detail + transactions |
| `PUT/PATCH` | `/api/v1/admin/funds/{id}/update/` | Update fund |
| `DELETE` | `/api/v1/admin/funds/{id}/delete/` | Soft-delete fund |
| `POST` | `/api/v1/admin/funds/{id}/add-transaction/` | Add credit/debit to fund |

**Fund types:** `welfare`, `library`, `education`, `emergency`, `dividend`, `statutory`, `reserve`, `other`

**Add Fund Transaction Example:**
```json
{
    "transaction_type": "credit",
    "amount": 5000,
    "description": "Monthly welfare collection",
    "payment_mode": "cash"
}
```

### Allocation Rules

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/allocation-rules/` | List all rules |
| `POST` | `/api/v1/admin/allocation-rules/create/` | Create a rule |
| `PUT/PATCH` | `/api/v1/admin/allocation-rules/{id}/update/` | Update a rule |
| `DELETE` | `/api/v1/admin/allocation-rules/{id}/delete/` | Delete a rule |

**Trigger events:** `member_registration`, `loan_interest`, `loan_penalty`, `account_interest`, `annual_profit`, `manual`

**Create Rule Example:**
```json
{
    "trigger_event": "annual_profit",
    "fund": 1,
    "allocation_type": "percentage",
    "percentage": 25.0,
    "description": "25% of annual profit to Reserve Fund (RCS Act mandate)"
}
```

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/reports/summary/` | Get financial summary for a period |
| `POST` | `/api/v1/admin/reports/distribute-profit/` | Distribute annual profit to funds |

**Financial Summary Query Parameters:**
- `period` — `month`, `quarter`, or `year` (default: `year`)
- `year` — Year (default: current year)
- `month` — Month number (1-12, only for `period=month`)
- `quarter` — Quarter number (1-4, only for `period=quarter`)

**Example:**
```
GET /api/v1/admin/reports/summary/?period=year&year=2025
```

**Response includes:**
- `loan_interest_income` — Total interest earned from loan repayments
- `penalty_income` — Late penalty fees collected
- `processing_fees` — Loan processing fees
- `deposit_interest_expense` — Interest liability on member deposits
- `gross_revenue` — Total revenue
- `net_profit` — Revenue minus expenses
- `active_loans_count`, `total_loans_outstanding`, `total_overdue`
- `npa_count` — Number of NPA (Non-Performing Asset) loans
- `recovery_rate` — Percentage of EMIs collected vs due
- `deposit_by_type` — Deposit portfolio breakdown by account type
- `monthly_interest_liability` — Monthly interest expense

**Distribute Profit:**
```
POST /api/v1/admin/reports/distribute-profit/
Content-Type: application/json

{
    "year": 2025
}
```

This applies all `annual_profit` allocation rules and distributes the calculated net profit to the configured funds.

### Interest Posting & Dividends

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/admin/interest/post/` | Calculate and post accrued interest to all deposit accounts |
| `POST` | `/api/v1/admin/dividend/distribute/` | Distribute dividends to eligible members |

**Post Interest:**
```
POST /api/v1/admin/interest/post/
```

Calculates daily interest on all active deposit accounts (FD, RD, CD, Sukanya, Suputra) from each account's `last_interest_calc_date` to today. Creates `InterestPayout` records and interest receipts, and credits the interest to each account balance.

**Response:**
```json
{
    "success": true,
    "message": "Posted ₹12,450 interest to 35 accounts.",
    "total_posted": "12450.00",
    "accounts_updated": 35
}
```

**Distribute Dividend:**
```
POST /api/v1/admin/dividend/distribute/
Content-Type: application/json

{
    "year": 2025,
    "dividend_rate": 10
}
```

Calculates dividend for each eligible member as `share_capital * rate / 100`, updates their `dividend_payable_balance`, and debits from the Dividend Fund (if configured).

**Response:**
```json
{
    "success": true,
    "message": "Distributed ₹50,000 @ 10% to 25 members.",
    "total_distributed": "50000.00",
    "member_count": 25
}
```

### Health Check

```
GET /health/
```

Returns database connectivity status. No authentication required.

```json
{
    "status": "ok",
    "database": "connected"
}
```

### Audit Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/audit-logs/` | List audit logs (paginated) |

**Query Parameters:**
- `action` — Filter: `create`, `update`, `delete`, `login`, `logout`, `approve`, `reject`, `reset_password`, `export`
- `entity_type` — Filter: `member`, `account`, `receipt`, `loan`, `fund`, `system`
- `page_size` — Items per page (default: 50)

---

## Member API Endpoints

These endpoints are for **member users only** (non-staff). Members can only view their own data.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/member/dashboard/` | Dashboard summary (accounts, loans, transactions) |
| `GET` | `/api/v1/member/accounts/` | List own accounts |
| `GET` | `/api/v1/member/accounts/{id}/` | Account detail + transaction history |
| `GET` | `/api/v1/member/loans/` | List own loans |
| `GET` | `/api/v1/member/loans/{id}/` | Loan detail + repayment schedule |
| `GET` | `/api/v1/member/transactions/` | All transactions across accounts |

**Dashboard Response includes:**
- Member profile (name, member_id, contact)
- Share capital and dividend information
- Account summaries (balance, count)
- Active loan summaries (outstanding, EMI)
- Recent transactions

**Transaction Filters:**
- `type` — Filter by transaction type
- `account` — Filter by account ID

---

## Using the API in a Mobile App

### Android / React Native / Flutter Integration

**Step 1: Login and store tokens**
```javascript
// Login
const response = await fetch('https://your-domain.com/api/v1/auth/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'member_user', password: 'password123' })
});
const { access, refresh } = await response.json();

// Store tokens securely
await SecureStorage.setItem('access_token', access);
await SecureStorage.setItem('refresh_token', refresh);
```

**Step 2: Make authenticated API calls**
```javascript
const token = await SecureStorage.getItem('access_token');
const response = await fetch('https://your-domain.com/api/v1/member/dashboard/', {
    headers: { 'Authorization': `Bearer ${token}` }
});
const data = await response.json();
```

**Step 3: Handle token expiry**
```javascript
async function apiCall(url, options = {}) {
    let token = await SecureStorage.getItem('access_token');
    options.headers = { ...options.headers, 'Authorization': `Bearer ${token}` };

    let response = await fetch(url, options);

    // If token expired (401), refresh it
    if (response.status === 401) {
        const refresh = await SecureStorage.getItem('refresh_token');
        const refreshResponse = await fetch('https://your-domain.com/api/v1/auth/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh })
        });

        if (refreshResponse.ok) {
            const { access } = await refreshResponse.json();
            await SecureStorage.setItem('access_token', access);
            options.headers['Authorization'] = `Bearer ${access}`;
            response = await fetch(url, options);
        } else {
            // Refresh token also expired - redirect to login
            navigateToLogin();
        }
    }

    return response;
}
```

### CORS Configuration

For mobile apps or SPAs hosted on a different domain, add the domain to `CORS_ALLOWED_ORIGINS` in `config/settings.py`:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:3000",      # React dev server
    "https://your-mobile-app.com",
]
```

---

## Error Codes

| HTTP Code | Meaning |
|-----------|---------|
| `200` | Success |
| `201` | Created successfully |
| `204` | Deleted successfully (no content) |
| `400` | Bad request (validation error or business rule violation) |
| `401` | Unauthorized (missing or expired token) |
| `403` | Forbidden (wrong role or segregation of duties violation) |
| `404` | Resource not found |
| `500` | Internal server error |

---

## Rate Limiting & Security

- All financial operations use **database-level atomic transactions** with `select_for_update()` locks
- Account balance updates use Django's **F() expressions** for atomic increments (no race conditions)
- Receipt numbers are generated atomically to prevent duplicates
- Passwords are hashed using Django's default PBKDF2 with SHA256
- All state-changing operations create **audit log entries** automatically
- Login/logout events are tracked in the audit log
- CSRF protection is active for session-based auth (web portal)
- JWT tokens are stateless and do not require CSRF

---

## Testing with cURL

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# List members
curl -s http://localhost:8000/api/v1/admin/members/ -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Get financial report
curl -s "http://localhost:8000/api/v1/admin/reports/summary/?period=year&year=2025" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Create a receipt
curl -s -X POST http://localhost:8000/api/v1/admin/receipts/create/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"member_account":1,"transaction_type":"credit","amount":5000,"payment_mode":"cash"}' | python3 -m json.tool

# Member login and dashboard
MEMBER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"sureshdesai1","password":"0210SURE"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

curl -s http://localhost:8000/api/v1/member/dashboard/ -H "Authorization: Bearer $MEMBER_TOKEN" | python3 -m json.tool
```

---

## Endpoint Count Summary

| Category | Endpoints |
|----------|-----------|
| Auth | 3 |
| Admin: Members | 5 |
| Admin: Accounts | 5 |
| Admin: Receipts | 3 |
| Admin: Loans | 5 |
| Admin: Funds | 6 |
| Admin: Allocation Rules | 4 |
| Admin: Reports | 2 |
| Admin: Audit Logs | 1 |
| Member | 6 |
| **Total** | **40** |
