"""
ABVTrends - Scraper Orchestrator

Coordinates running multiple scrapers and processing the collected data.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_context
from app.models.product import Product
from app.models.signal import Signal, SignalType
from app.models.source import Source
from app.scrapers.ai_scraper import AIWebScraper
from app.scrapers.sources_config import (
    SourceConfig,
    SourceTier,
    TIER1_MEDIA_SOURCES,
    TIER2_RETAIL_SOURCES,
    get_sources_by_tier,
)
from app.scrapers.utils.base_scraper import ScrapedItem
from app.services.trend_engine import TrendEngine

logger = logging.getLogger(__name__)


class ScraperOrchestrator:
    """
    Orchestrates the execution of AI-powered scrapers and processes results.

    Features:
    - Run AI scraper across all configured sources
    - Match scraped data to products in database
    - Store signals in database
    - Process signals to update trend scores
    """

    def __init__(self):
        # Try to get API key from environment or settings
        from app.core.config import settings
        self.openai_api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set - AI scraping will fail")

    async def run_all_scrapers(
        self,
        include_tier1: bool = True,
        include_tier2: bool = True,
        parallel: bool = False,
        max_articles_per_source: int = 5,
        max_days_old: int = 30,
    ) -> dict[str, Any]:
        """
        Run AI scrapers across all configured sources and process results.

        Args:
            include_tier1: Run tier1 (media) scrapers
            include_tier2: Run tier2 (retailer) scrapers
            parallel: Run scrapers in parallel (faster but more resource intensive)
            max_articles_per_source: Max articles to extract per source

        Returns:
            Dictionary with summary statistics
        """
        logger.info("Starting AI scraper orchestration")
        start_time = datetime.utcnow()

        # Collect sources to scrape
        sources_to_scrape: list[SourceConfig] = []
        if include_tier1:
            sources_to_scrape.extend(TIER1_MEDIA_SOURCES)
        if include_tier2:
            sources_to_scrape.extend(TIER2_RETAIL_SOURCES)

        logger.info(f"AI scraping {len(sources_to_scrape)} sources")

        all_items: list[tuple[str, ScrapedItem]] = []
        errors: dict[str, str] = {}

        # Run AI scraper
        async with AIWebScraper(openai_api_key=self.openai_api_key) as scraper:
            if parallel:
                # Run sources in parallel (batched for rate limiting)
                max_concurrent = 3
                for i in range(0, len(sources_to_scrape), max_concurrent):
                    batch = sources_to_scrape[i : i + max_concurrent]

                    tasks = [
                        scraper.scrape_source(source, max_articles=max_articles_per_source, max_days_old=max_days_old)
                        for source in batch
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for source, result in zip(batch, results):
                        if isinstance(result, Exception):
                            logger.error(f"Source {source['name']} failed: {result}")
                            errors[source['name']] = str(result)
                        else:
                            items = result
                            all_items.extend([(source['name'], item) for item in items])
                            logger.info(f"Source {source['name']} collected {len(items)} items")

                    # Rate limiting between batches
                    if i + max_concurrent < len(sources_to_scrape):
                        await asyncio.sleep(5)
            else:
                # Run sources sequentially
                for source in sources_to_scrape:
                    try:
                        items = await scraper.scrape_source(source, max_articles=max_articles_per_source, max_days_old=max_days_old)
                        all_items.extend([(source['name'], item) for item in items])
                        logger.info(f"Source {source['name']} collected {len(items)} items")
                    except Exception as e:
                        logger.error(f"Source {source['name']} failed: {e}")
                        errors[source['name']] = str(e)

        # Process and store all items
        async with get_db_context() as session:
            stored_count = await self._process_and_store_items(session, all_items)

            # Recalculate trend scores
            logger.info("Recalculating trend scores...")
            trend_engine = TrendEngine(session)
            await trend_engine.calculate_all_scores()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_seconds": duration,
            "scrapers_run": len(sources_to_scrape),
            "scrapers_failed": len(errors),
            "errors": errors,
            "items_collected": len(all_items),
            "items_stored": stored_count,
        }

        logger.info(f"AI scraping completed in {duration:.2f}s: {len(all_items)} items collected, {stored_count} stored")
        return summary

    async def _process_and_store_items(
        self,
        session: AsyncSession,
        items: list[tuple[str, ScrapedItem]],
    ) -> int:
        """
        Process scraped items and store in database.

        Args:
            session: Database session
            items: List of (scraper_name, item) tuples

        Returns:
            Number of items successfully stored
        """
        stored_count = 0

        for scraper_name, item in items:
            try:
                # Get or create source
                source = await self._get_or_create_source(session, scraper_name)

                # Try to match to existing product
                product = await self._match_product(session, item)

                # Create signal (id auto-generated by default=uuid.uuid4)
                signal = Signal(
                    signal_type=item.signal_type,
                    source_id=source.id,
                    product_id=product.id if product else None,
                    title=item.title,
                    url=item.url,
                    raw_data=item.raw_data,
                    captured_at=item.captured_at,
                    processed=False,
                )

                session.add(signal)
                stored_count += 1

            except Exception as e:
                logger.error(f"Error storing item {item.title}: {e}", exc_info=True)
                continue

        await session.commit()
        return stored_count

    async def _get_or_create_source(
        self,
        session: AsyncSession,
        source_name: str,
    ) -> Source:
        """Get existing source or create new one."""
        stmt = select(Source).where(Source.name == source_name)
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            # Find source config
            from app.models.source import SourceType
            from app.models.source import SourceTier as DBSourceTier
            from app.scrapers.sources_config import get_source_by_name

            source_config = get_source_by_name(source_name)
            if not source_config:
                # Fallback for unknown sources
                logger.warning(f"Unknown source: {source_name}, creating with defaults")
                source_type = SourceType.MEDIA
                tier = DBSourceTier.TIER1
                base_url = "https://unknown.com"
            else:
                # Determine source type and tier from config
                if source_config["tier"] == SourceTier.TIER1_MEDIA:
                    source_type = SourceType.MEDIA
                    tier = DBSourceTier.TIER1
                else:
                    source_type = SourceType.RETAILER
                    tier = DBSourceTier.TIER2
                base_url = source_config["url"]

            source = Source(
                name=source_name,
                slug=source_name.lower().replace(" ", "_").replace(".", "_"),
                source_type=source_type,
                tier=tier,
                base_url=base_url,
                scraper_class="app.scrapers.ai_scraper.AIWebScraper",
                scrape_config={},
                is_active=True,
            )
            session.add(source)
            await session.flush()

        return source

    async def _match_product(
        self,
        session: AsyncSession,
        item: ScrapedItem,
    ) -> Optional[Product]:
        """
        Try to match scraped item to an existing product.

        Uses fuzzy matching on product names and brands.
        If no match found, may create a new product (for retailer signals).

        Args:
            session: Database session
            item: Scraped item

        Returns:
            Matched Product or None
        """
        if not item.product_hint:
            return None

        # Normalize the product hint
        product_hint = item.product_hint.lower().strip()

        # Try exact match first
        stmt = select(Product).where(
            func.lower(Product.name).contains(product_hint)
        ).limit(1)

        result = await session.execute(stmt)
        product = result.scalar_one_or_none()

        if product:
            return product

        # For retailer signals with clear product info, create product
        if item.signal_type in [SignalType.NEW_SKU, SignalType.PRICE_CHANGE, SignalType.PROMOTION]:
            product = await self._create_product_from_item(session, item)
            return product

        return None

    async def _create_product_from_item(
        self,
        session: AsyncSession,
        item: ScrapedItem,
    ) -> Product:
        """
        Create a new product from scraped item data.

        Args:
            session: Database session
            item: Scraped item with product data

        Returns:
            Created Product
        """
        # Extract product details from raw data
        name = item.title
        brand = item.raw_data.get("brand")
        category = item.raw_data.get("category", "spirits")
        subcategory = item.raw_data.get("subcategory")
        image_url = item.raw_data.get("image_url")

        product = Product(
            name=name,
            brand=brand,
            category=category,
            subcategory=subcategory,
            image_url=image_url,
            description=None,
        )

        session.add(product)
        await session.flush()

        logger.info(f"Created new product: {name}")
        return product

    async def run_single_scraper(
        self,
        source_name: str,
        max_articles: int = 5,
    ) -> dict[str, Any]:
        """
        Run AI scraper on a single source by name.

        Args:
            source_name: Name of source to scrape
            max_articles: Maximum articles to extract

        Returns:
            Summary dictionary
        """
        from app.scrapers.sources_config import get_source_by_name

        # Find source config
        source_config = get_source_by_name(source_name)
        if not source_config:
            raise ValueError(f"Unknown source: {source_name}")

        start_time = datetime.utcnow()

        try:
            # Run AI scraper
            async with AIWebScraper(openai_api_key=self.openai_api_key) as scraper:
                items = await scraper.scrape_source(source_config, max_articles=max_articles)

            # Store items
            async with get_db_context() as session:
                stored_count = await self._process_and_store_items(
                    session,
                    [(source_name, item) for item in items]
                )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            return {
                "scraper": source_name,
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_seconds": duration,
                "items_collected": len(items),
                "items_stored": stored_count,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error running AI scraper on {source_name}: {e}")
            return {
                "scraper": source_name,
                "started_at": start_time.isoformat(),
                "error": str(e),
            }
