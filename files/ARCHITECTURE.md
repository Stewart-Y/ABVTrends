# ABVTrends Architecture

## Overview

ABVTrends is an AI-powered analytics platform that tracks and predicts trends in the alcohol beverage industry. It aggregates signals from public media sources and private distributor data to generate real-time trend scores and forecasts.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   PUBLIC SOURCES                         PRIVATE SOURCES (Distributor)     │
│   ┌─────────────────────┐               ┌─────────────────────┐            │
│   │ Media Scrapers      │               │ Distributor Scrapers│            │
│   │ • VinePair          │               │ • LibDib            │            │
│   │ • Liquor.com        │               │ • SGWS              │            │
│   │ • BevNET            │               │ • RNDC              │            │
│   │ • Punch             │               │ • Provi             │            │
│   │ • Wine Enthusiast   │               │ • Breakthru         │            │
│   │ • + 15 more         │               │ • Park Street       │            │
│   └─────────┬───────────┘               │ • Republic National │            │
│             │                           └─────────┬───────────┘            │
│   ┌─────────┴───────────┐                         │                        │
│   │ Public Data APIs    │                         │                        │
│   │ • Google Trends     │                         │                        │
│   │ • Wine-Searcher     │                         │                        │
│   │ • Vivino            │                         │                        │
│   │ • Untappd           │                         │                        │
│   └─────────┬───────────┘                         │                        │
│             │                                     │                        │
└─────────────┼─────────────────────────────────────┼────────────────────────┘
              │                                     │
              ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                     SCRAPER SCHEDULER                        │          │
│   │                     (APScheduler / Celery)                   │          │
│   │                                                              │          │
│   │   • Hourly: Distributor scrapers                            │          │
│   │   • Hourly: Media scrapers                                  │          │
│   │   • Daily:  Google Trends refresh                           │          │
│   │   • Weekly: Full catalog sync                               │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                     SESSION MANAGER                          │          │
│   │                                                              │          │
│   │   • Stores distributor auth cookies in Secrets Manager      │          │
│   │   • Tracks session expiration                               │          │
│   │   • Auto-refreshes via Playwright when expired              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PROCESSING LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                   PRODUCT MATCHER                            │          │
│   │                                                              │          │
│   │   • Fuzzy matching across sources (name normalization)      │          │
│   │   • AI-assisted matching for ambiguous cases                │          │
│   │   • Creates unified product_id                              │          │
│   │   • Manual review queue for low-confidence matches          │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                   TREND SCORER                               │          │
│   │                                                              │          │
│   │   Inputs (per product):                                     │          │
│   │   • media_score:     Article mentions, sentiment, recency   │          │
│   │   • retail_score:    # distributors, new additions          │          │
│   │   • price_score:     Stability, discounting patterns        │          │
│   │   • inventory_score: Stock levels, velocity                 │          │
│   │   • search_score:    Google Trends data                     │          │
│   │   • seasonal_score:  Time-of-year adjustments               │          │
│   │                                                              │          │
│   │   Output:                                                    │          │
│   │   • trend_score: 0-100                                      │          │
│   │   • tier: Viral/Trending/Emerging/Stable/Declining          │          │
│   │   • momentum: Change vs previous period                     │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                   FORECASTER                                 │          │
│   │                                                              │          │
│   │   • Prophet / ARIMA for time-series prediction              │          │
│   │   • 7/30/90 day forecasts                                   │          │
│   │   • Confidence intervals                                    │          │
│   │   • AI-generated reasoning text                             │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   PostgreSQL (RDS)                                                         │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                                                              │          │
│   │   CORE TABLES              TIMESERIES TABLES                │          │
│   │   • products               • price_history                  │          │
│   │   • brands                 • inventory_history              │          │
│   │   • categories             • trend_scores_history           │          │
│   │   • distributors           • media_mentions                 │          │
│   │   • articles                                                 │          │
│   │                                                              │          │
│   │   SCRAPER TABLES           MATCHING TABLES                  │          │
│   │   • scrape_runs            • product_aliases                │          │
│   │   • scrape_errors          • match_queue                    │          │
│   │   • raw_product_data                                        │          │
│   │                                                              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│   Redis (ElastiCache)                                                      │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │   • API response caching                                    │          │
│   │   • Session storage                                         │          │
│   │   • Rate limiting                                           │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   FastAPI                                                                  │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                                                              │          │
│   │   /api/v1/trends              GET  - List trending products │          │
│   │   /api/v1/trends/{id}         GET  - Single product detail  │          │
│   │   /api/v1/products            GET  - Product search         │          │
│   │   /api/v1/products/{id}       GET  - Product with scores    │          │
│   │   /api/v1/products/{id}/history    GET  - Historical data   │          │
│   │   /api/v1/products/{id}/forecast   GET  - AI predictions    │          │
│   │   /api/v1/discover/rising     GET  - Early movers           │          │
│   │   /api/v1/discover/viral      GET  - Score 90+              │          │
│   │   /api/v1/discover/new        GET  - Recently added         │          │
│   │   /api/v1/categories          GET  - Category list          │          │
│   │   /api/v1/scraper/status      GET  - Scraper health         │          │
│   │   /api/v1/scraper/trigger     POST - Manual scrape trigger  │          │
│   │                                                              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Next.js                                                                  │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                                                              │          │
│   │   /                     Dashboard with KPIs                 │          │
│   │   /trends               Trending products table             │          │
│   │   /trends/[id]          Product detail + charts             │          │
│   │   /discover             Product discovery sections          │          │
│   │   /search               Search interface                    │          │
│   │   /admin/scraper        Scraper control panel               │          │
│   │                                                              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 14 (App Router) |
| Database | PostgreSQL 15 (RDS) |
| Cache | Redis (ElastiCache) |
| Task Queue | Celery + Redis |
| Scraping | Playwright + httpx |
| AI/ML | OpenAI API, Prophet |
| Infrastructure | AWS (ECS Fargate, ALB, ECR) |
| CI/CD | GitHub Actions |
| Secrets | AWS Secrets Manager |

