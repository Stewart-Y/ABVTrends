"""ABVTrends Scrapers - Data collection from media, retail, and distributor sources."""

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
from app.scrapers.distributors import (
    DISTRIBUTOR_SCRAPERS,
    BaseDistributorScraper,
    LibDibScraper,
    RawProduct,
    ScrapeResult,
    SessionManager,
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
    # Distributors
    "BaseDistributorScraper",
    "RawProduct",
    "ScrapeResult",
    "SessionManager",
    "LibDibScraper",
    "DISTRIBUTOR_SCRAPERS",
]

# Combined registry of all media/retail scrapers
ALL_SCRAPERS = {**TIER1_SCRAPERS, **TIER2_SCRAPERS}
