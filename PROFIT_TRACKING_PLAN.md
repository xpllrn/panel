# Profit Tracking, Financial Reporting & API Plan

## Current State

The system tracks individual transactions (deposits, withdrawals, loan EMIs, interest) but has **no aggregate financial reporting**. There is no way to see:
- How much interest income the society earned from loans
- How much interest the society owes to members on their deposits
- Net profit or loss for any period
- Fund allocation summaries
- Financial health dashboard

---

## How a Cooperative Society Makes Money

This is based on how real cooperative credit societies (like Saraswat, Cosmos, Janakalyan) operate in India.

### Revenue (Money IN)
| Source | How It Works | Currently Tracked? |
|--------|-------------|-------------------|
| **Loan Interest** | Members pay EMIs that include interest. The interest portion is the society's income. | Partially — EMIs recorded, interest/principal split exists in `LoanRepayment`, not aggregated. |
| **Loan Processing Fees** | 1-2% one-time fee when a loan is disbursed. | Not tracked. No field exists. |
| **Penalties/Late Fees** | Charged on overdue EMIs (typically 2% per month on overdue amount). | `overdue_amount` exists on Loan model but penalty income isn't tracked separately. |
| **Membership/Entry Fees** | One-time fee from new members (₹100-500). | Not tracked separately. Registration fund allocation exists but isn't flagged as revenue. |

### Expenses (Money OUT)
| Source | How It Works | Currently Tracked? |
|--------|-------------|-------------------|
| **Deposit Interest** | Society pays interest to members on FD/RD/CD accounts. This is the biggest expense. | `interest_rate` exists on `MemberAccount`. `accrued_interest` field exists but payouts aren't recorded. |
| **Operating Costs** | Staff salaries, rent, utilities. | Out of scope for this system. |
| **Dividend Payments** | Annual profit share distributed to members based on share capital. | Dividend Fund type exists but no distribution mechanism. |

### How Profit Flows Into Funds (Real Cooperative Model)

This is how it works at real cooperative societies regulated by RBI/RCS:

```
Annual Profit (calculated at year-end)
    │
    ├── 25% → Reserve Fund         (mandatory under RCS Act)
    ├── 10% → Statutory Fund       (mandatory)
    ├── 10% → Education Fund       (mandatory for some states)
    ├── Up to 15% → Dividend Fund  (distributed to members by share capital)
    └── Remaining → General Fund   (society's discretion: welfare, building, etc.)
```

**This is exactly what the Funds + Allocation Rules system is built for.**
The `FundAllocationRule` model supports an `annual_profit` trigger event — but the trigger has never been wired up because there's no profit calculation yet.

### Profit Formula
```
Gross Revenue  = Loan Interest Earned + Processing Fees + Penalty Income + Entry Fees
Total Expenses = Deposit Interest Paid + Operating Costs
Net Profit     = Gross Revenue - Total Expenses

Distributable Profit = Net Profit - Mandatory Fund Reserves (25% + 10% + 10%)
Dividend Per Share   = (Dividend Pool) / (Total Share Capital of All Members)
```

---

## Implementation Plan

### Phase 1: Financial Summary (No Migration Needed)

Everything for v1 can be computed from existing data in `LoanRepayment` and `MemberAccount`.

#### 1.1 — Profit Calculation Logic

New utility function in `accounts/utils.py`:

```python
def get_financial_summary(start_date, end_date):
    """Calculate revenue, expenses, and profit for a given period."""

    # REVENUE: Interest earned from loan repayments
    loan_interest = LoanRepayment.objects.filter(
        payment_status="paid",
        paid_date__range=(start_date, end_date),
    ).aggregate(total=Sum("interest_component"))["total"] or Decimal("0.00")

    # REVENUE: Principal collected (cash inflow, not profit)
    principal_collected = LoanRepayment.objects.filter(
        payment_status="paid",
        paid_date__range=(start_date, end_date),
    ).aggregate(total=Sum("principal_component"))["total"] or Decimal("0.00")

    # EXPENSE: Monthly interest liability on member deposits
    # sum(account.balance * rate / 100 / 12) for each deposit account
    deposit_accounts = MemberAccount.objects.filter(
        is_deleted=False, status="active"
    ).exclude(account_type__in=["share", "od"])
    monthly_interest_liability = sum(
        (acc.balance * acc.interest_rate / 100 / 12)
        for acc in deposit_accounts
    )
    # Scale to the period
    months_in_period = max(1, (end_date - start_date).days / 30)
    deposit_interest_expense = monthly_interest_liability * Decimal(str(months_in_period))

    # Fund allocations in period
    fund_credits = FundTransaction.objects.filter(
        transaction_type="credit",
        created_at__date__range=(start_date, end_date),
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    net_profit = loan_interest - deposit_interest_expense

    return {
        "loan_interest_income": loan_interest,
        "principal_collected": principal_collected,
        "deposit_interest_expense": deposit_interest_expense,
        "fund_allocations": fund_credits,
        "gross_revenue": loan_interest,
        "total_expenses": deposit_interest_expense,
        "net_profit": net_profit,
    }
```

