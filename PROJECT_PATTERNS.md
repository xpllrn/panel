# Django Banking System - Project Patterns & Conventions

**Generated:** March 22, 2026  
**Purpose:** Consistency hook configuration for Kiro AI

This document defines ALL patterns, conventions, and standards used in this Django project. Any code generated must strictly follow these patterns.

---

## 1. DJANGO APPS OVERVIEW

### accounts
- **Purpose:** Core authentication, user management, and all banking models
- **Contains:** User model, MemberAccount, Receipt, Loan, LoanRepayment, BankAccount, AuditLog
- **Views:** Authentication views (login, logout, signup-disabled), API info endpoint
- **Key Files:** models.py (all models), forms.py, utils.py, validators

### admin_portal
- **Purpose:** Administrative interface for staff to manage members, accounts, loans, receipts
- **Contains:** 40+ admin views, no models (uses accounts models)
- **Views:** All CRUD operations for members, accounts, loans, receipts, audit logs, exports
- **Key Files:** views.py (2214 lines), urls.py, tests.py

### member_portal
- **Purpose:** Member-facing portal for viewing own data
- **Contains:** Read-only views for members, no models (uses accounts models)
- **Views:** Dashboard, accounts, loans, transactions, profile, password change
- **Key Files:** views.py, urls.py, tests.py

### config
- **Purpose:** Django project configuration
- **Contains:** settings.py, urls.py, wsgi.py, asgi.py
- **Key Files:** Root URL configuration, settings with security headers

---

## 2. VIEW PATTERNS

### STRICT RULE: 100% Function-Based Views

**NO CLASS-BASED VIEWS ARE USED IN THIS PROJECT**


All views are function-based views with the `_view` suffix.

### View Naming Convention

**Pattern:** `{action}_{entity}_view` or `{entity}_view`

**Examples:**
- `login_view` - Authentication
- `members_view` - List view
- `add_member_view` - Create action
- `edit_member_view` - Update action
- `delete_member_view` - Delete action
- `get_member_view` - Retrieve single item (API-style)
- `member_dashboard_view` - Member portal views use `member_` prefix
- `export_members_view` - Export action

**API-Style Views (return JSON):**
- `get_member_view(request, user_id)` - GET single item
- `add_member_view(request)` - POST create
- `edit_member_view(request, user_id)` - POST update
- `delete_member_view(request, user_id)` - POST delete
- `search_members_view(request)` - GET search/filter

**Template-Rendering Views:**
- `members_view(request)` - List page
- `home_view(request)` - Dashboard page
- `profile_view(request)` - Profile page

### View Decorator Patterns

**Admin Portal Views:**
```python
@login_required
@admin_required
def view_name(request):
    """Docstring describing the view."""
    ...
```

**Member Portal Views:**
```python
@member_required  # This includes @login_required internally
def member_view_name(request):
    """Docstring describing the view."""
    ...
```

**Authentication Views:**
```python
def login_view(request):  # No decorator - public
    ...

@login_required
def logout_view(request):  # Only login required
    ...
```

**Decorator Stacking Order (when multiple):**
1. `@login_required` (outermost)
2. `@admin_required` or `@member_required`
3. Custom decorators (if any)

### View Docstring Pattern

**Every view must have a docstring:**
```python
def members_view(request):
    """Members management view with pagination and search"""
    ...
```

**Format:** Single-line description of what the view does


### View Response Patterns

**JSON Responses (API-style views):**
```python
# Success
return JsonResponse({'success': True})
return JsonResponse({'success': True, 'user_id': user.id})
return JsonResponse({'success': True, 'data': {...}})

# Error
return JsonResponse({'success': False, 'error': 'Error message'})
```

**Template Responses:**
```python
return render(request, 'app/template.html', context)
```

**Redirects:**
```python
return redirect('/url/')
return redirect('url_name')
```

**HTTP Errors:**
```python
return HttpResponseForbidden("Access denied. Administrators only.")
return HttpResponseNotAllowed(["POST"])
```

### View Method Handling Pattern

**POST-only views:**
```python
def add_member_view(request):
    """Create a new member with auto-generated password from DOB"""
    if request.method == "POST":
        try:
            # Process POST data
            ...
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})
```

