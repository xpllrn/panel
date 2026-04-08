# CLAUDE.md - Project Guidelines for AI Agents

This is the single source of truth for AI coding agents working in this Django codebase. It consolidates all project conventions, architecture, tooling, and integration details.

---

## Project Overview

**Name:** Django Admin Panel (Cooperative Society Banking System)
**Framework:** Django 4.2+ / Django REST Framework 3.14.0
**Language:** Python 3.9+ (Python 3.11 in Docker)
**Database:** PostgreSQL 15
**Frontend:** Vanilla JavaScript, Bootstrap 5, custom CSS
**Containerization:** Docker & Docker Compose

This is an admin panel for managing members, accounts (FD, CD, RD, OD, Share, Sukanya, Suputra), loans, receipts, funds, and audit logs for a cooperative society/credit union.

---

## Build & Run Commands

```bash
# Docker (recommended)
docker-compose up --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py collectstatic --noinput

# Local development
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Database
python manage.py makemigrations
python manage.py migrate
```

## Linting & Formatting

Uses **ruff** (config in `pyproject.toml`). Always run before committing:

```bash
ruff check . --fix && ruff format .
```

- Target: Python 3.9+, line length 120
- Rules: E, W, F, I, B, UP, DJ (Django-specific)
- Ignored: E501 (line length), DJ001 (nullable CharField)
- Excludes: migrations, staticfiles, media, __pycache__

## Testing

```bash
python manage.py test                                    # All tests
python manage.py test accounts                           # Single app
python manage.py test accounts.tests.SplitFullNameTests  # Single class
python manage.py test -v 2 accounts.tests.PANValidatorTests  # Verbose
```

---

## Architecture

### Django Apps

| App | Purpose | Key Files |
|-----|---------|-----------|
| `accounts` | Auth, user management, all core models | models.py (9 models), forms.py, utils.py, api_views.py |
| `admin_portal` | Admin interface (60+ routes, 40+ views) | views.py (~2870 lines), urls.py |
| `member_portal` | Member self-service portal (read-only) | views.py, urls.py (15 routes) |
| `config` | Django project config | settings.py, urls.py |

### Core Models (accounts/models.py)

```
User (AbstractUser, 200+ fields - center hub)
  |-- MemberAccount (1:N) - 7 account types per member
  |     |-- Receipt (1:N) - transaction tracking
  |-- Loan (1:N) - loan management with EMI
  |     |-- LoanRepayment (1:N) - installments
  |-- AuditLog (1:N) - complete audit trail
  |-- FundAccount (1:N) - organizational funds
  |     |-- FundTransaction (1:N) - fund movements
  |     |-- FundAllocationRule (1:N) - auto-allocation rules
  |-- User (self-ref FK) - introducer_member
```

### Key Validators (Indian formats)

- PAN: `^[A-Z]{5}[0-9]{4}[A-Z]$`
- Aadhaar: `^[2-9][0-9]{11}$`
- Phone: `^[6-9][0-9]{9}$`
- IFSC: `^[A-Z]{4}0[A-Z0-9]{6}$`
- Pincode: `^[1-9][0-9]{5}$`

### URL Structure

- `/login/`, `/logout/` - Authentication
- `/home/` - Admin dashboard
- `/members/`, `/accounts/`, `/receipts/`, `/loans/` - Admin CRUD
- `/funds/`, `/allocation-rules/` - Fund management
- `/audit-logs/`, `/profile/`, `/calculator/` - Admin tools
- `/member/` - Member portal (dashboard, accounts, loans, transactions, profile)
- `/admin/` - Django admin

---

## Code Style Rules

### CRITICAL: No Type Hints

This codebase does NOT use type hints. Use docstrings instead:

```python
def split_full_name(full_name):
    """Split a full name into first_name and last_name."""
```

### CRITICAL: Function-Based Views Only

No class-based views. All views are function-based with `_view` suffix.

### Import Order

