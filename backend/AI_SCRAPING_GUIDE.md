# ABVTrends AI-Powered Scraping Architecture

## Overview

ABVTrends has transitioned from brittle CSS selector-based scrapers to a robust **AI-powered content extraction system** that uses Large Language Models (OpenAI GPT-4) to intelligently interpret and extract structured trend data from raw HTML.

## Why AI Scraping?

### Problems with Traditional Scrapers
- ❌ CSS selectors break when websites redesign
- ❌ Requires constant maintenance
- ❌ Can't adapt to new content formats
- ❌ Fragile across different layouts
- ❌ Time-consuming to build and maintain

### Benefits of AI Scraping
- ✅ Robust to layout changes
- ✅ Adapts to different content structures automatically
- ✅ Extracts semantic meaning, not just HTML elements
- ✅ Single extraction logic works across all sources
- ✅ Identifies trends, not just articles
- ✅ Scales to 40+ sources without custom code

## Architecture

```
┌─────────────────┐
│  Legal Sources  │  (40+ media & retail sites)
│  (HTTP Fetch)   │
└────────┬────────┘
         │ Raw HTML
         ▼
┌─────────────────┐
│ HTML Cleaner    │  (BeautifulSoup)
│  - Remove ads   │
│  - Extract text │
│  - Limit tokens │
└────────┬────────┘
         │ Clean Text
         ▼
┌─────────────────┐
│  AI Extractor   │  (OpenAI GPT-4)
│  - Identify     │
│    trends       │
│  - Extract      │
│    entities     │
│  - Classify     │
│    signals      │
└────────┬────────┘
         │ Structured JSON
         ▼
┌─────────────────┐
│  ScrapedItem    │  (Database Model)
│  Converter      │
└────────┬────────┘
         │
         ▼
    [Database]
```

## Key Components

### 1. AIExtractor (`app/services/ai_extractor.py`)

The core AI service that interprets content:

```python
from app.services.ai_extractor import AIExtractor

extractor = AIExtractor(api_key="your-openai-key")
trend = await extractor.extract_from_html(html, url)

# Returns ExtractedTrend with:
# - title: Article title
# - summary: 2-3 sentence trend analysis
# - product_name: Specific product if applicable
# - brand: Brand name
# - category: spirits/wine/beer/rtd
# - celebrity_affiliation: If celebrity-backed
# - trend_reason: Why it's trending
# - confidence_score: 0.0-1.0
```

### 2. AIWebScraper (`app/scrapers/ai_scraper.py`)

Orchestrates the scraping process:

```python
from app.scrapers.ai_scraper import AIWebScraper

async with AIWebScraper(openai_api_key=api_key) as scraper:
    items = await scraper.scrape_source(source_config, max_articles=10)
```

### 3. Sources Configuration (`app/scrapers/sources_config.py`)

All 40+ legal sources in one place:

```python
from app.scrapers.sources_config import (
    ALL_SOURCES,
    TIER1_MEDIA_SOURCES,
    TIER2_RETAIL_SOURCES,
    get_source_by_name,
    get_sources_by_priority,
)

# Get high-priority sources
priority_sources = get_sources_by_priority(min_priority=4)

# Get specific source
bevnet = get_source_by_name("BevNET")
```

## Legal Sources (40+)

### Tier 1: Media & Industry Sources (20)
- BevNET
- Shanken News Daily
- VinePair
- Liquor.com
- Punch
- Food & Wine - Drinks
- Eater - Drinks
- The Manual
- Esquire - Drinks
- DISCUS
- American Distilling Institute
- Tasting Table
- Forbes - Spirits
- Whiskey Raiders
- The Whiskey Wash
- SevenFifty Daily
- Craft Spirits Magazine
- Beverage Dynamics
- The Drinks Business
- Drinks Intel

### Tier 2: Retailer Listings (12)
- ReserveBar
- Total Wine
- BevMo
- Drizly
- GoPuff
- Wine.com
- Binny's
- ABC Fine Wine
- Specs
- Mission Liquor
- K&L Wine Merchants
- Crown Wine & Spirits

