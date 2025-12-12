"""
ABVTrends - Celery Application

Celery configuration for background task processing.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "abvtrends",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Task routing
    task_routes={
        "app.workers.tasks.run_tier1_scrapers": {"queue": "scrapers"},
        "app.workers.tasks.run_tier2_scrapers": {"queue": "scrapers"},
        "app.workers.tasks.scrape_all_distributors": {"queue": "scrapers"},
        "app.workers.tasks.scrape_distributor": {"queue": "scrapers"},
        "app.workers.tasks.calculate_trend_scores": {"queue": "default"},
        "app.workers.tasks.calculate_enhanced_trends": {"queue": "default"},
        "app.workers.tasks.train_models": {"queue": "ml"},
        "app.workers.tasks.generate_forecasts": {"queue": "ml"},
        "app.workers.tasks.check_model_drift": {"queue": "ml"},
    },

    # Beat schedule for periodic tasks
    beat_schedule={
        # Scraping tasks
        "run-tier1-scrapers-every-6-hours": {
            "task": "app.workers.tasks.run_tier1_scrapers",
            "schedule": crontab(minute=0, hour="*/6"),
            "options": {"queue": "scrapers"},
        },
        "run-tier2-scrapers-every-12-hours": {
            "task": "app.workers.tasks.run_tier2_scrapers",
            "schedule": crontab(minute=30, hour="*/12"),
            "options": {"queue": "scrapers"},
        },

        # Distributor scraping (Phase 5) - hourly
        "scrape-distributors-hourly": {
            "task": "app.workers.tasks.scrape_all_distributors",
            "schedule": crontab(minute=15),  # :15 past every hour
            "options": {"queue": "scrapers"},
        },

        # Trend calculation - legacy (signals-based)
        "calculate-scores-hourly": {
            "task": "app.workers.tasks.calculate_trend_scores",
            "schedule": crontab(minute=0),  # Every hour
            "options": {"queue": "default"},
        },

        # Enhanced trend calculation (distributor-based) - runs after scraping
        "calculate-enhanced-trends-hourly": {
            "task": "app.workers.tasks.calculate_enhanced_trends",
            "schedule": crontab(minute=45),  # :45 past every hour (after scrape completes)
            "options": {"queue": "default"},
        },

        # Scraper health check - every 6 hours
        "check-scraper-health": {
            "task": "app.workers.tasks.check_scraper_health",
            "schedule": crontab(minute=0, hour="*/6"),
            "options": {"queue": "default"},
        },

        # ML tasks (daily at 3 AM UTC)
        "retrain-models-daily": {
            "task": "app.workers.tasks.train_models",
            "schedule": crontab(minute=0, hour=settings.model_retrain_hour),
            "options": {"queue": "ml"},
        },
        "generate-forecasts-daily": {
            "task": "app.workers.tasks.generate_forecasts",
            "schedule": crontab(minute=30, hour=settings.model_retrain_hour),
            "options": {"queue": "ml"},
        },
        "check-drift-daily": {
            "task": "app.workers.tasks.check_model_drift",
            "schedule": crontab(minute=0, hour=settings.model_retrain_hour + 1),
            "options": {"queue": "ml"},
        },

        # Maintenance
        "cleanup-old-signals-weekly": {
            "task": "app.workers.tasks.cleanup_old_signals",
            "schedule": crontab(minute=0, hour=4, day_of_week=0),  # Sunday 4 AM
            "options": {"queue": "default"},
        },
    },
)


if __name__ == "__main__":
    celery_app.start()
