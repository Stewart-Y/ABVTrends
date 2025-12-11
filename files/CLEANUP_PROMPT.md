# Claude Code: Project Cleanup Task

## Context
ABVTrends is an AI-powered analytics platform for tracking alcohol beverage trends. The project has accumulated unnecessary files, features, and dependencies that need to be removed to keep it lean and maintainable.

## Your Task
Audit the entire codebase and remove anything that is NOT essential to these core features:

### Core Features to KEEP
1. **Backend (FastAPI)**
   - REST API endpoints for trends, products, search, discover
   - PostgreSQL database connection (async)
   - AI/OpenAI integration for article analysis
   - Scraper framework (media sources)
   - Trend calculation engine
   - Scheduler for automated jobs

2. **Frontend (Next.js)**
   - Dashboard with KPI cards
   - Trends Explorer (list view with filters)
   - Product detail pages with score breakdowns
   - Discover page (new arrivals, rising, viral)
   - Search functionality
   - Basic responsive layout

3. **Infrastructure**
   - Docker/docker-compose setup
   - Environment variable configuration
   - Basic CI/CD (GitHub Actions)

### What to REMOVE
- Unused React components
- Unused API endpoints
- Unused database models/tables
- Unused dependencies in package.json and requirements.txt
- Dead code (functions/classes never called)
- Redundant CSS/styling files
- Test files for removed features
- Commented-out code blocks
- Duplicate functionality
- Over-engineered abstractions that aren't needed yet
- Any feature that was started but never completed

## Process

### Step 1: Audit
First, list out:
```
FILES TO DELETE:
- [filename] - reason

DEPENDENCIES TO REMOVE:
- [package] - reason

CODE TO SIMPLIFY:
- [file:function] - reason
```

### Step 2: Confirm
Show me the audit list BEFORE making changes. Wait for my approval.

### Step 3: Execute
After approval:
1. Remove identified files
2. Clean up imports in remaining files
3. Remove unused dependencies
4. Run linter to catch any broken imports
5. Verify app still builds and runs

### Step 4: Report
After cleanup, show me:
- Files deleted (count)
- Lines of code removed (estimate)
- Dependencies removed
- New folder structure

## Rules
- Do NOT remove anything related to: database, API, scraping, AI/OpenAI, trend calculation
- Do NOT remove environment/config files
- Do NOT remove Docker setup
- When in doubt, ASK before deleting
- Keep all migrations (database history matters)

## Start
Begin by reading the project structure and listing what you find. Show me the audit before making any changes.
