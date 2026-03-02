# Local Development with Docker

This project uses Docker for local PostgreSQL development to improve speed and eliminate network latency.

## Quick Start

```bash
# 1. Start PostgreSQL
docker compose up -d

# 2. Run migrations (first time only)
python3 manage.py migrate

# 3. Create superuser (first time only)
python3 manage.py createsuperuser

# 4. Start development server
python3 manage.py runserver
```

## What's Running?

- **PostgreSQL 15** on `localhost:5432`
- **Database**: `panel_dev`
- **User**: `postgres`
- **Password**: `postgres`

## Speed Comparison

- **Supabase (remote)**: 200-500ms per query
- **Local Docker**: 5-20ms per query
- **Speed improvement**: 10-100x faster! 🚀

## Common Commands

```bash
# Start database
docker compose up -d

# Stop database
docker compose down

# View logs
docker compose logs -f

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
python3 manage.py migrate
```

## Environment Files

- `.env.local` - Local development (Docker PostgreSQL)
- `.env.production` - Production (Supabase)
- `.env` - Active config (symlink or copy of above)

## Switching Environments

```bash
# Use local database
cp .env.local .env

# Use production database (Supabase)
cp .env.production .env
```

## Troubleshooting

### Connection refused
```bash
# Check if container is running
docker compose ps

# Restart container
docker compose restart
```

### Password authentication failed
```bash
# Reset database
docker compose down -v
docker compose up -d
python3 manage.py migrate
```

### Port already in use
```bash
# Check what's using port 5432
lsof -i :5432

# Stop local PostgreSQL if installed
brew services stop postgresql
```

## Production Deployment

Production uses Supabase (hosted PostgreSQL). See `deploy/` folder for deployment guides.
