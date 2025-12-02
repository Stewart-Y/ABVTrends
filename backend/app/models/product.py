"""
ABVTrends - Product Model

Represents alcohol products (spirits, wines, RTDs) tracked by the platform.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.signal import Signal
    from app.models.trend_score import TrendScore


class ProductCategory(str, enum.Enum):
    """Product category enumeration."""

    SPIRITS = "spirits"
    WINE = "wine"
    RTD = "rtd"  # Ready-to-drink
    BEER = "beer"


class ProductSubcategory(str, enum.Enum):
    """Product subcategory enumeration."""

    # Spirits
    WHISKEY = "whiskey"
    BOURBON = "bourbon"
    SCOTCH = "scotch"
    VODKA = "vodka"
    GIN = "gin"
    RUM = "rum"
    TEQUILA = "tequila"
    MEZCAL = "mezcal"
    BRANDY = "brandy"
    COGNAC = "cognac"
    LIQUEUR = "liqueur"

    # Wine
    RED_WINE = "red_wine"
    WHITE_WINE = "white_wine"
    ROSE = "rose"
    SPARKLING = "sparkling"
    CHAMPAGNE = "champagne"
    NATURAL_WINE = "natural_wine"
    ORANGE_WINE = "orange_wine"

    # RTD
    HARD_SELTZER = "hard_seltzer"
    CANNED_COCKTAIL = "canned_cocktail"
    HARD_KOMBUCHA = "hard_kombucha"

    # Beer
    CRAFT_BEER = "craft_beer"
    IPA = "ipa"
    LAGER = "lager"
    STOUT = "stout"

    # Other
    OTHER = "other"


class Product(Base):
    """
    Product model representing an alcohol product.

    Attributes:
        id: Unique identifier (UUID)
        name: Product name (e.g., "Clase Azul Reposado")
        brand: Brand name (e.g., "Clase Azul")
        category: Main category (spirits, wine, rtd, beer)
        subcategory: Specific type (whiskey, tequila, etc.)
        description: Optional product description
        image_url: URL to product image
        external_ids: JSON mapping of external IDs (e.g., {"totalwine": "123"})
        created_at: Timestamp when product was first tracked
        updated_at: Timestamp of last update
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    brand: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    category: Mapped[ProductCategory] = mapped_column(
        Enum(ProductCategory),
        nullable=False,
        index=True,
    )
    subcategory: Mapped[Optional[ProductSubcategory]] = mapped_column(
        Enum(ProductSubcategory),
        nullable=True,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
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
        back_populates="product",
        lazy="selectin",
    )
    trend_scores: Mapped[list["TrendScore"]] = relationship(
        "TrendScore",
        back_populates="product",
        lazy="selectin",
        order_by="desc(TrendScore.calculated_at)",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_products_category_name", "category", "name"),
        Index("ix_products_brand_name", "brand", "name"),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}', category={self.category})>"

    @property
    def latest_score(self) -> Optional[float]:
        """Get the most recent trend score for this product."""
        if self.trend_scores:
            return self.trend_scores[0].score
        return None
