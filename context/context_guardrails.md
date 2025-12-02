# ABVTrends - Context Guardrails

> This document defines the architectural rules, naming conventions, safety rails, and behavioral guidelines for Claude (or any AI agent) when working on this codebase.

---

## 1. Project Identity

**Name:** ABVTrends
**Tagline:** The Bloomberg Terminal for Alcohol Trends
**Domain:** B2B SaaS - Alcohol Industry Intelligence

**Mission:** Help distributors, brands, retailers, and collectors spot emerging alcohol trends before they go mainstream.

**Core Value Proposition:**
- Detect buzz, launches, regional velocity, price movements, influencer surges, and seasonal patterns
- Calculate weighted Trend Scores (0-100) for spirits, wines, and RTDs
- Forecast next-week trends using ML models (Prophet + LSTM)
- Deliver actionable insights via a modern web dashboard

---

## 2. Architecture Philosophy

### 2.1 Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                        │
│  Presentation Layer - React components, charts, user interaction │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (FastAPI)                       │
│     REST endpoints, authentication, rate limiting, validation    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER (Python)                       │
│  trend_engine, forecast_engine, signal_processor - business logic│
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│     DATA LAYER (Postgres) │   │    ML LAYER (Prophet/LSTM)    │
│   Products, Signals, Scores│   │  Training, Forecasting, Drift │
└───────────────────────────┘   └───────────────────────────────┘
                    ▲                       ▲
                    │                       │
┌─────────────────────────────────────────────────────────────────┐
│                    WORKER LAYER (Celery + Redis)                 │
│         Background jobs: scraping, scoring, retraining           │
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌─────────────────────────────────────────────────────────────────┐
│                     SCRAPER LAYER (Playwright)                   │
│              Tier 1 (Media) + Tier 2 (Retailers)                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Principles

1. **Single Responsibility:** Each module does one thing well
2. **Dependency Injection:** Services receive dependencies, don't create them
3. **Interface Segregation:** Small, focused interfaces over monolithic ones
4. **Fail Fast:** Validate early, error explicitly, never silently swallow exceptions
5. **Idempotency:** Scraping and processing operations must be safely re-runnable

---

## 3. Folder Structure Rules

### 3.1 Backend (`/backend`)

| Folder | Purpose | Rules |
|--------|---------|-------|
| `app/api/v1/` | REST endpoints | One file per resource domain. Use FastAPI routers. Always version APIs. |
| `app/core/` | Configuration & infrastructure | `config.py` for settings, `database.py` for DB setup. No business logic here. |
| `app/models/` | SQLAlchemy ORM models | One model per file. Use snake_case for tables. All models inherit from `Base`. |
| `app/schemas/` | Pydantic schemas | Request/response DTOs. Never expose ORM models directly to API. |
| `app/services/` | Business logic | Pure Python classes. No direct DB access - use repositories pattern if scaling. |
| `app/scrapers/` | Web scraping | `tier1/` for media, `tier2/` for retailers. All inherit from `BaseScraper`. |
| `app/ml/` | Machine learning | `training/` for model training, `forecasting/` for inference, `evaluation/` for monitoring. |
| `app/workers/` | Background tasks | Celery tasks only. Keep tasks thin - delegate to services. |

### 3.2 Frontend (`/frontend`)

| Folder | Purpose | Rules |
|--------|---------|-------|
| `components/` | Reusable UI components | PascalCase filenames. One component per file. Props interface defined in same file. |
| `pages/` | Next.js routes | File-based routing. Use `getServerSideProps` for data fetching where SEO matters. |
| `services/` | API client functions | Typed fetch wrappers. Use React Query for caching. |
| `styles/` | Global styles | Tailwind utilities. Minimal custom CSS. |

### 3.3 Context (`/context`)

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `context_guardrails.md` | This file - rules for AI agents | Update when architecture changes |
| `app_mind_map.md` | System overview and relationships | Update when adding major features |

