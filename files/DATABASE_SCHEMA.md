# ABVTrends Database Schema

## Overview

PostgreSQL database with timeseries data support. Uses Alembic for migrations.

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    brands       │       │   categories    │       │  distributors   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ name            │       │ name            │       │ name            │
│ slug            │       │ slug            │       │ slug            │
│ logo_url        │       │ parent_id (FK)  │       │ website         │
│ website         │       │ type            │       │ api_base_url    │
│ country         │       │ (spirits/wine/  │       │ is_active       │
│ created_at      │       │  beer/rtd)      │       │ created_at      │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │                         │                         │
         ▼                         ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                            products                                   │
├──────────────────────────────────────────────────────────────────────┤
│ id (PK, UUID)                                                        │
│ name                                                                 │
│ slug                                                                 │
│ brand_id (FK → brands)                                               │
│ category_id (FK → categories)                                        │
│ subcategory                                                          │
│ description                                                          │
│ volume_ml                                                            │
│ abv                                                                  │
│ country                                                              │
│ region                                                               │
│ image_url                                                            │
│ upc                                                                  │
│ created_at                                                           │
│ updated_at                                                           │
└──────────────────────────────────────────────────────────────────────┘
         │
         │
         ├───────────────────────────────────────────────────────────┐
         │                         │                                 │
         ▼                         ▼                                 ▼
┌─────────────────┐     ┌──────────────────┐            ┌──────────────────┐
│ product_aliases │     │ trend_scores     │            │ price_history    │
├─────────────────┤     ├──────────────────┤            ├──────────────────┤
│ id (PK)         │     │ id (PK)          │            │ id (PK)          │
│ product_id (FK) │     │ product_id (FK)  │            │ product_id (FK)  │
│ source          │     │ score            │            │ distributor_id   │
│ external_id     │     │ tier             │            │ price            │
│ external_name   │     │ momentum         │            │ price_type       │
│ created_at      │     │ media_score      │            │ recorded_at      │
└─────────────────┘     │ retail_score     │            └──────────────────┘
                        │ price_score      │
                        │ inventory_score  │            ┌──────────────────┐
                        │ search_score     │            │ inventory_history│
                        │ calculated_at    │            ├──────────────────┤
                        └──────────────────┘            │ id (PK)          │
                                 │                      │ product_id (FK)  │
                                 ▼                      │ distributor_id   │
                        ┌──────────────────┐            │ quantity         │
                        │ trend_forecasts  │            │ available_states │
                        ├──────────────────┤            │ recorded_at      │
                        │ id (PK)          │            └──────────────────┘
                        │ product_id (FK)  │
                        │ forecast_7d      │
                        │ forecast_30d     │
                        │ forecast_90d     │
                        │ confidence       │
                        │ prediction       │
                        │ reasoning        │
                        │ calculated_at    │
                        └──────────────────┘
```

## Table Definitions

### Core Tables

```sql
-- Brands
CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    logo_url VARCHAR(500),
    website VARCHAR(500),
    country VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_brands_slug ON brands(slug);

-- Categories (hierarchical)
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    type VARCHAR(50) NOT NULL, -- spirits, wine, beer, rtd
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_categories_type ON categories(type);
CREATE INDEX idx_categories_parent ON categories(parent_id);

