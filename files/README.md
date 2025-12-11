# ABVTrends Distributor Scraper System

## Context for Claude Code

This package contains architecture documentation and reference implementations for adding distributor data scraping to ABVTrends.

**What is ABVTrends?**
An AI-powered analytics platform that tracks and predicts trends in the alcohol beverage industry. It aggregates signals from media coverage, retail availability, and industry news to generate real-time trend scores.

**What are we building?**
A system to scrape product, pricing, and inventory data from beverage distributor portals (LibDib, SGWS, RNDC, etc.) to enhance trend scoring and forecasting.

**Key constraints:**
1. Credentials must NEVER be hardcoded - use environment variables locally, AWS Secrets Manager in prod
2. Scrapers run hourly on a schedule
3. All data is timeseries (historical tracking for forecasting)
4. Must integrate with existing FastAPI backend and PostgreSQL database

---

## Files in This Package

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | Complete system architecture, database schema, interfaces |
| `IMPLEMENTATION_PLAN.md` | Step-by-step build instructions |
| `scrapers/libdib.py` | Reference implementation for LibDib scraper |
| `.env.example` | Template for environment variables |

---

## How to Use This Package

### For Claude Code:

1. **Read `ARCHITECTURE.md` first** - understand the full system design
2. **Follow `IMPLEMENTATION_PLAN.md`** - phases are ordered by dependency
3. **Use `scrapers/libdib.py` as reference** - other scrapers follow same pattern
4. **Never hardcode credentials** - always use `os.getenv()` or secrets manager

### Quick Start Commands:

```bash
# Copy these files into the ABVTrends backend directory
cp -r scrapers/ /path/to/abvtrends/backend/app/scrapers/
cp .env.example /path/to/abvtrends/backend/.env.example

# Install dependencies
pip install httpx playwright python-dotenv
playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env with real credentials

# Test LibDib scraper
cd /path/to/abvtrends/backend
python -m app.scrapers.distributors.libdib
```

---

## Architecture Summary

```
Hourly Cron
    │
    ▼
┌─────────────────┐
│  Orchestrator   │ ─── Runs all enabled scrapers
└────────┬────────┘
         │
    ┌────┴────┬─────────┐
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│LibDib │ │ SGWS  │ │ RNDC  │  ... more scrapers
└───┬───┘ └───┬───┘ └───┬───┘
    │         │         │
    └─────────┼─────────┘
              ▼
    ┌─────────────────┐
    │   Normalizer    │ ─── Unified schema, product matching
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   PostgreSQL    │ ─── Products, price_history, inventory_history
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Trend Scoring  │ ─── Combines media + distributor signals
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │    FastAPI      │ ─── Serves to frontend
    └─────────────────┘
```

---

## Key Interfaces

### Scraper Base Class

All scrapers implement:
- `authenticate()` → Verify session is valid
- `get_categories()` → List available categories
- `get_products(category)` → Fetch products
- `scrape_all()` → Full scrape of all categories

### Data Models

- `RawProduct` - Raw data from a distributor (before normalization)
- `ScrapeResult` - Result of a scrape operation
- `Product` - Unified product in database
- `PriceHistory` - Timeseries price data
- `InventoryHistory` - Timeseries inventory data

---

## Important Notes

1. **Session cookies expire** - LibDib sessions last hours/days. The system should handle re-auth gracefully or use Playwright for auto-login.

2. **Rate limiting** - Add delays between requests (1-2 seconds). We're scraping hourly, not continuously, so this is fine.

3. **Product matching is hard** - Same product has different names across distributors. AI-assisted fuzzy matching is needed.

4. **Start with LibDib** - It's already documented. Other distributors need similar DevTools exploration to find their APIs.

5. **Don't expose raw distributor data** - The API serves trend scores and normalized data, not raw scrape results.

---

## Questions?

If anything is unclear, check `ARCHITECTURE.md` for details or ask for clarification.
