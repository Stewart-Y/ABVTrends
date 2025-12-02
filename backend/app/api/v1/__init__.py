"""ABVTrends API v1 - REST API endpoints."""

from fastapi import APIRouter

from app.api.v1.forecasts import router as forecasts_router
from app.api.v1.products import router as products_router
from app.api.v1.signals import router as signals_router
from app.api.v1.trends import router as trends_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include all routers
api_router.include_router(trends_router)
api_router.include_router(products_router)
api_router.include_router(forecasts_router)
api_router.include_router(signals_router)

__all__ = ["api_router"]