-- Distributors
CREATE TABLE distributors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    website VARCHAR(500),
    api_base_url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    scraper_class VARCHAR(100), -- e.g., 'LibDibScraper'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Products (unified product catalog)
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(500) NOT NULL,
    slug VARCHAR(500) UNIQUE NOT NULL,
    brand_id INTEGER REFERENCES brands(id),
    category_id INTEGER REFERENCES categories(id),
    subcategory VARCHAR(100),
    description TEXT,
    volume_ml INTEGER,
    abv DECIMAL(5,2),
    country VARCHAR(100),
    region VARCHAR(100),
    image_url VARCHAR(500),
    upc VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_products_brand ON products(brand_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_slug ON products(slug);
CREATE INDEX idx_products_upc ON products(upc) WHERE upc IS NOT NULL;
CREATE INDEX idx_products_name_trgm ON products USING gin(name gin_trgm_ops);

-- Product aliases (maps external IDs to unified products)
CREATE TABLE product_aliases (
    id SERIAL PRIMARY KEY,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL, -- 'libdib', 'sgws', 'vinepair', etc.
    external_id VARCHAR(255) NOT NULL,
    external_name VARCHAR(500),
    external_url VARCHAR(500),
    confidence DECIMAL(3,2) DEFAULT 1.0, -- match confidence 0-1
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(source, external_id)
);

CREATE INDEX idx_product_aliases_product ON product_aliases(product_id);
CREATE INDEX idx_product_aliases_source ON product_aliases(source, external_id);
```

### Timeseries Tables

```sql
-- Price history
CREATE TABLE price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    distributor_id INTEGER REFERENCES distributors(id),
    price DECIMAL(10,2) NOT NULL,
    price_type VARCHAR(50) DEFAULT 'wholesale', -- wholesale, retail, case, bottle
    currency VARCHAR(3) DEFAULT 'USD',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_price_history_product ON price_history(product_id, recorded_at DESC);
CREATE INDEX idx_price_history_recorded ON price_history(recorded_at DESC);

-- Inventory history
CREATE TABLE inventory_history (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    distributor_id INTEGER REFERENCES distributors(id),
    quantity INTEGER,
    in_stock BOOLEAN DEFAULT true,
    available_states TEXT[], -- array of state codes
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_inventory_history_product ON inventory_history(product_id, recorded_at DESC);

-- Trend scores (snapshot per calculation)
CREATE TABLE trend_scores (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    tier VARCHAR(20) NOT NULL, -- viral, trending, emerging, stable, declining
    momentum INTEGER, -- change from previous period
    media_score INTEGER,
    retail_score INTEGER,
    price_score INTEGER,
    inventory_score INTEGER,
    search_score INTEGER,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trend_scores_product ON trend_scores(product_id, calculated_at DESC);
CREATE INDEX idx_trend_scores_calculated ON trend_scores(calculated_at DESC);
CREATE INDEX idx_trend_scores_score ON trend_scores(score DESC, calculated_at DESC);

-- Current trend scores (materialized view or table for fast queries)
CREATE TABLE current_trend_scores (
    product_id UUID PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    tier VARCHAR(20) NOT NULL,
    momentum INTEGER,
    media_score INTEGER,
    retail_score INTEGER,
    price_score INTEGER,
    inventory_score INTEGER,
    search_score INTEGER,
    calculated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_current_scores_score ON current_trend_scores(score DESC);
CREATE INDEX idx_current_scores_tier ON current_trend_scores(tier);

-- Trend forecasts
CREATE TABLE trend_forecasts (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    forecast_7d INTEGER,
    forecast_30d INTEGER,
    forecast_90d INTEGER,
    confidence DECIMAL(3,2),
    prediction VARCHAR(20), -- rising, peaking, stable, declining
    reasoning TEXT, -- AI-generated explanation
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_forecasts_product ON trend_forecasts(product_id, calculated_at DESC);
```

### Media & Articles Tables

```sql
-- Articles
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL, -- vinepair, liquor.com, etc.
    url VARCHAR(1000) UNIQUE NOT NULL,
    title VARCHAR(500),
    author VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content TEXT,
    summary TEXT, -- AI-generated summary
    sentiment DECIMAL(3,2), -- -1 to 1
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_published ON articles(published_at DESC);

-- Article to product mentions
CREATE TABLE article_mentions (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    mention_type VARCHAR(50), -- featured, mentioned, reviewed, listed
    sentiment DECIMAL(3,2),
    excerpt TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_mentions_product ON article_mentions(product_id);
CREATE INDEX idx_mentions_article ON article_mentions(article_id);
```

### Scraper Management Tables

```sql
-- Scrape runs (audit log)
CREATE TABLE scrape_runs (
    id SERIAL PRIMARY KEY,
    scraper_name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL, -- distributor, media
    status VARCHAR(20) NOT NULL, -- running, success, failed, partial
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    products_scraped INTEGER DEFAULT 0,
    products_new INTEGER DEFAULT 0,
    products_updated INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX idx_scrape_runs_scraper ON scrape_runs(scraper_name, started_at DESC);
CREATE INDEX idx_scrape_runs_status ON scrape_runs(status);

-- Scrape errors
CREATE TABLE scrape_errors (
    id SERIAL PRIMARY KEY,
    scrape_run_id INTEGER REFERENCES scrape_runs(id) ON DELETE CASCADE,
    error_type VARCHAR(100),
    error_message TEXT,
    stack_trace TEXT,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scrape_errors_run ON scrape_errors(scrape_run_id);

-- Raw product data (staging table for incoming scrapes)
CREATE TABLE raw_product_data (
    id BIGSERIAL PRIMARY KEY,
    scrape_run_id INTEGER REFERENCES scrape_runs(id),
    source VARCHAR(100) NOT NULL,
    external_id VARCHAR(255),
    raw_data JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    matched_product_id UUID REFERENCES products(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_raw_data_source ON raw_product_data(source, external_id);
CREATE INDEX idx_raw_data_processed ON raw_product_data(processed) WHERE NOT processed;

-- Product match queue (for manual review)
CREATE TABLE match_queue (
    id SERIAL PRIMARY KEY,
    raw_data_id BIGINT REFERENCES raw_product_data(id),
    candidate_product_id UUID REFERENCES products(id),
    confidence DECIMAL(3,2),
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, new_product
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_match_queue_status ON match_queue(status);
```

## Useful Queries

### Get trending products

```sql
SELECT 
    p.id,
    p.name,
    p.slug,
    b.name as brand_name,
    c.name as category_name,
    cts.score,
    cts.tier,
    cts.momentum,
    cts.media_score,
    cts.retail_score
FROM products p
JOIN current_trend_scores cts ON p.id = cts.product_id
LEFT JOIN brands b ON p.brand_id = b.id
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.is_active = true
ORDER BY cts.score DESC
LIMIT 50;
```

### Get product with historical trend data

```sql
SELECT 
    ts.calculated_at::date as date,
    ts.score,
    ts.momentum,
    ts.media_score,
    ts.retail_score
FROM trend_scores ts
WHERE ts.product_id = $1
  AND ts.calculated_at > NOW() - INTERVAL '90 days'
ORDER BY ts.calculated_at;
```

### Get early movers (rising products)

```sql
SELECT 
    p.id,
    p.name,
    cts.score,
    cts.momentum
FROM products p
JOIN current_trend_scores cts ON p.id = cts.product_id
WHERE cts.tier = 'emerging'
  AND cts.momentum > 10
ORDER BY cts.momentum DESC
LIMIT 20;
```

### Get price history for a product

```sql
SELECT 
    ph.recorded_at::date as date,
    d.name as distributor,
    ph.price,
    ph.price_type
FROM price_history ph
JOIN distributors d ON ph.distributor_id = d.id
WHERE ph.product_id = $1
  AND ph.recorded_at > NOW() - INTERVAL '30 days'
ORDER BY ph.recorded_at;
```

### Count products by distributor availability

```sql
SELECT 
    d.name as distributor,
    COUNT(DISTINCT pa.product_id) as product_count
FROM distributors d
JOIN product_aliases pa ON pa.source = d.slug
GROUP BY d.id, d.name
ORDER BY product_count DESC;
```

## Maintenance

### Partition strategy for timeseries tables

For large deployments, partition by month:

```sql
-- Example: partition price_history by month
CREATE TABLE price_history (
    id BIGSERIAL,
    product_id UUID NOT NULL,
    distributor_id INTEGER,
    price DECIMAL(10,2) NOT NULL,
    price_type VARCHAR(50),
    currency VARCHAR(3) DEFAULT 'USD',
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL
) PARTITION BY RANGE (recorded_at);

-- Create monthly partitions
CREATE TABLE price_history_2025_01 PARTITION OF price_history
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ... etc
```

### Data retention

```sql
-- Delete old raw data (keep 30 days)
DELETE FROM raw_product_data 
WHERE created_at < NOW() - INTERVAL '30 days' 
  AND processed = true;

-- Archive old trend scores (keep 2 years in main table)
-- Move older data to archive table or delete
```

### Indexes to monitor

```sql
-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```
