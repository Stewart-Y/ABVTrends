"""
ABVTrends - FastAPI Application

Main entry point for the ABVTrends API server.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import close_db, init_db, set_db_available

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=settings.log_format,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Runs on startup and shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Initialize database (with graceful fallback for local dev without DB)
    try:
        await init_db()
        logger.info("Database tables initialized")
        app.state.db_available = True
        set_db_available(True)
    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        logger.warning("Running in demo mode without database")
        app.state.db_available = False
        set_db_available(False)

    # Start scraper scheduler if enabled
    if settings.environment == "production":
        try:
            from app.services.scraper_scheduler import start_scheduler
            scheduler = await start_scheduler()
            app.state.scheduler = scheduler
            logger.info("✓ Scraper scheduler started (automatic hourly scraping)")
        except Exception as e:
            logger.warning(f"Failed to start scraper scheduler: {e}")
            app.state.scheduler = None
    else:
        logger.info("Scraper scheduler disabled in development mode")
        app.state.scheduler = None

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop scheduler
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        try:
            from app.services.scraper_scheduler import stop_scheduler
            await stop_scheduler()
            logger.info("Scraper scheduler stopped")
        except Exception as e:
            logger.warning(f"Error stopping scheduler: {e}")

    # Close database
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception:
        pass


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="The Bloomberg Terminal for Alcohol Trends - Track trending spirits, wines, and RTDs",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://abvtrends.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc) if settings.debug else None,
            }
        },
    )


# Include API routes
app.include_router(api_router)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.app_name,
        "description": "The Bloomberg Terminal for Alcohol Trends",
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "Disabled in production",
        "api_base": "/api/v1",
        "endpoints": {
            "trends": "/api/v1/trends",
            "products": "/api/v1/products",
            "forecasts": "/api/v1/forecasts",
            "signals": "/api/v1/signals",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
