"""
ABVTrends - VinePair Scraper

Scrapes articles from VinePair.com for alcohol-related media mentions.
VinePair is a leading drinks media publication covering spirits, wine, and beer.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from app.models.signal import SignalType
from app.scrapers.utils.base_scraper import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class VinePairScraper(BaseScraper):
    """
    Scraper for VinePair.com articles.

    Targets:
    - Latest articles from homepage
    - Category pages (spirits, wine, beer)
    - Trending/popular articles

    Extracts:
    - Article title
    - URL
    - Publication date
    - Author
    - Category tags
    - Product mentions in content
    """

    SOURCE_NAME = "vinepair"
    BASE_URL = "https://vinepair.com"

    # Category URLs to scrape (updated URLs based on current site structure)
    CATEGORY_URLS = [
        "/",  # Homepage
        "/explore/category/wine/?post_type=post",
        "/explore/category/spirit/?post_type=post",
        "/explore/category/beer/?post_type=post",
    ]

    # Patterns for identifying product mentions
    PRODUCT_PATTERNS = [
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Whiskey|Bourbon|Scotch|Vodka|Gin|Rum|Tequila|Mezcal|Brandy|Cognac))",
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Wine|Champagne|Prosecco|Cabernet|Chardonnay|Pinot))",
        r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:IPA|Lager|Stout|Ale|Porter))",
    ]

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_base_url(self) -> str:
        return self.BASE_URL

    async def scrape(self) -> list[ScrapedItem]:
        """
        Scrape VinePair for latest articles.

        Returns:
            List of ScrapedItem objects representing article signals
        """
        items: list[ScrapedItem] = []
        seen_urls: set[str] = set()

        for category_url in self.CATEGORY_URLS:
            try:
                url = self.build_url(category_url)
                logger.info(f"Scraping VinePair category: {url}")

                html = await self.fetch_html(url)
                soup = self.parse_html(html)

                # Extract articles from the page
                articles = self._extract_articles(soup)

                for article in articles:
                    if article.url not in seen_urls:
                        seen_urls.add(article.url)
                        items.append(article)

            except Exception as e:
                logger.error(f"Error scraping VinePair {category_url}: {e}")
                continue

        logger.info(f"VinePair scraper found {len(items)} articles")
        return items

    def _extract_articles(self, soup: BeautifulSoup) -> list[ScrapedItem]:
        """Extract articles from page HTML."""
        items: list[ScrapedItem] = []

        # VinePair uses article cards with various class patterns
        article_selectors = [
            "article.post",
            ".article-card",
            ".story-card",
            ".post-item",
            'article[class*="post"]',
        ]

        articles: list[Tag] = []
        for selector in article_selectors:
            found = soup.select(selector)
            if found:
                articles.extend(found)
                break

        # Fallback: look for links in main content area
        if not articles:
            main_content = soup.select_one("main, .main-content, #content")
            if main_content:
                articles = main_content.find_all("article")

        for article in articles[:20]:  # Limit to 20 articles per page
            try:
                item = self._parse_article(article)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing article: {e}")
                continue

        return items

    def _parse_article(self, article: Tag) -> Optional[ScrapedItem]:
        """Parse a single article element."""
        # Extract title and URL
        title_elem = article.select_one("h2 a, h3 a, .title a, .entry-title a, a.title")
        if not title_elem:
            # Try finding any link with substantial text
            for link in article.find_all("a", href=True):
                text = link.get_text(strip=True)
                if len(text) > 20:
                    title_elem = link
                    break

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        url = title_elem.get("href", "")

        if not title or not url:
            return None

        # Make URL absolute
        if not url.startswith("http"):
            url = self.build_url(url)

        # Skip non-article URLs
        if "/author/" in url or "/category/" in url or "/tag/" in url:
            return None

        # Extract publication date
        date_elem = article.select_one("time, .date, .post-date, .entry-date")
        captured_at = self._parse_date(date_elem) if date_elem else datetime.utcnow()

        # Extract author
        author_elem = article.select_one(".author, .byline, .post-author")
        author = author_elem.get_text(strip=True) if author_elem else None

        # Extract category/tags
        category_elem = article.select_one(".category, .post-category, .tag")
        category = category_elem.get_text(strip=True) if category_elem else None

        # Extract excerpt/description
        excerpt_elem = article.select_one(
            ".excerpt, .entry-summary, .description, p"
        )
        excerpt = excerpt_elem.get_text(strip=True)[:500] if excerpt_elem else None

        # Extract image URL
        img_elem = article.select_one("img")
        image_url = None
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")

        # Build raw data
        raw_data = {
            "source": self.SOURCE_NAME,
            "author": author,
            "category": category,
            "excerpt": excerpt,
            "image_url": image_url,
            "scraped_at": datetime.utcnow().isoformat(),
        }

        # Try to extract product mentions from title/excerpt
        product_hint = self._extract_product_hint(title, excerpt)

        return ScrapedItem(
            signal_type=SignalType.MEDIA_MENTION,
            title=title,
            url=url,
            raw_data=raw_data,
            captured_at=captured_at,
            product_hint=product_hint,
        )

    def _parse_date(self, date_elem: Tag) -> datetime:
        """Parse date from various formats."""
        # Try datetime attribute first
        datetime_attr = date_elem.get("datetime")
        if datetime_attr:
            try:
                # ISO format
                return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Try parsing text content
        date_text = date_elem.get_text(strip=True)
        date_formats = [
            "%B %d, %Y",  # January 15, 2025
            "%b %d, %Y",  # Jan 15, 2025
            "%Y-%m-%d",  # 2025-01-15
            "%m/%d/%Y",  # 01/15/2025
            "%d %B %Y",  # 15 January 2025
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        # Default to now if parsing fails
        return datetime.utcnow()

    def _extract_product_hint(
        self, title: str, excerpt: Optional[str]
    ) -> Optional[str]:
        """
        Try to extract a product name from title or excerpt.

        This is used as a hint for the product matching service.
        """
        text = f"{title} {excerpt or ''}"

        for pattern in self.PRODUCT_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                # Return the first match that looks like a product name
                return matches[0]

        return None

    async def scrape_article_detail(self, url: str) -> Optional[dict]:
        """
        Scrape detailed content from a single article page.

        Use this for deeper analysis of specific articles.

        Args:
            url: Article URL

        Returns:
            Dictionary with article details or None if failed
        """
        try:
            html = await self.fetch_html(url)
            soup = self.parse_html(html)

            # Extract article body
            content_elem = soup.select_one(
                "article .content, .entry-content, .article-body, .post-content"
            )
            content = content_elem.get_text(strip=True) if content_elem else ""

            # Extract all product mentions from full content
            product_mentions = []
            for pattern in self.PRODUCT_PATTERNS:
                matches = re.findall(pattern, content)
                product_mentions.extend(matches)

            # Remove duplicates while preserving order
            product_mentions = list(dict.fromkeys(product_mentions))

            return {
                "url": url,
                "full_content": content[:5000],  # Limit content length
                "product_mentions": product_mentions,
                "word_count": len(content.split()),
            }

        except Exception as e:
            logger.error(f"Error scraping article detail {url}: {e}")
            return None
