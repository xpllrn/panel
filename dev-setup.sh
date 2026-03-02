#!/bin/bash
# Local Development Setup Script

set -e

echo "🚀 Setting up local development environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Start PostgreSQL container
echo "📦 Starting PostgreSQL container..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Check if .env exists, if not create from .env.local
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.local..."
    cp .env.local .env
else
    echo "⚠️  .env already exists. Using existing file."
fi

# Run migrations
echo "🔄 Running database migrations..."
python manage.py migrate

# Create superuser prompt
echo ""
echo "✅ Database is ready!"
echo ""
echo "To create a superuser, run:"
echo "  python manage.py createsuperuser"
echo ""
echo "To start the development server, run:"
echo "  python manage.py runserver"
echo ""
echo "To stop PostgreSQL, run:"
echo "  docker-compose down"
echo ""
