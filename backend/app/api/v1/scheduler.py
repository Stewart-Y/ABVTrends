"""
ABVTrends API - Scheduler Endpoints

Monitor and control the automatic scraper scheduler.
"""

from fastapi import APIRouter, HTTPException, Request

from app.services.scraper_scheduler import get_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status")
async def get_scheduler_status(request: Request):
    """
    Get the current status of the scraper scheduler.

    Returns:
        - is_running: Whether the scheduler is currently active
        - last_run: ISO timestamp of the last completed scrape
        - next_runs: Dictionary of next scheduled run times for each job
        - jobs_count: Number of scheduled jobs
    """
    scheduler = get_scheduler()
    status = scheduler.get_status()

    return {
        "status": "ok",
        "scheduler": status,
    }


@router.post("/start")
async def start_scheduler_endpoint(request: Request):
    """
    Manually start the scraper scheduler.

    This is useful for development or when the scheduler was stopped.
    """
    scheduler = get_scheduler()

    if scheduler.is_running:
        return {
            "status": "already_running",
            "message": "Scheduler is already running",
            "scheduler": scheduler.get_status(),
        }

    try:
        scheduler.start()
        return {
            "status": "started",
            "message": "Scheduler started successfully",
            "scheduler": scheduler.get_status(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start scheduler: {str(e)}",
        )


@router.post("/stop")
async def stop_scheduler_endpoint(request: Request):
    """
    Manually stop the scraper scheduler.

    This will prevent any scheduled scrapes from running.
    """
    scheduler = get_scheduler()

    if not scheduler.is_running:
        return {
            "status": "already_stopped",
            "message": "Scheduler is not running",
        }

    try:
        scheduler.stop()
        return {
            "status": "stopped",
            "message": "Scheduler stopped successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop scheduler: {str(e)}",
        )


@router.get("/next-runs")
async def get_next_run_times(request: Request):
    """
    Get the next scheduled run times for all jobs.

    Returns a dictionary mapping job names to their next run times.
    """
    scheduler = get_scheduler()

    if not scheduler.is_running:
        return {
            "status": "scheduler_not_running",
            "next_runs": {},
        }

    return {
        "status": "ok",
        "next_runs": scheduler.get_next_run_times(),
    }
