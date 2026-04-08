#!/bin/bash

# Example: Using code-review-graph for code review
# This demonstrates a typical code review workflow

set -e

echo "📝 Code Review Graph - Example Workflow"
echo "========================================"
echo ""

# 1. Update the graph
echo "1️⃣  Updating code graph..."
docker-compose exec -T web code-review-graph update
echo "   ✓ Graph updated"
echo ""

# 2. Show graph statistics
echo "2️⃣  Graph statistics:"
docker-compose exec -T web code-review-graph status
echo ""

# 3. Detect changes since last commit
echo "3️⃣  Analyzing changes since last commit..."
docker-compose exec -T web code-review-graph detect-changes
echo ""

# 4. Show available commands
echo "4️⃣  Available commands for deeper analysis:"
echo ""
echo "   Visualization:"
echo "   $ docker-compose exec web code-review-graph visualize"
echo ""
echo "   Architecture overview:"
echo "   $ docker-compose exec web code-review-graph wiki"
echo ""
echo "   Watch mode (auto-update on file changes):"
echo "   $ docker-compose exec web code-review-graph watch"
echo ""
echo "   Query specific file:"
echo "   $ docker-compose exec web code-review-graph query accounts/models.py"
echo ""

echo "✅ Review workflow complete!"
echo ""
echo "💡 Tip: Use AI assistant slash commands for interactive reviews:"
echo "   /code-review-graph:review-delta"
echo "   /code-review-graph:review-pr"