**GET/POST views:**
```python
def profile_view(request):
    """Admin profile view"""
    if request.method == "POST":
        # Handle form submission
        ...
        messages.success(request, "Profile updated successfully!")
        return redirect("/profile/")
    
    return render(request, "admin/profile.html")
```

---

## 3. URL PATTERNS

### URL Naming Convention

**Pattern:** `{entity}` or `{action}_{entity}`

**Root URLs (config/urls.py):**
- No app_name namespace
- Direct URL patterns for admin portal
- Includes for member_portal and accounts

**App URLs with Namespace:**
```python
# member_portal/urls.py
app_name = "member_portal"

# admin_portal/urls.py  
app_name = "admin_portal"

# accounts/urls.py
# No app_name (root level)
```

### URL Structure Examples

**Admin Portal (no namespace):**
```python
path("home/", views.home_view, name="home")
path("members/", views.members_view, name="members")
path("members/add/", views.add_member_view, name="add_member")
path("members/<int:user_id>/edit/", views.edit_member_view, name="edit_member")
path("members/<int:user_id>/delete/", views.delete_member_view, name="delete_member")
path("api/members/search/", views.search_members_view, name="search_members")
```

**Member Portal (with namespace):**
```python
app_name = "member_portal"

path("", views.member_dashboard_view, name="dashboard")
path("accounts/", views.member_accounts_view, name="accounts")
path("accounts/<int:account_id>/", views.member_account_detail_view, name="account_detail")
path("loans/<int:loan_id>/", views.member_loan_detail_view, name="loan_detail")
```

**URL Parameter Naming:**
- `user_id` - for User model
- `account_id` - for MemberAccount model
- `loan_id` - for Loan model
- `receipt_id` - for Receipt model
- `log_id` - for AuditLog model

### URL Template Usage

**Admin portal (no namespace):**
```html
{% url 'home' %}
{% url 'members' %}
{% url 'edit_member' user.id %}
```

**Member portal (with namespace):**
```html
{% url 'member_portal:dashboard' %}
{% url 'member_portal:accounts' %}
{% url 'member_portal:account_detail' account.id %}
```

**Shared URLs (accounts app):**
```html
{% url 'login' %}
{% url 'logout' %}
```


---

## 4. TEMPLATE ORGANIZATION

### Template Directory Structure

```
templates/
├── accounts/          # Authentication templates
│   ├── login.html
│   └── signup.html
├── admin/             # Admin portal templates
│   ├── base.html      # Admin base template
│   ├── home.html
│   ├── members.html
│   ├── accounts.html
│   ├── loans.html
│   ├── receipts.html
│   ├── audit_logs.html
│   ├── calculator.html
│   └── profile.html
└── member/            # Member portal templates
    ├── base.html      # Member base template
    ├── dashboard.html
    ├── accounts.html
    ├── account_detail.html
    ├── loans.html
    ├── loan_detail.html
    ├── transactions.html
    └── profile.html
```

### Template Inheritance Pattern

**Two Base Templates:**

1. **templates/admin/base.html** - Admin portal base
2. **templates/member/base.html** - Member portal base

**All page templates extend their respective base:**

```html
<!-- Admin portal pages -->
{% extends "admin/base.html" %}

<!-- Member portal pages -->
{% extends "member/base.html" %}
```

### Base Template Structure

**Both base templates follow this structure:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Default Title{% endblock %}</title>
    {% load static %}
    
    <!-- Core CSS (shared) -->
    <link rel="stylesheet" href="{% static 'css/base.css' %}">
    <link rel="stylesheet" href="{% static 'css/layout.css' %}">
    <link rel="stylesheet" href="{% static 'css/components.css' %}">
    <link rel="stylesheet" href="{% static 'css/page-layout.css' %}">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <div class="app-layout">
        <!-- Sidebar Navigation -->
        <nav class="sidebar">
            <!-- Navigation links -->
        </nav>
        
        <!-- Main Content -->
        <main class="main-content">
            {% if messages %}
            <div class="messages">
                {% for message in messages %}
                <div class="message message-{{ message.tags }}">
                    {{ message }}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            {% block content %}{% endblock %}
        </main>
    </div>
    
    <script src="{% static 'js/utils.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Template Block Pattern

**Standard blocks in base templates:**
- `{% block title %}` - Page title
- `{% block extra_css %}` - Page-specific CSS
- `{% block content %}` - Main content area
- `{% block extra_js %}` - Page-specific JavaScript

