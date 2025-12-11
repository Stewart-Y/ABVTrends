# ABVTrends Implementation Plan

## Overview

This document outlines the phased implementation plan for adding distributor scraping to ABVTrends. Designed to be executed by Claude Code.

## Prerequisites

Before starting, ensure:

1. **Environment setup**
   ```bash
   # Clone repo and setup
   cd abvtrends
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Install Playwright browsers
   playwright install chromium
   ```

2. **Environment variables** in `.env`:
   ```
   DATABASE_URL=postgresql://...
   REDIS_URL=redis://localhost:6379
   OPENAI_API_KEY=sk-...
   
   # Distributor credentials
   LIBDIB_EMAIL=...
   LIBDIB_PASSWORD=...
   LIBDIB_ENTITY_SLUG=weshipexpress
   ```

3. **Database** running with base schema

---

## Phase 1: Database Schema Updates

**Goal**: Add tables for distributor data, timeseries tracking, and scraper management.

### Tasks

1. **Create Alembic migration for new tables**:
   - `distributors` - List of distributor sources
   - `product_aliases` - Maps external IDs to unified products
   - `price_history` - Timeseries price data
   - `inventory_history` - Timeseries inventory data
   - `scrape_runs` - Audit log of scraper runs
   - `scrape_errors` - Error tracking
   - `raw_product_data` - Staging table for incoming data

2. **Add indexes** for performance:
   - `idx_price_history_product` on (product_id, recorded_at)
   - `idx_trend_scores_calculated` on (calculated_at DESC)
   - Trigram index on product names for fuzzy search

3. **Seed initial data**:
   - Insert distributor records (LibDib, SGWS, etc.)
   - Insert category hierarchy

### Commands for Claude Code

```
Read DATABASE_SCHEMA.md and create Alembic migration for all tables.
Include proper indexes and foreign keys.
Generate seed data script for distributors and categories.
```

---

## Phase 2: Scraper Framework

**Goal**: Build base scraper classes and session management.

### Tasks

1. **Create directory structure**:
   ```
   app/scrapers/
   ├── __init__.py
   ├── base.py              # BaseDistributorScraper class
   ├── session_manager.py   # Session/auth management
   └── distributors/
       ├── __init__.py
       └── libdib.py        # First implementation
   ```

2. **Implement base classes** (from SCRAPER_FRAMEWORK.md):
   - `RawProduct` dataclass
   - `ScrapeResult` dataclass  
   - `BaseDistributorScraper` abstract class

3. **Implement SessionManager**:
   - AWS Secrets Manager integration
   - Local fallback for development
   - Playwright refresh methods

4. **Implement LibDibScraper**:
   - Authentication with session cookies
   - Product fetching with pagination
   - Category iteration
   - Response parsing

### Commands for Claude Code

```
Read SCRAPER_FRAMEWORK.md and implement the complete scraper framework.
Start with base.py, then session_manager.py, then libdib.py.
Add comprehensive error handling and logging.
Write unit tests for parsing logic.
```

---

## Phase 3: Data Pipeline

**Goal**: Process scraped data into unified product records.

### Tasks

1. **Create ProductMatcher service**:
   ```
   app/services/
   ├── product_matcher.py   # Fuzzy matching logic
   ├── trend_scorer.py      # Score calculation
   └── forecaster.py        # AI predictions
   ```

2. **Implement matching logic**:
   - Exact match by UPC (if available)
   - Fuzzy match by brand + name + volume (using rapidfuzz)
   - AI-assisted matching for low-confidence cases
   - Queue for manual review

3. **Implement data storage**:
   - Insert raw data to `raw_product_data`
   - Match to existing products or create new
   - Update `product_aliases` mapping
   - Insert to `price_history` and `inventory_history`

### Commands for Claude Code

```
Create ProductMatcher service that:
1. Takes RawProduct from scraper
2. Attempts to match to existing product in DB
3. Creates new product if no match found
4. Stores price/inventory history
5. Returns match confidence score

Use rapidfuzz for string matching.
Integration with OpenAI for ambiguous cases (batch, async).
```

---

## Phase 4: Trend Scoring Enhancement

**Goal**: Incorporate distributor signals into trend scores.

### Tasks

1. **Update TrendScorer** to include:
   - `retail_score`: Based on distributor presence
     - Number of distributors carrying product
     - Recently added to new distributor (+boost)
     - State availability breadth
   - `inventory_score`: Based on stock signals
     - Stock levels relative to historical
     - Velocity (stock changes over time)
   - `price_score`: Based on pricing patterns
     - Price stability
     - Discounting detection

2. **Update score weights**:
   ```python
   weights = {
       'media': 0.25,      # Existing
       'retail': 0.25,     # NEW - distributor presence
       'price': 0.15,      # NEW - pricing signals
       'inventory': 0.20,  # NEW - stock signals
       'search': 0.15      # Existing (Google Trends)
   }
   ```

3. **Update current_trend_scores** materialized view/table

### Commands for Claude Code

```
Update TrendScorer service to incorporate distributor signals.
Add retail_score, inventory_score, price_score calculations.
Update the composite score calculation with new weights.
Add momentum calculation (vs 24h ago, 7d ago).
Update current_trend_scores after each calculation.
```

---

## Phase 5: Celery Tasks & Scheduling

**Goal**: Automate hourly scrape cycle.

### Tasks

