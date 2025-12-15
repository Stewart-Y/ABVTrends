"""ABVTrends Models - SQLAlchemy ORM models."""

from app.models.product import Product, ProductCategory, ProductSubcategory
from app.models.signal import Signal, SignalType
from app.models.source import ModelVersion, Source, SourceTier, SourceType
from app.models.trend_score import Forecast, TrendScore
from app.models.distributor import (
    Distributor,
    ProductAlias,
    PriceHistory,
    InventoryHistory,
    ScrapeRun,
    ScrapeError,
    RawProductData,
    MatchQueue,
    Article,
    ArticleMention,
    CurrentTrendScore,
)
from app.models.user import User, ApiKey, UserRole

__all__ = [
    # Product
    "Product",
    "ProductCategory",
    "ProductSubcategory",
    # Signal
    "Signal",
    "SignalType",
    # Source
    "Source",
    "SourceTier",
    "SourceType",
    "ModelVersion",
    # Trend Score
    "TrendScore",
    "Forecast",
    # Distributor
    "Distributor",
    "ProductAlias",
    "PriceHistory",
    "InventoryHistory",
    "ScrapeRun",
    "ScrapeError",
    "RawProductData",
    "MatchQueue",
    "Article",
    "ArticleMention",
    "CurrentTrendScore",
    # User & Auth
    "User",
    "ApiKey",
    "UserRole",
]
