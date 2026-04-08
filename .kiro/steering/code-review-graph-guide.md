---
inclusion: manual
---

# Code Review Graph Quick Reference

This steering file provides quick guidance for using code-review-graph in this Django project.

## When to Use Code Review Graph

Use code-review-graph when:
- Reviewing code changes (PRs, commits)
- Understanding blast radius of changes
- Finding affected tests and dependencies
- Analyzing architecture and code structure
- Refactoring code safely
- Onboarding to unfamiliar code areas

## Available Commands

### For AI Assistants (You)

When the user asks for code review or impact analysis, you can:

1. **Build/Update Graph**
   ```bash
   docker-compose exec web code-review-graph build
   ```

2. **Get Impact Radius**
   ```bash
   docker-compose exec web code-review-graph detect-changes
   ```

3. **Query Graph**
   Use MCP tools (automatically available after graph is built):
   - `get_impact_radius_tool` - Get blast radius of changes
   - `query_graph_tool` - Query callers, callees, tests
   - `semantic_search_nodes_tool` - Search code entities
   - `get_review_context_tool` - Get optimized review context

### Slash Commands (User Can Use)

- `/code-review-graph:build-graph` - Build or rebuild
- `/code-review-graph:review-delta` - Review recent changes
- `/code-review-graph:review-pr` - Full PR review

## Project-Specific Usage Patterns

### Django Model Changes

When `accounts/models.py` changes:
1. Find affected views: Query graph for callers
2. Find affected serializers: Check API views
3. Find affected tests: Query test coverage
4. Check migrations: Look for model references

### API Endpoint Changes

When `accounts/api_views.py` changes:
1. Find frontend consumers: Check static/js files
2. Find URL routing: Check urls.py
3. Find tests: Query test coverage
4. Check permissions: Look for decorator usage

### View Changes

When `admin_portal/views.py` changes:
1. Find templates: Check template references
2. Find URL patterns: Check urls.py
3. Find forms: Check form imports
4. Find tests: Query test coverage

## Token Optimization Strategy

The graph reduces token usage by:
1. **Structural Summary**: Compact representation of code structure
2. **Blast Radius**: Only affected files, not entire codebase
3. **Dependency Chains**: Precise import and call relationships
4. **Test Mapping**: Direct test-to-code relationships

Expected reduction: 6-9x fewer tokens for this Django project size.

## Integration with Review Workflow

### Pre-Review Checklist

1. Ensure graph is up to date: `code-review-graph update`
2. Get change summary: `code-review-graph detect-changes`
3. Review blast radius before detailed analysis
4. Focus on high-risk changes first

### Review Process

1. **Identify Changes**: Use git diff or detect-changes
2. **Get Context**: Use get_review_context_tool
3. **Analyze Impact**: Use get_impact_radius_tool
4. **Check Tests**: Query test coverage for changed code
5. **Review Dependencies**: Check affected callers/callees

### Post-Review

1. Update graph: `code-review-graph update`
2. Verify test coverage for new code
3. Check for architectural impacts

## Common Queries

### "What's affected by this change?"
Use `get_impact_radius_tool` with changed file paths

### "Where is this function called?"
Use `query_graph_tool` with function name and "callers" query type

### "What tests cover this code?"
Use `query_graph_tool` with file path and "tests" query type

### "Show me the architecture"
Use `get_architecture_overview_tool`

### "Find large functions"
Use `find_large_functions_tool` with line threshold

## Performance Notes

- Initial build: ~10 seconds for this project
- Incremental updates: <2 seconds
- Graph queries: <1ms
- Watch mode: Auto-updates on file save

## Troubleshooting

### Graph out of date
```bash
docker-compose exec web code-review-graph build --force
```

### MCP tools not available
Ensure graph is built and MCP server is configured:
```bash
docker-compose exec web code-review-graph install
docker-compose exec web code-review-graph build
```

### Large context still being used
Check `.code-review-graphignore` - may need to exclude more files

## Best Practices

1. **Keep graph updated**: Run `update` after significant changes
2. **Use blast radius first**: Don't read entire files unnecessarily
3. **Trust the graph**: It has 100% recall (never misses affected files)
4. **Exclude noise**: Use `.code-review-graphignore` for generated files
5. **Leverage MCP tools**: They're optimized for token efficiency

## Resources

- Full setup guide: `CODE_REVIEW_GRAPH_SETUP.md`
- GitHub: https://github.com/tirth8205/code-review-graph
- Quick setup: `./scripts/setup_code_review_graph.sh`
