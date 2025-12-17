"""
ABVTrends - Scraper Logs API

Real-time streaming of scraper logs using Server-Sent Events (SSE).
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.scraper_orchestrator import ScraperOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["scraper"])

# Global state to track scraping
scraper_state = {
    "is_running": False,
    "current_source": None,
    "progress": 0,
    "total": 0,
}

# Log buffer for real-time streaming
log_buffer: list[dict] = []
MAX_LOG_BUFFER = 1000


class ScraperStartRequest(BaseModel):
    tier1: bool = True
    tier2: bool = False
    parallel: bool = False
    max_articles: int = 5


class LogStreamHandler(logging.Handler):
    """Custom logging handler that adds logs to the buffer."""

    def emit(self, record):
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "message": self.format(record),
                "logger": record.name,
            }
            log_buffer.append(log_entry)

            # Keep buffer size manageable
            if len(log_buffer) > MAX_LOG_BUFFER:
                log_buffer.pop(0)

        except Exception:
            self.handleError(record)


# Add custom handler to relevant loggers
stream_handler = LogStreamHandler()
stream_handler.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger('app.scrapers').addHandler(stream_handler)
logging.getLogger('app.services.scraper_orchestrator').addHandler(stream_handler)


async def run_scraper_background(config: ScraperStartRequest):
    """Run scraper in background and update state."""
    global scraper_state

    scraper_state["is_running"] = True
    scraper_state["progress"] = 0

    try:
        orchestrator = ScraperOrchestrator()

        # Calculate total sources
        total = 0
        if config.tier1:
            total += 20  # Tier 1 sources
        if config.tier2:
            total += 12  # Tier 2 sources

        scraper_state["total"] = total

        log_buffer.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "message": f"🚀 Starting AI scraper - {total} sources to scrape",
            "logger": "scraper_api",
        })

        # Run scraper
        summary = await orchestrator.run_all_scrapers(
            include_tier1=config.tier1,
            include_tier2=config.tier2,
            parallel=config.parallel,
            max_articles_per_source=config.max_articles,
        )

        log_buffer.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "message": f"✅ Scraping complete! Collected {summary['items_collected']} items, stored {summary['items_stored']}",
            "logger": "scraper_api",
        })

    except Exception as e:
        logger.error(f"Scraper failed: {e}", exc_info=True)
        log_buffer.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "message": f"❌ Scraper failed: {str(e)}",
            "logger": "scraper_api",
        })
    finally:
        scraper_state["is_running"] = False
        scraper_state["current_source"] = None
        scraper_state["progress"] = 0


@router.post("/start")
async def start_scraper(config: ScraperStartRequest, background_tasks: BackgroundTasks):
    """
    Start the scraper in the background.

    The scraper runs asynchronously and logs can be streamed via /scraper/logs/stream.
    """
    if scraper_state["is_running"]:
        return {
            "success": False,
            "message": "Scraper is already running",
            "state": scraper_state,
        }

    # Clear old logs
    log_buffer.clear()

    # Start scraper in background
    background_tasks.add_task(run_scraper_background, config)

    return {
        "success": True,
        "message": "Scraper started successfully",
        "config": config.dict(),
        "state": scraper_state,
    }


@router.get("/status")
async def get_scraper_status():
    """Get current scraper status."""
    return {
        "is_running": scraper_state["is_running"],
        "current_source": scraper_state["current_source"],
        "progress": scraper_state["progress"],
        "total": scraper_state["total"],
        "logs_count": len(log_buffer),
    }


@router.get("/logs")
async def get_recent_logs(limit: int = 100):
    """Get recent logs from the buffer."""
    return {
        "logs": log_buffer[-limit:],
        "total": len(log_buffer),
    }


async def log_stream_generator() -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events for log streaming."""
    import json

    last_index = 0

    # Send initial connection message
    yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to scraper logs'})}\n\n"

    try:
        while True:
            # Check for new logs
            if last_index < len(log_buffer):
                # Send all new logs
                new_logs = log_buffer[last_index:]
                for log in new_logs:
                    yield f"data: {json.dumps({'type': 'log', 'data': log})}\n\n"

                last_index = len(log_buffer)

            # Send heartbeat every 15 seconds to keep connection alive
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Wait before checking again
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        yield f"data: {json.dumps({'type': 'disconnected', 'message': 'Stream closed'})}\n\n"


@router.get("/logs/stream")
async def stream_logs():
    """
    Stream scraper logs in real-time using Server-Sent Events (SSE).

    Connect to this endpoint to receive live log updates as they happen.
    """
    return StreamingResponse(
        log_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# =============================================================================
# Per-Distributor Logs (Stealth Scraping)
# =============================================================================

@router.get("/distributor/{slug}/logs")
async def get_distributor_logs(slug: str, lines: int = 100):
    """
    Get recent logs for a specific distributor.

    Each distributor has its own log file tracking:
    - Authentication success/failure
    - Products scraped per session
    - Rate limiting events
    - Errors and exceptions

    Args:
        slug: Distributor identifier (e.g., 'libdib', 'provi', 'sgws')
        lines: Number of recent log lines to return (default: 100)
    """
    from app.services.scraper_logger import get_recent_logs, LOG_DIR

    logs = get_recent_logs(slug, lines)

    return {
        "distributor": slug,
        "log_file": str(LOG_DIR / f"{slug}.log"),
        "lines_returned": len(logs),
        "logs": [line.strip() for line in logs],
    }


@router.get("/distributor/errors")
async def get_all_distributor_errors():
    """
    Get error summary across all distributors.

    Returns error counts and recent error messages for each
    distributor to help identify problematic scrapers.
    """
    from app.services.scraper_logger import get_error_summary

    summary = get_error_summary()

    # Calculate totals
    total_errors = sum(s["error_count"] for s in summary.values())

    return {
        "total_errors": total_errors,
        "distributors": summary,
    }


@router.get("/distributor/stats")
async def get_distributor_scraping_stats():
    """
    Get current daily scraping statistics for all distributors.

    Shows items scraped, daily limits, remaining budget,
    and session counts for each distributor.
    """
    from app.services.stealth_scraper import get_scraper_stats

    stats = await get_scraper_stats()

    # Calculate totals
    total_scraped = sum(s["items_scraped"] for s in stats.values())
    total_limit = sum(s["daily_limit"] for s in stats.values())

    return {
        "total_scraped_today": total_scraped,
        "total_daily_limit": total_limit,
        "remaining_budget": total_limit - total_scraped,
        "distributors": stats,
    }
