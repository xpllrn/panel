#!/bin/bash

# Setup script for code-review-graph
# This script installs and configures code-review-graph for the Django project

set -e

echo "🚀 Setting up code-review-graph..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Docker containers are not running. Starting them..."
    docker-compose up -d
    sleep 5
fi

echo "📦 Installing code-review-graph in Docker container..."
docker-compose exec -T web pip install code-review-graph

echo "⚙️  Configuring code-review-graph..."
docker-compose exec -T web code-review-graph install

echo "🔨 Building code graph (this may take ~10 seconds)..."
docker-compose exec -T web code-review-graph build

echo "📊 Graph statistics:"
docker-compose exec -T web code-review-graph status

echo ""
echo "✅ Setup complete!"
echo ""
echo "You can now use code-review-graph with your AI assistant:"
echo "  - /code-review-graph:build-graph"
echo "  - /code-review-graph:review-delta"
echo "  - /code-review-graph:review-pr"
echo ""
echo "Or ask naturally:"
echo '  - "Build the code review graph for this project"'
echo '  - "Review my recent changes using the code graph"'
echo ""
echo "For more information, see CODE_REVIEW_GRAPH_SETUP.md"
