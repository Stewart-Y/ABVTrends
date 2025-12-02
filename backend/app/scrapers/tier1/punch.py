"""
ABVTrends - Punch Scraper

Scrapes articles from PunchDrink.com.
Punch is a respected publication covering cocktails, spirits, wine, and bar culture.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from app.models.signal import SignalType
from app.scrapers.utils.base_scraper import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class PunchScraper(BaseScraper):
    """
    Scraper for PunchDrink.com articles.

    Targets:
    - Latest articles and features
    - Spirit deep dives
    - Wine coverage
    - Recipe sections (brand mentions)
    - Industry news

    Punch tends to have more in-depth, editorial content compared to other sources.
    """

    SOURCE_NAME = "punch"
    BASE_URL = "https://punchdrink.com"

    CATEGORY_URLS = [
        "/",  # Homepage
        "/articles/",
        "/spirits/",
        "/wine/",
        "/recipes/",
        "/news/",
    ]

    # Product/brand patterns specific to Punch's editorial style
    PRODUCT_PATTERNS = [
        # Specific product mentions (brand + type)
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Single Malt|Blended|Bourbon|Rye|Scotch|Irish Whiskey))",
        # Winery/vineyard names
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Vineyard|Winery|Estate|Cellars))",
        # Distillery names
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Distillery|Distilling|Distillers))",
        # Natural wine producers
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Natural Wine|Pet-Nat|Orange Wine))",
    ]

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_base_url(self) -> str:
        return self.BASE_URL

    async def scrape(self) -> list[ScrapedItem]:
        """
        Scrape Punch for latest articles.

        Returns:
            List of ScrapedItem objects
        """
        items: list[ScrapedItem] = []
        seen_urls: set[str] = set()

        for category_url in self.CATEGORY_URLS:
            try:
                url = self.build_url(category_url)
                logger.info(f"Scraping Punch: {url}")

                html = await self.fetch_html(url)
                soup = self.parse_html(html)

                articles = self._extract_articles(soup)

                for article in articles:
                    if article.url not in seen_urls:
                        seen_urls.add(article.url)
                        items.append(article)

            except Exception as e:
                logger.error(f"Error scraping Punch {category_url}: {e}")
                continue

        logger.info(f"Punch scraper found {len(items)} articles")
        return items

    def _extract_articles(self, soup: BeautifulSoup) -> list[ScrapedItem]:
        """Extract articles from Punch page HTML."""
        items: list[ScrapedItem] = []

        # Punch uses clean, minimal markup
        article_selectors = [
            "article",
            ".post",
            ".article",
            ".story",
            ".card",
            'div[class*="article"]',
            'div[class*="post"]',
        ]

        articles: list[Tag] = []
        for selector in article_selectors:
            found = soup.select(selector)
            if found:
                articles = found
                break

        # Fallback: look for main content links
        if not articles:
            main = soup.select_one("main, #main, .main-content")
            if main:
                # Get all heading links
                articles = main.select("h2 a, h3 a")

        for article in articles[:20]:
            try:
                item = self._parse_article(article)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing Punch article: {e}")
                continue

        return items

    def _parse_article(self, article: Tag) -> Optional[ScrapedItem]:
        """Parse a single article element."""
        # Handle case where article is already a link
        if article.name == "a":
            title = article.get_text(strip=True)
            url = article.get("href", "")
        else:
            # Find title link
            title_elem = article.select_one(
                "h2 a, h3 a, .title a, .headline a, a.title, a.headline"
            )

            if not title_elem:
                # Try any link with substantial text
                for link in article.find_all("a", href=True):
                    text = link.get_text(strip=True)
                    if len(text) > 15:
                        title_elem = link
                        break

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            url = title_elem.get("href", "")

        if not title or not url:
            return None

        # Ensure absolute URL
        if not url.startswith("http"):
            url = self.build_url(url)

        # Skip non-article URLs
        skip_patterns = [
            "/author/",
            "/tag/",
            "/category/",
            "/page/",
            "#",
            "javascript:",
        ]
        if any(pattern in url.lower() for pattern in skip_patterns):
            return None

        # Extract date
        date_elem = article.select_one("time, .date, .published, [datetime]")
        captured_at = self._parse_date(date_elem) if date_elem else datetime.utcnow()

        # Extract author
        author_elem = article.select_one(".author, .byline, .writer, [rel='author']")
        author = author_elem.get_text(strip=True) if author_elem else None
        if author:
            # Clean up author text
            author = author.replace("By ", "").replace("by ", "").strip()

        # Extract category/section
        category_elem = article.select_one(".category, .section, .tag, .kicker")
        category = category_elem.get_text(strip=True) if category_elem else None

        # Determine signal type
        signal_type = self._determine_signal_type(title, category)

        # Extract excerpt
        excerpt_elem = article.select_one(
            ".excerpt, .summary, .description, .dek, p"
        )
        excerpt = None
        if excerpt_elem:
            excerpt = excerpt_elem.get_text(strip=True)[:500]

        # Extract image
        img_elem = article.select_one("img")
        image_url = None
        if img_elem:
            image_url = (
                img_elem.get("src")
                or img_elem.get("data-src")
                or img_elem.get("srcset", "").split()[0] if img_elem.get("srcset") else None
            )

        raw_data = {
            "source": self.SOURCE_NAME,
            "author": author,
            "category": category,
            "excerpt": excerpt,
            "image_url": image_url,
            "scraped_at": datetime.utcnow().isoformat(),
        }

        product_hint = self._extract_product_mentions(title, excerpt)

        return ScrapedItem(
            signal_type=signal_type,
            title=title,
            url=url,
            raw_data=raw_data,
            captured_at=captured_at,
            product_hint=product_hint,
        )

    def _determine_signal_type(
        self, title: str, category: Optional[str]
    ) -> SignalType:
        """Determine signal type based on content."""
        lower_title = title.lower()
        lower_category = (category or "").lower()

        # Feature articles (Punch specialty)
        feature_indicators = [
            "guide",
            "essential",
            "deep dive",
            "history of",
            "story of",
            "rise of",
            "future of",
        ]
        if any(ind in lower_title for ind in feature_indicators):
            return SignalType.ARTICLE_FEATURE

        # Award/recognition content
        award_indicators = ["best", "top", "award", "winner", "favorites"]
        if any(ind in lower_title for ind in award_indicators):
            return SignalType.AWARD_MENTION

        # Recipe content still counts as media mention
        return SignalType.MEDIA_MENTION

    def _parse_date(self, date_elem: Tag) -> datetime:
        """Parse date from element."""
        # Try datetime attribute
        datetime_attr = date_elem.get("datetime")
        if datetime_attr:
            try:
                return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
            except ValueError:
                pass

        date_text = date_elem.get_text(strip=True)

        # Common date formats
        formats = [
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%B %Y",
            "%d %B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        return datetime.utcnow()

    def _extract_product_mentions(
        self, title: str, excerpt: Optional[str]
    ) -> Optional[str]:
        """Extract product/brand mentions."""
        text = f"{title} {excerpt or ''}"

        for pattern in self.PRODUCT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0]

        # Also look for common brand names
        common_brands = [
            "Lagavulin",
            "Macallan",
            "Ardbeg",
            "Laphroaig",
            "Domaine",
            "Chateau",
            "Bodega",
        ]

        for brand in common_brands:
            if brand.lower() in text.lower():
                return brand

        return None

    async def scrape_deep_dives(self) -> list[ScrapedItem]:
        """
        Scrape Punch's deep-dive/long-form content.

        These are high-quality editorial features that often indicate
        significant industry trends.
        """
        items: list[ScrapedItem] = []

        deep_dive_urls = [
            "/spirits/whiskey/",
            "/spirits/mezcal/",
            "/spirits/rum/",
            "/wine/natural-wine/",
            "/wine/champagne/",
        ]

        for path in deep_dive_urls:
            try:
                url = self.build_url(path)
                html = await self.fetch_html(url)
                soup = self.parse_html(html)

                # Extract articles with ARTICLE_FEATURE type
                articles = self._extract_articles(soup)
                for article in articles:
                    article.signal_type = SignalType.ARTICLE_FEATURE
                    items.append(article)

            except Exception as e:
                logger.debug(f"Error scraping deep dive {path}: {e}")
                continue

        return items
