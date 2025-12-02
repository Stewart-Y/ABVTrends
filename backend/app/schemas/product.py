"""
ABVTrends - Product Schemas

Pydantic schemas for Product API request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.product import ProductCategory, ProductSubcategory


class ProductBase(BaseModel):
    """Base schema for Product with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    brand: Optional[str] = Field(None, max_length=255, description="Brand name")
    category: ProductCategory = Field(..., description="Product category")
    subcategory: Optional[ProductSubcategory] = Field(
        None, description="Product subcategory"
    )
    description: Optional[str] = Field(None, description="Product description")
    image_url: Optional[HttpUrl] = Field(None, description="URL to product image")


class ProductCreate(ProductBase):
    """Schema for creating a new Product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a Product (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand: Optional[str] = Field(None, max_length=255)
    category: Optional[ProductCategory] = None
    subcategory: Optional[ProductSubcategory] = None
    description: Optional[str] = None
    image_url: Optional[HttpUrl] = None


class ProductResponse(ProductBase):
    """Schema for Product API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    latest_score: Optional[float] = Field(
        None, description="Most recent trend score (0-100)"
    )


class ProductListResponse(BaseModel):
    """Schema for paginated Product list response."""

    data: list[ProductResponse]
    meta: "PaginationMeta"


class ProductDetailResponse(ProductResponse):
    """Schema for detailed Product response with score history."""

    score_history: list["TrendScoreSummary"] = Field(
        default_factory=list, description="Recent trend scores"
    )
    signal_count: int = Field(0, description="Total signals for this product")


class ProductWithTrend(ProductResponse):
    """Schema for Product with current trend information."""

    trend_score: float = Field(..., ge=0, le=100, description="Current trend score")
    trend_tier: str = Field(
        ..., description="Trend tier: viral, trending, emerging, stable, declining"
    )
    score_change_24h: Optional[float] = Field(
        None, description="Score change in last 24 hours"
    )
    score_change_7d: Optional[float] = Field(
        None, description="Score change in last 7 days"
    )


class TrendScoreSummary(BaseModel):
    """Summary of a trend score for history display."""

    model_config = ConfigDict(from_attributes=True)

    score: float = Field(..., ge=0, le=100)
    calculated_at: datetime


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)

    @classmethod
    def create(cls, page: int, per_page: int, total: int) -> "PaginationMeta":
        """Factory method to create pagination metadata."""
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(page=page, per_page=per_page, total=total, total_pages=total_pages)


class ProductFilter(BaseModel):
    """Query parameters for filtering products."""

    category: Optional[ProductCategory] = None
    subcategory: Optional[ProductSubcategory] = None
    brand: Optional[str] = None
    min_score: Optional[float] = Field(None, ge=0, le=100)
    max_score: Optional[float] = Field(None, ge=0, le=100)
    search: Optional[str] = Field(None, min_length=1, max_length=100)


# Forward references
ProductListResponse.model_rebuild()
ProductDetailResponse.model_rebuild()