**Child template pattern:**
```html
{% extends "admin/base.html" %}
{% load static %}

{% block title %}Members - Admin Portal{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/pages/members.css' %}">
{% endblock %}

{% block content %}
<!-- Page content here -->
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/members.js' %}"></script>
{% endblock %}
```

### Template Naming Convention

**Pattern:** `{entity}.html` or `{entity}_{detail}.html`

**Examples:**
- `members.html` - List view
- `accounts.html` - List view
- `account_detail.html` - Detail view
- `loan_detail.html` - Detail view
- `home.html` - Dashboard
- `profile.html` - Profile page

### Active Navigation Link Pattern

**Using request.resolver_match.url_name:**

```html
<a href="{% url 'members' %}" 
   class="sidebar-link {% if request.resolver_match.url_name == 'members' %}active{% endif %}"
   {% if request.resolver_match.url_name == 'members' %}aria-current="page"{% endif %}>
    Members
</a>
```

**For multiple related pages:**
```html
<a href="{% url 'member_portal:accounts' %}"
    class="sidebar-link {% if request.resolver_match.url_name == 'accounts' or request.resolver_match.url_name == 'account_detail' %}active{% endif %}">
    My Accounts
</a>
```

---

## 5. IMPORT CONVENTIONS

### Import Order (STRICT)

**1. Django imports (grouped by subpackage)**
```python
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
```

**2. Standard library imports**
```python
import functools
import json
from datetime import date, timedelta
from decimal import Decimal
```

**3. Third-party imports**
```python
from rest_framework.decorators import api_view
from rest_framework.response import Response
```

**4. Local app imports**
```python
from accounts.models import AuditLog, Loan, LoanRepayment, MemberAccount, Receipt, User
from accounts.utils import log_action, split_full_name, validate_password_strength
```

### Local App Import Patterns

**Absolute imports for cross-app:**
```python
# In admin_portal/views.py
from accounts.models import User, MemberAccount, Receipt, Loan
from accounts.utils import log_action, split_full_name

# In member_portal/views.py
from accounts.models import Loan, LoanRepayment, MemberAccount, Receipt
```

**Relative imports within same app:**
```python
# In accounts/views.py
from .forms import LoginForm

# In accounts/urls.py
from . import api_views, views

# In accounts/forms.py
from .models import User
```

**NEVER use relative imports across apps** - always use absolute:
```python
# CORRECT
from accounts.models import User

# WRONG
from ..accounts.models import User
```

### Lazy Imports Pattern

**For avoiding circular imports or heavy modules:**
```python
def add_member_view(request):
    if request.method == "POST":
        # Import inside function
        from accounts.models import MemberAccount
        from datetime import date
        ...
```

**Used for:**
- Avoiding circular dependencies
- Heavy imports only needed in specific code paths
- Optional dependencies

---

## 6. MODEL CONVENTIONS

### Model Naming

**Pattern:** Singular noun, PascalCase

**Examples:**
- `User` (not Users)
- `MemberAccount` (not MemberAccounts)
- `Receipt` (not Receipts)
- `Loan` (not Loans)
- `LoanRepayment` (not LoanRepayments)
- `BankAccount` (not BankAccounts)
- `AuditLog` (not AuditLogs)

### Model Location

**ALL models are in accounts/models.py**

No models in admin_portal or member_portal apps.

### Field Naming Conventions

**Pattern:** `snake_case`

**Common patterns:**
- `created_at` - DateTimeField(auto_now_add=True)
- `updated_at` - DateTimeField(auto_now=True)
- `is_deleted` - BooleanField(default=False) for soft delete
- `deleted_at` - DateTimeField(nullable) for soft delete timestamp
- `{entity}_id` - ForeignKey field name (e.g., user_id, account_id)

**Choice fields:**
```python
STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]

status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
```

### Validator Naming

**Pattern:** `{field}_validator`

**Defined at module level:**
```python
pan_validator = RegexValidator(
    regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$',
    message='PAN must be in format: ABCDE1234F'
)

aadhar_validator = RegexValidator(
    regex=r'^[2-9][0-9]{11}$',
    message='Aadhaar must be 12 digits and cannot start with 0 or 1'
)

phone_validator = RegexValidator(
    regex=r'^[6-9][0-9]{9}$',
    message='Phone must be 10 digits starting with 6, 7, 8, or 9'
)
```

