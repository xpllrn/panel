# Cooperative panel (monorepo)

Django backend with a REST API, server-rendered **admin** and **member** web portals, a **static public marketing site** (served separately, for example via GitHub Pages), and an **Android** member app.

## Repository layout

| Path | What it is |
|------|------------|
| Repo root (`manage.py`, `config/`, `accounts/`, …) | Django project: PostgreSQL models, `api/v1/` REST API, auth, business logic |
| `admin_portal/` | Admin-only HTML views and routes (dashboard, members, loans, funds, …) |
| `member_portal/` | Logged-in member web UI (`/member/…`) |
| `templates/`, `static/` | Django templates and static assets for both portals |
| `docs/` | **Static public website** (plain HTML/CSS/JS). Intended for GitHub Pages: in the repo’s **Settings → Pages**, set source to the **`/docs`** folder on your default branch. Add a **`docs/.nojekyll`** file (already present) so GitHub does not run Jekyll on these files. |
| `android-app/` | Kotlin / Jetpack Compose **member** mobile app (talks to the same API) |

The Django app is **not** the marketing site: `/` still redirects staff or members into the panel. The cooperative’s brochure-style pages live only under `docs/` for static hosting.

## Features

- Admin authentication (Login/Signup)
- Admin profile management with clickable avatar upload
- Members listing page
- Notification settings (Email & Push)
- Left sidebar navigation with dark theme
- Responsive design with Bootstrap 5
- PostgreSQL database
- Docker containerization
- REST API ready

## Tech Stack

- Django 4.2+
- Django REST Framework 3.14.0
- PostgreSQL 15
- Docker & Docker Compose
- Bootstrap 5

## Quick Start

### Prerequisites

- Docker & Docker Compose

### Installation

1. Clone the repository and navigate to the project directory

2. **Set up environment variables:**
```bash
cp .env.example .env
```

3. **Generate a secure SECRET_KEY:**
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copy the output and update `SECRET_KEY` in your `.env` file.

4. Build and start the containers:
```bash
docker-compose up --build
```

5. In a new terminal, run migrations:
```bash
docker-compose exec web python manage.py migrate
```

6. Collect static files:
```bash
docker-compose exec web python manage.py collectstatic --noinput
```

7. Create a superuser (admin):
```bash
docker-compose exec web python manage.py createsuperuser
```

8. Access the application:
   - Admin panel: http://localhost:8000
   - Django admin: http://localhost:8000/admin

### Code Review Graph Setup (Optional)

For AI-assisted code reviews with optimized token usage:

```bash
# Install in Docker container
docker-compose exec web pip install code-review-graph
docker-compose exec web code-review-graph install
docker-compose exec web code-review-graph build
```

This builds a knowledge graph of your codebase that reduces AI token usage by up to 8.2x during code reviews. See `CODE_REVIEW_GRAPH_SETUP.md` for details.

### Environment Variables

Required environment variables in `.env`:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (required) | Generate with command above |
| `DEBUG` | Debug mode (False in production) | `True` or `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `adminpanel` |
| `DB_USER` | PostgreSQL username | `admin` |
| `DB_PASSWORD` | PostgreSQL password | `admin123` |
| `DB_HOST` | PostgreSQL host | `db` (Docker) or `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |

**Security Note:** Never commit your `.env` file to version control!

### Local Development (Without Docker)

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL database and update .env file

4. Run migrations and create superuser:
```bash
python manage.py migrate
python manage.py createsuperuser
```

5. Run the development server:
```bash
python manage.py runserver
```

## Project structure (detailed)

```
.
├── config/              # Django settings, root URLconf
├── accounts/            # Models, API, auth, forms
├── admin_portal/        # Admin UI views
├── member_portal/       # Member web portal views
├── templates/           # Django templates (accounts, admin, member, emails)
├── static/              # Panel static files (CSS, JS)
├── docs/                # Public static website (GitHub Pages)
├── android-app/         # Member Android app
├── docker-compose.yml
├── Dockerfile
├── manage.py
└── requirements.txt
```

## Available Pages

| Route | Description |
|-------|-------------|
| `/login/` | Admin login page |
| `/signup/` | Admin registration |
| `/home/` | Admin dashboard |
| `/members/` | List of all members |
| `/profile/` | Admin profile edit |
| `/admin/` | Django admin panel |

## Docker Commands

```bash
# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Restart containers
docker-compose up

# Create additional admin users
docker-compose exec web python manage.py createsuperuser

# Access Django shell
docker-compose exec web python manage.py shell
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

5. Set up database backups

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