All sources verified to:
- ✅ Contain publicly accessible content
- ✅ Not require authentication
- ✅ Not have scraping restrictions in robots.txt
- ✅ Be relevant to alcohol trend analysis

## Usage

### CLI Command

Test AI scraping on a single source:

```bash
cd backend
source venv/bin/activate

# Set your OpenAI API key
export OPENAI_API_KEY='sk-proj-...'

# Test on BevNET (default)
python cli.py ai-scrape

# Test on specific source
python cli.py ai-scrape --source "VinePair" --max-articles 10

# List available sources
python cli.py ai-scrape --source "invalid"
```

### Python API

```python
from app.scrapers.ai_scraper import AIWebScraper
from app.scrapers.sources_config import get_source_by_name

# Get source config
source = get_source_by_name("BevNET")

# Scrape with AI
async with AIWebScraper(openai_api_key="sk-proj-...") as scraper:
    items = await scraper.scrape_source(source, max_articles=10)

    for item in items:
        print(f"Title: {item.title}")
        print(f"Brand: {item.raw_data['brand']}")
        print(f"Trend: {item.raw_data['trend_reason']}")
```

### Batch Scraping

Scrape multiple sources concurrently:

```python
from app.scrapers.ai_scraper import AIWebScraper
from app.scrapers.sources_config import SourceTier

async with AIWebScraper(openai_api_key="sk-proj-...") as scraper:
    # Scrape all Tier 1 media sources (priority 3+)
    items = await scraper.scrape_all_sources(
        tier=SourceTier.TIER1_MEDIA,
        min_priority=3,
        max_articles_per_source=5,
        max_concurrent=3,  # Rate limiting
    )
```

## AI Extraction Prompt

The AI uses this prompt to extract trends:

```
You are an expert trend analyst for the alcohol beverage industry.

Extract the following information and return ONLY valid JSON:

{
  "title": "Article or product title",
  "summary": "2-3 sentence summary of why this is trending",
  "product_name": "Full product name (null if not applicable)",
  "brand": "Brand name",
  "category": "spirits/wine/beer/rtd/sake",
  "subcategory": "tequila/whiskey/vodka/gin/rum/etc",
  "celebrity_affiliation": "Celebrity/influencer name if applicable",
  "trend_reason": "celebrity_launch/new_product/award/seasonal/regional/collaboration",
  "published_date": "YYYY-MM-DD",
  "confidence_score": 0.0-1.0
}

Focus on:
- New product launches
- Celebrity/influencer partnerships
- Awards and accolades
- Regional or seasonal trends
- Retailer new arrivals
- Brand collaborations
```

## Output Format

Each extracted trend returns:

```json
{
  "title": "Karol G partners with Casa Dragones on limited tequila",
  "summary": "Colombian pop star Karol G teams up with Casa Dragones to launch a limited-edition tequila, aimed at expanding the brand's appeal to Gen Z consumers.",
  "product_name": "Casa Dragones x Karol G Limited Tequila",
  "brand": "Casa Dragones",
  "category": "spirits",
  "subcategory": "tequila",
  "celebrity_affiliation": "Karol G",
  "trend_reason": "celebrity_launch",
  "source_url": "https://www.bevnet.com/articles/karol-g-casa-dragones-release",
  "published_date": "2025-11-30",
  "confidence_score": 0.95
}
```

## Rate Limiting & Costs

### Rate Limits
- **Per-source delay**: 2 seconds between articles
- **Batch delay**: 5 seconds between source batches
- **Max concurrent**: 3 sources at a time

### API Costs (OpenAI GPT-4 Turbo)
- **Input**: $10 per million tokens (~6,000 chars per article)
- **Output**: $30 per million tokens (~500 chars per extraction)
- **Estimated cost per article**: ~$0.002-0.004
- **Cost for 1000 articles**: ~$2-4

### Optimization Tips
- Limit `max_articles_per_source` (default: 5)
- Use `min_priority` to scrape high-value sources first
- Cache results to avoid re-scraping
- Batch process during off-peak hours

## Integration with Existing System

The AI scraper produces `ScrapedItem` objects compatible with the existing database:

```python
# AI scraper produces ScrapedItem objects
items = await scraper.scrape_source(source)

# Store in database using existing orchestrator
from app.services.scraper_orchestrator import ScraperOrchestrator

orchestrator = ScraperOrchestrator()
async with get_db_context() as session:
    stored = await orchestrator._process_and_store_items(
        session,
        [("ai_bevnet", item) for item in items]
    )
```

## Error Handling

The AI scraper handles:
- ✅ HTTP timeouts and failures (retries with exponential backoff)
- ✅ Malformed HTML (BeautifulSoup graceful degradation)
- ✅ AI parsing failures (returns None for low-confidence)
- ✅ Rate limit errors (built-in delays)
- ✅ Invalid JSON responses (exception handling)

## Monitoring & Logging

All extraction steps are logged:

```python
import logging

logger = logging.getLogger("app.scrapers.ai_scraper")
logger.setLevel(logging.INFO)

# Logs include:
# - "AI scraping: BevNET (https://...)"
# - "Found 15 article URLs from BevNET"
# - "✓ Extracted: Celebrity Tequila Launch"
# - "✗ Low confidence or irrelevant: recipe-page"
# - "AI scraper extracted 12 items from BevNET"
```

## Testing

```bash
# Test AI extraction on a single source
python cli.py ai-scrape --source "BevNET" --max-articles 3

# Expected output:
# AI Scraping: BevNET
# ============================================================
# Source: BevNET
# URL: https://www.bevnet.com/
# Max articles: 3
#
# ✓ Extracted 3 items
#
#     Extracted Trends
# ┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
# ┃ Title                  ┃ Brand      ┃ Category ┃ Reason          ┃
# ┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
# │ Celebrity Vodka Launch │ Grey Goose │ spirits  │ celebrity_launch│
# └────────────────────────┴────────────┴──────────┴─────────────────┘
```

## Next Steps

1. **Set up OpenAI API key**:
   ```bash
   export OPENAI_API_KEY='sk-proj-...'
   ```

2. **Test single source**:
   ```bash
   python cli.py ai-scrape --source "BevNET" --max-articles 3
   ```

3. **Integrate with orchestrator** to run daily scrapes

4. **Monitor costs** in OpenAI dashboard

5. **Tune confidence threshold** (currently 0.3) based on quality

## Future Enhancements

- [ ] Add Anthropic Claude as fallback extractor
- [ ] Implement result caching (avoid re-scraping same URLs)
- [ ] Add sentiment analysis to summaries
- [ ] Extract product images from HTML
- [ ] Build training dataset for fine-tuned model
- [ ] Add webhook for real-time trend alerts
- [ ] Implement source health monitoring
- [ ] Add A/B testing for different prompts

## Troubleshooting

### Issue: "OPENAI_API_KEY not set"
**Solution**: Export the API key
```bash
export OPENAI_API_KEY='sk-proj-...'
```

### Issue: "Low confidence extractions"
**Solution**: Check if source content is relevant to alcohol trends. May need to adjust article link heuristics.

### Issue: "JSON parsing failed"
**Solution**: GPT-4 with `response_format={"type": "json_object"}` guarantees valid JSON. Check logs for actual response if this occurs.

### Issue: "Too slow"
**Solution**: Reduce `max_articles_per_source` or increase `max_concurrent` batches.

## Architecture Decisions

### Why OpenAI GPT-4?
- ✅ Best-in-class instruction following
- ✅ Guaranteed JSON formatting with response_format
- ✅ Strong semantic understanding
- ✅ Widely available and reliable API
- ✅ Fast response times (~1-2s per article)

### Why not Claude?
- Compatible architecture - can add as fallback
- GPT-4 has native JSON mode for guaranteed structured output
- More familiar to most developers

### Why not fine-tuned models?
- Need training data first (building dataset now)
- Zero-shot works well enough for MVP
- Can fine-tune later for cost optimization

---

**Built with**: Python 3.9+, OpenAI GPT-4 Turbo, httpx, BeautifulSoup4

**Maintained by**: ABVTrends Backend Team