#### 1.2 — New Admin View: `reports_view`

New "Reports" page accessible from the sidebar. Shows:
- **Period selector** (This Month / This Quarter / This Year / Custom)
- **4 stat cards**: Loan Interest Income, Deposit Interest Expense, Net Profit, Total Loans Outstanding
- **Revenue vs Expense bar chart** (month-by-month for the selected year)
- **Loan Portfolio**: active loans, disbursed amount, outstanding, overdue, recovery rate
- **Deposit Portfolio**: by account type (FD/RD/CD/Share), total deposits, interest liability
- **Fund Balances**: all funds with current balance, total allocated this period

#### 1.3 — Profit Distribution to Funds (Annual)

Wire up the existing `annual_profit` trigger event:
- Admin clicks "Distribute Annual Profit" on the Reports page
- System calculates net profit for the fiscal year
- Applies all `FundAllocationRule` entries with `trigger_event="annual_profit"`
- Creates `FundTransaction` records for each allocation
- Creates audit log entries

This connects the Reports page to the Funds page — profit is calculated in Reports, distributed in Funds.

### Phase 2: Reports Page UI

#### 2.1 — Files to Create/Modify
- `templates/admin/reports.html` — new template
- `admin_portal/views.py` — add `reports_view` and `distribute_profit_view`
- `admin_portal/urls.py` — add routes
- `config/urls.py` — register routes
- `templates/admin/base.html` — add "Reports" to sidebar
- `static/css/pages/reports.css` — report-specific styles
- `static/js/reports.js` — chart rendering (using Chart.js via CDN)

#### 2.2 — Page Layout

```
┌──────────────────────────────────────────────────────┐
│  Financial Reports              [This Year ▼] [2026] │
├────────────┬────────────┬────────────┬───────────────┤
│ Loan       │ Deposit    │ Net        │ Loans         │
│ Interest   │ Interest   │ Profit     │ Outstanding   │
│ ₹1,24,500  │ ₹45,200   │ ₹79,300   │ ₹15,00,000    │
├────────────┴────────────┴────────────┴───────────────┤
│                                                       │
│  Revenue vs Expense (bar chart, month-by-month)       │
│                                                       │
├───────────────────────┬───────────────────────────────┤
│ Loan Portfolio        │ Deposit Portfolio              │
│                       │                               │
│ Active: 15            │ FD: ₹X (7.5% avg)            │
│ Disbursed: ₹X         │ RD: ₹X (7.0%)                │
│ Outstanding: ₹X       │ CD: ₹X (7.0%)                │
│ Overdue: ₹X (3)       │ Share: ₹X                     │
│ Recovery: 94%         │ Monthly liability: ₹X         │
│ Interest Earned: ₹X   │ Maturing soon: 3 (₹X)        │
├───────────────────────┴───────────────────────────────┤
│ Fund Balances                                         │
│ Welfare: ₹X  Reserve: ₹X  Education: ₹X  Other: ₹X │
│ Total allocated this period: ₹X                       │
│                                                       │
│ [Distribute Annual Profit]  (visible only for yearly) │
└───────────────────────────────────────────────────────┘
```

#### 2.3 — Dashboard Integration
Add a "Net Profit" stat card to the admin home page, replacing the "Today's Transactions" card or adding a 5th card row.

### Phase 3: Enhanced Tracking (Requires Migration)

Add these fields for more accurate tracking:

```python
# On Loan model — processing fee
processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

# On LoanRepayment model — penalty tracking
penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
```

Create a new model for deposit interest payouts:

