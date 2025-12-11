"""
ABVTrends - Distributor Models

Models for distributor scraping and data management.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class Distributor(Base):
    """
    Distributor model representing a beverage distributor source.

    Attributes:
        id: Auto-incrementing ID
        name: Human-readable name
        slug: URL-friendly identifier
        website: Main website URL
        api_base_url: API endpoint base URL
        is_active: Whether scraping is enabled
        scraper_class: Python class name for scraper
        created_at: When added
        updated_at: Last update
    """

    __tablename__ = "distributors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scraper_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
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
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory",
        back_populates="distributor",
        lazy="dynamic",
    )
    inventory_history: Mapped[list["InventoryHistory"]] = relationship(
        "InventoryHistory",
        back_populates="distributor",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Distributor(id={self.id}, name='{self.name}', active={self.is_active})>"


class ProductAlias(Base):
    """
    Maps external product IDs to unified products.

    Allows matching products across different distributor systems.
    """

    __tablename__ = "product_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # 'libdib', 'sgws', etc.
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="aliases")

    __table_args__ = (
        Index("ix_product_aliases_source", "source", "external_id"),
    )

    def __repr__(self) -> str:
        return f"<ProductAlias(source='{self.source}', external_id='{self.external_id}')>"


class PriceHistory(Base):
    """
    Timeseries price data for products.
    """

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    distributor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("distributors.id"),
        nullable=True,
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_type: Mapped[str] = mapped_column(String(50), default="wholesale")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="price_history")
    distributor: Mapped[Optional["Distributor"]] = relationship("Distributor", back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_product", "product_id", "recorded_at"),
        Index("ix_price_history_recorded", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<PriceHistory(product_id={self.product_id}, price={self.price})>"


class InventoryHistory(Base):
    """
    Timeseries inventory data for products.
    """

    __tablename__ = "inventory_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    distributor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("distributors.id"),
        nullable=True,
    )
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    available_states: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="inventory_history")
    distributor: Mapped[Optional["Distributor"]] = relationship("Distributor", back_populates="inventory_history")

    __table_args__ = (
        Index("ix_inventory_history_product", "product_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<InventoryHistory(product_id={self.product_id}, qty={self.quantity})>"


class ScrapeRun(Base):
    """
    Audit log of scraper runs.
    """

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scraper_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # distributor, media
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running, success, failed, partial
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    products_scraped: Mapped[int] = mapped_column(Integer, default=0)
    products_new: Mapped[int] = mapped_column(Integer, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    run_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    errors: Mapped[list["ScrapeError"]] = relationship("ScrapeError", back_populates="scrape_run")
    raw_data: Mapped[list["RawProductData"]] = relationship("RawProductData", back_populates="scrape_run")

    __table_args__ = (
        Index("ix_scrape_runs_scraper", "scraper_name", "started_at"),
        Index("ix_scrape_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ScrapeRun(id={self.id}, scraper='{self.scraper_name}', status='{self.status}')>"


class ScrapeError(Base):
    """
    Error tracking for scraper runs.
    """

    __tablename__ = "scrape_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("scrape_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    scrape_run: Mapped[Optional["ScrapeRun"]] = relationship("ScrapeRun", back_populates="errors")

    __table_args__ = (
        Index("ix_scrape_errors_run", "scrape_run_id"),
    )

    def __repr__(self) -> str:
        return f"<ScrapeError(id={self.id}, type='{self.error_type}')>"


class RawProductData(Base):
    """
    Staging table for incoming scraped data.
    """

    __tablename__ = "raw_product_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("scrape_runs.id"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    scrape_run: Mapped[Optional["ScrapeRun"]] = relationship("ScrapeRun", back_populates="raw_data")
    matched_product: Mapped[Optional["Product"]] = relationship("Product")

    __table_args__ = (
        Index("ix_raw_data_source", "source", "external_id"),
    )

    def __repr__(self) -> str:
        return f"<RawProductData(id={self.id}, source='{self.source}')>"


class MatchQueue(Base):
    """
    Queue for manual review of low-confidence matches.
    """

    __tablename__ = "match_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_data_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("raw_product_data.id"),
        nullable=True,
    )
    candidate_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id"),
        nullable=True,
    )
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, rejected, new_product
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_match_queue_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<MatchQueue(id={self.id}, status='{self.status}')>"


class Article(Base):
    """
    Media articles scraped from sources.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI-generated
    sentiment: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    mentions: Mapped[list["ArticleMention"]] = relationship("ArticleMention", back_populates="article")

    __table_args__ = (
        Index("ix_articles_source", "source"),
        Index("ix_articles_published", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, source='{self.source}', title='{self.title[:50]}...')>"


class ArticleMention(Base):
    """
    Product mentions within articles.
    """

    __tablename__ = "article_mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    mention_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # featured, mentioned, reviewed
    sentiment: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    article: Mapped["Article"] = relationship("Article", back_populates="mentions")
    product: Mapped["Product"] = relationship("Product", back_populates="article_mentions")

    __table_args__ = (
        Index("ix_mentions_product", "product_id"),
        Index("ix_mentions_article", "article_id"),
    )

    def __repr__(self) -> str:
        return f"<ArticleMention(article_id={self.article_id}, product_id={self.product_id})>"


class CurrentTrendScore(Base):
    """
    Current (latest) trend scores for fast lookup.
    """

    __tablename__ = "current_trend_scores"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    momentum: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    media_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retail_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inventory_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    search_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calculated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="current_score")

    __table_args__ = (
        Index("ix_current_scores_score", "score"),
        Index("ix_current_scores_tier", "tier"),
    )

    def __repr__(self) -> str:
        return f"<CurrentTrendScore(product_id={self.product_id}, score={self.score}, tier='{self.tier}')>"
