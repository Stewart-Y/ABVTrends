"""
ABVTrends - Signal Processor Service

Processes raw scraped items into signals and matches them to products.
Handles deduplication, entity matching, and signal enrichment.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductCategory
from app.models.signal import Signal, SignalType
from app.models.source import Source
from app.scrapers.utils import ScrapedItem

logger = logging.getLogger(__name__)


class SignalProcessorError(Exception):
    """Exception raised during signal processing."""

    pass


class SignalProcessor:
    """
    Processes scraped items into database signals.

    Responsibilities:
    - Deduplicate signals (avoid storing duplicates)
    - Match signals to existing products (fuzzy matching)
    - Create new products when appropriate
    - Enrich signals with metadata
    - Handle batch processing efficiently
    """

    # Minimum similarity score for product matching (0-100)
    MATCH_THRESHOLD = 85

    # Minimum signals before auto-creating a product
    MIN_SIGNALS_FOR_AUTO_CREATE = 3

    def __init__(self, db: AsyncSession):
        """
        Initialize the signal processor.

        Args:
            db: Async database session
        """
        self.db = db
        self._product_cache: dict[str, Product] = {}
        self._source_cache: dict[str, Source] = {}

    async def process_scraped_items(
        self,
        items: list[ScrapedItem],
        source_name: str,
    ) -> tuple[int, int, int]:
        """
        Process a batch of scraped items into signals.

        Args:
            items: List of ScrapedItem objects from a scraper
            source_name: Name of the source (e.g., 'vinepair')

        Returns:
            Tuple of (created_count, duplicate_count, matched_count)
        """
        created = 0
        duplicates = 0
        matched = 0

        source = await self._get_or_create_source(source_name)

        for item in items:
            try:
                # Check for duplicate
                is_duplicate = await self._is_duplicate_signal(item, source.id)
                if is_duplicate:
                    duplicates += 1
                    continue

                # Try to match to existing product
                product = await self._match_product(item)
                if product:
                    matched += 1

                # Create the signal
                signal = Signal(
                    product_id=product.id if product else None,
                    source_id=source.id,
                    signal_type=item.signal_type,
                    raw_data=item.raw_data,
                    url=item.url,
                    title=item.title,
                    captured_at=item.captured_at,
                    processed=False,
                )

                self.db.add(signal)
                created += 1

            except Exception as e:
                logger.error(f"Error processing item '{item.title}': {e}")
                continue

        # Commit all signals
        await self.db.commit()

        # Update source statistics
        source.last_scraped_at = datetime.utcnow()
        source.total_signals += created
        await self.db.commit()

        logger.info(
            f"Processed {len(items)} items from {source_name}: "
            f"{created} created, {duplicates} duplicates, {matched} matched"
        )

        return created, duplicates, matched

    async def _is_duplicate_signal(
        self,
        item: ScrapedItem,
        source_id: UUID,
    ) -> bool:
        """
        Check if a signal already exists.

        Uses URL as primary deduplication key.
        Falls back to title + date comparison.
        """
        # Check by URL first (most reliable)
        if item.url:
            result = await self.db.execute(
                select(Signal.id)
                .where(Signal.url == item.url)
                .where(Signal.source_id == source_id)
                .limit(1)
            )
            if result.scalar_one_or_none():
                return True

        # Check by title + similar date (within 24 hours)
        time_window = timedelta(hours=24)
        result = await self.db.execute(
            select(Signal.id)
            .where(Signal.title == item.title)
            .where(Signal.source_id == source_id)
            .where(Signal.captured_at >= item.captured_at - time_window)
            .where(Signal.captured_at <= item.captured_at + time_window)
            .limit(1)
        )

        return result.scalar_one_or_none() is not None

    async def _match_product(self, item: ScrapedItem) -> Optional[Product]:
        """
        Try to match a scraped item to an existing product.

        Uses fuzzy string matching on product names.
        """
        # Use product hint if available
        search_term = item.product_hint or item.title

        # Clean the search term
        search_term = self._clean_product_name(search_term)

        if not search_term or len(search_term) < 3:
            return None

        # Check cache first
        cache_key = search_term.lower()
        if cache_key in self._product_cache:
            return self._product_cache[cache_key]

        # Query products that might match
        result = await self.db.execute(
            select(Product).limit(500)  # Get recent products for matching
        )
        products = result.scalars().all()

        best_match: Optional[Product] = None
        best_score = 0

        for product in products:
            # Calculate similarity score
            score = fuzz.token_sort_ratio(
                search_term.lower(),
                product.name.lower(),
            )

            if score > best_score and score >= self.MATCH_THRESHOLD:
                best_score = score
                best_match = product

        if best_match:
            self._product_cache[cache_key] = best_match
            logger.debug(
                f"Matched '{search_term}' to product '{best_match.name}' "
                f"(score: {best_score})"
            )

        return best_match

    def _clean_product_name(self, name: str) -> str:
        """
        Clean product name for better matching.

        Removes common noise words and normalizes text.
        """
        # Remove size specifications
        name = re.sub(r"\d+\s*(?:ml|L|liter|oz)\b", "", name, flags=re.IGNORECASE)

        # Remove common words that don't help matching
        noise_words = [
            "the", "a", "an", "and", "or", "of", "with", "from",
            "limited", "edition", "special", "release", "new",
        ]

        words = name.split()
        cleaned_words = [w for w in words if w.lower() not in noise_words]

        return " ".join(cleaned_words).strip()

    async def _get_or_create_source(self, source_name: str) -> Source:
        """Get or create a source record."""
        if source_name in self._source_cache:
            return self._source_cache[source_name]

        result = await self.db.execute(
            select(Source).where(Source.slug == source_name)
        )
        source = result.scalar_one_or_none()

        if not source:
            # Determine source type and tier from name
            from app.models.source import SourceTier, SourceType

            is_tier1 = source_name in ["vinepair", "liquor_com", "punch"]

            source = Source(
                name=source_name.replace("_", " ").title(),
                slug=source_name,
                tier=SourceTier.TIER1 if is_tier1 else SourceTier.TIER2,
                source_type=SourceType.MEDIA if is_tier1 else SourceType.RETAILER,
                base_url=self._get_base_url(source_name),
                scraper_class=f"app.scrapers.{'tier1' if is_tier1 else 'tier2'}.{source_name}",
            )
            self.db.add(source)
            await self.db.commit()
            await self.db.refresh(source)

        self._source_cache[source_name] = source
        return source

    def _get_base_url(self, source_name: str) -> str:
        """Get base URL for a source."""
        urls = {
            "vinepair": "https://vinepair.com",
            "liquor_com": "https://www.liquor.com",
            "punch": "https://punchdrink.com",
            "totalwine": "https://www.totalwine.com",
            "reservebar": "https://www.reservebar.com",
            "bevmo": "https://www.bevmo.com",
        }
        return urls.get(source_name, "")

    async def process_unmatched_signals(self) -> int:
        """
        Process signals that don't have a product match.

        Creates new products for signals that appear frequently enough.

        Returns:
            Number of new products created
        """
        # Find unmatched signals grouped by product hint
        result = await self.db.execute(
            select(Signal)
            .where(Signal.product_id.is_(None))
            .where(Signal.processed == False)  # noqa: E712
            .order_by(Signal.captured_at.desc())
            .limit(1000)
        )
        unmatched_signals = result.scalars().all()

        # Group by cleaned title/hint
        signal_groups: dict[str, list[Signal]] = {}

        for signal in unmatched_signals:
            key = self._clean_product_name(signal.title or "").lower()
            if key and len(key) > 3:
                if key not in signal_groups:
                    signal_groups[key] = []
                signal_groups[key].append(signal)

        # Create products for groups with enough signals
        created_count = 0

        for name_key, signals in signal_groups.items():
            if len(signals) >= self.MIN_SIGNALS_FOR_AUTO_CREATE:
                # Use the most common title as the product name
                titles = [s.title for s in signals if s.title]
                product_name = max(set(titles), key=titles.count) if titles else name_key

                # Determine category from signal types
                category = self._infer_category(signals)

                # Create the product
                product = Product(
                    name=product_name,
                    category=category,
                )
                self.db.add(product)
                await self.db.flush()

                # Update signals with the new product
                for signal in signals:
                    signal.product_id = product.id
                    signal.processed = True

                created_count += 1
                logger.info(f"Auto-created product: {product_name}")

        await self.db.commit()
        return created_count

    def _infer_category(self, signals: list[Signal]) -> ProductCategory:
        """Infer product category from signal data."""
        # Check raw data for category hints
        category_keywords = {
            ProductCategory.SPIRITS: [
                "whiskey", "bourbon", "scotch", "vodka", "gin",
                "rum", "tequila", "mezcal", "brandy", "cognac",
            ],
            ProductCategory.WINE: [
                "wine", "cabernet", "chardonnay", "pinot", "merlot",
                "champagne", "prosecco", "rose", "riesling",
            ],
            ProductCategory.RTD: [
                "seltzer", "canned", "ready to drink", "rtd",
                "cocktail can", "hard seltzer",
            ],
            ProductCategory.BEER: [
                "beer", "ipa", "lager", "stout", "ale", "porter",
            ],
        }

        # Collect all text from signals
        all_text = " ".join([
            (s.title or "") + " " + str(s.raw_data)
            for s in signals
        ]).lower()

        # Count keyword matches
        scores: dict[ProductCategory, int] = {}

        for category, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in all_text)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)

        # Default to spirits
        return ProductCategory.SPIRITS

    async def mark_signals_processed(
        self,
        signal_ids: list[UUID],
    ) -> int:
        """
        Mark signals as processed.

        Args:
            signal_ids: List of signal IDs to mark

        Returns:
            Number of signals updated
        """
        result = await self.db.execute(
            select(Signal).where(Signal.id.in_(signal_ids))
        )
        signals = result.scalars().all()

        for signal in signals:
            signal.processed = True

        await self.db.commit()
        return len(signals)

    async def get_unprocessed_signals(
        self,
        limit: int = 100,
        signal_type: Optional[SignalType] = None,
    ) -> list[Signal]:
        """
        Get unprocessed signals for trend calculation.

        Args:
            limit: Maximum number of signals to return
            signal_type: Optional filter by signal type

        Returns:
            List of Signal objects
        """
        query = (
            select(Signal)
            .where(Signal.processed == False)  # noqa: E712
            .where(Signal.product_id.isnot(None))  # Only matched signals
            .order_by(Signal.captured_at.desc())
            .limit(limit)
        )

        if signal_type:
            query = query.where(Signal.signal_type == signal_type)

        result = await self.db.execute(query)
        return list(result.scalars().all())
