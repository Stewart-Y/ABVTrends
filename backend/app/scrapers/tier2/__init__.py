"""ABVTrends Tier 2 Scrapers - Retailers."""

from app.scrapers.tier2.bevmo import BevMoScraper
from app.scrapers.tier2.reservebar import ReserveBarScraper
from app.scrapers.tier2.totalwine import TotalWineScraper

__all__ = [
    "TotalWineScraper",
    "ReserveBarScraper",
    "BevMoScraper",
]

# Registry of all Tier 2 scrapers
TIER2_SCRAPERS = {
    "totalwine": TotalWineScraper,
    "reservebar": ReserveBarScraper,
    "bevmo": BevMoScraper,
}
