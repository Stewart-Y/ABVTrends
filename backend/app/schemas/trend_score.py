"""
ABVTrends - Trend Score and Forecast Schemas

Pydantic schemas for TrendScore and Forecast API validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrendScoreBase(BaseModel):
    """Base schema for TrendScore."""

    score: float = Field(..., ge=0, le=100, description="Composite trend score")
    media_score: float = Field(0.0, ge=0, le=100, description="Media component score")
    social_score: float = Field(0.0, ge=0, le=100, description="Social component score")
    retailer_score: float = Field(
        0.0, ge=0, le=100, description="Retailer component score"
    )
    price_score: float = Field(0.0, ge=0, le=100, description="Price component score")
    search_score: float = Field(0.0, ge=0, le=100, description="Search component score")
    seasonal_score: float = Field(
        0.0, ge=0, le=100, description="Seasonal component score"
    )


class TrendScoreCreate(TrendScoreBase):
    """Schema for creating a TrendScore."""

    product_id: UUID
    signal_count: int = Field(0, ge=0)
    calculated_at: datetime


class TrendScoreResponse(TrendScoreBase):
    """Schema for TrendScore API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    signal_count: int
    calculation_version: str
    calculated_at: datetime
    created_at: datetime
    trend_tier: str = Field(
        ..., description="Tier: viral, trending, emerging, stable, declining"
    )


class TrendScoreListResponse(BaseModel):
    """Schema for TrendScore list response."""

    data: list[TrendScoreResponse]
    meta: "TrendPaginationMeta"


class TrendPaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    per_page: int
    total: int


class TrendScoreHistory(BaseModel):
    """Historical trend scores for a product."""

    product_id: UUID
    product_name: str
    scores: list[TrendScoreResponse]
    period_start: datetime
    period_end: datetime


class ComponentBreakdown(BaseModel):
    """Breakdown of trend score components."""

    media: float = Field(..., ge=0, le=100)
    social: float = Field(..., ge=0, le=100)
    retailer: float = Field(..., ge=0, le=100)
    price: float = Field(..., ge=0, le=100)
    search: float = Field(..., ge=0, le=100)
    seasonal: float = Field(..., ge=0, le=100)


# Forecast Schemas


class ForecastBase(BaseModel):
    """Base schema for Forecast."""

    forecast_date: datetime = Field(..., description="Date being predicted")
    predicted_score: float = Field(
        ..., ge=0, le=100, description="Predicted trend score"
    )
    confidence_lower_80: Optional[float] = Field(
        None, description="Lower bound of 80% CI"
    )
    confidence_upper_80: Optional[float] = Field(
        None, description="Upper bound of 80% CI"
    )
    confidence_lower_95: Optional[float] = Field(
        None, description="Lower bound of 95% CI"
    )
    confidence_upper_95: Optional[float] = Field(
        None, description="Upper bound of 95% CI"
    )


class ForecastCreate(ForecastBase):
    """Schema for creating a Forecast."""

    product_id: UUID
    model_version: str
    model_type: str = "ensemble"


class ForecastResponse(ForecastBase):
    """Schema for Forecast API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    model_version: str
    model_type: str
    created_at: datetime


class ForecastListResponse(BaseModel):
    """Schema for Forecast list response."""

    data: list[ForecastResponse]


class ProductForecast(BaseModel):
    """Complete forecast for a product."""

    product_id: UUID
    product_name: str
    current_score: float
    forecasts: list[ForecastResponse]
    model_version: str
    generated_at: datetime


class ForecastSummary(BaseModel):
    """Summary of forecast for dashboard display."""

    product_id: UUID
    product_name: str
    current_score: float
    predicted_score_7d: float
    trend_direction: str = Field(
        ..., description="up, down, or stable"
    )
    confidence: float = Field(..., ge=0, le=100, description="Prediction confidence %")


# Trending Products


class TrendingProduct(BaseModel):
    """Product with trend information for dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    brand: Optional[str]
    category: str
    subcategory: Optional[str]
    image_url: Optional[str]
    trend_score: float
    trend_tier: str
    score_change_24h: Optional[float]
    score_change_7d: Optional[float]
    component_breakdown: ComponentBreakdown


class TrendingListResponse(BaseModel):
    """Response for trending products endpoint."""

    data: list[TrendingProduct]
    meta: TrendPaginationMeta
    generated_at: datetime


class TopTrendsResponse(BaseModel):
    """Response for top trends dashboard widget."""

    viral: list[TrendingProduct] = Field(default_factory=list, max_length=5)
    trending: list[TrendingProduct] = Field(default_factory=list, max_length=10)
    emerging: list[TrendingProduct] = Field(default_factory=list, max_length=10)
    generated_at: datetime


class TrendFilter(BaseModel):
    """Filter parameters for trending products."""

    category: Optional[str] = None
    subcategory: Optional[str] = None
    min_score: Optional[float] = Field(None, ge=0, le=100)
    max_score: Optional[float] = Field(None, ge=0, le=100)
    tier: Optional[str] = Field(
        None, description="Filter by tier: viral, trending, emerging, stable, declining"
    )
    sort_by: str = Field("score", description="Sort field: score, change_24h, change_7d")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


# Forward references
TrendScoreListResponse.model_rebuild()