### 3.4 Infrastructure (`/infra`)

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local development stack |
| `.env.example` | Environment variable template (never commit real secrets) |
| `railway.json` | Railway deployment config |
| `vercel.json` | Vercel frontend config |

---

## 4. Naming Conventions

### 4.1 Python (Backend)

```python
# Files: snake_case.py
trend_engine.py
base_scraper.py

# Classes: PascalCase
class TrendEngine:
class VinePairScraper(BaseScraper):

# Functions/Methods: snake_case
def calculate_trend_score():
def fetch_articles():

# Constants: SCREAMING_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TREND_WEIGHT = 0.15

# Private methods: leading underscore
def _normalize_score():

# Database tables: snake_case, plural
products, signals, trend_scores

# Database columns: snake_case
created_at, trend_score, product_id
```

### 4.2 TypeScript (Frontend)

```typescript
// Files: kebab-case.tsx or PascalCase.tsx for components
trend-card.tsx OR TrendCard.tsx
use-trends.ts

// Components: PascalCase
export function TrendCard() {}
export function ProductDetail() {}

// Hooks: camelCase with 'use' prefix
export function useTrends() {}
export function useProductForecast() {}

// Interfaces/Types: PascalCase with descriptive suffix
interface TrendResponse {}
type ProductCategory = 'spirits' | 'wine' | 'rtd'

// Constants: SCREAMING_SNAKE_CASE
const API_BASE_URL = ''
const REFRESH_INTERVAL_MS = 30000
```

### 4.3 API Endpoints

```
GET    /api/v1/trends              # List trending products
GET    /api/v1/trends/{id}         # Single trend detail
GET    /api/v1/products            # List products
GET    /api/v1/products/{id}       # Product detail with history
GET    /api/v1/forecasts/{id}      # Forecast for product
POST   /api/v1/signals             # (Internal) Ingest new signal
GET    /api/v1/signals             # List recent signals
```

---

## 5. Claude Safety Rails

### 5.1 NEVER Do These

1. **Never delete or overwrite** `context_guardrails.md` or `app_mind_map.md` without explicit user approval
2. **Never hardcode secrets** - always use environment variables
3. **Never skip error handling** - all external calls (DB, API, scraping) must have try/except
4. **Never use `print()` for logging** - use Python's `logging` module
5. **Never commit commented-out code** - delete unused code
6. **Never use `any` type in TypeScript** without explicit justification
7. **Never bypass the schema layer** - API responses must go through Pydantic
8. **Never run scrapers without rate limiting** - respect robots.txt and add delays
9. **Never store ML models in git** - use external storage or MLflow

### 5.2 ALWAYS Do These

1. **Always read existing files** before modifying them
2. **Always maintain backward compatibility** in API changes (or version bump)
3. **Always add type hints** to Python functions
4. **Always validate input** at API boundaries
5. **Always use async** for I/O-bound operations in FastAPI
6. **Always add docstrings** to public functions and classes
7. **Always handle the empty state** in frontend components
8. **Always use parameterized queries** - never string concatenation for SQL
9. **Always implement retry logic** for scrapers with exponential backoff

### 5.3 When Updating Files

```
Before modifying any file:
1. Read the current file content
2. Understand the existing patterns
3. Maintain consistency with surrounding code
4. Update related files if interface changes
5. Update tests if behavior changes
6. Update this guardrails doc if architecture changes
```

---

## 6. Data Flow Rules

### 6.1 Signal Ingestion Pipeline

```
[Scraper] → [Raw Data] → [Signal Processor] → [DB: signals table]
                                                      │
                                                      ▼
                                            [Trend Engine]
                                                      │
                                                      ▼
                                            [DB: trend_scores table]
```

### 6.2 Forecast Pipeline

```
[Daily Cron] → [Fetch Historical Scores] → [Prophet/LSTM Training]
                                                      │
                                                      ▼
                                            [Model Evaluation]
                                                      │
                                           ┌─────────┴─────────┐
                                           ▼                   ▼
                                    [Drift Check]       [Save Model]
                                           │                   │
                                           ▼                   ▼
                                    [Alert if drift]   [Run Forecast]
                                                              │
                                                              ▼
                                                    [DB: forecasts table]
```

