"""
ABVTrends - Source Model

Represents data sources (websites) that are scraped for signals.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.signal import Signal


class SourceTier(str, enum.Enum):
    """Source tier classification."""

    TIER1 = "tier1"  # Media sites (VinePair, Liquor.com, Punch)
    TIER2 = "tier2"  # Retailers (TotalWine, ReserveBar, BevMo)
    TIER3 = "tier3"  # Social media (future)
    TIER4 = "tier4"  # Search/analytics (future)


class SourceType(str, enum.Enum):
    """Type of source."""

    MEDIA = "media"
    RETAILER = "retailer"
    SOCIAL = "social"
    SEARCH = "search"
    API = "api"


class Source(Base):
    """
    Source model representing a data source.

    Sources are websites or APIs that are scraped for signals.
    Each source has a corresponding scraper class.

    Attributes:
        id: Unique identifier (UUID)
        name: Human-readable name (e.g., "VinePair")
        slug: URL-friendly identifier (e.g., "vinepair")
        tier: Source tier classification
        source_type: Type of source (media, retailer, etc.)
        base_url: Base URL of the source
        scraper_class: Python class path for the scraper
        scrape_config: JSONB configuration for the scraper
        is_active: Whether scraping is enabled
        scrape_frequency_hours: How often to scrape
        last_scraped_at: Timestamp of last successful scrape
        last_error: Last error message if any
        total_signals: Count of signals from this source
        created_at: When source was added
        updated_at: Last update timestamp
    """

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    tier: Mapped[SourceTier] = mapped_column(
        Enum(SourceTier),
        nullable=False,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType),
        nullable=False,
        index=True,
    )
    base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    scraper_class: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    scrape_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    scrape_frequency_hours: Mapped[int] = mapped_column(
        Integer,
        default=6,
        nullable=False,
    )
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    total_signals: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    signals: Mapped[list["Signal"]] = relationship(
        "Signal",
        back_populates="source",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, name='{self.name}', tier={self.tier})>"

    @property
    def is_due_for_scrape(self) -> bool:
        """Check if this source is due for a scrape based on frequency."""
        if not self.is_active:
            return False
        if self.last_scraped_at is None:
            return True

        from datetime import timedelta

        next_scrape = self.last_scraped_at + timedelta(hours=self.scrape_frequency_hours)
        return datetime.now(self.last_scraped_at.tzinfo) >= next_scrape

    @property
    def is_media_source(self) -> bool:
        """Check if this is a media source."""
        return self.source_type == SourceType.MEDIA

    @property
    def is_retailer_source(self) -> bool:
        """Check if this is a retailer source."""
        return self.source_type == SourceType.RETAILER


class ModelVersion(Base):
    """
    ModelVersion model for tracking ML model versions.

    Stores metadata about trained models for versioning and rollback.

    Attributes:
        id: Unique identifier (UUID)
        version: Semantic version string (e.g., "1.0.0")
        model_type: Type of model (prophet, lstm, ensemble)
        file_path: Path to stored model file
        metrics: JSONB containing evaluation metrics
        is_active: Whether this is the active model version
        training_started_at: When training started
        training_completed_at: When training completed
        created_at: Database insertion timestamp
    """

    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    model_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    file_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    training_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    training_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ModelVersion(id={self.id}, version='{self.version}', "
            f"type={self.model_type}, active={self.is_active})>"
        )