```python
# 1. Django imports (grouped by subpackage)
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q

# 2. Standard library imports
from datetime import date, timedelta

# 3. Third-party imports
from rest_framework.decorators import api_view

# 4. Local app imports
from accounts.models import User
from .utils import split_full_name
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | `snake_case.py` | `api_views.py` |
| Functions/Views | `snake_case` / `_view` suffix | `add_member_view` |
| Classes | `PascalCase` | `MemberAccount` |
| Model classes | Singular nouns | `User`, `Loan` |
| Form classes | `*Form` suffix | `SignUpForm` |
| Test classes | `*Tests` suffix | `SplitFullNameTests` |
| Constants | `UPPER_SNAKE_CASE` | `STATUS_CHOICES` |
| Validators | `snake_case_validator` | `pan_validator` |
| JavaScript | `camelCase` | `getCSRFToken` |

### View Naming Pattern

- `{action}_{entity}_view` - CRUD: `add_member_view`, `edit_member_view`, `delete_member_view`
- `{entity}_view` or `{entities}_view` - List/page: `members_view`, `home_view`
- `get_{entity}_view` - Single item retrieval: `get_member_view`
- `export_{entity}_view` - Exports: `export_members_view`
- `search_{entity}_view` - Search: `search_members_view`
- Member portal: `member_{entity}_view` prefix

### View Decorator Order

```python
# Admin views
@login_required
@admin_required
def my_view(request):
    """Single-line docstring."""
    ...

# Member views
@login_required
@member_required
def member_my_view(request):
    """Single-line docstring."""
    ...
```

### JSON Response Format

```python
# Success
return JsonResponse({"success": True})
return JsonResponse({"success": True, "user": {...}})

# Error
return JsonResponse({"success": False, "error": "Error message"})
```

### Error Handling

```python
try:
    user = User.objects.get(id=user_id)
except User.DoesNotExist:
    return JsonResponse({"success": False, "error": "User not found"})
except Exception as e:
    return JsonResponse({"success": False, "error": str(e)})
```

### Model Validators

Define at module level using `RegexValidator`:

```python
pan_validator = RegexValidator(
    regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    message="PAN must be in format: ABCDE1234F",
)
```

### Model Choices

```python
STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
]
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
```

### Financial Operations

- Always use `transaction.atomic()` for financial operations
- Use `F()` expressions for atomic balance updates
- Use `select_for_update()` for account number generation
- Always call `log_action()` for audit trail
- Soft-delete pattern: `is_deleted`, `deleted_at` fields

### Audit Logging

```python
from accounts.models import AuditLog
AuditLog.objects.create(
    user=request.user,
    action="create",  # create, update, delete, login, logout, approve, reject, reset_password, export
    entity_type="member",
    entity_id=str(user.id),
    description="Created member: John Doe",
    ip_address=request.META.get("REMOTE_ADDR"),
)
```

### Pagination Pattern

Views use manual pagination with `Paginator` from `django.core.paginator`.

---

## Security Guidelines

- Environment variables via `python-decouple` - never hardcode secrets
- CSRF protection enabled - include tokens in AJAX requests
- Password validators: min 8 chars, not common, not numeric-only
- Production security: HSTS (1 year), secure cookies, SSL redirect, XFrame protection
- Role-based access: `@admin_required` and `@member_required` decorators
- Always escape user content in JavaScript with `escapeHTML()`
- Rate limiting on member creation (10/minute per admin)
- Never commit `.env` files

---

## Do Not

- Do not add type hints (not used in this codebase)
- Do not use class-based views
- Do not commit `.env` files or secrets
- Do not use `DEBUG=True` in production
- Do not skip CSRF tokens in forms/AJAX
- Do not put imports inside functions (always at module top)

---

## Project Structure

```
.
├── config/              # Django settings, root URLs, WSGI/ASGI
├── accounts/            # Core app: models, auth, forms, utils, API
│   ├── models.py        # 9 models (User, MemberAccount, Receipt, Loan, etc.)
│   ├── views.py         # Auth views (login, logout)
│   ├── api_views.py     # REST API endpoints
│   ├── forms.py         # Django forms
│   ├── utils.py         # Utilities (split_full_name, apply_fund_allocations)
│   ├── admin.py         # Django admin registration
│   └── migrations/      # 23 migration files
├── admin_portal/        # Admin dashboard (views only, no models)
│   ├── views.py         # 40+ admin views (~2870 lines)
│   └── urls.py          # 60 URL patterns
├── member_portal/       # Member self-service (read-only views)
│   ├── views.py         # Member views
│   └── urls.py          # 15 URL patterns
├── templates/
│   ├── accounts/        # login.html, signup.html
│   ├── admin/           # 11 admin templates (base, home, members, accounts, etc.)
│   └── member/          # 8 member templates (base, dashboard, accounts, etc.)
├── static/
│   ├── css/             # base.css, layout.css, components.css, pages/
│   └── js/              # utils.js, members.js, accounts.js, loans.js, etc.
├── scripts/             # setup_code_review_graph.sh, example_code_review.sh
├── .kiro/               # Kiro steering and hooks
├── docker-compose.yml   # PostgreSQL + Django services
├── Dockerfile           # Python 3.11-slim, Gunicorn
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Ruff configuration
└── .code-review-graphignore  # Graph exclusion patterns
```

---

## Code Review Graph Integration

This project uses [code-review-graph](https://github.com/tirth8205/code-review-graph) for AI-powered code review optimization. It builds a structural knowledge graph using Tree-sitter AST parsing and reduces token usage by up to 8.2x.

### Setup

```bash
# Docker (recommended)
./scripts/setup_code_review_graph.sh

