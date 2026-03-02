# AGENTS.md - Coding Agent Guidelines

This document provides instructions for AI coding agents working in this Django codebase.

## Project Overview

- **Framework**: Django 4.2 with Django REST Framework 3.14.0
- **Language**: Python 3.9+
- **Database**: PostgreSQL (Local via Docker for dev, Supabase for production)
- **Frontend**: Vanilla JavaScript with custom CSS
- **Backend-as-a-Service**: Supabase (production database, storage, auth APIs)

## Build & Run Commands

### Local Development Setup (First Time)

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL with Docker and run migrations
./dev-setup.sh

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Daily Development

```bash
# Start PostgreSQL (if not running)
docker-compose up -d

# Run development server
python manage.py runserver

# Stop PostgreSQL when done
docker-compose down
```

### Database Migrations

```bash
python manage.py makemigrations    # Create new migrations
python manage.py migrate           # Apply migrations to Supabase
```

### Supabase Configuration (Production Only)

For production deployment, configure Supabase:

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Copy database credentials from **Settings → Database**
3. Copy API keys from **Settings → API**
4. Update `.env.production` with all Supabase credentials

```bash
# Required .env variables for Supabase (production):
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-publishable-key
SUPABASE_SERVICE_KEY=your-secret-key
DB_NAME=postgres
DB_USER=postgres.[project-ref]
DB_PASSWORD=your-db-password
DB_HOST=aws-0-[region].pooler.supabase.com
DB_PORT=5432

# IMPORTANT:
# Use "Session Pooler" (port 5432) or "Transaction Pooler" (port 6543).
# Do NOT use direct connection (db.xxx.supabase.co) as it is IPv6-only.
```

### Local Development Configuration

For local development, use `.env.local` (already configured):

```bash
# Local PostgreSQL via Docker
DB_NAME=panel_dev
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

## Linting & Formatting

This project uses **ruff** for linting and formatting. Configuration is in `pyproject.toml`.

```bash
# Check for issues
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Format code
ruff format .

# Check formatting without changing files
ruff format . --check
```

Always run `ruff check . --fix && ruff format .` before committing.

## Testing Commands

### Run All Tests

```bash
python manage.py test
```

### Run Single Test (Important)

```bash
# Run tests for a specific app
python manage.py test accounts
python manage.py test admin_portal

# Run a specific test class
python manage.py test accounts.tests.SplitFullNameTests

# Run a specific test method
python manage.py test accounts.tests.SplitFullNameTests.test_splits_two_part_name

# With verbosity
python manage.py test -v 2 accounts.tests.PANValidatorTests
```

## Code Style Guidelines

### Import Order

Follow this order, with Django imports grouped by subpackage:

```python
# 1. Django imports (grouped by subpackage)
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Q

# 2. Standard library imports
from datetime import date, timedelta

# 3. Third-party imports
from rest_framework.decorators import api_view

# 4. Local app imports
from accounts.models import User
from accounts.forms import SignUpForm
from .utils import split_full_name
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | `snake_case.py` | `api_views.py`, `admin_portal` |
| Functions | `snake_case` | `split_full_name`, `validate_password_strength` |
| View functions | `snake_case_view` | `login_view`, `members_view` |
| Classes | `PascalCase` | `User`, `BankAccount` |
| Model classes | Singular nouns | `User`, `BankAccount` |
| Form classes | `*Form` suffix | `SignUpForm`, `LoginForm` |
| Test classes | `*Tests` suffix | `SplitFullNameTests` |
| Config classes | `*Config` suffix | `AccountsConfig` |
| Constants | `UPPER_SNAKE_CASE` | `MEMBER_TYPE_CHOICES`, `STATUS_CHOICES` |
| Validators | `snake_case_validator` | `pan_validator`, `phone_validator` |
| JavaScript | `camelCase` | `getCSRFToken`, `showMemberModal` |

### Type Annotations

This codebase does NOT use type hints. Use docstrings for documentation:

```python
def split_full_name(full_name):
    """
    Split a full name into first_name and last_name.
    
    Args:
        full_name: A string containing the full name
        
    Returns:
        tuple: (first_name, last_name)
    """
```

### Error Handling

#### Python/Django Pattern

```python
# Use specific exceptions first
try:
    user = User.objects.get(id=user_id)
except User.DoesNotExist:
    return JsonResponse({'success': False, 'error': 'User not found'})
except Exception as e:
    return JsonResponse({'success': False, 'error': str(e)})
```

#### JSON Response Format

```python
# Success
return JsonResponse({'success': True})
return JsonResponse({'success': True, 'user': {...}})

# Error
return JsonResponse({'success': False, 'error': 'Error message'})
```

### Model Validators

Define validators at module level using `RegexValidator`:

```python
pan_validator = RegexValidator(
    regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$',
    message='PAN must be in format: ABCDE1234F'
)
```

### View Decorators

Stack decorators with `@login_required` first:

```python
@login_required
@admin_required  # Custom decorator if needed
def view_function(request):
    ...
```

## Testing Patterns

### Test Structure

```python
class SplitFullNameTests(TestCase):
    """Tests for the split_full_name utility function."""
    
    def test_splits_two_part_name(self):
        """Should correctly split 'John Doe' into first and last name."""
        first, last = split_full_name("John Doe")
        self.assertEqual(first, "John")
        self.assertEqual(last, "Doe")
```

### Test Naming

- Test methods: `test_<behavior_being_tested>`
- Descriptive docstrings explaining expected behavior
- Use `setUp` for fixtures

## Project Structure

```
.
├── accounts/           # User authentication and profile app
│   ├── models.py       # User and BankAccount models
│   ├── views.py        # Auth views (login, signup, logout)
│   ├── api_views.py    # REST API endpoints
│   ├── forms.py        # Django forms
│   ├── utils.py        # Utility functions
│   └── tests.py        # Unit tests
├── admin_portal/       # Admin portal app
│   ├── views.py        # Admin views
│   └── tests.py        # Integration tests
├── member_portal/      # Member portal app
│   ├── views.py        # Member views
│   └── tests.py        # Member portal tests
├── config/             # Django settings
│   ├── settings.py     # Main settings (Supabase DB config)
│   ├── supabase_client.py  # Supabase client singleton
│   └── urls.py         # Root URL configuration
├── templates/          # HTML templates
├── static/             # Static files (CSS, JS)
└── media/              # User uploads
```

## Security Guidelines

- Environment variables via `python-decouple` - never hardcode secrets
- CSRF protection is enabled - include tokens in AJAX requests
- Use Django's password validators (min 8 chars, not common)
- Security headers are configured for production (HSTS, XSS filter, etc.)
- Supabase connection uses SSL (`sslmode=require`)

## Supabase Integration

### Database Access
All database access is through Django ORM → `psycopg2-binary` → Supabase PostgreSQL.
No direct Supabase client usage for database queries.

### Supabase Client
For Supabase-specific features (storage, auth, realtime), use:

```python
from config.supabase_client import get_supabase_client

client = get_supabase_client()
```

## Common Patterns

### Creating a New View

```python
@login_required
def my_view(request):
    if request.method == 'POST':
        # Handle form submission
        return JsonResponse({'success': True})
    
    context = {'data': some_data}
    return render(request, 'app/template.html', context)
```

### Model Choices

```python
STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]

status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
```

## Do Not

- Do not add type hints (not used in this codebase)
- Do not commit `.env` files or secrets
- Do not use `DEBUG=True` in production
- Do not skip CSRF tokens in forms/AJAX
