"""ABVTrends Distributor Scrapers - Data collection from distributor portals."""

from app.scrapers.distributors.base import (
    BaseDistributorScraper,
    RawProduct,
    ScrapeResult,
)
from app.scrapers.distributors.libdib import LibDibScraper
from app.scrapers.distributors.rndc import RNDCScraper
from app.scrapers.distributors.sgws import SGWSScraper
from app.scrapers.distributors.session_manager import SessionManager

# Registry of available distributor scrapers
DISTRIBUTOR_SCRAPERS: dict[str, type[BaseDistributorScraper]] = {
    "libdib": LibDibScraper,
    "sgws": SGWSScraper,
    "rndc": RNDCScraper,
    # Add more scrapers here as they're implemented:
    # "breakthru": BreakthruScraper,
    # "provi": ProviScraper,
}

__all__ = [
    # Base classes
    "BaseDistributorScraper",
    "RawProduct",
    "ScrapeResult",
    # Session management
    "SessionManager",
    # Scrapers
    "LibDibScraper",
    "RNDCScraper",
    "SGWSScraper",
    # Registry
    "DISTRIBUTOR_SCRAPERS",
]
