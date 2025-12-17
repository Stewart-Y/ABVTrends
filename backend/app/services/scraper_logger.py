"""
ABVTrends - Scraper Logger

Per-distributor logging system for monitoring scraper health and issues.
Each distributor gets its own log file for easy debugging.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import settings

# Log directory
LOG_DIR = Path(settings.model_storage_path).parent / "logs" / "scrapers"


def setup_scraper_logging() -> None:
    """Initialize the scraper logging directory."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_scraper_logger(distributor_slug: str) -> logging.Logger:
    """
    Get a logger for a specific distributor.

    Each distributor gets:
    - Its own log file: logs/scrapers/{distributor}.log
    - Timestamped entries with log level
    - Automatic rotation when file gets large

    Args:
        distributor_slug: The distributor identifier (e.g., 'libdib', 'provi')

    Returns:
        Logger configured for that distributor
    """
    # Create logs directory if needed
    setup_scraper_logging()

    # Create a unique logger for this distributor
    logger_name = f"scraper.{distributor_slug}"
    logger = logging.getLogger(logger_name)

    # Only add handlers if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # File handler for this distributor
        log_file = LOG_DIR / f"{distributor_slug}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Detailed format for files
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)

        # Simpler format for console
        console_formatter = logging.Formatter(
            f"[{distributor_slug.upper()}] %(levelname)s: %(message)s"
        )
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Prevent propagation to root logger (avoid duplicate logs)
        logger.propagate = False

    return logger


class ScraperLogContext:
    """
    Context manager for tracking a scraping session.

    Usage:
        with ScraperLogContext("libdib") as log:
            log.start_session()
            log.info("Authenticating...")
            log.products_scraped(50)
            log.error("Rate limited", retry_in=30)
    """

    def __init__(self, distributor_slug: str):
        self.slug = distributor_slug
        self.logger = get_scraper_logger(distributor_slug)
        self.session_start: Optional[datetime] = None
        self.products_count = 0
        self.errors_count = 0

    def __enter__(self) -> "ScraperLogContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.error(f"Session crashed: {exc_val}")
        self.end_session()

    def start_session(self, batch_size: int = 0, offset: int = 0) -> None:
        """Log the start of a scraping session."""
        self.session_start = datetime.utcnow()
        self.products_count = 0
        self.errors_count = 0
        self.logger.info("=" * 60)
        self.logger.info(f"SESSION START | batch={batch_size} offset={offset}")

    def end_session(self) -> None:
        """Log the end of a scraping session."""
        if self.session_start:
            duration = (datetime.utcnow() - self.session_start).total_seconds()
            self.logger.info(
                f"SESSION END | products={self.products_count} "
                f"errors={self.errors_count} duration={duration:.1f}s"
            )
            self.logger.info("=" * 60)

    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(f"WARNING: {message}")

    def error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message."""
        self.errors_count += 1
        if exception:
            self.logger.error(f"ERROR: {message}", exc_info=exception)
        else:
            self.logger.error(f"ERROR: {message}")

    def auth_success(self) -> None:
        """Log successful authentication."""
        self.logger.info("AUTH: Success")

    def auth_failed(self, reason: str) -> None:
        """Log failed authentication."""
        self.errors_count += 1
        self.logger.error(f"AUTH FAILED: {reason}")

    def products_scraped(self, count: int, category: Optional[str] = None) -> None:
        """Log products scraped."""
        self.products_count += count
        cat_info = f" category={category}" if category else ""
        self.logger.info(f"SCRAPED: {count} products{cat_info} (total: {self.products_count})")

    def rate_limited(self, wait_seconds: int) -> None:
        """Log rate limiting."""
        self.logger.warning(f"RATE LIMITED: waiting {wait_seconds}s")

    def page_fetched(self, page: int, items: int) -> None:
        """Log page fetch."""
        self.logger.debug(f"PAGE {page}: {items} items")

    def noise_action(self, action_type: str) -> None:
        """Log noise action."""
        self.logger.debug(f"NOISE: {action_type}")

    def budget_status(self, scraped: int, limit: int) -> None:
        """Log daily budget status."""
        remaining = limit - scraped
        pct = (scraped / limit) * 100 if limit > 0 else 0
        self.logger.info(f"BUDGET: {scraped}/{limit} ({pct:.0f}%) - {remaining} remaining")


def get_recent_logs(distributor_slug: str, lines: int = 100) -> list[str]:
    """
    Get recent log entries for a distributor.

    Args:
        distributor_slug: The distributor identifier
        lines: Number of recent lines to return

    Returns:
        List of recent log lines
    """
    log_file = LOG_DIR / f"{distributor_slug}.log"

    if not log_file.exists():
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
        return all_lines[-lines:]


def get_error_summary() -> dict[str, dict]:
    """
    Get error summary across all distributors.

    Returns:
        Dict with error counts and recent errors per distributor
    """
    setup_scraper_logging()
    summary = {}

    for log_file in LOG_DIR.glob("*.log"):
        slug = log_file.stem
        errors = []
        error_count = 0

        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if "ERROR" in line or "FAILED" in line:
                    error_count += 1
                    errors.append(line.strip())

        summary[slug] = {
            "error_count": error_count,
            "recent_errors": errors[-5:],  # Last 5 errors
            "log_file": str(log_file),
        }

    return summary


def clear_old_logs(days: int = 7) -> int:
    """
    Clear log entries older than specified days.

    Args:
        days: Keep logs from last N days

    Returns:
        Number of files cleaned
    """
    import time

    setup_scraper_logging()
    cleaned = 0
    cutoff = time.time() - (days * 24 * 60 * 60)

    for log_file in LOG_DIR.glob("*.log"):
        if log_file.stat().st_mtime < cutoff:
            # Archive old file
            archive_name = f"{log_file.stem}_{datetime.now().strftime('%Y%m%d')}.log.old"
            log_file.rename(LOG_DIR / archive_name)
            cleaned += 1

    return cleaned