1. **Configure Celery**:
   ```python
   # app/tasks/celery_app.py
   celery_app = Celery(
       "abvtrends",
       broker=settings.redis_url,
       backend=settings.redis_url
   )
   ```

2. **Create scrape tasks**:
   - `scrape_all_distributors` - Runs all distributor scrapers
   - `scrape_distributor(name)` - Run single scraper
   - `process_raw_data` - Match and store products
   - `calculate_trends` - Update all trend scores
   - `update_forecasts` - Update AI predictions

3. **Configure beat schedule**:
   ```python
   celery_app.conf.beat_schedule = {
       "scrape-hourly": {
           "task": "scrape_all_distributors",
           "schedule": 3600.0,
       },
       "calculate-trends": {
           "task": "calculate_trends", 
           "schedule": 3600.0,
           "options": {"countdown": 600}  # After scrapes
       },
   }
   ```

4. **Add health monitoring**:
   - Track consecutive failures
   - Alert on 3+ failures
   - Scraper status endpoint

### Commands for Claude Code

```
Set up Celery with Redis broker.
Create scrape tasks from SCRAPER_FRAMEWORK.md.
Configure beat schedule for hourly runs.
Add error tracking and alerting logic.
Create /api/v1/scraper/status endpoint.
```

---

## Phase 6: API Endpoints

**Goal**: Expose distributor data through API.

### Tasks

1. **New endpoints**:
   ```
   GET /api/v1/products/{id}/prices
     - Historical price data by distributor
   
   GET /api/v1/products/{id}/availability  
     - Current distributor availability
   
   GET /api/v1/products/{id}/history
     - Combined trend + price + inventory history
   
   GET /api/v1/discover/new-arrivals
     - Recently added to distributors
   
   GET /api/v1/scraper/status
     - Scraper health dashboard data
   
   POST /api/v1/scraper/trigger/{distributor}
     - Manual scrape trigger (admin only)
   ```

2. **Update existing endpoints**:
   - `/api/v1/trends` - Include retail_score in response
   - `/api/v1/products/{id}` - Include distributor data

3. **Add caching**:
   - Redis caching for trend data (5 min TTL)
   - Cache invalidation after scrape cycle

### Commands for Claude Code

```
Add new API endpoints for distributor data.
Update existing trend/product endpoints.
Implement Redis caching with proper invalidation.
Add OpenAPI documentation for all new endpoints.
```

---

## Phase 7: Frontend Updates

**Goal**: Display distributor signals in UI.

### Tasks

1. **Product detail page**:
   - Add "Available From" section showing distributors
   - Add price history chart (by distributor)
   - Add inventory indicator
   - Update score breakdown to show retail/inventory/price

2. **Discover page**:
   - Add "New Arrivals" section (recently added to distributors)
   - Filter by distributor availability

3. **Admin page**:
   - Scraper status dashboard
   - Manual trigger buttons
   - Error log viewer

### Commands for Claude Code

```
Update product detail page to show distributor data.
Add price history chart using recharts.
Create scraper admin dashboard at /admin/scraper.
Add "New Arrivals" section to discover page.
```

---

## Phase 8: Additional Scrapers

**Goal**: Add remaining distributor scrapers.

### Priority Order

1. **SGWS** (Southern Glazer's) - Largest distributor
2. **RNDC** (Republic National) - Major distributor
3. **Breakthru Beverage** - Growing distributor
4. **Provi** - B2B marketplace
5. **Park Street** - Craft spirits focus
6. **LibDib** ✓ (already done)

### For Each Scraper

1. Inspect network traffic (like we did for LibDib)
2. Document API endpoints
3. Implement scraper class
4. Add session refresh method
5. Test and validate
6. Add to task registry

### Commands for Claude Code

```
When I provide network traffic screenshots for a new distributor,
analyze the API and implement a scraper following the LibDib pattern.
Add to DISTRIBUTOR_SCRAPERS registry and create session refresh method.
```

---

## Testing Strategy

### Unit Tests

```
tests/
├── scrapers/
│   ├── test_libdib.py
│   └── test_base.py
├── services/
│   ├── test_product_matcher.py
│   └── test_trend_scorer.py
└── api/
    └── test_products.py
```

### Integration Tests

- Full scrape cycle with mock responses
- Database operations
- API endpoint responses

### E2E Tests (Playwright)

- Dashboard loads with trend data
- Product detail shows distributor info
- Admin can trigger manual scrape

---

## Deployment Checklist

### AWS Setup

- [ ] Create secrets in Secrets Manager for each distributor
- [ ] Update ECS task definition with new env vars
- [ ] Add Redis (ElastiCache) for Celery broker
- [ ] Configure Celery worker in separate ECS service
- [ ] Set up CloudWatch alarms for scraper failures

### Database

- [ ] Run migrations on RDS
- [ ] Create read replica for analytics queries (optional)
- [ ] Set up automated backups

### Monitoring

- [ ] Scraper success/failure metrics
- [ ] API latency dashboards
- [ ] Alert on consecutive scraper failures

---

## Quick Start for Claude Code

```
I want to implement the ABVTrends distributor scraping system.

Please read these files first:
- ARCHITECTURE.md - Overall system design
- DATABASE_SCHEMA.md - Database tables
- SCRAPER_FRAMEWORK.md - Scraper implementation details

Start with Phase 1 (database migrations), then proceed sequentially.

Credentials are in .env file - use python-dotenv to load them.
Never hardcode any credentials in the code.

Ask me questions if anything is unclear before implementing.
```
