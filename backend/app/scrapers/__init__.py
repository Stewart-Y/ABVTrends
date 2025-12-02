"""ABVTrends Scrapers - Data collection from media and retail sources."""

from app.scrapers.tier1 import (
    TIER1_SCRAPERS,
    LiquorComScraper,
    PunchScraper,
    VinePairScraper,
)
from app.scrapers.tier2 import (
    TIER2_SCRAPERS,
    BevMoScraper,
    ReserveBarScraper,
    TotalWineScraper,
)
from app.scrapers.utils import (
    BaseScraper,
    BlockedError,
    Proxy,
    ProxyHandler,
    RateLimitError,
    ScrapedItem,
    ScraperError,
)

__all__ = [
    # Base
    "BaseScraper",
    "ScrapedItem",
    "ScraperError",
    "RateLimitError",
    "BlockedError",
    "Proxy",
    "ProxyHandler",
    # Tier 1
    "VinePairScraper",
    "LiquorComScraper",
    "PunchScraper",
    "TIER1_SCRAPERS",
    # Tier 2
    "TotalWineScraper",
    "ReserveBarScraper",
    "BevMoScraper",
    "TIER2_SCRAPERS",
]

# Combined registry of all scrapers
ALL_SCRAPERS = {**TIER1_SCRAPERS, **TIER2_SCRAPERS}
