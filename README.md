# Django Admin Panel

A modern admin panel built with Django, Django REST Framework, and Supabase (PostgreSQL).

## Features

- Admin authentication (Login/Signup)
- Admin profile management with clickable avatar upload
- Members listing page with search and pagination
- Member portal with read-only account, loan, and transaction views
- Notification settings (Email & Push)
- Left sidebar navigation with dark theme
- Responsive design with Bootstrap 5
- Supabase PostgreSQL database (hosted)
- REST API ready

## Tech Stack

- Django 4.2
- Django REST Framework 3.14.0
- Supabase (PostgreSQL)
- Supabase Python Client
- Bootstrap 5

## Quick Start

### Prerequisites

- Python 3.9+
- A Supabase account and project ([supabase.com](https://supabase.com))

### Installation

1. Clone the repository and navigate to the project directory

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
```bash
cp .env.example .env
```

5. **Configure Supabase credentials in `.env`:**
   - Go to your Supabase dashboard → **Settings → Database** for DB connection details
   - Go to **Settings → API** for API keys
   - Update all `SUPABASE_*` and `DB_*` variables in `.env`

6. **Generate a secure SECRET_KEY:**
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copy the output and update `SECRET_KEY` in your `.env` file.

7. Run migrations:
```bash
python manage.py migrate
```

8. Create a superuser (admin):
```bash
python manage.py createsuperuser
```

9. Run the development server:
```bash
python manage.py runserver
```

10. Access the application:
    - Admin panel: http://localhost:8000
    - Member portal: http://localhost:8000/member/
    - Django admin: http://localhost:8000/admin

### Environment Variables

Required environment variables in `.env`:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (required) | Generate with command above |
| `DEBUG` | Debug mode (False in production) | `True` or `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase publishable (anon) key | From Supabase dashboard |
| `SUPABASE_SERVICE_KEY` | Supabase secret (service) key | From Supabase dashboard |
| `DB_NAME` | Database name | `postgres` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | Your Supabase DB password |
| `DB_HOST` | Database host | `db.xxx.supabase.co` |
| `DB_PORT` | Database port | `5432` |

**Security Note:** Never commit your `.env` file to version control!

## Project Structure

```
.
├── config/              # Django settings and configuration
│   ├── settings.py      # Main settings (Supabase DB config)
│   ├── supabase_client.py  # Supabase client singleton
│   └── urls.py          # Root URL configuration
├── accounts/            # User authentication and profile app
├── admin_portal/        # Admin portal app
├── member_portal/       # Member portal app
├── templates/           # HTML templates
├── static/              # Static files (CSS, JS, images)
├── media/               # User uploaded files
└── requirements.txt     # Python dependencies
```

## Available Pages

| Route | Description |
|-------|-------------|
| `/login/` | Login page |
| `/home/` | Admin dashboard |
| `/members/` | List of all members |
| `/accounts/` | Member accounts management |
| `/receipts/` | Receipts management |
| `/loans/` | Loans management |
| `/profile/` | Admin profile |
| `/member/` | Member portal dashboard |
| `/member/accounts/` | Member's accounts |
| `/member/loans/` | Member's loans |
| `/member/transactions/` | Member's transactions |
| `/member/profile/` | Member profile & password |
| `/admin/` | Django admin panel |

## Development Commands

```bash
# Run development server
python manage.py runserver

# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test accounts
python manage.py test admin_portal
python manage.py test member_portal

# Create demo data
python manage.py create_demo_data

# Lint and format
ruff check . --fix && ruff format .
```

## Production Deployment

### Security Checklist

- [ ] Generate a strong `SECRET_KEY` and keep it secret
- [ ] Set `DEBUG=False` in production
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Use strong database credentials
- [ ] Enable HTTPS/SSL
- [ ] Set secure cookie flags (automatically enabled when DEBUG=False)
- [ ] Configure CORS properly
- [ ] Set up proper logging
- [ ] Use environment variables for all secrets
- [ ] Never commit `.env` file to version control

### Deployment Steps

1. Update `.env` with production values:
```bash
SECRET_KEY=<generate-new-key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

2. Use a production-grade web server (Gunicorn + Nginx)

3. Set up SSL certificates (Let's Encrypt recommended)

4. Configure static files serving through Nginx

5. Supabase handles database backups automatically

6. Configure monitoring and logging

### Password Requirements

Passwords must meet the following criteria:
- Minimum 8 characters
- Not too similar to username or email
- Not a commonly used password
- Not entirely numeric
- Mix of uppercase, lowercase, and numbers recommended

## License

MIT
