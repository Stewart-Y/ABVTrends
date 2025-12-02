"""ABVTrends Tier 1 Scrapers - Media Sites."""

from app.scrapers.tier1.liquor_com import LiquorComScraper
from app.scrapers.tier1.punch import PunchScraper
from app.scrapers.tier1.vinepair import VinePairScraper

__all__ = [
    "VinePairScraper",
    "LiquorComScraper",
    "PunchScraper",
]

# Registry of all Tier 1 scrapers
TIER1_SCRAPERS = {
    "vinepair": VinePairScraper,
    "liquor_com": LiquorComScraper,
    "punch": PunchScraper,
}
