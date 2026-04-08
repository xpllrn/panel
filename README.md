# Django Admin Panel

A modern admin panel built with Django, Django REST Framework, and PostgreSQL, fully containerized with Docker.

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

- Django 5.0.1
- Django REST Framework 3.14.0
- PostgreSQL 15
- Docker & Docker Compose
- Bootstrap 5
- code-review-graph (AI-powered code review optimization)

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

## Project Structure

```
.
├── config/              # Django settings and configuration
├── accounts/            # User authentication and profile app
├── admin_portal/        # Admin portal app
├── templates/           # HTML templates
├── static/              # Static files (CSS, JS, images)
├── media/               # User uploaded files
├── docker-compose.yml   # Docker compose configuration
├── Dockerfile           # Docker image configuration
└── requirements.txt     # Python dependencies
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
