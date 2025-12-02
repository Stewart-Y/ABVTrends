"""ABVTrends Schemas - Pydantic request/response models."""

from app.schemas.product import (
    PaginationMeta,
    ProductCreate,
    ProductDetailResponse,
    ProductFilter,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    ProductWithTrend,
    TrendScoreSummary,
)
from app.schemas.signal import (
    SignalBatchCreate,
    SignalCreate,
    SignalFilter,
    SignalListResponse,
    SignalPaginationMeta,
    SignalResponse,
    SignalStats,
    SignalUpdate,
    SignalWithProduct,
    SignalWithSource,
)
from app.schemas.trend_score import (
    ComponentBreakdown,
    ForecastCreate,
    ForecastListResponse,
    ForecastResponse,
    ForecastSummary,
    ProductForecast,
    TopTrendsResponse,
    TrendFilter,
    TrendingListResponse,
    TrendingProduct,
    TrendPaginationMeta,
    TrendScoreCreate,
    TrendScoreHistory,
    TrendScoreListResponse,
    TrendScoreResponse,
)

__all__ = [
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductListResponse",
    "ProductDetailResponse",
    "ProductWithTrend",
    "ProductFilter",
    "PaginationMeta",
    "TrendScoreSummary",
    # Signal
    "SignalCreate",
    "SignalUpdate",
    "SignalResponse",
    "SignalListResponse",
    "SignalPaginationMeta",
    "SignalFilter",
    "SignalBatchCreate",
    "SignalStats",
    "SignalWithSource",
    "SignalWithProduct",
    # TrendScore
    "TrendScoreCreate",
    "TrendScoreResponse",
    "TrendScoreListResponse",
    "TrendScoreHistory",
    "TrendPaginationMeta",
    "ComponentBreakdown",
    # Forecast
    "ForecastCreate",
    "ForecastResponse",
    "ForecastListResponse",
    "ForecastSummary",
    "ProductForecast",
    # Trending
    "TrendingProduct",
    "TrendingListResponse",
    "TopTrendsResponse",
    "TrendFilter",
]
