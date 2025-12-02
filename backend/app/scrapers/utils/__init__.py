"""ABVTrends Scraper Utilities."""

from app.scrapers.utils.base_scraper import (
    BaseScraper,
    BlockedError,
    RateLimitError,
    ScrapedItem,
    ScraperError,
)
from app.scrapers.utils.proxy_handler import (
    Proxy,
    ProxyHandler,
    ProxyRotatingClient,
    default_proxy_handler,
)

__all__ = [
    # Base Scraper
    "BaseScraper",
    "ScrapedItem",
    "ScraperError",
    "RateLimitError",
    "BlockedError",
    # Proxy Handler
    "Proxy",
    "ProxyHandler",
    "ProxyRotatingClient",
    "default_proxy_handler",
]