**Usage in model:**
```python
pan_number = models.CharField(
    max_length=10,
    blank=True,
    null=True,
    verbose_name="PAN Number",
    validators=[pan_validator]
)
```

### Model Meta Class Pattern

```python
class Meta:
    ordering = ["-created_at"]
    verbose_name = "Member Account"
    verbose_name_plural = "Member Accounts"
```

### Model __str__ Method Pattern

**Return human-readable string:**
```python
def __str__(self):
    return f"{self.account_number} - {self.get_account_type_display()} ({self.user.display_name})"
```

### Model Property Pattern

**Use @property for computed fields:**
```python
@property
def display_name(self):
    """Return full display name from first_name + last_name, falling back to username."""
    name = f"{self.first_name} {self.last_name}".strip()
    return name or self.username

@property
def age(self):
    """Calculate age from date of birth"""
    if self.date_of_birth:
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    return None
```

### ForeignKey Pattern

```python
user = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name="member_accounts"
)

created_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    related_name="receipts_created",
    verbose_name="Created By (Admin)"
)
```

**related_name pattern:** `{model_name}s` or `{model_name}s_{descriptor}`

### Soft Delete Pattern

**Every user-facing model has:**
```python
is_deleted = models.BooleanField(default=False, db_index=True)
deleted_at = models.DateTimeField(blank=True, null=True)
```

**Soft delete in views:**
```python
user.is_deleted = True
user.deleted_at = timezone.now()
user.status = 'closed'
user.save()
```

**Query pattern:**
```python
User.objects.filter(is_deleted=False)
MemberAccount.objects.filter(is_deleted=False)
```

---

## 7. UTILITY & HELPER PATTERNS

### Utility File Location

**accounts/utils.py** - All shared utility functions

### Utility Function Naming

**Pattern:** `{verb}_{noun}` or `{action}_description`

**Examples:**
- `split_full_name(full_name)` - String manipulation
- `combine_name(first_name, last_name)` - String manipulation
- `validate_password_strength(password, user=None)` - Validation
- `log_action(request, action, entity_type, entity_id, description)` - Logging
- `_get_client_ip(request)` - Private helper (underscore prefix)

### Utility Function Pattern

```python
def split_full_name(full_name):
    """
    Split a full name into first_name and last_name.
    
    Args:
        full_name: A string containing the full name
        
    Returns:
        tuple: (first_name, last_name)
    
    Examples:
        >>> split_full_name("John Doe")
        ('John', 'Doe')
        >>> split_full_name("John")
        ('John', '')
    """
    if not full_name:
        return ("", "")
    
    full_name = full_name.strip()
    if not full_name:
        return ("", "")
    
    parts = full_name.split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    
    return (first_name, last_name)
```

### Common Utilities Used Across Apps

**From accounts.utils:**
- `split_full_name()` - Used in admin_portal, accounts
- `validate_password_strength()` - Used in admin_portal
- `log_action()` - Used extensively in admin_portal for audit logging

**Usage pattern:**
```python
from accounts.utils import log_action, split_full_name

# In view
first_name, last_name = split_full_name(full_name)
user.first_name = first_name
user.last_name = last_name

log_action(
    request,
    "create",
    "member",
    user.id,
    f"Created member {username} ({user.display_name})"
)
```

---

## 8. FORM PATTERNS

### Form Naming Convention

**Pattern:** `{Entity}Form`

**Examples:**
- `SignUpForm` - extends UserCreationForm
- `LoginForm` - extends AuthenticationForm
- `UserProfileForm` - extends ModelForm
- `NotificationSettingsForm` - extends ModelForm

### Form Location

**accounts/forms.py** - All forms

### Form Class Pattern

```python
class UserProfileForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}),
    )

    class Meta:
        model = User
        fields = ["email", "mobile_primary"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "mobile_primary": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["name"].initial = self.instance.display_name

    def save(self, commit=True):
        user = super().save(commit=False)
        name = self.cleaned_data.get("name", "").strip()
        if name:
            from accounts.utils import split_full_name
            user.first_name, user.last_name = split_full_name(name)
        if commit:
            user.save()
        return user
```

---

## 9. DECORATOR PATTERNS

### Custom Decorator Location

