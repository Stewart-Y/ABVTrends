"""
ABVTrends - Scraper Scheduler

Automatically runs scrapers on a schedule (hourly, daily, etc.)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.scraper_orchestrator import ScraperOrchestrator

logger = logging.getLogger(__name__)


class ScraperScheduler:
    """
    Schedules and runs scrapers automatically.

    Features:
    - Hourly scraping of all sources
    - Configurable schedules per tier
    - Automatic retry on failures
    - Prevents overlapping runs
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.orchestrator = ScraperOrchestrator()
        self.is_running = False
        self.last_run: Optional[datetime] = None

    def start(self):
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        # Schedule Tier 1 (Media) - Every hour
        self.scheduler.add_job(
            self._run_tier1_scraper,
            trigger=CronTrigger(minute=0),  # Every hour at :00
            id="tier1_hourly",
            name="Tier 1 Media Scraper (Hourly)",
            max_instances=1,  # Prevent overlapping runs
            replace_existing=True,
        )

        # Schedule Tier 2 (Retailers) - Every 4 hours
        self.scheduler.add_job(
            self._run_tier2_scraper,
            trigger=CronTrigger(hour="*/4", minute=15),  # Every 4 hours at :15
            id="tier2_4hourly",
            name="Tier 2 Retailer Scraper (Every 4 hours)",
            max_instances=1,
            replace_existing=True,
        )

        # Schedule full scrape - Daily at 2 AM
        self.scheduler.add_job(
            self._run_full_scraper,
            trigger=CronTrigger(hour=2, minute=0),  # Daily at 2:00 AM
            id="full_daily",
            name="Full Scraper (Daily)",
            max_instances=1,
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Scraper scheduler started")
        logger.info("  - Tier 1 (Media): Every hour at :00")
        logger.info("  - Tier 2 (Retailers): Every 4 hours at :15")
        logger.info("  - Full scrape: Daily at 2:00 AM")

    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Scraper scheduler stopped")

    async def _run_tier1_scraper(self):
        """Run Tier 1 (media) scrapers."""
        logger.info("=== Scheduled Tier 1 scrape starting ===")
        start_time = datetime.utcnow()

        try:
            summary = await self.orchestrator.run_all_scrapers(
                include_tier1=True,
                include_tier2=False,
                parallel=True,  # Run in parallel for speed
                max_articles_per_source=5,
                max_days_old=7,  # Only articles from last 7 days
            )

            duration = summary["duration_seconds"]
            logger.info(
                f"✓ Tier 1 scrape complete: {summary['items_collected']} items "
                f"collected, {summary['items_stored']} stored in {duration:.2f}s"
            )

            if summary["scrapers_failed"] > 0:
                logger.warning(f"⚠ {summary['scrapers_failed']} sources failed")
                for source, error in summary["errors"].items():
                    logger.error(f"  - {source}: {error}")

            self.last_run = start_time

        except Exception as e:
            logger.error(f"✗ Tier 1 scrape failed: {e}", exc_info=True)

    async def _run_tier2_scraper(self):
        """Run Tier 2 (retailer) scrapers."""
        logger.info("=== Scheduled Tier 2 scrape starting ===")
        start_time = datetime.utcnow()

        try:
            summary = await self.orchestrator.run_all_scrapers(
                include_tier1=False,
                include_tier2=True,
                parallel=True,
                max_articles_per_source=5,
                max_days_old=14,  # Retailers update less frequently - 14 days
            )

            duration = summary["duration_seconds"]
            logger.info(
                f"✓ Tier 2 scrape complete: {summary['items_collected']} items "
                f"collected, {summary['items_stored']} stored in {duration:.2f}s"
            )

            if summary["scrapers_failed"] > 0:
                logger.warning(f"⚠ {summary['scrapers_failed']} sources failed")
                for source, error in summary["errors"].items():
                    logger.error(f"  - {source}: {error}")

            self.last_run = start_time

        except Exception as e:
            logger.error(f"✗ Tier 2 scrape failed: {e}", exc_info=True)

    async def _run_full_scraper(self):
        """Run full scrape of all tiers."""
        logger.info("=== Scheduled FULL scrape starting ===")
        start_time = datetime.utcnow()

        try:
            summary = await self.orchestrator.run_all_scrapers(
                include_tier1=True,
                include_tier2=True,
                parallel=True,
                max_articles_per_source=10,  # More articles for daily run
                max_days_old=14,  # 14 days for comprehensive daily scrape
            )

            duration = summary["duration_seconds"]
            logger.info(
                f"✓ Full scrape complete: {summary['items_collected']} items "
                f"collected, {summary['items_stored']} stored in {duration:.2f}s"
            )

            if summary["scrapers_failed"] > 0:
                logger.warning(f"⚠ {summary['scrapers_failed']} sources failed")
                for source, error in summary["errors"].items():
                    logger.error(f"  - {source}: {error}")

            self.last_run = start_time

        except Exception as e:
            logger.error(f"✗ Full scrape failed: {e}", exc_info=True)

    def get_next_run_times(self) -> dict:
        """Get next scheduled run times for each job."""
        if not self.is_running:
            return {}

        next_runs = {}
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            next_runs[job.name] = next_run.isoformat() if next_run else None

        return next_runs

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_runs": self.get_next_run_times(),
            "jobs_count": len(self.scheduler.get_jobs()) if self.is_running else 0,
        }


# Global scheduler instance
_scheduler: Optional[ScraperScheduler] = None


def get_scheduler() -> ScraperScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ScraperScheduler()
    return _scheduler


async def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


async def stop_scheduler():
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()


if __name__ == "__main__":
    # Test the scheduler
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def main():
        scheduler = get_scheduler()
        scheduler.start()

        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        logger.info(f"Status: {scheduler.get_status()}")

        try:
            # Keep running
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.stop()

    asyncio.run(main())
