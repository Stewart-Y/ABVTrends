"""
ABVTrends - Signal Model

Represents raw signals captured from various sources (media mentions, price changes, etc.).
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.source import Source


class SignalType(str, enum.Enum):
    """Types of signals that can be captured."""

    # Media signals
    MEDIA_MENTION = "media_mention"
    ARTICLE_FEATURE = "article_feature"
    AWARD_MENTION = "award_mention"

    # Retailer signals
    NEW_SKU = "new_sku"
    PRICE_CHANGE = "price_change"
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    OUT_OF_STOCK = "out_of_stock"
    BACK_IN_STOCK = "back_in_stock"
    PROMOTION = "promotion"

    # Social signals (future)
    SOCIAL_MENTION = "social_mention"
    INFLUENCER_POST = "influencer_post"
    VIRAL_CONTENT = "viral_content"

    # Search signals (future)
    SEARCH_SPIKE = "search_spike"
    TRENDING_SEARCH = "trending_search"


class Signal(Base):
    """
    Signal model representing a single data point from a source.

    Signals are the raw building blocks for trend calculation.
    They capture specific events like media mentions, price changes, etc.

    Attributes:
        id: Unique identifier (UUID)
        product_id: Foreign key to associated product (nullable for unmatched signals)
        source_id: Foreign key to the source that generated this signal
        signal_type: Type of signal (media_mention, price_change, etc.)
        raw_data: JSONB containing the raw scraped data
        processed: Whether this signal has been processed into trend scores
        sentiment_score: Optional sentiment analysis score (-1.0 to 1.0)
        captured_at: When the original content was published/detected
        created_at: When this signal was stored in our system
    """

    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    signal_type: Mapped[SignalType] = mapped_column(
        Enum(SignalType),
        nullable=False,
        index=True,
    )
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
    )
    url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        back_populates="signals",
    )
    source: Mapped[Optional["Source"]] = relationship(
        "Source",
        back_populates="signals",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_signals_product_captured", "product_id", "captured_at"),
        Index("ix_signals_type_captured", "signal_type", "captured_at"),
        Index("ix_signals_unprocessed", "processed", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Signal(id={self.id}, type={self.signal_type}, "
            f"product_id={self.product_id})>"
        )

    @property
    def is_media_signal(self) -> bool:
        """Check if this is a media-related signal."""
        return self.signal_type in {
            SignalType.MEDIA_MENTION,
            SignalType.ARTICLE_FEATURE,
            SignalType.AWARD_MENTION,
        }

    @property
    def is_retailer_signal(self) -> bool:
        """Check if this is a retailer-related signal."""
        return self.signal_type in {
            SignalType.NEW_SKU,
            SignalType.PRICE_CHANGE,
            SignalType.PRICE_DROP,
            SignalType.PRICE_INCREASE,
            SignalType.OUT_OF_STOCK,
            SignalType.BACK_IN_STOCK,
            SignalType.PROMOTION,
        }

    @property
    def is_price_signal(self) -> bool:
        """Check if this is a price-related signal."""
        return self.signal_type in {
            SignalType.PRICE_CHANGE,
            SignalType.PRICE_DROP,
            SignalType.PRICE_INCREASE,
        }