```python
class InterestPayout(models.Model):
    """Records interest paid to members on their deposit accounts."""
    account = models.ForeignKey(MemberAccount, on_delete=models.CASCADE, related_name="interest_payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## Phase 4: API Layer & Mobile Access

### Recommended Approach: API + PWA

**Why PWA over a native Android app:**
| Factor | Native App | PWA |
|--------|-----------|-----|
| Development time | 2-3 months | 1-2 weeks (just add manifest + service worker) |
| Works on iOS + Android | Need 2 apps or React Native | Yes, one codebase |
| Play Store approval | Required (takes time) | Not needed |
| Updates | Users must update | Auto-updates |
| Offline support | Yes | Yes (service worker) |
| Push notifications | Yes | Yes (Web Push API) |
| Install on home screen | Yes | Yes |
| Cost | High | Low |

Real examples: Starbucks, Twitter Lite, Pinterest all use PWAs. For a cooperative society with 25-500 members, a PWA is the pragmatic choice.

### 4.1 — PWA Setup (Quick Win)

Add to the existing Django project:
- `static/manifest.json` — app name, icons, theme color
- `static/service-worker.js` — caching strategy for offline access
- Update `templates/member/base.html` to include manifest link
- Member portal becomes "installable" on any phone

### 4.2 — REST API (For Future Native App or Third-Party Integration)

Build alongside the existing views — same models, new interface.

**New packages:**
```
djangorestframework-simplejwt   (JWT authentication)
drf-spectacular                 (Swagger/OpenAPI documentation)
django-filter                   (query parameter filtering)
```

**Authentication:**
```
POST /api/v1/auth/login/         → { "access": "jwt-token", "refresh": "..." }
POST /api/v1/auth/refresh/       → refresh access token
GET  /api/v1/auth/profile/       → current user info
```

**Member API (read-only):**
```
GET /api/v1/member/dashboard/          → account summary + stats
GET /api/v1/member/accounts/           → list member's accounts
GET /api/v1/member/accounts/:id/       → account detail + recent transactions
GET /api/v1/member/loans/              → list member's loans
GET /api/v1/member/loans/:id/          → loan detail + repayment schedule
GET /api/v1/member/transactions/       → paginated transaction history
```

**Admin API (full CRUD):**
```
/api/v1/admin/members/          → list, create, update, delete
/api/v1/admin/accounts/         → list, create, update, delete
/api/v1/admin/loans/            → list, create, approve, record EMI
/api/v1/admin/receipts/         → list, create
/api/v1/admin/reports/summary/  → financial summary (same as reports page)
/api/v1/admin/reports/export/   → CSV/PDF export
```

**New files:**
```
accounts/serializers.py         — DRF serializers for all 9 models
accounts/api_urls.py            — /api/v1/ URL routing
accounts/api_permissions.py     — IsAdmin, IsMember permission classes
accounts/api_views.py           — update existing stub with real ViewSets
```

---

## Implementation Order

| # | Task | Effort | Needs Migration? | Priority |
|---|------|--------|-----------------|----------|
| 1 | Financial summary function (Python logic) | 3 hours | No | HIGH |
| 2 | Reports page view + template + chart | 1 day | No | HIGH |
| 3 | Add "Reports" to sidebar + URL routes | 30 min | No | HIGH |
| 4 | Dashboard net profit stat card | 1 hour | No | HIGH |
| 5 | Annual profit distribution to funds | 3 hours | No | HIGH |
| 6 | PWA manifest + service worker | 2 hours | No | MEDIUM |
| 7 | Loan processing fee field | 1 hour | Yes | MEDIUM |
| 8 | Penalty tracking on LoanRepayment | 1 hour | Yes | MEDIUM |
| 9 | Deposit interest payout model + view | 3 hours | Yes | MEDIUM |
| 10 | Export report to CSV | 2 hours | No | LOW |
| 11 | JWT auth setup | 2 hours | Yes | LOW |
| 12 | API serializers + ViewSets | 1-2 days | No | LOW |
| 13 | Swagger API docs | 1 hour | No | LOW |

---

## Cleanup: Remove code-review-graph

The `code-review-graph` package is installed but never used (no graph DB built). For a project of this size (~100 files), it's unnecessary overhead.

**Remove:**
- Delete `code-review-graph>=0.1.0` from `requirements.txt`
- Delete `.code-review-graphignore`
- Delete `scripts/setup_code_review_graph.sh` and `scripts/example_code_review.sh`
- Delete `.kiro/steering/code-review-graph-guide.md`
- Remove code-review-graph references from `CLAUDE.md`
- Remove code-review-graph section from `README.md`

---

## Summary

1. **Phase 1 (Reports)**: Can be built NOW with zero migrations. Computes profit from existing `LoanRepayment` data. Wires up the `annual_profit` fund allocation trigger.
2. **Phase 2 (PWA)**: Quick win — makes the member portal installable on phones without building a separate app.
3. **Phase 3 (Enhanced tracking)**: Adds processing fees, penalties, and interest payouts for more accurate reporting.
4. **Phase 4 (REST API)**: Only needed if/when a native mobile app is confirmed. The PWA approach covers 90% of use cases.
