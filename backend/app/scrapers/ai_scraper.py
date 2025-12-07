"""
ABVTrends - AI-Powered Scraper

Simple HTTP fetcher + AI extraction pipeline.
Replaces brittle CSS selector-based scrapers with robust AI interpretation.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from app.models.signal import SignalType
from app.scrapers.sources_config import (
    ALL_SOURCES,
    SourceConfig,
    SourceTier,
    get_sources_by_priority,
    get_sources_by_tier,
)
from app.scrapers.utils.base_scraper import ScrapedItem
from app.services.ai_extractor import AIExtractor, ExtractedTrend

logger = logging.getLogger(__name__)


class AIWebScraper:
    """
    AI-powered web scraper.

    Fetches content from legal sources and uses AI to extract structured trend data.
    Much more robust than CSS selector-based scrapers.
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize AI scraper.

        Args:
            openai_api_key: OpenAI API key (reads from env if not provided)
        """
        self.extractor = AIExtractor(api_key=openai_api_key)
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "ABVTrends/1.0 (Trend Research Bot; contact@abvtrends.com)"
            },
            follow_redirects=True,
        )

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def scrape_source(
        self, source: SourceConfig, max_articles: int = 10, max_days_old: int = 30
    ) -> List[ScrapedItem]:
        """
        Scrape a single source using AI extraction.

        Args:
            source: Source configuration
            max_articles: Maximum number of articles to extract
            max_days_old: Maximum age of articles in days (default 30)

        Returns:
            List of ScrapedItem objects
        """
        logger.info(f"AI scraping: {source['name']} ({source['url']})")
        items: List[ScrapedItem] = []
        skipped_old = 0

        try:
            # Fetch homepage
            response = await self.http_client.get(source["url"])
            response.raise_for_status()
            html = response.text

            # Extract article links
            article_urls = self._extract_article_links(html, source["url"])

            # Limit articles
            article_urls = article_urls[:max_articles]

            logger.info(
                f"Found {len(article_urls)} article URLs from {source['name']}"
            )

            # Calculate cutoff date
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=max_days_old)

            # Process each article with AI
            for url in article_urls:
                try:
                    # Fetch article
                    article_response = await self.http_client.get(url)
                    article_response.raise_for_status()
                    article_html = article_response.text

                    # AI extraction
                    extracted = await self.extractor.extract_from_html(
                        article_html, url
                    )

                    if extracted and extracted.confidence_score >= 0.3:
                        # Check article freshness
                        if extracted.published_date:
                            try:
                                pub_date = datetime.fromisoformat(extracted.published_date.replace('Z', '+00:00'))

                                if pub_date < cutoff_date:
                                    skipped_old += 1
                                    logger.debug(f"✗ Article too old ({extracted.published_date}): {extracted.title[:50]}")
                                    continue
                                else:
                                    logger.debug(f"✓ Fresh article ({extracted.published_date}): {extracted.title[:50]}")
                            except (ValueError, TypeError) as e:
                                # If date parsing fails, include the article anyway
                                logger.debug(f"⚠ Could not parse date '{extracted.published_date}': {e}")
                        else:
                            # No date found - include the article but log it
                            logger.debug(f"⚠ No date found for: {extracted.title[:50]}")

                        # Convert to ScrapedItem
                        item = self._to_scraped_item(extracted, source["name"])
                        items.append(item)
                        logger.debug(f"✓ Extracted: {extracted.title}")
                    else:
                        logger.debug(f"✗ Low confidence or irrelevant: {url}")

                    # Rate limiting
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.warning(f"Failed to process article {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to scrape {source['name']}: {e}")

        if skipped_old > 0:
            logger.info(f"Skipped {skipped_old} articles older than {max_days_old} days")

        logger.info(f"AI scraper extracted {len(items)} items from {source['name']}")
        return items

    def _extract_article_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract article URLs from homepage HTML.

        Uses simple heuristics to find article links.

        Args:
            html: Homepage HTML
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute article URLs
        """
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []

        # Find all links
        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Skip external links, footer links, etc.
            if any(
                skip in href.lower()
                for skip in [
                    "facebook",
                    "twitter",
                    "instagram",
                    "youtube",
                    "mailto:",
                    "tel:",
                    "#",
                    "javascript:",
                ]
            ):
                continue

            # Make absolute
            if href.startswith("/"):
                href = base_url.rstrip("/") + href
            elif not href.startswith("http"):
                continue

            # Only include links from same domain
            if base_url.split("//")[1].split("/")[0] not in href:
                continue

            # Heuristic: article URLs often contain /article/, /news/, /spirits/, etc.
            # or have longer paths
            if (
                any(
                    keyword in href.lower()
                    for keyword in [
                        "/article",
                        "/news",
                        "/spirits",
                        "/wine",
                        "/beer",
                        "/drinks",
                        "/food-drink",
                        "/cocktails",
                        "/whiskey",
                        "/tequila",
                        "/vodka",
                    ]
                )
                or href.count("/") >= 4
            ):
                if href not in links:
                    links.append(href)

        return links[:50]  # Limit to first 50 links found

    def _to_scraped_item(
        self, extracted: ExtractedTrend, source_name: str
    ) -> ScrapedItem:
        """
        Convert AI-extracted trend to ScrapedItem.

        Args:
            extracted: Extracted trend from AI
            source_name: Source name

        Returns:
            ScrapedItem for database storage
        """
        # Determine signal type from trend reason
        signal_type = SignalType.MEDIA_MENTION
        if extracted.trend_reason:
            reason_lower = extracted.trend_reason.lower()
            if "celebrity" in reason_lower or "launch" in reason_lower:
                signal_type = SignalType.ARTICLE_FEATURE
            elif "award" in reason_lower:
                signal_type = SignalType.AWARD_MENTION
            elif "new_product" in reason_lower:
                signal_type = SignalType.NEW_SKU

        # Parse published date
        captured_at = datetime.utcnow()
        if extracted.published_date:
            try:
                captured_at = datetime.fromisoformat(extracted.published_date)
            except (ValueError, TypeError):
                pass

        # Build raw data
        raw_data = {
            "source": source_name,
            "summary": extracted.summary,
            "product_name": extracted.product_name,
            "brand": extracted.brand,
            "category": extracted.category,
            "celebrity_affiliation": extracted.celebrity_affiliation,
            "trend_reason": extracted.trend_reason,
            "confidence_score": extracted.confidence_score,
            "scraped_at": datetime.utcnow().isoformat(),
        }

        # Product hint for matching
        product_hint = None
        if extracted.product_name:
            product_hint = extracted.product_name
        elif extracted.brand:
            product_hint = extracted.brand

        return ScrapedItem(
            signal_type=signal_type,
            title=extracted.title,
            url=extracted.source_url,
            raw_data=raw_data,
            captured_at=captured_at,
            product_hint=product_hint,
        )

    async def scrape_all_sources(
        self,
        tier: Optional[SourceTier] = None,
        min_priority: int = 3,
        max_articles_per_source: int = 5,
        max_concurrent: int = 3,
    ) -> List[ScrapedItem]:
        """
        Scrape multiple sources concurrently.

        Args:
            tier: Filter by tier (None = all tiers)
            min_priority: Minimum priority threshold
            max_articles_per_source: Max articles to extract per source
            max_concurrent: Max concurrent source requests

        Returns:
            Combined list of all extracted items
        """
        # Get sources to scrape
        if tier:
            sources = get_sources_by_tier(tier)
        else:
            sources = get_sources_by_priority(min_priority)

        logger.info(
            f"AI scraping {len(sources)} sources (tier={tier}, min_priority={min_priority})"
        )

        all_items: List[ScrapedItem] = []

        # Process sources in batches to limit concurrency
        for i in range(0, len(sources), max_concurrent):
            batch = sources[i : i + max_concurrent]

            tasks = [
                self.scrape_source(source, max_articles=max_articles_per_source)
                for source in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for source, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Source {source['name']} failed: {result}")
                else:
                    all_items.extend(result)

            # Rate limiting between batches
            if i + max_concurrent < len(sources):
                await asyncio.sleep(5)

        logger.info(f"AI scraping complete: {len(all_items)} total items extracted")
        return all_items
