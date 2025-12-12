"""
ABVTrends - Enhanced Trend Scorer Service

Calculates trend scores incorporating distributor data:
- Retail Score: Distributor presence and availability
- Price Score: Pricing patterns and stability
- Inventory Score: Stock levels and velocity

Phase 4 enhancement to the trend scoring system.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.distributor import (
    CurrentTrendScore,
    Distributor,
    InventoryHistory,
    PriceHistory,
    ProductAlias,
)
from app.models.product import Product
from app.models.trend_score import TrendScore

logger = logging.getLogger(__name__)


@dataclass
class DistributorScores:
    """Scores derived from distributor data."""

    retail_score: float = 50.0
    price_score: float = 50.0
    inventory_score: float = 50.0


@dataclass
class EnhancedScores:
    """Full component scores including distributor signals."""

    media: float = 50.0
    social: float = 50.0
    retail: float = 50.0
    price: float = 50.0
    inventory: float = 50.0
    search: float = 50.0
    momentum_24h: float = 0.0
    momentum_7d: float = 0.0

    @property
    def composite(self) -> float:
        """Calculate weighted composite score."""
        weights = {
            "media": 0.25,
            "retail": 0.25,
            "price": 0.15,
            "inventory": 0.20,
            "search": 0.15,
        }
        # Social is absorbed into media for now
        return (
            self.media * weights["media"]
            + self.retail * weights["retail"]
            + self.price * weights["price"]
            + self.inventory * weights["inventory"]
            + self.search * weights["search"]
        )


class TrendScorer:
    """
    Enhanced trend scorer that incorporates distributor data.

    Scoring Components (updated weights):
    - Media Score (25%): Article mentions, awards, sentiment
    - Retail Score (25%): Distributor presence, state availability
    - Price Score (15%): Price stability, discounts, movement
    - Inventory Score (20%): Stock levels, velocity, availability
    - Search Score (15%): Search trends (placeholder)

    New Features:
    - Momentum calculation (24h and 7d change)
    - Tier assignment (viral, trending, emerging, stable, declining)
    """

    # Thresholds for tier assignment
    TIER_THRESHOLDS = {
        "viral": 85,
        "trending": 70,
        "emerging": 50,
        "stable": 30,
    }

    def __init__(self, db: AsyncSession):
        """Initialize the trend scorer."""
        self.db = db

    async def calculate_product_score(
        self,
        product_id: UUID,
        save: bool = True,
    ) -> EnhancedScores:
        """
        Calculate enhanced trend score for a product.

        Args:
            product_id: Product UUID
            save: Whether to save to CurrentTrendScore

        Returns:
            EnhancedScores with all components
        """
        scores = EnhancedScores()

        # Calculate distributor-based scores
        distributor_scores = await self._calculate_distributor_scores(product_id)
        scores.retail = distributor_scores.retail_score
        scores.price = distributor_scores.price_score
        scores.inventory = distributor_scores.inventory_score

        # Calculate momentum (score change over time)
        momentum = await self._calculate_momentum(product_id)
        scores.momentum_24h = momentum.get("24h", 0.0)
        scores.momentum_7d = momentum.get("7d", 0.0)

        # Media score - check for recent article mentions
        scores.media = await self._calculate_media_score(product_id)

        # Search score - placeholder for now
        scores.search = 50.0

        if save:
            await self._save_current_score(product_id, scores)

        return scores

    async def calculate_all_scores(self) -> int:
        """
        Calculate trend scores for all active products.

        Returns:
            Number of products scored
        """
        # Get all active products with distributor data
        result = await self.db.execute(
            select(Product.id)
            .join(ProductAlias, Product.id == ProductAlias.product_id)
            .where(Product.is_active == True)
            .distinct()
        )
        product_ids = [row[0] for row in result.all()]

        count = 0
        for product_id in product_ids:
            try:
                await self.calculate_product_score(product_id)
                count += 1
            except Exception as e:
                logger.error(f"Error scoring product {product_id}: {e}")

        logger.info(f"Calculated scores for {count} products")
        return count

    async def _calculate_distributor_scores(
        self,
        product_id: UUID,
    ) -> DistributorScores:
        """
        Calculate scores from distributor data.

        Args:
            product_id: Product UUID

        Returns:
            DistributorScores with retail, price, and inventory scores
        """
        scores = DistributorScores()

        # Get distributor presence (retail_score)
        scores.retail_score = await self._calc_retail_score(product_id)

        # Get price patterns (price_score)
        scores.price_score = await self._calc_price_score(product_id)

        # Get inventory signals (inventory_score)
        scores.inventory_score = await self._calc_inventory_score(product_id)

        return scores

    async def _calc_retail_score(self, product_id: UUID) -> float:
        """
        Calculate retail score based on distributor presence.

        Factors:
        - Number of distributors carrying the product
        - State availability breadth
        - Recent additions (new distributor = boost)
        """
        # Count distributors carrying this product
        alias_result = await self.db.execute(
            select(func.count(ProductAlias.id.distinct()))
            .where(ProductAlias.product_id == product_id)
        )
        distributor_count = alias_result.scalar() or 0

        # Base score: 30 points per distributor, max 90
        base_score = min(distributor_count * 30, 90)

        # Check for recent additions (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await self.db.execute(
            select(func.count(ProductAlias.id))
            .where(ProductAlias.product_id == product_id)
            .where(ProductAlias.created_at >= week_ago)
        )
        recent_additions = recent_result.scalar() or 0

        # Boost for new distributor listings
        new_listing_boost = min(recent_additions * 20, 40)

        # Check state availability from inventory
        state_result = await self.db.execute(
            select(InventoryHistory.available_states)
            .where(InventoryHistory.product_id == product_id)
            .order_by(InventoryHistory.recorded_at.desc())
            .limit(1)
        )
        state_row = state_result.first()
        states = state_row[0] if state_row and state_row[0] else []

        # Boost for wide state availability (1 point per state, max 20)
        state_boost = min(len(states), 20)

        total = base_score + new_listing_boost + state_boost
        return min(max(total, 0), 100)

    async def _calc_price_score(self, product_id: UUID) -> float:
        """
        Calculate price score based on pricing patterns.

        Factors:
        - Price stability (consistent = good)
        - Recent discounts (promotional activity = boost)
        - Price trend (stable or slight increase = healthy)
        """
        # Get price history for last 30 days
        month_ago = datetime.utcnow() - timedelta(days=30)
        result = await self.db.execute(
            select(PriceHistory.price, PriceHistory.recorded_at)
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.recorded_at >= month_ago)
            .order_by(PriceHistory.recorded_at.asc())
        )
        prices = [(float(row[0]), row[1]) for row in result.all()]

        if not prices:
            return 50.0  # Neutral if no price data

        if len(prices) == 1:
            return 60.0  # Slight boost for having a price

        # Calculate price volatility (standard deviation)
        price_values = [p[0] for p in prices]
        avg_price = sum(price_values) / len(price_values)
        variance = sum((p - avg_price) ** 2 for p in price_values) / len(price_values)
        std_dev = variance ** 0.5
        volatility_pct = (std_dev / avg_price) * 100 if avg_price > 0 else 0

        # Low volatility = stable pricing = good score
        # < 5% volatility = stable, > 20% = unstable
        if volatility_pct < 5:
            stability_score = 80
        elif volatility_pct < 10:
            stability_score = 70
        elif volatility_pct < 20:
            stability_score = 55
        else:
            stability_score = 40

        # Check for recent price drops (promotional activity)
        if len(prices) >= 2:
            recent_price = prices[-1][0]
            oldest_price = prices[0][0]
            price_change_pct = ((recent_price - oldest_price) / oldest_price) * 100

            if price_change_pct < -10:
                # Significant discount - promotional push
                promo_boost = 15
            elif price_change_pct < -5:
                promo_boost = 10
            elif price_change_pct > 10:
                # Price increase - could indicate scarcity/demand
                promo_boost = 5
            else:
                promo_boost = 0
        else:
            promo_boost = 0

        total = stability_score + promo_boost
        return min(max(total, 0), 100)

    async def _calc_inventory_score(self, product_id: UUID) -> float:
        """
        Calculate inventory score based on stock signals.

        Factors:
        - In-stock status
        - Stock velocity (how fast it moves)
        - Consistent availability
        """
        # Get inventory history for last 14 days
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        result = await self.db.execute(
            select(
                InventoryHistory.quantity,
                InventoryHistory.in_stock,
                InventoryHistory.recorded_at,
            )
            .where(InventoryHistory.product_id == product_id)
            .where(InventoryHistory.recorded_at >= two_weeks_ago)
            .order_by(InventoryHistory.recorded_at.asc())
        )
        inventory_records = list(result.all())

        if not inventory_records:
            return 50.0  # Neutral if no inventory data

        # Calculate in-stock percentage
        in_stock_count = sum(1 for r in inventory_records if r[1])
        in_stock_pct = (in_stock_count / len(inventory_records)) * 100

        # Base score from availability
        if in_stock_pct >= 95:
            availability_score = 70
        elif in_stock_pct >= 80:
            availability_score = 60
        elif in_stock_pct >= 50:
            availability_score = 45
        else:
            availability_score = 30

        # Calculate velocity (stock movement)
        quantities = [r[0] for r in inventory_records if r[0] is not None]
        if len(quantities) >= 2:
            # Positive velocity = stock is moving (selling)
            velocity = quantities[0] - quantities[-1]  # Decrease = sales
            if velocity > 0:
                # Stock decreased = selling well
                velocity_boost = min(velocity * 2, 30)
            else:
                velocity_boost = 0
        else:
            velocity_boost = 0

        total = availability_score + velocity_boost
        return min(max(total, 0), 100)

    async def _calculate_media_score(self, product_id: UUID) -> float:
        """
        Calculate media score from article mentions.

        Uses the ArticleMention table if available.
        """
        from app.models.distributor import ArticleMention

        # Count recent mentions (last 30 days)
        month_ago = datetime.utcnow() - timedelta(days=30)

        try:
            result = await self.db.execute(
                select(func.count(ArticleMention.id))
                .where(ArticleMention.product_id == product_id)
                .where(ArticleMention.created_at >= month_ago)
            )
            mention_count = result.scalar() or 0

            # Score: 10 points per mention, max 80 from mentions
            base_score = min(mention_count * 10, 80)

            # Check sentiment if available
            sentiment_result = await self.db.execute(
                select(func.avg(ArticleMention.sentiment))
                .where(ArticleMention.product_id == product_id)
                .where(ArticleMention.created_at >= month_ago)
            )
            avg_sentiment = sentiment_result.scalar()

            if avg_sentiment is not None:
                # Sentiment is -1 to 1, convert to 0-20 boost
                sentiment_boost = ((avg_sentiment + 1) / 2) * 20
            else:
                sentiment_boost = 10  # Neutral

            return min(base_score + sentiment_boost, 100)

        except Exception:
            # If no article mentions exist, return neutral
            return 50.0

    async def _calculate_momentum(
        self,
        product_id: UUID,
    ) -> dict[str, float]:
        """
        Calculate momentum (score change over time).

        Returns:
            Dict with '24h' and '7d' momentum values
        """
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Get current score
        current_result = await self.db.execute(
            select(CurrentTrendScore.score)
            .where(CurrentTrendScore.product_id == product_id)
        )
        current_row = current_result.first()
        current_score = float(current_row[0]) if current_row else None

        if current_score is None:
            return {"24h": 0.0, "7d": 0.0}

        # Get score from 24h ago
        score_24h_result = await self.db.execute(
            select(TrendScore.score)
            .where(TrendScore.product_id == product_id)
            .where(TrendScore.calculated_at <= day_ago)
            .order_by(TrendScore.calculated_at.desc())
            .limit(1)
        )
        score_24h_row = score_24h_result.first()
        score_24h = float(score_24h_row[0]) if score_24h_row else current_score

        # Get score from 7d ago
        score_7d_result = await self.db.execute(
            select(TrendScore.score)
            .where(TrendScore.product_id == product_id)
            .where(TrendScore.calculated_at <= week_ago)
            .order_by(TrendScore.calculated_at.desc())
            .limit(1)
        )
        score_7d_row = score_7d_result.first()
        score_7d = float(score_7d_row[0]) if score_7d_row else current_score

        return {
            "24h": current_score - score_24h,
            "7d": current_score - score_7d,
        }

    def _get_tier(self, score: float) -> str:
        """Get tier based on score."""
        if score >= self.TIER_THRESHOLDS["viral"]:
            return "viral"
        elif score >= self.TIER_THRESHOLDS["trending"]:
            return "trending"
        elif score >= self.TIER_THRESHOLDS["emerging"]:
            return "emerging"
        elif score >= self.TIER_THRESHOLDS["stable"]:
            return "stable"
        else:
            return "declining"

    async def _save_current_score(
        self,
        product_id: UUID,
        scores: EnhancedScores,
    ) -> CurrentTrendScore:
        """
        Save or update the current trend score.

        Args:
            product_id: Product UUID
            scores: Calculated scores

        Returns:
            CurrentTrendScore record
        """
        composite = scores.composite
        tier = self._get_tier(composite)

        # Check if record exists
        result = await self.db.execute(
            select(CurrentTrendScore)
            .where(CurrentTrendScore.product_id == product_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.score = int(composite)
            existing.tier = tier
            existing.momentum = int(scores.momentum_24h)
            existing.media_score = int(scores.media)
            existing.retail_score = int(scores.retail)
            existing.price_score = int(scores.price)
            existing.inventory_score = int(scores.inventory)
            existing.search_score = int(scores.search)
            existing.calculated_at = datetime.utcnow()
        else:
            # Create new record
            new_score = CurrentTrendScore(
                product_id=product_id,
                score=int(composite),
                tier=tier,
                momentum=int(scores.momentum_24h),
                media_score=int(scores.media),
                retail_score=int(scores.retail),
                price_score=int(scores.price),
                inventory_score=int(scores.inventory),
                search_score=int(scores.search),
                calculated_at=datetime.utcnow(),
            )
            self.db.add(new_score)

        await self.db.commit()

        # Return the record
        result = await self.db.execute(
            select(CurrentTrendScore)
            .where(CurrentTrendScore.product_id == product_id)
        )
        return result.scalar_one()

    async def get_top_trending(
        self,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> list[tuple[Product, CurrentTrendScore]]:
        """
        Get top trending products.

        Args:
            limit: Number of products to return
            category: Optional category filter

        Returns:
            List of (Product, CurrentTrendScore) tuples
        """
        query = (
            select(Product, CurrentTrendScore)
            .join(CurrentTrendScore, Product.id == CurrentTrendScore.product_id)
            .where(Product.is_active == True)
            .order_by(CurrentTrendScore.score.desc())
            .limit(limit)
        )

        if category:
            query = query.where(Product.category == category)

        result = await self.db.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def get_momentum_leaders(
        self,
        limit: int = 10,
        period: str = "24h",
    ) -> list[tuple[Product, CurrentTrendScore]]:
        """
        Get products with highest momentum (biggest score increases).

        Args:
            limit: Number of products to return
            period: '24h' or '7d'

        Returns:
            List of (Product, CurrentTrendScore) tuples
        """
        query = (
            select(Product, CurrentTrendScore)
            .join(CurrentTrendScore, Product.id == CurrentTrendScore.product_id)
            .where(Product.is_active == True)
            .where(CurrentTrendScore.momentum.isnot(None))
            .order_by(CurrentTrendScore.momentum.desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        return [(row[0], row[1]) for row in result.all()]
