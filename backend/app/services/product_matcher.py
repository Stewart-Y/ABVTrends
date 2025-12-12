"""
ABVTrends - Product Matcher Service

Matches raw product data from distributors to existing products in the database.
Uses fuzzy matching with UPC as primary identifier, then name+brand+volume.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.distributor import ProductAlias
from app.models.product import Product, ProductCategory, ProductSubcategory
from app.scrapers.distributors.base import RawProduct

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a product matching attempt."""

    matched: bool
    product_id: Optional[UUID] = None
    product: Optional[Product] = None
    confidence: float = 0.0
    match_type: str = "none"  # upc, alias, fuzzy, new
    is_new: bool = False


class ProductMatcher:
    """
    Matches raw distributor products to existing products.

    Matching strategy (in order of priority):
    1. Exact UPC match
    2. Existing alias match (source + external_id)
    3. Fuzzy match on brand + name + volume
    4. Create new product if no match found

    Configuration:
    - HIGH_CONFIDENCE_THRESHOLD: Auto-match and store alias (85+)
    - LOW_CONFIDENCE_THRESHOLD: Queue for manual review (60-84)
    - Below 60: Create as new product
    """

    HIGH_CONFIDENCE_THRESHOLD = 85
    LOW_CONFIDENCE_THRESHOLD = 60

    def __init__(self, db: AsyncSession):
        """
        Initialize the product matcher.

        Args:
            db: Async database session
        """
        self.db = db
        self._product_cache: dict[str, Product] = {}

    async def match(
        self,
        raw_product: RawProduct,
        source: str,
        create_if_missing: bool = True,
    ) -> MatchResult:
        """
        Match a raw product to an existing product or create a new one.

        Args:
            raw_product: Raw product data from scraper
            source: Source identifier (e.g., 'libdib')
            create_if_missing: Whether to create new product if no match

        Returns:
            MatchResult with matched product and confidence
        """
        # 1. Try UPC match first (most reliable)
        if raw_product.upc:
            result = await self._match_by_upc(raw_product.upc)
            if result.matched:
                await self._ensure_alias(
                    result.product_id, source, raw_product, result.confidence
                )
                return result

        # 2. Try existing alias match
        result = await self._match_by_alias(source, raw_product.external_id)
        if result.matched:
            return result

        # 3. Try fuzzy matching
        result = await self._match_fuzzy(raw_product)
        if result.matched and result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            await self._ensure_alias(
                result.product_id, source, raw_product, result.confidence
            )
            return result

        # 4. Create new product if no match found
        if create_if_missing:
            product = await self._create_product(raw_product)
            await self._ensure_alias(product.id, source, raw_product, 1.0)
            return MatchResult(
                matched=True,
                product_id=product.id,
                product=product,
                confidence=1.0,
                match_type="new",
                is_new=True,
            )

        return MatchResult(matched=False)

    async def _match_by_upc(self, upc: str) -> MatchResult:
        """Match product by UPC code."""
        # Normalize UPC (remove leading zeros, spaces)
        normalized_upc = upc.strip().lstrip("0")

        query = select(Product).where(
            or_(
                Product.upc == upc,
                Product.upc == normalized_upc,
            )
        )
        result = await self.db.execute(query)
        product = result.scalar_one_or_none()

        if product:
            logger.debug(f"UPC match found: {upc} -> {product.name}")
            return MatchResult(
                matched=True,
                product_id=product.id,
                product=product,
                confidence=1.0,
                match_type="upc",
            )

        return MatchResult(matched=False)

    async def _match_by_alias(self, source: str, external_id: str) -> MatchResult:
        """Match product by existing alias."""
        query = (
            select(ProductAlias)
            .where(ProductAlias.source == source)
            .where(ProductAlias.external_id == external_id)
        )
        result = await self.db.execute(query)
        alias = result.scalar_one_or_none()

        if alias:
            # Load the product
            product = await self.db.get(Product, alias.product_id)
            if product:
                logger.debug(
                    f"Alias match found: {source}/{external_id} -> {product.name}"
                )
                return MatchResult(
                    matched=True,
                    product_id=product.id,
                    product=product,
                    confidence=float(alias.confidence),
                    match_type="alias",
                )

        return MatchResult(matched=False)

    async def _match_fuzzy(self, raw_product: RawProduct) -> MatchResult:
        """
        Match product using fuzzy string matching.

        Considers: brand, name, volume
        """
        # Build search query - get candidate products
        query = select(Product).where(Product.is_active == True)

        # Filter by category if we have one
        if raw_product.category:
            category = self._map_category(raw_product.category)
            if category:
                query = query.where(Product.category == category)

        # Limit candidates for performance
        query = query.limit(1000)

        result = await self.db.execute(query)
        candidates = result.scalars().all()

        if not candidates:
            return MatchResult(matched=False)

        best_match: Optional[Product] = None
        best_score = 0.0

        # Normalize the raw product for comparison
        raw_name = self._normalize_name(raw_product.name)
        raw_brand = self._normalize_name(raw_product.brand or "")
        raw_volume = raw_product.volume_ml

        for candidate in candidates:
            score = self._calculate_similarity(
                raw_name,
                raw_brand,
                raw_volume,
                candidate,
            )

            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= self.LOW_CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Fuzzy match: '{raw_product.name}' -> '{best_match.name}' "
                f"(score: {best_score:.1f})"
            )
            return MatchResult(
                matched=True,
                product_id=best_match.id,
                product=best_match,
                confidence=best_score / 100.0,
                match_type="fuzzy",
            )

        return MatchResult(matched=False)

    def _calculate_similarity(
        self,
        raw_name: str,
        raw_brand: str,
        raw_volume: Optional[int],
        candidate: Product,
    ) -> float:
        """
        Calculate similarity score between raw product and candidate.

        Returns score 0-100.
        """
        candidate_name = self._normalize_name(candidate.name)
        candidate_brand = self._normalize_name(candidate.brand or "")

        # Name similarity (60% weight)
        name_score = fuzz.token_sort_ratio(raw_name, candidate_name)

        # Brand similarity (25% weight)
        brand_score = 100.0
        if raw_brand and candidate_brand:
            brand_score = fuzz.token_sort_ratio(raw_brand, candidate_brand)
        elif raw_brand or candidate_brand:
            # One has brand, other doesn't - slight penalty
            brand_score = 70.0

        # Volume match (15% weight)
        volume_score = 100.0
        if raw_volume and candidate.volume_ml:
            if raw_volume == candidate.volume_ml:
                volume_score = 100.0
            else:
                # Penalize volume mismatch
                diff_pct = abs(raw_volume - candidate.volume_ml) / max(
                    raw_volume, candidate.volume_ml
                )
                volume_score = max(0, 100 - (diff_pct * 200))
        elif raw_volume or candidate.volume_ml:
            # One has volume, other doesn't
            volume_score = 50.0

        # Weighted average
        total_score = (name_score * 0.60) + (brand_score * 0.25) + (volume_score * 0.15)

        return total_score

    def _normalize_name(self, name: str) -> str:
        """Normalize product name for comparison."""
        if not name:
            return ""

        # Lowercase
        name = name.lower()

        # Remove common suffixes/descriptors
        remove_patterns = [
            r"\b\d+\s*(ml|l|oz|proof|%|abv)\b",
            r"\bcase\s*of\s*\d+\b",
            r"\(\d+\s*pack\)",
            r"\b(limited|special|reserve|edition|batch)\b",
        ]

        for pattern in remove_patterns:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)

        # Remove extra whitespace
        name = re.sub(r"\s+", " ", name).strip()

        return name

    def _map_category(self, category_str: str) -> Optional[ProductCategory]:
        """Map raw category string to ProductCategory enum."""
        category_map = {
            "spirits": ProductCategory.SPIRITS,
            "wine": ProductCategory.WINE,
            "rtd": ProductCategory.RTD,
            "beer": ProductCategory.BEER,
        }
        return category_map.get(category_str.lower())

    def _map_subcategory(self, subcategory_str: str) -> Optional[ProductSubcategory]:
        """Map raw subcategory string to ProductSubcategory enum."""
        subcategory_map = {
            "vodka": ProductSubcategory.VODKA,
            "whiskey": ProductSubcategory.WHISKEY,
            "bourbon": ProductSubcategory.BOURBON,
            "scotch": ProductSubcategory.SCOTCH,
            "gin": ProductSubcategory.GIN,
            "rum": ProductSubcategory.RUM,
            "tequila": ProductSubcategory.TEQUILA,
            "mezcal": ProductSubcategory.MEZCAL,
            "brandy": ProductSubcategory.BRANDY,
            "cognac": ProductSubcategory.COGNAC,
            "liqueur": ProductSubcategory.LIQUEUR,
            "red": ProductSubcategory.RED_WINE,
            "red_wine": ProductSubcategory.RED_WINE,
            "white": ProductSubcategory.WHITE_WINE,
            "white_wine": ProductSubcategory.WHITE_WINE,
            "rose": ProductSubcategory.ROSE,
            "sparkling": ProductSubcategory.SPARKLING,
            "hard_seltzer": ProductSubcategory.HARD_SELTZER,
            "canned_cocktail": ProductSubcategory.CANNED_COCKTAIL,
        }
        return subcategory_map.get(subcategory_str.lower())

    async def _create_product(self, raw_product: RawProduct) -> Product:
        """Create a new product from raw data."""
        category = self._map_category(raw_product.category or "spirits")
        subcategory = self._map_subcategory(raw_product.subcategory or "other")

        product = Product(
            name=raw_product.name,
            brand=raw_product.brand,
            category=category or ProductCategory.SPIRITS,
            subcategory=subcategory,
            description=raw_product.description,
            image_url=raw_product.image_url,
            volume_ml=raw_product.volume_ml,
            abv=raw_product.abv,
            upc=raw_product.upc,
            is_active=True,
        )

        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)

        logger.info(f"Created new product: {product.name} (ID: {product.id})")

        return product

    async def _ensure_alias(
        self,
        product_id: UUID,
        source: str,
        raw_product: RawProduct,
        confidence: float,
    ) -> None:
        """Ensure a product alias exists for this source/external_id."""
        # Check if alias already exists
        query = (
            select(ProductAlias)
            .where(ProductAlias.source == source)
            .where(ProductAlias.external_id == raw_product.external_id)
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if not existing:
            alias = ProductAlias(
                product_id=product_id,
                source=source,
                external_id=raw_product.external_id,
                external_name=raw_product.name[:500] if raw_product.name else None,
                external_url=raw_product.url[:500] if raw_product.url else None,
                confidence=confidence,
            )
            self.db.add(alias)
            logger.debug(
                f"Created alias: {source}/{raw_product.external_id} -> {product_id}"
            )
