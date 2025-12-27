"""
ABVTrends - Distributors API Endpoints

REST API for distributor management and scraper control.
Scrape trigger endpoints require admin authentication.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.distributor import Distributor, ScrapeRun, ScrapeError
from app.models.user import User
from app.scrapers.distributors import (
    DISTRIBUTOR_SCRAPERS,
    SessionManager,
    ScrapeResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/distributors", tags=["distributors"])


# Pydantic schemas
class DistributorResponse(BaseModel):
    """Response model for a distributor."""

    id: int
    name: str
    slug: str
    website_url: Optional[str] = None
    is_active: bool
    scraper_class: Optional[str] = None
    last_scrape_at: Optional[datetime] = None
    last_scrape_status: Optional[str] = None
    products_count: Optional[int] = None

    class Config:
        from_attributes = True


class DistributorListResponse(BaseModel):
    """Response model for list of distributors."""

    distributors: list[DistributorResponse]
    total: int


class ScrapeStatusResponse(BaseModel):
    """Response model for scraper status."""

    distributor: str
    is_running: bool
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_products_count: Optional[int] = None
    last_run_errors: Optional[list[str]] = None
    total_runs: int
    success_rate: float


class ScrapeResultResponse(BaseModel):
    """Response model for scrape result."""

    success: bool
    message: str
    products_count: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Track running scrapes
_running_scrapes: dict[str, bool] = {}


@router.get("", response_model=DistributorListResponse)
async def list_distributors(
    active_only: bool = Query(True, description="Only return active distributors"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all distributors with their scrape status.
    """
    query = select(Distributor)
    if active_only:
        query = query.where(Distributor.is_active == True)
    query = query.order_by(Distributor.name)

    result = await db.execute(query)
    distributors = result.scalars().all()

    # Get last scrape info for each distributor
    distributor_responses = []
    for dist in distributors:
        # Get last scrape run
        last_run_query = (
            select(ScrapeRun)
            .where(ScrapeRun.distributor_id == dist.id)
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        )
        last_run_result = await db.execute(last_run_query)
        last_run = last_run_result.scalar_one_or_none()

        distributor_responses.append(
            DistributorResponse(
                id=dist.id,
                name=dist.name,
                slug=dist.slug,
                website_url=dist.website,
                is_active=dist.is_active,
                scraper_class=dist.scraper_class,
                last_scrape_at=last_run.started_at if last_run else None,
                last_scrape_status=last_run.status if last_run else None,
                products_count=last_run.products_found if last_run else None,
            )
        )

    return DistributorListResponse(
        distributors=distributor_responses,
        total=len(distributor_responses),
    )


@router.get("/{slug}/status", response_model=ScrapeStatusResponse)
async def get_scraper_status(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get status information for a distributor's scraper.
    """
    # Get distributor
    query = select(Distributor).where(Distributor.slug == slug)
    result = await db.execute(query)
    distributor = result.scalar_one_or_none()

    if not distributor:
        raise HTTPException(status_code=404, detail=f"Distributor '{slug}' not found")

    # Get scrape runs
    runs_query = (
        select(ScrapeRun)
        .where(ScrapeRun.distributor_id == distributor.id)
        .order_by(ScrapeRun.started_at.desc())
        .limit(100)
    )
    runs_result = await db.execute(runs_query)
    runs = runs_result.scalars().all()

    # Calculate stats
    total_runs = len(runs)
    successful_runs = sum(1 for r in runs if r.status == "completed")
    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0

    last_run = runs[0] if runs else None

    # Get errors from last run if any
    last_errors = []
    if last_run:
        errors_query = (
            select(ScrapeError)
            .where(ScrapeError.scrape_run_id == last_run.id)
            .limit(10)
        )
        errors_result = await db.execute(errors_query)
        errors = errors_result.scalars().all()
        last_errors = [e.error_message for e in errors]

    return ScrapeStatusResponse(
        distributor=slug,
        is_running=_running_scrapes.get(slug, False),
        last_run_at=last_run.started_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
        last_run_products_count=last_run.products_found if last_run else None,
        last_run_errors=last_errors if last_errors else None,
        total_runs=total_runs,
        success_rate=success_rate,
    )


@router.post("/{slug}/scrape", response_model=ScrapeResultResponse)
async def trigger_scrape(
    slug: str,
    background_tasks: BackgroundTasks,
    categories: Optional[list[str]] = Query(
        None, description="Specific categories to scrape"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=10000, description="Max products to scrape"
    ),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Trigger a scrape for a distributor.

    This runs the scrape in the background and returns immediately.
    Check status via GET /distributors/{slug}/status
    """
    # Check if scraper exists
    if slug not in DISTRIBUTOR_SCRAPERS:
        raise HTTPException(
            status_code=404,
            detail=f"No scraper implemented for '{slug}'",
        )

    # Check if already running
    if _running_scrapes.get(slug, False):
        raise HTTPException(
            status_code=409,
            detail=f"Scrape already running for '{slug}'",
        )

    # Get distributor from DB
    query = select(Distributor).where(Distributor.slug == slug)
    result = await db.execute(query)
    distributor = result.scalar_one_or_none()

    if not distributor:
        raise HTTPException(status_code=404, detail=f"Distributor '{slug}' not found")

    if not distributor.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Distributor '{slug}' is not active",
        )

    # Start background scrape
    background_tasks.add_task(
        run_scrape_task,
        slug=slug,
        distributor_id=distributor.id,
        categories=categories,
        limit=limit,
    )

    return ScrapeResultResponse(
        success=True,
        message=f"Scrape started for '{slug}'. Check status endpoint for progress.",
    )