**admin_portal/views.py:**
```python
def admin_required(view_func):
    """Decorator to check if user is staff"""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Access denied. Administrators only.")
        return view_func(request, *args, **kwargs)
    return wrapper
```

**member_portal/views.py:**
```python
def member_required(view_func):
    """Decorator to ensure user is a logged-in member (not admin/staff)."""
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

### Decorator Usage Pattern

**Always use functools.wraps:**
```python
import functools

def my_decorator(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Decorator logic
        return view_func(request, *args, **kwargs)
    return wrapper
```

---

## 10. STATIC FILES ORGANIZATION

### Static Directory Structure

```
static/
├── css/
│   ├── base.css           # Base styles
│   ├── layout.css         # Layout styles
│   ├── components.css     # Reusable components
│   ├── page-layout.css    # Page-specific layouts
│   ├── auth.css           # Authentication pages
│   └── pages/             # Page-specific styles
│       ├── accounts.css
│       ├── audit_logs.css
│       ├── calculator.css
│       ├── dashboard.css
│       ├── loans.css
│       ├── member.css
│       ├── members.css
│       ├── modals.css
│       ├── profile.css
│       └── receipts.css
└── js/
    ├── utils.js           # Shared utilities
    ├── accounts.js        # Account management
    ├── audit_logs.js      # Audit logs
    ├── calculator.js      # Banking calculator
    ├── loans.js           # Loan management
    ├── member.js          # Member portal
    ├── members.js         # Member management
    ├── profile.js         # Profile page
    └── receipts.js        # Receipt management
```

### CSS Loading Pattern

**Base template loads core CSS:**
```html
<link rel="stylesheet" href="{% static 'css/base.css' %}">
<link rel="stylesheet" href="{% static 'css/layout.css' %}">
<link rel="stylesheet" href="{% static 'css/components.css' %}">
<link rel="stylesheet" href="{% static 'css/page-layout.css' %}">
```

**Page-specific CSS in extra_css block:**
```html
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/pages/members.css' %}">
{% endblock %}
```

### JavaScript Loading Pattern

**Base template loads utils:**
```html
<script src="{% static 'js/utils.js' %}"></script>
```

**Page-specific JS in extra_js block:**
```html
{% block extra_js %}
<script src="{% static 'js/members.js' %}"></script>
{% endblock %}
```

---

## 11. JAVASCRIPT CONVENTIONS

### Naming Convention

**Pattern:** camelCase

**Examples:**
- `getCSRFToken()` - Function
- `showMemberModal()` - Function
- `closeMemberModal()` - Function
- `memberModal` - Variable
- `currentPage` - Variable

### CSRF Token Pattern

**Every AJAX POST request includes CSRF token:**
```javascript
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

fetch(url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify(data)
})
```

---

## 12. ERROR HANDLING PATTERNS

### View Error Handling

**Try-except with specific exceptions first:**
```python
try:
    user = User.objects.get(id=user_id)
    # Process user
    return JsonResponse({"success": True})
except User.DoesNotExist:
    return JsonResponse({"success": False, "error": "User not found"})
except Exception as e:
    return JsonResponse({"success": False, "error": str(e)})
```

### Validation Pattern

**Check required fields:**
```python
if not username:
    return JsonResponse({"success": False, "error": "Username is required"})
if not email:
    return JsonResponse({"success": False, "error": "Email is required"})
```

**Check duplicates:**
```python
if User.objects.filter(username=username).exists():
    return JsonResponse({"success": False, "error": "Username already exists"})
```

**Check permissions:**
```python
if user.id == request.user.id:
    return JsonResponse({"success": False, "error": "You cannot delete yourself"})
```

---

## 13. DATABASE TRANSACTION PATTERNS

### Atomic Transactions with Retry

**For operations with auto-generated numbers:**
```python
max_retries = 5
for attempt in range(max_retries):
    try:
        with transaction.atomic():
            # Lock row with select_for_update()
            last_record = Model.objects.select_for_update().filter(...).first()
            
            # Generate next number
            next_seq = calculate_next_sequence(last_record)
            
            # Create record
            obj = Model.objects.create(...)
            
        # Success - break out of retry loop
        return JsonResponse({"success": True})
    except IntegrityError:
        if attempt == max_retries - 1:
            raise
        continue
