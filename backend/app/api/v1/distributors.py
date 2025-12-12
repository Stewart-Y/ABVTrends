"""
ABVTrends - Distributors API Endpoints

REST API for distributor management and scraper control.
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

from app.core.database import get_db
from app.models.distributor import Distributor, ScrapeRun, ScrapeError
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

    id: UUID
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
                website_url=dist.website_url,
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
    """
    from datetime import datetime, timedelta

    alerts = []
    scraper_health = []

    # Get all active distributors
    result = await db.execute(
        select(Distributor).where(Distributor.is_active == True)
    )
    distributors = result.scalars().all()

    now = datetime.utcnow()
    healthy_count = 0

    for dist in distributors:
        # Get last scrape run
        last_run_result = await db.execute(
            select(ScrapeRun)
            .where(ScrapeRun.distributor_id == dist.id)
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()

        status = "unknown"
        last_run_at = None
        hours_since = None

        if last_run:
            last_run_at = last_run.started_at
            hours_since = (now - last_run.started_at).total_seconds() / 3600

            if last_run.status == "completed":
                if hours_since < 24:
                    status = "healthy"
                    healthy_count += 1
                else:
                    status = "stale"
                    alerts.append({
                        "type": "stale_data",
                        "distributor": dist.slug,
                        "hours_since_run": round(hours_since, 1),
                    })
            elif last_run.status == "failed":
                status = "failed"
                alerts.append({
                    "type": "last_run_failed",
                    "distributor": dist.slug,
                })
            else:
                status = last_run.status
        else:
            alerts.append({
                "type": "never_run",
                "distributor": dist.slug,
            })

        scraper_health.append({
            "distributor": dist.name,
            "slug": dist.slug,
            "status": status,
            "last_run_at": last_run_at.isoformat() if last_run_at else None,
            "hours_since_run": round(hours_since, 1) if hours_since else None,
            "is_running": _running_scrapes.get(dist.slug, False),
        })

    return {
        "overall_healthy": len(alerts) == 0,
        "healthy_count": healthy_count,
        "total_count": len(distributors),
        "scrapers": scraper_health,
        "alerts": alerts,
        "checked_at": now.isoformat(),
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
