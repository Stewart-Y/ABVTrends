"""
ABVTrends - Trend Engine Service

Calculates trend scores for products based on multiple signal components.
Implements the weighted 6-component scoring system.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product
from app.models.signal import Signal, SignalType
from app.models.trend_score import TrendScore

logger = logging.getLogger(__name__)


@dataclass
class ComponentScores:
    """Container for individual component scores."""

    media: float = 0.0
    social: float = 0.0
    retailer: float = 0.0
    price: float = 0.0
    search: float = 0.0
    seasonal: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "media": self.media,
            "social": self.social,
            "retailer": self.retailer,
            "price": self.price,
            "search": self.search,
            "seasonal": self.seasonal,
        }


class TrendEngineError(Exception):
    """Exception raised during trend calculation."""

    pass


class TrendEngine:
    """
    Calculates trend scores for products.

    The Trend Score (0-100) is a weighted composite of 6 components:
    - Media Mentions (20%): Article count & sentiment from media sources
    - Social Velocity (20%): Rate of social media mentions (future)
    - Retailer Presence (15%): Availability across retailers
    - Price Movement (15%): Price changes and promotions
    - Search Interest (15%): Search volume trends (future)
    - Seasonal Alignment (15%): Holiday/season relevance

    Calculation formula:
    score = (media * 0.20 + social * 0.20 + retailer * 0.15 +
             price * 0.15 + search * 0.15 + seasonal * 0.15) * 100
    """

    # Time window for signal aggregation (days)
    SIGNAL_WINDOW_DAYS = 7

    # Normalization factors (adjust based on data)
    MEDIA_MAX_SIGNALS = 20  # Max expected media signals per week
    RETAILER_MAX_SIGNALS = 10  # Max expected retailer signals per week
    PRICE_BOOST_THRESHOLD = 0.10  # 10% price change threshold

    def __init__(self, db: AsyncSession):
        """
        Initialize the trend engine.

        Args:
            db: Async database session
        """
        self.db = db

        # Load weights from config
        self.weights = {
            "media": settings.weight_media_mentions,
            "social": settings.weight_social_velocity,
            "retailer": settings.weight_retailer_presence,
            "price": settings.weight_price_movement,
            "search": settings.weight_search_interest,
            "seasonal": settings.weight_seasonal_alignment,
        }

    async def calculate_score(
        self,
        product_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> TrendScore:
        """
        Calculate trend score for a single product.

        Args:
            product_id: Product UUID
            as_of: Point in time for calculation (default: now)

        Returns:
            TrendScore object with calculated values
        """
        as_of = as_of or datetime.utcnow()
        window_start = as_of - timedelta(days=self.SIGNAL_WINDOW_DAYS)

        # Get signals for this product within the window
        result = await self.db.execute(
            select(Signal)
            .where(Signal.product_id == product_id)
            .where(Signal.captured_at >= window_start)
            .where(Signal.captured_at <= as_of)
        )
        signals = list(result.scalars().all())

        # Calculate component scores
        components = await self._calculate_components(signals, as_of)

        # Calculate weighted composite score
        composite_score = self._calculate_composite(components)

        # Create TrendScore record
        trend_score = TrendScore(
            product_id=product_id,
            score=composite_score,
            media_score=components.media,
            social_score=components.social,
            retailer_score=components.retailer,
            price_score=components.price,
            search_score=components.search,
            seasonal_score=components.seasonal,
            signal_count=len(signals),
            calculated_at=as_of,
        )

        self.db.add(trend_score)
        await self.db.commit()
        await self.db.refresh(trend_score)

        logger.debug(
            f"Calculated score for product {product_id}: {composite_score:.1f} "
            f"(signals: {len(signals)})"
        )

        return trend_score

    async def calculate_all_scores(
        self,
        as_of: Optional[datetime] = None,
    ) -> int:
        """
        Calculate trend scores for all products with recent signals.

        Args:
            as_of: Point in time for calculation

        Returns:
            Number of scores calculated
        """
        as_of = as_of or datetime.utcnow()
        window_start = as_of - timedelta(days=self.SIGNAL_WINDOW_DAYS)

        # Get products with recent signals
        result = await self.db.execute(
            select(Signal.product_id)
            .where(Signal.product_id.isnot(None))
            .where(Signal.captured_at >= window_start)
            .distinct()
        )
        product_ids = [row[0] for row in result.all()]

        count = 0
        for product_id in product_ids:
            try:
                await self.calculate_score(product_id, as_of)
                count += 1
            except Exception as e:
                logger.error(f"Error calculating score for {product_id}: {e}")
                continue

        logger.info(f"Calculated scores for {count} products")
        return count

    async def _calculate_components(
        self,
        signals: list[Signal],
        as_of: datetime,
    ) -> ComponentScores:
        """
        Calculate individual component scores from signals.

        Args:
            signals: List of signals for the product
            as_of: Reference point in time

        Returns:
            ComponentScores with normalized values (0-100)
        """
        components = ComponentScores()

        # Group signals by type
        media_signals = [s for s in signals if s.is_media_signal]
        retailer_signals = [s for s in signals if s.is_retailer_signal]
        price_signals = [s for s in signals if s.is_price_signal]

        # Calculate media score
        components.media = self._calc_media_score(media_signals)

        # Calculate retailer score
        components.retailer = self._calc_retailer_score(retailer_signals)

        # Calculate price score
        components.price = self._calc_price_score(price_signals)

        # Calculate seasonal score
        components.seasonal = self._calc_seasonal_score(as_of)

        # Social and search scores are placeholders (future integrations)
        components.social = await self._calc_social_score(signals)
        components.search = await self._calc_search_score(signals)

        return components

    def _calc_media_score(self, signals: list[Signal]) -> float:
        """
        Calculate media component score.

        Based on:
        - Number of mentions
        - Sentiment scores (if available)
        - Source quality (feature vs mention)
        """
        if not signals:
            return 0.0

        # Base score from mention count
        mention_count = len(signals)
        base_score = min(mention_count / self.MEDIA_MAX_SIGNALS, 1.0) * 60

        # Boost for article features
        feature_count = sum(
            1 for s in signals if s.signal_type == SignalType.ARTICLE_FEATURE
        )
        feature_boost = min(feature_count * 10, 20)

        # Boost for awards
        award_count = sum(
            1 for s in signals if s.signal_type == SignalType.AWARD_MENTION
        )
        award_boost = min(award_count * 10, 20)

        # Sentiment adjustment
        sentiment_scores = [
            s.sentiment_score for s in signals
            if s.sentiment_score is not None
        ]
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            # Convert -1 to 1 range to 0 to 1
            sentiment_factor = (avg_sentiment + 1) / 2
            sentiment_boost = (sentiment_factor - 0.5) * 20
        else:
            sentiment_boost = 0

        total = base_score + feature_boost + award_boost + sentiment_boost
        return min(max(total, 0), 100)

    def _calc_retailer_score(self, signals: list[Signal]) -> float:
        """
        Calculate retailer component score.

        Based on:
        - Number of retailers carrying the product
        - New SKU additions
        - Stock status
        """
        if not signals:
            return 0.0

        # Count unique sources (retailers)
        unique_sources = len(set(s.source_id for s in signals if s.source_id))
        base_score = min(unique_sources / 3, 1.0) * 40  # Max 3 retailers expected

        # Boost for new SKUs
        new_sku_count = sum(
            1 for s in signals if s.signal_type == SignalType.NEW_SKU
        )
        new_sku_boost = min(new_sku_count * 15, 30)

        # Penalty for out-of-stock signals
        oos_count = sum(
            1 for s in signals if s.signal_type == SignalType.OUT_OF_STOCK
        )
        oos_penalty = min(oos_count * 10, 30)

        # Boost for back-in-stock (indicates demand)
        back_in_stock = sum(
            1 for s in signals if s.signal_type == SignalType.BACK_IN_STOCK
        )
        restock_boost = min(back_in_stock * 10, 20)

        total = base_score + new_sku_boost + restock_boost - oos_penalty
        return min(max(total, 0), 100)

    def _calc_price_score(self, signals: list[Signal]) -> float:
        """
        Calculate price component score.

        Higher score for:
        - Price drops (indicates promotional push)
        - Promotions
        - Price stability (not negative)
        """
        if not signals:
            return 50.0  # Neutral score if no price signals

        score = 50.0  # Start neutral

        for signal in signals:
            raw_data = signal.raw_data or {}

            if signal.signal_type == SignalType.PRICE_DROP:
                # Price drops indicate promotional activity
                discount_pct = raw_data.get("discount_percent", 0)
                if discount_pct > 20:
                    score += 20  # Significant promotion
                elif discount_pct > 10:
                    score += 10
                else:
                    score += 5

            elif signal.signal_type == SignalType.PRICE_INCREASE:
                # Price increases might indicate demand or scarcity
                score += 5

            elif signal.signal_type == SignalType.PROMOTION:
                score += 15

        return min(max(score, 0), 100)

    def _calc_seasonal_score(self, as_of: datetime) -> float:
        """
        Calculate seasonal alignment score.

        Boosts scores during relevant seasons/holidays.
        """
        month = as_of.month
        day = as_of.day

        # Base seasonal patterns
        seasonal_boosts = {
            # Winter holidays (high alcohol sales)
            12: 80,  # December
            1: 60,   # January (New Year)
            # Summer
            6: 70,   # June
            7: 75,   # July (July 4th)
            8: 65,   # August
            # Fall
            10: 60,  # October (Halloween)
            11: 75,  # November (Thanksgiving)
            # Spring
            3: 55,   # March (St. Patrick's)
            5: 60,   # May (Cinco de Mayo, Memorial Day)
        }

        base_score = seasonal_boosts.get(month, 50)

        # Specific holiday boosts
        if month == 12 and day >= 20:
            base_score = 90  # Christmas week
        elif month == 11 and day >= 20:
            base_score = 85  # Thanksgiving week
        elif month == 7 and day <= 7:
            base_score = 80  # July 4th week
        elif month == 2 and day >= 10 and day <= 14:
            base_score = 70  # Valentine's Day

        return base_score

    async def _calc_social_score(self, signals: list[Signal]) -> float:
        """
        Calculate social media score.

        Placeholder for future social media API integration.
        """
        # Future: Integrate with social media APIs
        # For now, use any social signals we have
        social_signals = [
            s for s in signals
            if s.signal_type in {
                SignalType.SOCIAL_MENTION,
                SignalType.INFLUENCER_POST,
                SignalType.VIRAL_CONTENT,
            }
        ]

        if not social_signals:
            return 50.0  # Neutral

        base_score = min(len(social_signals) * 10, 100)

        # Boost for viral content
        viral_count = sum(
            1 for s in social_signals
            if s.signal_type == SignalType.VIRAL_CONTENT
        )
        base_score += min(viral_count * 20, 40)

        return min(base_score, 100)

    async def _calc_search_score(self, signals: list[Signal]) -> float:
        """
        Calculate search interest score.

        Placeholder for future Google Trends API integration.
        """
        # Future: Integrate with Google Trends API
        search_signals = [
            s for s in signals
            if s.signal_type in {
                SignalType.SEARCH_SPIKE,
                SignalType.TRENDING_SEARCH,
            }
        ]

        if not search_signals:
            return 50.0  # Neutral

        return min(len(search_signals) * 25, 100)

    def _calculate_composite(self, components: ComponentScores) -> float:
        """
        Calculate weighted composite score.

        Args:
            components: Individual component scores

        Returns:
            Composite score (0-100)
        """
        composite = (
            components.media * self.weights["media"]
            + components.social * self.weights["social"]
            + components.retailer * self.weights["retailer"]
            + components.price * self.weights["price"]
            + components.search * self.weights["search"]
            + components.seasonal * self.weights["seasonal"]
        )

        return min(max(composite, 0), 100)

    async def get_trending_products(
        self,
        limit: int = 10,
        min_score: float = 50.0,
    ) -> list[tuple[Product, TrendScore]]:
        """
        Get top trending products.

        Args:
            limit: Maximum number of products to return
            min_score: Minimum score threshold

        Returns:
            List of (Product, TrendScore) tuples
        """
        # Get latest scores for each product
        subquery = (
            select(
                TrendScore.product_id,
                func.max(TrendScore.calculated_at).label("latest"),
            )
            .group_by(TrendScore.product_id)
            .subquery()
        )

        result = await self.db.execute(
            select(Product, TrendScore)
            .join(TrendScore, Product.id == TrendScore.product_id)
            .join(
                subquery,
                (TrendScore.product_id == subquery.c.product_id)
                & (TrendScore.calculated_at == subquery.c.latest),
            )
            .where(TrendScore.score >= min_score)
            .order_by(TrendScore.score.desc())
            .limit(limit)
        )

        return [(row[0], row[1]) for row in result.all()]

    async def get_score_history(
        self,
        product_id: UUID,
        days: int = 30,
    ) -> list[TrendScore]:
        """
        Get trend score history for a product.

        Args:
            product_id: Product UUID
            days: Number of days of history

        Returns:
            List of TrendScore objects
        """
        since = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(TrendScore)
            .where(TrendScore.product_id == product_id)
            .where(TrendScore.calculated_at >= since)
            .order_by(TrendScore.calculated_at.asc())
        )

        return list(result.scalars().all())
