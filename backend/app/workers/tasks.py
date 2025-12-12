"""
ABVTrends - Celery Tasks

Background tasks for scraping, scoring, and ML operations.
Includes distributor scraping tasks (Phase 5).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_db_context
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Track scraper health
_scraper_status: dict[str, dict] = {}


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If already in an async context, create a new loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)
def run_tier1_scrapers(self):
    """
    Run all Tier 1 (media) scrapers.

    Scrapes VinePair, Liquor.com, and Punch for articles.
    """
    logger.info("Starting Tier 1 scrapers...")

    async def _run():
        from app.scrapers.tier1 import TIER1_SCRAPERS
        from app.services.signal_processor import SignalProcessor

        results = {}

        for source_name, scraper_class in TIER1_SCRAPERS.items():
            try:
                logger.info(f"Running {source_name} scraper...")

                async with scraper_class() as scraper:
                    items = await scraper.scrape()

                async with get_db_context() as db:
                    processor = SignalProcessor(db)
                    created, dupes, matched = await processor.process_scraped_items(
                        items, source_name
                    )

                results[source_name] = {
                    "items": len(items),
                    "created": created,
                    "duplicates": dupes,
                    "matched": matched,
                }

            except Exception as e:
                logger.error(f"Error in {source_name} scraper: {e}")
                results[source_name] = {"error": str(e)}

        return results

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(f"Tier 1 scrapers failed: {e}")
        self.retry(countdown=300)  # Retry in 5 minutes


@celery_app.task(bind=True, max_retries=3)
def run_tier2_scrapers(self):
    """
    Run all Tier 2 (retailer) scrapers.

    Scrapes TotalWine, ReserveBar, and BevMo for products.
    """
    logger.info("Starting Tier 2 scrapers...")

    async def _run():
        from app.scrapers.tier2 import TIER2_SCRAPERS
        from app.services.signal_processor import SignalProcessor

        results = {}

        for source_name, scraper_class in TIER2_SCRAPERS.items():
            try:
                logger.info(f"Running {source_name} scraper...")

                async with scraper_class() as scraper:
                    items = await scraper.scrape()

                async with get_db_context() as db:
                    processor = SignalProcessor(db)
                    created, dupes, matched = await processor.process_scraped_items(
                        items, source_name
                    )

                results[source_name] = {
                    "items": len(items),
                    "created": created,
                    "duplicates": dupes,
                    "matched": matched,
                }

            except Exception as e:
                logger.error(f"Error in {source_name} scraper: {e}")
                results[source_name] = {"error": str(e)}

        return results

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(f"Tier 2 scrapers failed: {e}")
        self.retry(countdown=300)


@celery_app.task
def calculate_trend_scores():
    """
    Calculate trend scores for all products with recent signals.
    """
    logger.info("Calculating trend scores...")

    async def _run():
        from app.services.trend_engine import TrendEngine

        async with get_db_context() as db:
            engine = TrendEngine(db)
            count = await engine.calculate_all_scores()

        return {"scores_calculated": count}

    return run_async(_run())


@celery_app.task
def train_models():
    """
    Train ML models for products with sufficient data.
    """
    logger.info("Training ML models...")

    async def _run():
        from sqlalchemy import func, select

        from app.models.trend_score import TrendScore
        from app.services.forecast_engine import ForecastEngine

        async with get_db_context() as db:
            # Get products with enough data
            result = await db.execute(
                select(TrendScore.product_id, func.count(TrendScore.id))
                .group_by(TrendScore.product_id)
                .having(func.count(TrendScore.id) >= 30)
            )
            products = [(row[0], row[1]) for row in result.all()]

            engine = ForecastEngine(db)
            results = {}

            for product_id, data_points in products:
                try:
                    result = await engine.train_models(product_id)
                    results[str(product_id)] = result
                except Exception as e:
                    logger.error(f"Training failed for {product_id}: {e}")
                    results[str(product_id)] = {"error": str(e)}

        return {
            "products_processed": len(products),
            "results": results,
        }

    return run_async(_run())


@celery_app.task
def generate_forecasts():
    """
    Generate forecasts for all trained models.
    """
    logger.info("Generating forecasts...")

    async def _run():
        from sqlalchemy import select

        from app.ml.training import ProphetTrainer
        from app.models.trend_score import TrendScore
        from app.services.forecast_engine import ForecastEngine

        trainer = ProphetTrainer()

        async with get_db_context() as db:
            # Get products with models
            result = await db.execute(
                select(TrendScore.product_id).distinct()
            )
            product_ids = [row[0] for row in result.all()]

            # Filter to those with trained models
            products_with_models = [
                pid for pid in product_ids
                if trainer.model_exists(pid)
            ]

            engine = ForecastEngine(db)
            forecasts = await engine.batch_forecast(products_with_models)

        return {
            "products_forecasted": len(forecasts),
            "total_forecasts": sum(len(f) for f in forecasts.values()),
        }

    return run_async(_run())


@celery_app.task
def check_model_drift():
    """
    Check for model performance drift.
    """
    logger.info("Checking model drift...")

    async def _run():
        from app.ml.evaluation.drift_check import DriftDetector

        async with get_db_context() as db:
            detector = DriftDetector(db)
            reports = await detector.check_all_models()

            drift_count = sum(1 for r in reports if r.drift_detected)
            retrain_needed = [
                str(r.product_id) for r in reports
                if r.recommendation in ("retrain_urgent", "retrain_suggested")
            ]

        return {
            "models_checked": len(reports),
            "drift_detected": drift_count,
            "retrain_needed": retrain_needed,
        }

    return run_async(_run())


@celery_app.task
def cleanup_old_signals():
    """
    Archive/delete signals older than 90 days.
    """
    logger.info("Cleaning up old signals...")

    async def _run():
        from sqlalchemy import delete

        from app.models.signal import Signal

        cutoff = datetime.utcnow() - timedelta(days=90)

        async with get_db_context() as db:
            result = await db.execute(
                delete(Signal)
                .where(Signal.captured_at < cutoff)
                .where(Signal.processed == True)  # noqa: E712
            )
            deleted_count = result.rowcount
            await db.commit()

        return {"deleted_signals": deleted_count}

    return run_async(_run())


@celery_app.task
def process_unmatched_signals():
    """
    Process signals without product matches.
    """
    logger.info("Processing unmatched signals...")

    async def _run():
        from app.services.signal_processor import SignalProcessor

        async with get_db_context() as db:
            processor = SignalProcessor(db)
            created = await processor.process_unmatched_signals()

        return {"products_created": created}

    return run_async(_run())


# On-demand tasks (called via API or manually)

@celery_app.task
def scrape_single_source(source_name: str):
    """
    Scrape a single source on demand.

    Args:
        source_name: Source identifier (e.g., 'vinepair')
    """
    logger.info(f"On-demand scrape for {source_name}...")

    async def _run():
        from app.scrapers import ALL_SCRAPERS
        from app.services.signal_processor import SignalProcessor

        if source_name not in ALL_SCRAPERS:
            return {"error": f"Unknown source: {source_name}"}

        scraper_class = ALL_SCRAPERS[source_name]

        async with scraper_class() as scraper:
            items = await scraper.scrape()

        async with get_db_context() as db:
            processor = SignalProcessor(db)
            created, dupes, matched = await processor.process_scraped_items(
                items, source_name
            )

        return {
            "source": source_name,
            "items": len(items),
            "created": created,
            "duplicates": dupes,
            "matched": matched,
        }

    return run_async(_run())


@celery_app.task
def train_single_product(product_id: str):
    """
    Train models for a single product.

    Args:
        product_id: Product UUID as string
    """
    from uuid import UUID

    logger.info(f"Training models for product {product_id}...")

    async def _run():
        from app.services.forecast_engine import ForecastEngine

        async with get_db_context() as db:
            engine = ForecastEngine(db)
            result = await engine.train_models(UUID(product_id))

        return result

    return run_async(_run())


# =============================================================================
# Distributor Scraping Tasks (Phase 5)
# =============================================================================


@celery_app.task(bind=True, max_retries=3)
def scrape_all_distributors(self):
    """
    Run all active distributor scrapers.

    Scrapes products from LibDib and other distributors,
    processes through data pipeline.
    """
    logger.info("Starting distributor scrapers...")

    async def _run():
        from dotenv import load_dotenv
        load_dotenv()

        from sqlalchemy import select
        from app.models.distributor import Distributor
        from app.scrapers.distributors import DISTRIBUTOR_SCRAPERS, SessionManager
        from app.services.data_pipeline import DataPipeline

        results = {}
        session_manager = SessionManager(use_aws=False)

        async with get_db_context() as db:
            # Get all active distributors
            result = await db.execute(
                select(Distributor).where(Distributor.is_active == True)
            )
            distributors = list(result.scalars().all())

        for distributor in distributors:
            slug = distributor.slug

            if slug not in DISTRIBUTOR_SCRAPERS:
                logger.warning(f"No scraper for distributor: {slug}")
                continue

            try:
                logger.info(f"Scraping {slug}...")
                started_at = datetime.utcnow()

                # Get credentials and create scraper
                credentials = await session_manager.get_session(slug)
                scraper_class = DISTRIBUTOR_SCRAPERS[slug]
                scraper = scraper_class(credentials)

                # Run scraper
                scrape_result = await scraper.run()

                # Process through data pipeline
                if scrape_result.products:
                    async with get_db_context() as db:
                        pipeline = DataPipeline(db)
                        stats = await pipeline.process_scrape_result(scrape_result, slug)

                    results[slug] = {
                        "success": True,
                        "products_scraped": scrape_result.products_count,
                        "products_created": stats.products_created,
                        "products_matched": stats.products_matched,
                        "products_queued": stats.products_queued,
                        "errors": len(stats.errors),
                        "duration_seconds": (datetime.utcnow() - started_at).total_seconds(),
                    }
                else:
                    results[slug] = {
                        "success": True,
                        "products_scraped": 0,
                        "errors": len(scrape_result.errors),
                    }

                # Update scraper status
                _scraper_status[slug] = {
                    "last_run": datetime.utcnow().isoformat(),
                    "status": "success",
                    "products": scrape_result.products_count,
                }

            except Exception as e:
                logger.error(f"Error scraping {slug}: {e}")
                results[slug] = {
                    "success": False,
                    "error": str(e),
                }
                _scraper_status[slug] = {
                    "last_run": datetime.utcnow().isoformat(),
                    "status": "failed",
                    "error": str(e),
                }

        return results

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(f"Distributor scrapers failed: {e}")
        self.retry(countdown=600)  # Retry in 10 minutes


@celery_app.task(bind=True, max_retries=2)
def scrape_distributor(self, slug: str, categories: Optional[list[str]] = None):
    """
    Scrape a single distributor on demand.

    Args:
        slug: Distributor slug (e.g., 'libdib')
        categories: Optional list of categories to scrape
    """
    logger.info(f"On-demand scrape for distributor: {slug}")

    async def _run():
        from dotenv import load_dotenv
        load_dotenv()

        from app.scrapers.distributors import DISTRIBUTOR_SCRAPERS, SessionManager
        from app.services.data_pipeline import DataPipeline

        if slug not in DISTRIBUTOR_SCRAPERS:
            return {"error": f"Unknown distributor: {slug}"}

        session_manager = SessionManager(use_aws=False)
        credentials = await session_manager.get_session(slug)

        scraper_class = DISTRIBUTOR_SCRAPERS[slug]
        scraper = scraper_class(credentials)

        # Run scraper
        scrape_result = await scraper.run(categories=categories)

        # Process through pipeline
        if scrape_result.products:
            async with get_db_context() as db:
                pipeline = DataPipeline(db)
                stats = await pipeline.process_scrape_result(scrape_result, slug)

            return {
                "distributor": slug,
                "products_scraped": scrape_result.products_count,
                "products_created": stats.products_created,
                "products_matched": stats.products_matched,
                "price_records": stats.price_records,
                "inventory_records": stats.inventory_records,
            }
        else:
            return {
                "distributor": slug,
                "products_scraped": 0,
                "errors": scrape_result.errors[:5],
            }

    try:
        return run_async(_run())
    except Exception as e:
        logger.error(f"Scrape failed for {slug}: {e}")
        self.retry(countdown=300)


@celery_app.task
def calculate_enhanced_trends():
    """
    Calculate enhanced trend scores using distributor data.

    Uses the new TrendScorer that incorporates:
    - Retail score (distributor presence)
    - Price score (pricing patterns)
    - Inventory score (stock signals)
    """
    logger.info("Calculating enhanced trend scores...")

    async def _run():
        from app.services.trend_scorer import TrendScorer

        async with get_db_context() as db:
            scorer = TrendScorer(db)
            count = await scorer.calculate_all_scores()

        return {
            "scores_calculated": count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    return run_async(_run())


@celery_app.task
def get_scraper_status():
    """
    Get current status of all scrapers.

    Returns health information for monitoring.
    """
    return {
        "scrapers": _scraper_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task
def check_scraper_health():
    """
    Check scraper health and alert on failures.

    Monitors consecutive failures and stale data.
    """
    logger.info("Checking scraper health...")

    alerts = []
    now = datetime.utcnow()

    for slug, status in _scraper_status.items():
        # Check for failures
        if status.get("status") == "failed":
            alerts.append({
                "type": "scraper_failed",
                "distributor": slug,
                "error": status.get("error"),
            })

        # Check for stale data (no run in 24+ hours)
        last_run = status.get("last_run")
        if last_run:
            last_run_dt = datetime.fromisoformat(last_run)
            hours_since = (now - last_run_dt).total_seconds() / 3600
            if hours_since > 24:
                alerts.append({
                    "type": "stale_data",
                    "distributor": slug,
                    "hours_since_last_run": round(hours_since, 1),
                })

    return {
        "healthy": len(alerts) == 0,
        "alerts": alerts,
        "checked_at": now.isoformat(),
    }