# Or manually
docker-compose exec web pip install code-review-graph
docker-compose exec web code-review-graph install
docker-compose exec web code-review-graph build
```

### CLI Commands

```bash
code-review-graph build              # Parse entire codebase (~10s)
code-review-graph update             # Incremental update (<2s)
code-review-graph status             # Graph statistics
code-review-graph watch              # Auto-update on file changes
code-review-graph detect-changes     # Risk-scored change impact
code-review-graph visualize          # Interactive HTML graph
code-review-graph wiki               # Generate markdown wiki
```

### AI Assistant Slash Commands

```
/code-review-graph:build-graph       # Build or rebuild the code graph
/code-review-graph:review-delta      # Review changes since last commit
/code-review-graph:review-pr         # Full PR review with blast-radius
```

### MCP Tools (22 available)

**Core:** `build_or_update_graph_tool`, `get_impact_radius_tool`, `get_review_context_tool`, `query_graph_tool`
**Search:** `semantic_search_nodes_tool`, `find_large_functions_tool`, `list_flows_tool`, `get_affected_flows_tool`
**Architecture:** `list_communities_tool`, `get_architecture_overview_tool`, `generate_wiki_tool`
**Refactoring:** `refactor_tool`, `apply_refactor_tool`
**Multi-repo:** `list_repos_tool`, `cross_repo_search_tool`

### Django-Specific Usage

```bash
# Find all views using a model
code-review-graph query accounts/models.py --type callers

# Find tests for a model
code-review-graph query accounts/models.py --type tests

# Blast radius of changes
code-review-graph detect-changes
```

### Configuration

- **Exclusions:** `.code-review-graphignore` (excludes cache, migrations, static, media, docs)
- **Database:** Stored in `.code-review-graph/` (gitignored)
- **Auto-update:** Hooks update graph on file save and git commit
- **Optional features:** `pip install code-review-graph[embeddings]`, `[communities]`, or `[all]`

### Workflow Templates

1. `review_changes` - Focused code review
2. `architecture_map` - Architecture overview
3. `debug_issue` - Debug with dependency context
4. `onboard_developer` - Onboarding docs
5. `pre_merge_check` - Pre-merge validation

### Performance

| Metric | Value |
|--------|-------|
| Initial build | ~10 seconds |
| Incremental update | <2 seconds |
| Query latency | <1ms |
| Token reduction | 6-9x |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (required) | - |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `adminpanel` |
| `DB_USER` | PostgreSQL username | `admin` |
| `DB_PASSWORD` | PostgreSQL password | - |
| `DB_HOST` | PostgreSQL host | `db` (Docker) / `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |

---

## Docker

```bash
docker-compose up --build          # Build and start
docker-compose logs -f             # View logs
docker-compose down                # Stop containers
docker-compose exec web python manage.py shell  # Django shell
docker-compose exec web python manage.py test   # Run tests
```

### Services

- `db`: PostgreSQL 15-alpine with persistent volume
- `web`: Django + Gunicorn (3 workers) on port 8000
