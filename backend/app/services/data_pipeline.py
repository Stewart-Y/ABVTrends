"""
ABVTrends - Data Pipeline Service

Processes scrape results from distributor scrapers:
1. Stores raw data in staging table
2. Matches products to existing records
3. Creates price and inventory history
4. Queues low-confidence matches for review
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.distributor import (
    Distributor,
    InventoryHistory,
    MatchQueue,
    PriceHistory,
    RawProductData,
    ScrapeError,
    ScrapeRun,
)
from app.scrapers.distributors.base import RawProduct, ScrapeResult
from app.services.product_matcher import MatchResult, ProductMatcher

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Statistics from a pipeline run."""

    total_products: int = 0
    products_matched: int = 0
    products_created: int = 0
    products_queued: int = 0
    products_failed: int = 0
    price_records: int = 0
    inventory_records: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class DataPipeline:
    """
    Processes distributor scrape results into the database.

    Main entry point is `process_scrape_result()` which:
    1. Records the scrape run
    2. Stores raw product data
    3. Matches products to existing records (or creates new)
    4. Creates price/inventory history entries
    5. Queues uncertain matches for manual review
    """

    # Confidence threshold for auto-matching
    AUTO_MATCH_THRESHOLD = 0.85
    QUEUE_THRESHOLD = 0.60

    def __init__(self, db: AsyncSession):
        """
        Initialize the data pipeline.

        Args:
            db: Async database session
        """
        self.db = db
        self.matcher = ProductMatcher(db)

    async def process_scrape_result(
        self,
        result: ScrapeResult,
        distributor_slug: str,
    ) -> PipelineStats:
        """
        Process a complete scrape result.

        Args:
            result: ScrapeResult from a distributor scraper
            distributor_slug: Slug of the distributor (e.g., 'libdib')

        Returns:
            PipelineStats with processing statistics
        """
        stats = PipelineStats(total_products=len(result.products))

        # Get distributor
        distributor = await self._get_distributor(distributor_slug)
        if not distributor:
            stats.errors.append(f"Distributor not found: {distributor_slug}")
            return stats

        # Create scrape run record
        scrape_run = await self._create_scrape_run(
            distributor=distributor,
            result=result,
        )

        try:
            # Process each product
            for raw_product in result.products:
                try:
                    await self._process_product(
                        raw_product=raw_product,
                        distributor=distributor,
                        scrape_run=scrape_run,
                        stats=stats,
                    )
                except Exception as e:
                    logger.error(f"Failed to process product {raw_product.name}: {e}")
                    stats.products_failed += 1
                    stats.errors.append(f"Product {raw_product.external_id}: {str(e)}")

            # Update scrape run with final stats
            scrape_run.status = "completed" if not stats.errors else "partial"
            scrape_run.completed_at = datetime.utcnow()
            scrape_run.products_scraped = stats.total_products
            scrape_run.products_new = stats.products_created
            scrape_run.products_updated = stats.products_matched
            scrape_run.error_count = len(stats.errors)

            await self.db.commit()

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            scrape_run.status = "failed"
            scrape_run.error_count = 1
            await self.db.commit()
            stats.errors.append(str(e))

        logger.info(
            f"Pipeline complete for {distributor_slug}: "
            f"{stats.products_matched} matched, {stats.products_created} new, "
            f"{stats.products_queued} queued, {stats.products_failed} failed"
        )

        return stats

    async def _get_distributor(self, slug: str) -> Optional[Distributor]:
        """Get distributor by slug."""
        query = select(Distributor).where(Distributor.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _create_scrape_run(
        self,
        distributor: Distributor,
        result: ScrapeResult,
    ) -> ScrapeRun:
        """Create a scrape run record."""
        scrape_run = ScrapeRun(
            distributor_id=distributor.id,
            scraper_name=result.source,
            source_type="distributor",
            status="running",
            started_at=result.started_at,
            products_found=result.products_count,
            run_metadata={
                "categories_scraped": result.metadata.get("categories_scraped", 0),
            },
        )

        self.db.add(scrape_run)
        await self.db.flush()

        return scrape_run

    async def _process_product(
        self,
        raw_product: RawProduct,
        distributor: Distributor,
        scrape_run: ScrapeRun,
        stats: PipelineStats,
    ) -> None:
        """
        Process a single raw product.

        1. Store raw data
        2. Match to existing product
        3. Create price/inventory history
        """
        # Store raw data
        raw_data_record = RawProductData(
            scrape_run_id=scrape_run.id,
            source=distributor.slug,
            external_id=raw_product.external_id,
            raw_data=raw_product.raw_data or {},
            processed=False,
        )
        self.db.add(raw_data_record)
        await self.db.flush()

        # Match product
        match_result = await self.matcher.match(
            raw_product=raw_product,
            source=distributor.slug,
            create_if_missing=True,
        )

        if not match_result.matched:
            stats.products_failed += 1
            return

        # Update stats
        if match_result.is_new:
            stats.products_created += 1
        else:
            stats.products_matched += 1

        # Mark raw data as processed
        raw_data_record.processed = True
        raw_data_record.matched_product_id = match_result.product_id

        # Queue for review if low confidence
        if (
            not match_result.is_new
            and match_result.match_type == "fuzzy"
            and match_result.confidence < self.AUTO_MATCH_THRESHOLD
        ):
            await self._queue_for_review(
                raw_data_record=raw_data_record,
                match_result=match_result,
            )
            stats.products_queued += 1

        # Create price history
        if raw_product.price is not None:
            await self._create_price_history(
                product_id=match_result.product_id,
                distributor_id=distributor.id,
                price=raw_product.price,
                price_type=raw_product.price_type,
            )
            stats.price_records += 1

        # Create inventory history
        if raw_product.inventory is not None or raw_product.in_stock is not None:
            await self._create_inventory_history(
                product_id=match_result.product_id,
                distributor_id=distributor.id,
                quantity=raw_product.inventory,
                in_stock=raw_product.in_stock,
                available_states=raw_product.available_states,
            )
            stats.inventory_records += 1

    async def _create_price_history(
        self,
        product_id: UUID,
        distributor_id: int,
        price: float,
        price_type: str,
    ) -> None:
        """Create a price history record."""
        price_record = PriceHistory(
            product_id=product_id,
            distributor_id=distributor_id,
            price=price,
            price_type=price_type,
            currency="USD",
        )
        self.db.add(price_record)

    async def _create_inventory_history(
        self,
        product_id: UUID,
        distributor_id: int,
        quantity: Optional[int],
        in_stock: bool,
        available_states: Optional[list[str]],
    ) -> None:
        """Create an inventory history record."""
        inventory_record = InventoryHistory(
            product_id=product_id,
            distributor_id=distributor_id,
            quantity=quantity,
            in_stock=in_stock if in_stock is not None else True,
            available_states=available_states,
        )
        self.db.add(inventory_record)

    async def _queue_for_review(
        self,
        raw_data_record: RawProductData,
        match_result: MatchResult,
    ) -> None:
        """Queue a low-confidence match for manual review."""
        queue_item = MatchQueue(
            raw_data_id=raw_data_record.id,
            candidate_product_id=match_result.product_id,
            confidence=match_result.confidence,
            status="pending",
        )
        self.db.add(queue_item)
        logger.debug(
            f"Queued for review: {raw_data_record.external_id} "
            f"-> {match_result.product_id} ({match_result.confidence:.2f})"
        )

    async def process_raw_products(
        self,
        products: list[RawProduct],
        distributor_slug: str,
    ) -> PipelineStats:
        """
        Process a list of raw products directly (without ScrapeResult).

        Convenience method for processing products outside of a full scrape.

        Args:
            products: List of RawProduct objects
            distributor_slug: Distributor slug

        Returns:
            PipelineStats
        """
        # Create a synthetic ScrapeResult
        result = ScrapeResult(
            success=True,
            source=distributor_slug,
            products=products,
            products_count=len(products),
            errors=[],
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        return await self.process_scrape_result(result, distributor_slug)