### 6.3 API Response Pipeline

```
[Request] → [Auth Middleware] → [Rate Limiter] → [Router]
                                                     │
                                                     ▼
                                              [Service Layer]
                                                     │
                                                     ▼
                                              [ORM Query]
                                                     │
                                                     ▼
                                              [Pydantic Schema]
                                                     │
                                                     ▼
                                              [JSON Response]
```

---

## 7. Trend Score Calculation

The Trend Score (0-100) is a weighted composite of 6 signals:

| Signal | Weight | Source | Description |
|--------|--------|--------|-------------|
| Media Mentions | 0.20 | Tier 1 scrapers | Article count & sentiment from VinePair, Liquor.com, Punch |
| Social Velocity | 0.20 | Future: social APIs | Rate of mention growth on social platforms |
| Retailer Presence | 0.15 | Tier 2 scrapers | Availability across TotalWine, ReserveBar, BevMo |
| Price Movement | 0.15 | Tier 2 scrapers | Price changes and promotional activity |
| Search Interest | 0.15 | Future: Google Trends API | Search volume trends |
| Seasonal Alignment | 0.15 | Internal calendar | Holiday/season relevance boost |

```python
# Calculation formula
trend_score = (
    media_score * 0.20 +
    social_score * 0.20 +
    retailer_score * 0.15 +
    price_score * 0.15 +
    search_score * 0.15 +
    seasonal_score * 0.15
) * 100
```

---

## 8. Error Handling Standards

### 8.1 Backend Exceptions

```python
# Custom exception hierarchy
class ABVTrendsError(Exception):
    """Base exception for all ABVTrends errors"""

class ScraperError(ABVTrendsError):
    """Raised when scraping fails"""

class TrendCalculationError(ABVTrendsError):
    """Raised when trend score calculation fails"""

class ForecastError(ABVTrendsError):
    """Raised when ML forecasting fails"""

class ValidationError(ABVTrendsError):
    """Raised when input validation fails"""
```

### 8.2 API Error Responses

```json
{
  "error": {
    "code": "TREND_NOT_FOUND",
    "message": "Trend with ID 123 not found",
    "details": null
  }
}
```

HTTP Status Codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error

---

## 9. Testing Standards

### 9.1 Test Structure

```
backend/
  tests/
    unit/
      test_trend_engine.py
      test_signal_processor.py
    integration/
      test_api_trends.py
      test_scraper_vinepair.py
    fixtures/
      sample_signals.json
      mock_responses/
```

### 9.2 Test Naming

```python
# Pattern: test_<method>_<scenario>_<expected>
def test_calculate_score_with_missing_signals_returns_partial():
def test_fetch_articles_when_site_down_retries_three_times():
def test_forecast_with_insufficient_data_raises_error():
```

---

## 10. Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:5432/abvtrends
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<random-32-char-string>

# Optional with defaults
LOG_LEVEL=INFO
SCRAPER_DELAY_SECONDS=2
MAX_CONCURRENT_SCRAPERS=3
FORECAST_HORIZON_DAYS=7
MODEL_RETRAIN_HOUR=3  # 3 AM UTC

# External APIs (future)
GOOGLE_TRENDS_API_KEY=
SOCIAL_API_KEY=
```

---

## 11. Deployment Checklist

Before deploying to production:

- [ ] All tests pass
- [ ] No hardcoded secrets
- [ ] Database migrations are up to date
- [ ] Environment variables are set in deployment platform
- [ ] Rate limiting is configured
- [ ] Error monitoring is set up (Sentry recommended)
- [ ] Logging is configured for production level
- [ ] Scraper delays are appropriate for production
- [ ] ML models are trained and stored
- [ ] Backup strategy is in place

---

## 12. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-XX | Initial guardrails document |

---

*This document is the source of truth for architectural decisions. Update it when the system evolves.*