## Directory Structure

```
abvtrends/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── trends.py
│   │   │   │   ├── products.py
│   │   │   │   ├── discover.py
│   │   │   │   └── scraper.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── secrets.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── models.py
│   │   ├── scrapers/
│   │   │   ├── base.py
│   │   │   ├── session_manager.py
│   │   │   ├── distributors/
│   │   │   │   ├── libdib.py
│   │   │   │   ├── sgws.py
│   │   │   │   ├── rndc.py
│   │   │   │   └── ...
│   │   │   └── media/
│   │   │       ├── vinepair.py
│   │   │       └── ...
│   │   ├── services/
│   │   │   ├── product_matcher.py
│   │   │   ├── trend_scorer.py
│   │   │   └── forecaster.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   └── scrape_tasks.py
│   │   └── main.py
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── ...
├── infrastructure/
│   └── terraform/
├── .env.example
├── docker-compose.yml
└── README.md
```

## Credential Management

**CRITICAL: Never hardcode credentials.**

### Local Development

```bash
# .env (add to .gitignore)
DATABASE_URL=postgresql://user:pass@localhost:5432/abvtrends
REDIS_URL=redis://localhost:6379

OPENAI_API_KEY=sk-...

# Distributor credentials
LIBDIB_EMAIL=your_email@example.com
LIBDIB_PASSWORD=your_password
SGWS_USERNAME=your_username
SGWS_PASSWORD=your_password
# ... etc
```

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openai_api_key: str
    
    # Distributor creds
    libdib_email: str
    libdib_password: str
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Production (AWS)

```python
# app/core/secrets.py
import boto3
import json
from functools import lru_cache

@lru_cache()
def get_secret(secret_name: str) -> dict:
    client = boto3.client('secretsmanager', region_name='us-west-2')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

def get_distributor_creds(distributor: str) -> dict:
    """Get credentials for a specific distributor."""
    return get_secret(f"abvtrends/{distributor}")
```

### Secrets Structure in AWS

```
abvtrends/database
  └── url, username, password

abvtrends/openai
  └── api_key

abvtrends/libdib
  └── email, password, session_id, csrf_token

abvtrends/sgws
  └── username, password, session_cookie

... etc for each distributor
```

## Hourly Scrape Cycle

```
:00  ─── Celery beat triggers scrape tasks
:01  ─── Session Manager checks/refreshes auth for each distributor
:02  ─── Distributor scrapers run in parallel (LibDib, SGWS, RNDC, etc.)
:05  ─── Media scrapers run in parallel
:08  ─── Raw data written to raw_product_data table
:09  ─── Product Matcher runs (dedup, normalize, create unified IDs)
:12  ─── Trend Scorer calculates new scores for all products
:15  ─── Forecaster updates predictions for top 500 products
:18  ─── Cache invalidation (Redis)
:20  ─── API serves fresh data
         │
         └──── Frontend auto-refreshes, users see updated trends
```

## Key Design Decisions

### 1. Product Matching Strategy

Products appear with different names across sources. Matching strategy:

1. **Exact match**: UPC/SKU if available
2. **Fuzzy match**: Brand + Name + Volume using rapidfuzz (>90% confidence)
3. **AI match**: Use OpenAI for ambiguous cases (batch process nightly)
4. **Manual queue**: Low-confidence matches flagged for review

### 2. Trend Score Calculation

```python
def calculate_trend_score(product: Product) -> TrendScore:
    weights = {
        'media': 0.25,
        'retail': 0.25,
        'price': 0.15,
        'inventory': 0.20,
        'search': 0.15
    }
    
    scores = {
        'media': calculate_media_score(product),      # 0-100
        'retail': calculate_retail_score(product),    # 0-100
        'price': calculate_price_score(product),      # 0-100
        'inventory': calculate_inventory_score(product),  # 0-100
        'search': calculate_search_score(product),    # 0-100
    }
    
    composite = sum(scores[k] * weights[k] for k in weights)
    
    return TrendScore(
        score=composite,
        tier=get_tier(composite),
        components=scores,
        momentum=calculate_momentum(product)
    )
```

### 3. Distributor Scraper Pattern

All distributor scrapers inherit from a base class:

```python
class BaseDistributorScraper(ABC):
    @abstractmethod
    async def authenticate(self) -> bool:
        """Login and store session cookies."""
        pass
    
    @abstractmethod
    async def get_products(self, category: str = None) -> list[RawProduct]:
        """Fetch product catalog."""
        pass
    
    @abstractmethod
    async def get_inventory(self, product_ids: list[str]) -> list[InventoryRecord]:
        """Fetch inventory levels."""
        pass
    
    async def run(self) -> ScrapeResult:
        """Main entry point - handles auth, scraping, error handling."""
        pass
```

### 4. Error Handling & Monitoring

- Each scrape run logged to `scrape_runs` table
- Failures logged to `scrape_errors` with full traceback
- Alert to Slack/email if scraper fails 3x consecutively
- Health endpoint for monitoring: `GET /api/v1/scraper/status`

## Performance Targets

| Metric | Target |
|--------|--------|
| Scrape cycle completion | < 20 minutes |
| API response time (p95) | < 200ms |
| Products tracked | 50,000+ |
| Historical data retention | 2 years |
| Forecast accuracy (30-day) | > 70% directional |