async def run_scrape_task(
    slug: str,
    distributor_id: UUID,
    categories: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> None:
    """
    Background task to run a scrape and process results through the data pipeline.
    """
    from app.core.database import get_db_context
    from app.services.data_pipeline import DataPipeline

    _running_scrapes[slug] = True

    try:
        # Get credentials and run scraper
        session_manager = SessionManager(use_aws=False)
        credentials = await session_manager.get_session(slug)

        scraper_class = DISTRIBUTOR_SCRAPERS[slug]
        scraper = scraper_class(credentials)

        logger.info(f"Starting scrape for {slug}...")
        result = await scraper.run(categories=categories)

        logger.info(
            f"Scrape completed for {slug}: "
            f"{result.products_count} products, {len(result.errors)} errors"
        )

        # Process results through data pipeline
        if result.products:
            logger.info(f"Processing {len(result.products)} products through pipeline...")
            async with get_db_context() as db:
                pipeline = DataPipeline(db)
                stats = await pipeline.process_scrape_result(result, slug)

            logger.info(
                f"Pipeline complete for {slug}: "
                f"{stats.products_matched} matched, {stats.products_created} new, "
                f"{stats.products_queued} queued, {stats.products_failed} failed"
            )
        else:
            logger.warning(f"No products to process for {slug}")

    except Exception as e:
        logger.exception(f"Scrape/pipeline failed for {slug}: {e}")

        # Log error to database
        try:
            async with get_db_context() as db:
                error = ScrapeError(
                    distributor_id=distributor_id,
                    error_type="exception",
                    error_message=str(e)[:1000],
                )
                db.add(error)
                await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to log error: {db_error}")

    finally:
        _running_scrapes[slug] = False


@router.get("/scraper/health")
async def get_scraper_health(
    db: AsyncSession = Depends(get_db),
):
    """
    Get health status of all distributor scrapers.

    Returns overall health and any alerts for failing or stale scrapers.
    Uses the comprehensive health check service.
    """
    from app.services.scraper_health import get_health_summary

    return await get_health_summary()


@router.get("/scraper/health/detailed")
async def get_detailed_scraper_health(
    send_discord: bool = Query(False, description="Send health report to Discord"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed health status for all scrapers with data flow metrics.

    Optionally sends a summary to Discord.
    """
    from app.services.scraper_health import run_health_check

    report = await run_health_check(send_discord=send_discord)

    return {
        "overall_healthy": report.overall_healthy,
        "healthy_count": report.healthy_count,
        "unhealthy_count": report.unhealthy_count,
        "total_count": report.total_count,
        "summary": {
            "total_products_24h": report.total_products_24h,
            "total_runs_24h": report.total_runs_24h,
            "total_errors_24h": report.total_errors_24h,
        },
        "scrapers": [
            {
                "slug": s.slug,
                "name": s.name,
                "status": s.status,
                "is_active": s.is_active,
                "is_running": s.is_running,
                "last_run": {
                    "at": s.last_run_at.isoformat() if s.last_run_at else None,
                    "status": s.last_run_status,
                    "duration_seconds": s.last_run_duration_seconds,
                    "hours_ago": round(s.hours_since_last_run, 1) if s.hours_since_last_run else None,
                    "products_found": s.products_found_last_run,
                    "products_new": s.products_new_last_run,
                    "products_updated": s.products_updated_last_run,
                    "errors": s.errors_last_run,
                },
                "metrics_24h": {
                    "total_runs": s.total_runs_24h,
                    "total_products": s.total_products_24h,
                    "total_errors": s.total_errors_24h,
                    "success_rate": round(s.success_rate_24h, 1),
                },
                "data_flow_24h": {
                    "raw_data_records": s.raw_data_count_24h,
                    "price_records": s.price_records_24h,
                    "inventory_records": s.inventory_records_24h,
                },
                "issues": s.issues,
            }
            for s in report.scrapers
        ],
        "alerts": report.alerts,
        "checked_at": report.checked_at.isoformat(),
        "discord_sent": send_discord,
    }


@router.get("/scraper/health/{slug}")
async def get_single_scraper_health(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed health status for a single scraper.
    """
    from app.services.scraper_health import check_single_scraper

    status = await check_single_scraper(slug)

    return {
        "slug": status.slug,
        "name": status.name,
        "status": status.status,
        "is_active": status.is_active,
        "is_running": status.is_running,
        "last_run": {
            "at": status.last_run_at.isoformat() if status.last_run_at else None,
            "status": status.last_run_status,
            "duration_seconds": status.last_run_duration_seconds,
            "hours_ago": round(status.hours_since_last_run, 1) if status.hours_since_last_run else None,
            "products_found": status.products_found_last_run,
            "products_new": status.products_new_last_run,
            "products_updated": status.products_updated_last_run,
            "errors": status.errors_last_run,
        },
        "metrics_24h": {
            "total_runs": status.total_runs_24h,
            "total_products": status.total_products_24h,
            "total_errors": status.total_errors_24h,
            "success_rate": round(status.success_rate_24h, 1),
        },
        "data_flow_24h": {
            "raw_data_records": status.raw_data_count_24h,
            "price_records": status.price_records_24h,
            "inventory_records": status.inventory_records_24h,
        },
        "issues": status.issues,
    }


@router.post("/scraper/test-run")
async def trigger_test_run(
    items_per_distributor: int = Query(10, ge=1, le=50, description="Items to scrape per distributor"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Trigger a test scrape for all 7 distributors.

    This bypasses business hours and stealth delays for quick testing.
    Sends Discord notifications:
    - When test starts
    - For each scraper failure
    - Final summary with results

    Returns immediately - check Discord for progress updates.
    """
    from app.services.stealth_scraper import run_test_scrape

    # Run synchronously since this is a test/debug endpoint
    # The user wants to see results in Discord
    result = await run_test_scrape(items_per_distributor=items_per_distributor)

    return {
        "success": True,
        "message": f"Test scrape complete. {result['total_scraped']} products from {result['successful_count']}/7 distributors.",
        "results": result["results"],
        "summary": {
            "total_scraped": result["total_scraped"],
            "successful_count": result["successful_count"],
            "error_count": result["error_count"],
            "duration_seconds": result["duration_seconds"],
        },
    }


@router.get("/scraper/runs")
async def get_recent_runs(
    limit: int = Query(20, ge=1, le=100),
    distributor: Optional[str] = Query(None, description="Filter by distributor slug"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent scrape runs across all distributors.
    """
    query = (
        select(ScrapeRun, Distributor.name, Distributor.slug)
        .join(Distributor, ScrapeRun.distributor_id == Distributor.id)
        .order_by(ScrapeRun.started_at.desc())
        .limit(limit)
    )

    if distributor:
        query = query.where(Distributor.slug == distributor)

    result = await db.execute(query)
    runs = result.all()

    return {
        "runs": [
            {
                "id": run.id,
                "distributor": dist_name,
                "distributor_slug": dist_slug,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "products_found": run.products_found,
                "products_new": run.products_new,
                "products_updated": run.products_updated,
                "error_count": run.error_count,
            }
            for run, dist_name, dist_slug in runs
        ],
    }
