"""
ABVTrends - Signal Schemas

Pydantic schemas for Signal API request/response validation.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.signal import SignalType


class SignalBase(BaseModel):
    """Base schema for Signal with common fields."""

    signal_type: SignalType = Field(..., description="Type of signal")
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Raw scraped data"
    )
    url: Optional[str] = Field(None, max_length=1024, description="Source URL")
    title: Optional[str] = Field(None, max_length=512, description="Article/item title")
    captured_at: datetime = Field(..., description="When the content was captured")


class SignalCreate(SignalBase):
    """Schema for creating a new Signal."""

    product_id: Optional[UUID] = Field(
        None, description="Associated product ID (can be matched later)"
    )
    source_id: Optional[UUID] = Field(None, description="Source that generated signal")
    sentiment_score: Optional[float] = Field(
        None, ge=-1.0, le=1.0, description="Sentiment score (-1 to 1)"
    )


class SignalUpdate(BaseModel):
    """Schema for updating a Signal."""

    product_id: Optional[UUID] = None
    processed: Optional[bool] = None
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)


class SignalResponse(SignalBase):
    """Schema for Signal API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: Optional[UUID]
    source_id: Optional[UUID]
    processed: bool
    sentiment_score: Optional[float]
    created_at: datetime


class SignalListResponse(BaseModel):
    """Schema for paginated Signal list response."""

    data: list[SignalResponse]
    meta: "SignalPaginationMeta"


class SignalPaginationMeta(BaseModel):
    """Pagination metadata for signal list responses."""

    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    total: int = Field(..., ge=0)


class SignalFilter(BaseModel):
    """Query parameters for filtering signals."""

    signal_type: Optional[SignalType] = None
    product_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    processed: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate that end_date is after start_date."""
        start_date = info.data.get("start_date")
        if v and start_date and v < start_date:
            raise ValueError("end_date must be after start_date")
        return v


class SignalBatchCreate(BaseModel):
    """Schema for batch creating signals."""

    signals: list[SignalCreate] = Field(
        ..., min_length=1, max_length=100, description="List of signals to create"
    )


class SignalStats(BaseModel):
    """Statistics about signals."""

    total_signals: int
    unprocessed_count: int
    signals_by_type: dict[str, int]
    signals_last_24h: int
    signals_last_7d: int


class SignalWithSource(SignalResponse):
    """Signal response with source details."""

    source_name: Optional[str] = None
    source_tier: Optional[str] = None


class SignalWithProduct(SignalResponse):
    """Signal response with product details."""

    product_name: Optional[str] = None
    product_category: Optional[str] = None


# Forward references
SignalListResponse.model_rebuild()
