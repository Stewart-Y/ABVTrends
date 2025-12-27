"""
ABVTrends - Scraper Health Check Service

Comprehensive health monitoring for all distributor scrapers.
Integrated with Discord notifications for real-time alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass, field

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_context
from app.models.distributor import (
    Distributor,
    ScrapeRun,
    ScrapeError,
    RawProductData,
    PriceHistory,
    InventoryHistory,
)
from app.services.discord_notifier import get_discord_notifier

logger = logging.getLogger(__name__)


@dataclass
class ScraperHealthStatus:
    """Health status for a single scraper."""
    slug: str
    name: str
    status: str  # healthy, stale, failed, never_run, unknown
    is_active: bool
    is_running: bool

    # Last run info
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_duration_seconds: Optional[float] = None
    hours_since_last_run: Optional[float] = None

    # Data metrics
    products_found_last_run: int = 0
    products_new_last_run: int = 0
    products_updated_last_run: int = 0
    errors_last_run: int = 0

    # Historical metrics (last 24 hours)
    total_runs_24h: int = 0
    total_products_24h: int = 0
    total_errors_24h: int = 0
    success_rate_24h: float = 0.0

    # Data flow verification
    raw_data_count_24h: int = 0
    price_records_24h: int = 0
    inventory_records_24h: int = 0

    # Issues
    issues: list[str] = field(default_factory=list)


@dataclass
class OverallHealthReport:
    """Overall health report for all scrapers."""
    overall_healthy: bool
    healthy_count: int
    unhealthy_count: int
    total_count: int

    # Aggregated metrics
    total_products_24h: int = 0
    total_runs_24h: int = 0
    total_errors_24h: int = 0

    # Detailed per-scraper status
    scrapers: list[ScraperHealthStatus] = field(default_factory=list)

    # Critical alerts
    alerts: list[dict[str, Any]] = field(default_factory=list)

    # Check timestamp
    checked_at: datetime = field(default_factory=datetime.utcnow)


class ScraperHealthChecker:
    """
    Comprehensive health checker for all distributor scrapers.

    Checks:
    - Last run status and timing
    - Data flow (raw data, prices, inventory)
    - Error rates
    - Success rates

    Integrates with Discord for alerting.
    """

    # Configuration
    STALE_THRESHOLD_HOURS = 26  # Mark as stale if no run in 26 hours (allows for weekends + buffer)
    FAILURE_THRESHOLD = 3  # Alert after 3 consecutive failures
    LOW_DATA_THRESHOLD = 5  # Alert if less than 5 products scraped

    # List of all distributors we expect to be scraping
    EXPECTED_DISTRIBUTORS = [
        "libdib",
        "sgws",
        "rndc",
        "sipmarket",
        "parkstreet",
        "breakthru",
        "provi",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.discord = get_discord_notifier()

    async def check_scraper_health(self, slug: str) -> ScraperHealthStatus:
        """Check health status for a single scraper."""
        now = datetime.utcnow()
        past_24h = now - timedelta(hours=24)

        # Get distributor info
        result = await self.db.execute(
            select(Distributor).where(Distributor.slug == slug)
        )
        distributor = result.scalar_one_or_none()

        if not distributor:
            return ScraperHealthStatus(
                slug=slug,
                name=slug.upper(),
                status="unknown",
                is_active=False,
                is_running=False,
                issues=["Distributor not found in database"],
            )

        status = ScraperHealthStatus(
            slug=slug,
            name=distributor.name,
            status="unknown",
            is_active=distributor.is_active,
            is_running=False,  # Will be set by checking running scrapes
        )

        # Get last run
        last_run_result = await self.db.execute(
            select(ScrapeRun)
            .where(
                and_(
                    ScrapeRun.distributor_id == distributor.id,
                    ScrapeRun.source_type == "distributor",
                )
            )
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()

        if last_run:
            status.last_run_at = last_run.started_at
            status.last_run_status = last_run.status
            status.products_found_last_run = last_run.products_found or 0
            status.products_new_last_run = last_run.products_new or 0
            status.products_updated_last_run = last_run.products_updated or 0
            status.errors_last_run = last_run.error_count or 0

            if last_run.completed_at and last_run.started_at:
                status.last_run_duration_seconds = (
                    last_run.completed_at - last_run.started_at
                ).total_seconds()

            status.hours_since_last_run = (now - last_run.started_at).total_seconds() / 3600

            # Determine status
            if last_run.status == "running":
                status.status = "running"
                status.is_running = True
            elif last_run.status == "completed":
                if status.hours_since_last_run < self.STALE_THRESHOLD_HOURS:
                    status.status = "healthy"
                else:
                    status.status = "stale"
                    status.issues.append(
                        f"No successful run in {status.hours_since_last_run:.1f} hours"
                    )
            elif last_run.status == "failed":
                status.status = "failed"
                status.issues.append("Last run failed")
        else:
            status.status = "never_run"
            status.issues.append("Scraper has never been run")

        # Get 24h metrics
        runs_24h_result = await self.db.execute(
            select(ScrapeRun)
            .where(
                and_(
                    ScrapeRun.distributor_id == distributor.id,
                    ScrapeRun.source_type == "distributor",
                    ScrapeRun.started_at >= past_24h,
                )
            )
        )
        runs_24h = runs_24h_result.scalars().all()

        status.total_runs_24h = len(runs_24h)
        status.total_products_24h = sum(r.products_found or 0 for r in runs_24h)
        status.total_errors_24h = sum(r.error_count or 0 for r in runs_24h)

        successful_runs = sum(1 for r in runs_24h if r.status == "completed")
        if runs_24h:
            status.success_rate_24h = (successful_runs / len(runs_24h)) * 100

        # Check data flow - raw product data
        raw_data_result = await self.db.execute(
            select(func.count(RawProductData.id))
            .where(
                and_(
                    RawProductData.source == slug,
                    RawProductData.created_at >= past_24h,
                )
            )
        )
        status.raw_data_count_24h = raw_data_result.scalar() or 0

        # Check data flow - price records
        price_result = await self.db.execute(
            select(func.count(PriceHistory.id))
            .where(
                and_(
                    PriceHistory.distributor_id == distributor.id,
                    PriceHistory.recorded_at >= past_24h,
                )
            )
        )
        status.price_records_24h = price_result.scalar() or 0

        # Check data flow - inventory records
        inventory_result = await self.db.execute(
            select(func.count(InventoryHistory.id))
            .where(
                and_(
                    InventoryHistory.distributor_id == distributor.id,
                    InventoryHistory.recorded_at >= past_24h,
                )
            )
        )
        status.inventory_records_24h = inventory_result.scalar() or 0

        # Add issues for low data
        if status.status == "healthy" and status.raw_data_count_24h < self.LOW_DATA_THRESHOLD:
            status.issues.append(
                f"Low data volume: only {status.raw_data_count_24h} raw records in 24h"
            )

        return status

    async def check_all_scrapers(self) -> OverallHealthReport:
        """Check health of all expected scrapers."""
        scrapers = []
        alerts = []
        healthy_count = 0
        unhealthy_count = 0

        total_products = 0
        total_runs = 0
        total_errors = 0

        for slug in self.EXPECTED_DISTRIBUTORS:
            status = await self.check_scraper_health(slug)
            scrapers.append(status)

            # Aggregate metrics
            total_products += status.total_products_24h
            total_runs += status.total_runs_24h
            total_errors += status.total_errors_24h

            # Count healthy/unhealthy
            if status.status in ("healthy", "running"):
                healthy_count += 1
            else:
                unhealthy_count += 1

                # Create alerts for unhealthy scrapers
                if status.status == "failed":
                    alerts.append({
                        "type": "scraper_failed",
                        "severity": "error",
                        "distributor": slug,
                        "message": f"{status.name} scraper failed",
                        "details": status.issues,
                    })
                elif status.status == "stale":
                    alerts.append({
                        "type": "scraper_stale",
                        "severity": "warning",
                        "distributor": slug,
                        "message": f"{status.name} data is stale",
                        "hours_since_run": status.hours_since_last_run,
                    })
                elif status.status == "never_run":
                    alerts.append({
                        "type": "scraper_never_run",
                        "severity": "info",
                        "distributor": slug,
                        "message": f"{status.name} has never been run",
                    })

        return OverallHealthReport(
            overall_healthy=unhealthy_count == 0,
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            total_count=len(scrapers),
            total_products_24h=total_products,
            total_runs_24h=total_runs,
            total_errors_24h=total_errors,
            scrapers=scrapers,
            alerts=alerts,
            checked_at=datetime.utcnow(),
        )

    async def send_health_report(self, report: OverallHealthReport) -> bool:
        """Send health report to Discord."""
        if not self.discord.enabled:
            logger.warning("Discord notifications disabled - skipping health report")
            return False

        # Build status breakdown
        status_lines = []
        for scraper in report.scrapers:
            emoji = {
                "healthy": "✅",
                "running": "🔄",
                "stale": "⚠️",
                "failed": "❌",
                "never_run": "⏸️",
                "unknown": "❓",
            }.get(scraper.status, "❓")

            line = f"{emoji} **{scraper.name}**: {scraper.status}"
            if scraper.hours_since_last_run:
                line += f" ({scraper.hours_since_last_run:.1f}h ago)"
            if scraper.products_found_last_run:
                line += f" - {scraper.products_found_last_run} products"
            status_lines.append(line)

        # Determine color
        if report.overall_healthy:
            color = 0x57F287  # Green
            title = "✅ All Scrapers Healthy"
        elif report.unhealthy_count <= 2:
            color = 0xFEE75C  # Yellow
            title = f"⚠️ {report.unhealthy_count} Scraper(s) Need Attention"
        else:
            color = 0xED4245  # Red
            title = f"❌ {report.unhealthy_count} Scrapers Unhealthy"

        return await self.discord.send(
            title=title,
            description="\n".join(status_lines),
            color=color,
            fields=[
                {
                    "name": "24h Summary",
                    "value": (
                        f"Runs: {report.total_runs_24h}\n"
                        f"Products: {report.total_products_24h}\n"
                        f"Errors: {report.total_errors_24h}"
                    ),
                    "inline": True,
                },
                {
                    "name": "Health Status",
                    "value": (
                        f"Healthy: {report.healthy_count}\n"
                        f"Unhealthy: {report.unhealthy_count}\n"
                        f"Total: {report.total_count}"
                    ),
                    "inline": True,
                },
            ],
            footer=f"ABVTrends Health Check • {report.checked_at.strftime('%Y-%m-%d %H:%M UTC')}",
        )

    async def send_scraper_alert(self, status: ScraperHealthStatus) -> bool:
        """Send alert for a specific scraper issue."""
        if not self.discord.enabled:
            return False

        if status.status == "failed":
            return await self.discord.scraper_error(
                distributor=status.slug,
                error="Scraper run failed",
                context={
                    "Last Run": status.last_run_at.strftime("%H:%M UTC") if status.last_run_at else "Never",
                    "Errors": status.errors_last_run,
                    "Products Found": status.products_found_last_run,
                },
            )
        elif status.status == "stale":
            return await self.discord.send(
                title="⏰ Stale Scraper Data",
                description=f"**{status.name}** hasn't run successfully in a while",
                color=0xFEE75C,  # Yellow
                fields=[
                    {
                        "name": "Hours Since Run",
                        "value": f"{status.hours_since_last_run:.1f}h",
                        "inline": True,
                    },
                    {
                        "name": "Last Status",
                        "value": status.last_run_status or "Unknown",
                        "inline": True,
                    },
                ],
            )

        return False


# Convenience functions

async def run_health_check(send_discord: bool = True) -> OverallHealthReport:
    """Run a full health check and optionally send to Discord."""
    async with get_db_context() as db:
        checker = ScraperHealthChecker(db)
        report = await checker.check_all_scrapers()

        if send_discord:
            await checker.send_health_report(report)

        return report


async def check_single_scraper(slug: str) -> ScraperHealthStatus:
    """Check health of a single scraper."""
    async with get_db_context() as db:
        checker = ScraperHealthChecker(db)
        return await checker.check_scraper_health(slug)


async def get_health_summary() -> dict[str, Any]:
    """Get a simple health summary dict for API responses."""
    report = await run_health_check(send_discord=False)

    return {
        "overall_healthy": report.overall_healthy,
        "healthy_count": report.healthy_count,
        "unhealthy_count": report.unhealthy_count,
        "total_count": report.total_count,
        "total_products_24h": report.total_products_24h,
        "total_runs_24h": report.total_runs_24h,
        "scrapers": [
            {
                "slug": s.slug,
                "name": s.name,
                "status": s.status,
                "is_active": s.is_active,
                "is_running": s.is_running,
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                "hours_since_last_run": round(s.hours_since_last_run, 1) if s.hours_since_last_run else None,
                "products_24h": s.total_products_24h,
                "raw_data_24h": s.raw_data_count_24h,
                "price_records_24h": s.price_records_24h,
                "success_rate_24h": round(s.success_rate_24h, 1),
                "issues": s.issues,
            }
            for s in report.scrapers
        ],
        "alerts": report.alerts,
        "checked_at": report.checked_at.isoformat(),
    }
