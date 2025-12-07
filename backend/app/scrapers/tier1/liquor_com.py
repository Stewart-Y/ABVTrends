"""
ABVTrends - Liquor.com Scraper

Scrapes articles and product features from Liquor.com.
Liquor.com is a major cocktail and spirits publication.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from app.models.signal import SignalType
from app.scrapers.utils.base_scraper import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class LiquorComScraper(BaseScraper):
    """
    Scraper for Liquor.com articles.

    Targets:
    - Latest news and articles
    - Spirit reviews and features
    - Cocktail recipes (for brand mentions)
    - "Best Of" lists

    Extracts:
    - Article title and URL
    - Publication date
    - Author
    - Product/brand mentions
    - Category tags
    """

    SOURCE_NAME = "liquor_com"
    BASE_URL = "https://www.liquor.com"

    CATEGORY_URLS = [
        "/",  # Homepage only - other URLs currently 404
    ]

    # Spirit brand patterns for extraction
    BRAND_PATTERNS = [
        # Whiskey brands
        r"\b(Maker's Mark|Buffalo Trace|Woodford Reserve|Wild Turkey|Knob Creek|Bulleit|Four Roses|Elijah Craig|Eagle Rare|Blanton's)\b",
        # Tequila brands
        r"\b(Patron|Don Julio|Casamigos|Clase Azul|Espolon|Herradura|Fortaleza|El Tesoro|Olmeca Altos)\b",
        # Vodka brands
        r"\b(Grey Goose|Belvedere|Ketel One|Absolut|Tito's|Smirnoff|Ciroc|Stolichnaya)\b",
        # Gin brands
        r"\b(Hendrick's|Tanqueray|Bombay Sapphire|Beefeater|Aviation|Roku|The Botanist|Monkey 47)\b",
        # Rum brands
        r"\b(Bacardi|Captain Morgan|Havana Club|Mount Gay|Appleton Estate|Diplomatico|Ron Zacapa|Plantation)\b",
    ]

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_base_url(self) -> str:
        return self.BASE_URL

    async def scrape(self) -> list[ScrapedItem]:
        """
        Scrape Liquor.com for latest articles.

        Returns:
            List of ScrapedItem objects
        """
        items: list[ScrapedItem] = []
        seen_urls: set[str] = set()

        for category_url in self.CATEGORY_URLS:
            try:
                url = self.build_url(category_url)
                logger.info(f"Scraping Liquor.com: {url}")

                html = await self.fetch_html(url)
                soup = self.parse_html(html)

                articles = self._extract_articles(soup)

                for article in articles:
                    if article.url not in seen_urls:
                        seen_urls.add(article.url)
                        items.append(article)

            except Exception as e:
                logger.error(f"Error scraping Liquor.com {category_url}: {e}")
                continue

        logger.info(f"Liquor.com scraper found {len(items)} articles")
        return items

    def _extract_articles(self, soup: BeautifulSoup) -> list[ScrapedItem]:
        """Extract articles from page HTML."""
        items: list[ScrapedItem] = []

        # Liquor.com article card selectors
        article_selectors = [
            ".card",
            ".article-card",
            ".comp.card",
            'div[class*="card"]',
            "article",
        ]

        articles: list[Tag] = []
        for selector in article_selectors:
            found = soup.select(selector)
            if found:
                articles = found
                break

        for article in articles[:25]:
            try:
                item = self._parse_article(article)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing Liquor.com article: {e}")
                continue

        return items

    def _parse_article(self, article: Tag) -> Optional[ScrapedItem]:
        """Parse a single article card."""
        # Find title and link - card__title contains the text, the card itself has the href
        title_elem = article.select_one(".card__title")

        if not title_elem:
            link_elem = article.select_one("a[href]")
            if link_elem:
                title_elem = link_elem

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # Get URL - might be on the element or parent
        url = title_elem.get("href", "")
        if not url:
            parent_link = article.select_one("a[href]")
            url = parent_link.get("href", "") if parent_link else ""

        if not title or not url:
            return None

        # Make URL absolute
        if not url.startswith("http"):
            url = self.build_url(url)

        # Skip non-content URLs
        skip_patterns = ["/author/", "/tag/", "/category/", "#", "javascript:"]
        if any(pattern in url.lower() for pattern in skip_patterns):
            return None

        # Extract date
        date_elem = article.select_one(
            ".card__date, time, .date, .published-date, [class*='date']"
        )
        captured_at = self._parse_date(date_elem) if date_elem else datetime.utcnow()

        # Extract author
        author_elem = article.select_one(
            ".card__author, .author, .byline, [class*='author']"
        )
        author = author_elem.get_text(strip=True) if author_elem else None

        # Extract category
        category_elem = article.select_one(
            ".card__kicker, .category, .tag, [class*='kicker']"
        )
        category = category_elem.get_text(strip=True) if category_elem else None

        # Determine signal type based on category/URL
        signal_type = self._determine_signal_type(url, category, title)

        # Extract excerpt
        excerpt_elem = article.select_one(
            ".card__description, .excerpt, .description, p"
        )
        excerpt = excerpt_elem.get_text(strip=True)[:500] if excerpt_elem else None

        # Extract image
        img_elem = article.select_one("img")
        image_url = None
        if img_elem:
            image_url = (
                img_elem.get("src")
                or img_elem.get("data-src")
                or img_elem.get("data-lazy-src")
            )

        # Build raw data
        raw_data = {
            "source": self.SOURCE_NAME,
            "author": author,
            "category": category,
            "excerpt": excerpt,
            "image_url": image_url,
            "scraped_at": datetime.utcnow().isoformat(),
        }

        # Extract brand mentions
        product_hint = self._extract_brand_mentions(title, excerpt)

        return ScrapedItem(
            signal_type=signal_type,
            title=title,
            url=url,
            raw_data=raw_data,
            captured_at=captured_at,
            product_hint=product_hint,
        )

    def _determine_signal_type(
        self, url: str, category: Optional[str], title: str
    ) -> SignalType:
        """Determine the signal type based on content indicators."""
        lower_title = title.lower()
        lower_url = url.lower()
        lower_category = (category or "").lower()

        # Check for awards/rankings
        award_keywords = ["best", "top", "award", "winner", "rated", "review"]
        if any(kw in lower_title or kw in lower_url for kw in award_keywords):
            return SignalType.AWARD_MENTION

        # Check for feature articles
        feature_keywords = ["feature", "spotlight", "profile", "interview", "story"]
        if any(kw in lower_category for kw in feature_keywords):
            return SignalType.ARTICLE_FEATURE

        # Default to media mention
        return SignalType.MEDIA_MENTION

    def _parse_date(self, date_elem: Tag) -> datetime:
        """Parse date from element."""
        datetime_attr = date_elem.get("datetime")
        if datetime_attr:
            try:
                return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
            except ValueError:
                pass

        date_text = date_elem.get_text(strip=True)

        # Handle relative dates
        if "ago" in date_text.lower():
            return self._parse_relative_date(date_text)

        # Try common formats
        date_formats = [
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%B %Y",
            "%b %Y",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        return datetime.utcnow()

    def _parse_relative_date(self, text: str) -> datetime:
        """Parse relative date strings like '2 days ago'."""
        from datetime import timedelta

        text = text.lower()
        now = datetime.utcnow()

        patterns = [
            (r"(\d+)\s*hour", lambda m: now - timedelta(hours=int(m.group(1)))),
            (r"(\d+)\s*day", lambda m: now - timedelta(days=int(m.group(1)))),
            (r"(\d+)\s*week", lambda m: now - timedelta(weeks=int(m.group(1)))),
            (r"(\d+)\s*month", lambda m: now - timedelta(days=int(m.group(1)) * 30)),
        ]

        for pattern, calculator in patterns:
            match = re.search(pattern, text)
            if match:
                return calculator(match)

        return now

    def _extract_brand_mentions(
        self, title: str, excerpt: Optional[str]
    ) -> Optional[str]:
        """Extract brand mentions from title and excerpt."""
        text = f"{title} {excerpt or ''}"

        for pattern in self.BRAND_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0]

        return None

    async def scrape_best_of_lists(self) -> list[ScrapedItem]:
        """
        Scrape "Best Of" lists specifically.

        These are high-value signals as they indicate editorial endorsement.
        """
        items: list[ScrapedItem] = []

        # Common "Best Of" URLs
        best_of_urls = [
            "/best-whiskey/",
            "/best-tequila/",
            "/best-vodka/",
            "/best-gin/",
            "/best-rum/",
            "/best-bourbon/",
        ]

        for path in best_of_urls:
            try:
                url = self.build_url(path)
                html = await self.fetch_html(url)
                soup = self.parse_html(html)

                # Extract product recommendations
                products = self._extract_product_list(soup, url)
                items.extend(products)

            except Exception as e:
                logger.debug(f"Error scraping best-of list {path}: {e}")
                continue

        return items

    def _extract_product_list(
        self, soup: BeautifulSoup, source_url: str
    ) -> list[ScrapedItem]:
        """Extract products from a list/ranking page."""
        items: list[ScrapedItem] = []

        # Look for product cards or list items
        product_elems = soup.select(
            ".product-card, .list-item, [class*='product'], h3"
        )

        for elem in product_elems:
            product_name = elem.get_text(strip=True)
            if len(product_name) < 5 or len(product_name) > 100:
                continue

            items.append(
                ScrapedItem(
                    signal_type=SignalType.AWARD_MENTION,
                    title=product_name,
                    url=source_url,
                    raw_data={
                        "source": self.SOURCE_NAME,
                        "list_type": "best_of",
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                    captured_at=datetime.utcnow(),
                    product_hint=product_name,
                )
            )

        return items