```

### Atomic Balance Updates

**Use F() expressions to avoid race conditions:**
```python
with transaction.atomic():
    account = MemberAccount.objects.select_for_update().get(id=account_id)
    
    # Update using F() expression
    MemberAccount.objects.filter(id=account.id).update(
        balance=F("balance") + amount,
        last_transaction_date=date.today()
    )
```

---

## 14. AUDIT LOGGING PATTERN

### Every Sensitive Action Must Be Logged

**Pattern:**
```python
from accounts.utils import log_action

log_action(
    request,
    "create",  # Action: create/update/delete/login/logout/approve/reject/reset_password/export
    "member",  # Entity: member/account/receipt/loan/system
    user.id,   # Entity ID (can be None)
    f"Created member {username} ({user.display_name})"  # Description
)
```

**Actions that MUST be logged:**
- Create member
- Edit member
- Delete member
- Reset password
- Create account
- Edit account
- Delete account
- Create receipt
- Create loan
- Approve loan
- Record EMI payment
- Export data

---

## 15. PAGINATION PATTERN

**Standard pagination:**
```python
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

page = request.GET.get("page", 1)
per_page = 25

queryset = Model.objects.filter(...).order_by("-created_at")

paginator = Paginator(queryset, per_page)
try:
    page_obj = paginator.page(page)
except PageNotAnInteger:
    page_obj = paginator.page(1)
except EmptyPage:
    page_obj = paginator.page(paginator.num_pages)

return render(request, "template.html", {"items": page_obj, "page_obj": page_obj})
```

---

## 16. TESTING PATTERNS

### Test Class Naming

**Pattern:** `{FunctionName}Tests` or `{Feature}Tests`

**Examples:**
- `SplitFullNameTests`
- `PANValidatorTests`
- `MembersViewTests`
- `AddMemberViewTests`

### Test Method Naming

**Pattern:** `test_{behavior_being_tested}`

**Examples:**
- `test_splits_two_part_name`
- `test_validates_correct_pan`
- `test_requires_authentication`
- `test_creates_member_successfully`

### Test Docstring Pattern

```python
def test_splits_two_part_name(self):
    """Should correctly split 'John Doe' into first and last name."""
    first, last = split_full_name("John Doe")
    self.assertEqual(first, "John")
    self.assertEqual(last, "Doe")
```

---

## 17. NO TYPE HINTS RULE

**CRITICAL: This project does NOT use type hints**

```python
# CORRECT - No type hints
def split_full_name(full_name):
    """Split a full name into first_name and last_name."""
    ...

# WRONG - Do not add type hints
def split_full_name(full_name: str) -> tuple[str, str]:
    ...
```

**Use docstrings for documentation instead**

---

## 18. CRITICAL PATTERNS SUMMARY

### MUST FOLLOW:

1. **100% Function-Based Views** - No class-based views
2. **View names end with `_view`** - e.g., `members_view`, `add_member_view`
3. **All models in accounts/models.py** - No models in other apps
4. **Singular model names** - `User`, not `Users`
5. **No type hints** - Use docstrings
6. **Import order** - Django, stdlib, third-party, local
7. **Relative imports within app** - `from .models import User`
8. **Absolute imports across apps** - `from accounts.models import User`
9. **JSON response format** - `{"success": True/False, "error": "..."}`
10. **Decorator order** - `@login_required` then `@admin_required`
11. **Template inheritance** - `admin/base.html` or `member/base.html`
12. **Soft delete pattern** - `is_deleted` + `deleted_at` fields
13. **Audit logging** - Log all sensitive actions
14. **CSRF tokens** - In all POST requests
15. **Atomic transactions** - For financial operations
16. **F() expressions** - For balance updates

### FILE NAMING:

- Python files: `snake_case.py`
- View functions: `{action}_{entity}_view`
- Model classes: `PascalCase` (singular)
- Form classes: `{Entity}Form`
- Test classes: `{Feature}Tests`
- Templates: `{entity}.html`
- CSS files: `{page}.css`
- JS files: `{page}.js`

### NEVER DO:

- Class-based views
- Type hints
- Models outside accounts app
- Plural model names
- Relative imports across apps
- Hardcoded secrets
- Missing CSRF tokens
- Direct balance updates (use F())
- Skip audit logging
- Forget soft delete checks

---

**END OF PATTERN DOCUMENT**

This document defines ALL patterns used in this Django banking system. Any code generated must strictly adhere to these conventions.

