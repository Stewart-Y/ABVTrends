"""
ABVTrends - Scraping Sources Configuration

Defines all legally scrape-safe websites for alcohol trend monitoring.
These sources have been verified to:
- Contain publicly accessible content
- Not require authentication
- Not have scraping restrictions in robots.txt
- Be relevant to alcohol trend analysis
"""

from enum import Enum
from typing import List, TypedDict


class SourceTier(str, Enum):
    """Source tier classification."""

    TIER1_MEDIA = "tier1_media"  # Media & industry sources
    TIER2_RETAIL = "tier2_retail"  # Public retailer listings


class SourceConfig(TypedDict):
    """Source configuration."""

    name: str
    url: str
    tier: SourceTier
    description: str
    priority: int  # 1-5, higher = more important


# Tier 1: Media & Industry Sources
TIER1_MEDIA_SOURCES: List[SourceConfig] = [
    {
        "name": "BevNET",
        "url": "https://www.bevnet.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Leading beverage industry news and analysis",
        "priority": 5,
    },
    {
        "name": "Shanken News Daily",
        "url": "https://www.shankennewsdaily.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Wine, beer, and spirits industry news",
        "priority": 5,
    },
    {
        "name": "VinePair",
        "url": "https://vinepair.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Wine and spirits culture magazine",
        "priority": 4,
    },
    {
        "name": "Liquor.com",
        "url": "https://www.liquor.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Cocktails and spirits publication",
        "priority": 4,
    },
    {
        "name": "Punch",
        "url": "https://punchdrink.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Craft cocktails and spirits magazine",
        "priority": 4,
    },
    {
        "name": "Food & Wine - Drinks",
        "url": "https://www.foodandwine.com/drinks",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Food & Wine drinks section",
        "priority": 3,
    },
    {
        "name": "Eater - Drinks",
        "url": "https://www.eater.com/drinks",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Eater cocktails and spirits coverage",
        "priority": 3,
    },
    {
        "name": "The Manual - Spirits",
        "url": "https://www.themanual.com/food-and-drink/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Men's lifestyle spirits coverage",
        "priority": 3,
    },
    {
        "name": "Esquire - Drinks",
        "url": "https://www.esquire.com/food-drink/drinks/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Esquire drinks and cocktails section",
        "priority": 3,
    },
    {
        "name": "DISCUS",
        "url": "https://www.distilledspirits.org/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Distilled Spirits Council press releases",
        "priority": 4,
    },
    {
        "name": "American Distilling Institute",
        "url": "https://distilling.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Craft distilling industry news",
        "priority": 3,
    },
    {
        "name": "Tasting Table",
        "url": "https://www.tastingtable.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Food and drink trends",
        "priority": 3,
    },
    {
        "name": "Forbes - Spirits",
        "url": "https://www.forbes.com/food-drink/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Forbes spirits and wine business news",
        "priority": 4,
    },
    {
        "name": "Whiskey Raiders",
        "url": "https://whiskeyraiders.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Whiskey reviews and news",
        "priority": 3,
    },
    {
        "name": "The Whiskey Wash",
        "url": "https://thewhiskeywash.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Whiskey culture and news",
        "priority": 3,
    },
    {
        "name": "SevenFifty Daily",
        "url": "https://daily.sevenfifty.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Wine and spirits trade publication",
        "priority": 4,
    },
    {
        "name": "Craft Spirits Magazine",
        "url": "https://www.craftspiritsmag.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Craft distilling magazine",
        "priority": 3,
    },
    {
        "name": "Beverage Dynamics",
        "url": "https://beveragedynamics.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Beverage retail and distribution news",
        "priority": 3,
    },
    {
        "name": "The Drinks Business",
        "url": "https://www.thedrinksbusiness.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Global drinks industry news",
        "priority": 4,
    },
    {
        "name": "Drinks Intel",
        "url": "https://drinksint.com/",
        "tier": SourceTier.TIER1_MEDIA,
        "description": "Drinks industry intelligence",
        "priority": 3,
    },
]

# Tier 2: Public Retailer Listings
TIER2_RETAIL_SOURCES: List[SourceConfig] = [
    {
        "name": "ReserveBar",
        "url": "https://www.reservebar.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Premium spirits online retailer",
        "priority": 4,
    },
    {
        "name": "Total Wine",
        "url": "https://www.totalwine.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Major wine and spirits retailer",
        "priority": 5,
    },
    {
        "name": "BevMo",
        "url": "https://www.bevmo.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Beverage retailer new arrivals",
        "priority": 4,
    },
    {
        "name": "Drizly",
        "url": "https://www.drizly.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Alcohol delivery platform",
        "priority": 4,
    },
    {
        "name": "GoPuff",
        "url": "https://www.gopuff.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "On-demand delivery including alcohol",
        "priority": 3,
    },
    {
        "name": "Wine.com",
        "url": "https://www.wine.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Online wine retailer",
        "priority": 4,
    },
    {
        "name": "Binny's",
        "url": "https://www.binnys.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Chicago-area wine and spirits retailer",
        "priority": 3,
    },
    {
        "name": "ABC Fine Wine",
        "url": "https://www.abcfws.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Florida wine and spirits chain",
        "priority": 3,
    },
    {
        "name": "Specs",
        "url": "https://www.specsonline.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Texas liquor retailer",
        "priority": 3,
    },
    {
        "name": "Mission Liquor",
        "url": "https://www.missionliquor.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "California spirits retailer",
        "priority": 2,
    },
    {
        "name": "K&L Wine Merchants",
        "url": "https://www.klwines.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "Specialty wine and spirits retailer",
        "priority": 3,
    },
    {
        "name": "Crown Wine & Spirits",
        "url": "https://www.crownwineandspirits.com/",
        "tier": SourceTier.TIER2_RETAIL,
        "description": "New York spirits retailer",
        "priority": 2,
    },
]

# Combined list of all sources
ALL_SOURCES = TIER1_MEDIA_SOURCES + TIER2_RETAIL_SOURCES


def get_sources_by_tier(tier: SourceTier) -> List[SourceConfig]:
    """Get all sources for a specific tier."""
    return [s for s in ALL_SOURCES if s["tier"] == tier]


def get_sources_by_priority(min_priority: int = 1) -> List[SourceConfig]:
    """Get sources above a minimum priority threshold."""
    return [s for s in ALL_SOURCES if s["priority"] >= min_priority]


def get_source_by_name(name: str):
    """Get source configuration by name."""
    for source in ALL_SOURCES:
        if source["name"].lower() == name.lower():
            return source
    return None
