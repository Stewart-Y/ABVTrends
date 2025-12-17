"""
ABVTrends - Stealth Scraper Service

Orchestrates distributor scraping with human-like behavior to avoid detection.
Features:
- Daily budget tracking per distributor
- Random delays between requests (3-8 seconds)
- "Noise" actions (homepage visits, random product clicks, idle pauses)
- Round-robin scheduling across distributors
- Business hours only (8 AM - 6 PM PT, weekdays)
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db_context
from app.scrapers.distributors import DISTRIBUTOR_SCRAPERS, RawProduct

logger = logging.getLogger(__name__)

# Pacific timezone for business hours
PT = ZoneInfo("America/Los_Angeles")

# All available distributors
DISTRIBUTOR_SLUGS = list(DISTRIBUTOR_SCRAPERS.keys())


@dataclass
class ScraperState:
    """State for a single distributor's scraping progress."""

    distributor_slug: str
    date: date
    items_scraped: int = 0
    daily_limit: int = 150
    last_offset: int = 0
    last_category: Optional[str] = None
    last_session_at: Optional[datetime] = None
    sessions_today: int = 0


@dataclass
class StealthConfig:
    """Configuration for stealth scraping behavior."""

    daily_limit: int = 150
    batch_size: int = 20
    min_delay: float = 3.0
    max_delay: float = 8.0
    noise_ratio: float = 0.15
    business_hours_start: int = 8
    business_hours_end: int = 18
    skip_weekends: bool = True

    @classmethod
    def from_settings(cls) -> "StealthConfig":
        """Create config from app settings."""
        return cls(
            daily_limit=settings.scraper_daily_limit_per_source,
            batch_size=settings.scraper_batch_size,
            min_delay=settings.scraper_min_delay_seconds,
            max_delay=settings.scraper_max_delay_seconds,
            noise_ratio=settings.scraper_noise_ratio,
            business_hours_start=settings.scraper_business_hours_start,
            business_hours_end=settings.scraper_business_hours_end,
            skip_weekends=settings.scraper_skip_weekends,
        )


class StealthScraper:
    """
    Stealth scraper orchestrator.

    Manages scraping across multiple distributors with human-like behavior
    to minimize detection risk.
    """

    def __init__(self, config: Optional[StealthConfig] = None):
        self.config = config or StealthConfig.from_settings()

    def is_business_hours(self) -> bool:
        """Check if current time is within business hours (PT)."""
        now_pt = datetime.now(PT)

        # Skip weekends
        if self.config.skip_weekends and now_pt.weekday() >= 5:
            logger.debug("Skipping: Weekend")
            return False

        # Check business hours
        hour = now_pt.hour
        if hour < self.config.business_hours_start or hour >= self.config.business_hours_end:
            logger.debug(f"Skipping: Outside business hours ({hour})")
            return False

        return True

    async def get_state(self, distributor_slug: str) -> ScraperState:
        """Get or create scraping state for a distributor."""
        today = date.today()

        async with get_db_context() as db:
            result = await db.execute(
                text("""
                    SELECT distributor_slug, date, items_scraped, daily_limit,
                           last_offset, last_category, last_session_at, sessions_today
                    FROM scraper_state
                    WHERE distributor_slug = :slug AND date = :date
                """),
                {"slug": distributor_slug, "date": today}
            )
            row = result.fetchone()

            if row:
                return ScraperState(
                    distributor_slug=row[0],
                    date=row[1],
                    items_scraped=row[2],
                    daily_limit=row[3],
                    last_offset=row[4],
                    last_category=row[5],
                    last_session_at=row[6],
                    sessions_today=row[7],
                )

        # Return new state for today
        return ScraperState(
            distributor_slug=distributor_slug,
            date=today,
            daily_limit=self.config.daily_limit,
        )

    async def update_state(
        self,
        distributor_slug: str,
        items_scraped: int,
        last_offset: int,
        last_category: Optional[str] = None,
    ) -> None:
        """Update scraping state after a session."""
        today = date.today()
        now = datetime.utcnow()

        async with get_db_context() as db:
            # Upsert state using PostgreSQL ON CONFLICT
            await db.execute(
                text("""
                    INSERT INTO scraper_state
                        (distributor_slug, date, items_scraped, daily_limit,
                         last_offset, last_category, last_session_at, sessions_today)
                    VALUES (:slug, :date, :items, :limit, :offset, :category, :session_at, 1)
                    ON CONFLICT (distributor_slug, date) DO UPDATE SET
                        items_scraped = :items,
                        last_offset = :offset,
                        last_category = :category,
                        last_session_at = :session_at,
                        sessions_today = scraper_state.sessions_today + 1,
                        updated_at = NOW()
                """),
                {
                    "slug": distributor_slug,
                    "date": today,
                    "items": items_scraped,
                    "limit": self.config.daily_limit,
                    "offset": last_offset,
                    "category": last_category,
                    "session_at": now,
                }
            )

    async def random_delay(self) -> None:
        """Wait a random human-like delay between requests."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        logger.debug(f"Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)

    async def perform_noise_action(self, scraper: Any) -> None:
        """
        Perform a random "noise" action to simulate human browsing.

        Actions:
        - Visit homepage
        - Browse a random category
        - Idle pause (reading)
        """
        actions = [
            ("homepage", self._noise_visit_homepage),
            ("category", self._noise_browse_category),
            ("idle", self._noise_idle_pause),
        ]

        action_name, action_fn = random.choice(actions)
        logger.debug(f"Noise action: {action_name}")

        try:
            await action_fn(scraper)
        except Exception as e:
            logger.debug(f"Noise action failed (expected): {e}")

    async def _noise_visit_homepage(self, scraper: Any) -> None:
        """Visit the distributor's homepage."""
        if hasattr(scraper, "base_url") and hasattr(scraper, "session"):
            try:
                await scraper.session.get(scraper.base_url)
                await asyncio.sleep(random.uniform(2, 5))
            except Exception:
                pass  # Noise actions can fail silently

    async def _noise_browse_category(self, scraper: Any) -> None:
        """Browse a random category without scraping."""
        if hasattr(scraper, "get_categories"):
            try:
                categories = await scraper.get_categories()
                if categories:
                    random.choice(categories)
                    await asyncio.sleep(random.uniform(3, 8))
            except Exception:
                pass

    async def _noise_idle_pause(self, scraper: Any) -> None:
        """Simulate reading/idle time."""
        await asyncio.sleep(random.uniform(10, 30))

    def should_do_noise(self) -> bool:
        """Randomly decide if we should do a noise action."""
        return random.random() < self.config.noise_ratio

    async def scrape_distributor(
        self,
        distributor_slug: str,
        batch_size: Optional[int] = None,
    ) -> list[RawProduct]:
        """
        Scrape products from a single distributor with stealth behavior.

        Args:
            distributor_slug: Which distributor to scrape
            batch_size: Override default batch size

        Returns:
            List of scraped products
        """
        batch_size = batch_size or self.config.batch_size

        # Check business hours
        if not self.is_business_hours():
            logger.info(f"Skipping {distributor_slug}: Outside business hours")
            return []

        # Get current state
        state = await self.get_state(distributor_slug)

        # Check daily budget
        if state.items_scraped >= state.daily_limit:
            logger.info(
                f"Skipping {distributor_slug}: Daily limit reached "
                f"({state.items_scraped}/{state.daily_limit})"
            )
            return []

        # Calculate how many items we can scrape
        remaining_budget = state.daily_limit - state.items_scraped
        items_to_scrape = min(batch_size, remaining_budget)

        logger.info(
            f"Starting stealth scrape: {distributor_slug} "
            f"(batch={items_to_scrape}, offset={state.last_offset}, "
            f"budget={remaining_budget}/{state.daily_limit})"
        )

        # Get scraper class and credentials
        scraper_class = DISTRIBUTOR_SCRAPERS.get(distributor_slug)
        if not scraper_class:
            logger.error(f"Unknown distributor: {distributor_slug}")
            return []

        credentials = self._get_credentials(distributor_slug)
        if not credentials:
            logger.error(f"No credentials for: {distributor_slug}")
            return []

        products: list[RawProduct] = []

        try:
            scraper = scraper_class(credentials)

            # Authenticate
            if not await scraper.authenticate():
                logger.error(f"Authentication failed: {distributor_slug}")
                return []

            # Maybe start with noise (20% chance)
            if self.should_do_noise():
                await self.perform_noise_action(scraper)
                await self.random_delay()

            # Get categories for rotation
            categories = await scraper.get_categories()
            if categories:
                # Rotate through categories
                cat_index = state.sessions_today % len(categories)
                category = categories[cat_index]
                category_id = category.get("id") or category.get("slug")
            else:
                category_id = None

            # Scrape with stealth delays
            products = await scraper.get_products(
                category=category_id,
                limit=items_to_scrape,
                offset=state.last_offset,
            )

            # Random noise actions during scraping
            if self.should_do_noise() and len(products) > 5:
                await self.perform_noise_action(scraper)

            # Update state
            new_offset = state.last_offset + len(products)
            new_total = state.items_scraped + len(products)

            await self.update_state(
                distributor_slug=distributor_slug,
                items_scraped=new_total,
                last_offset=new_offset,
                last_category=category_id,
            )

            logger.info(
                f"Completed stealth scrape: {distributor_slug} "
                f"({len(products)} products, total today: {new_total})"
            )

        except Exception as e:
            logger.error(f"Stealth scrape failed for {distributor_slug}: {e}")

        return products

    async def scrape_round_robin(
        self,
        distributors: Optional[list[str]] = None,
        batch_size: Optional[int] = None,
    ) -> dict[str, list[RawProduct]]:
        """
        Scrape from multiple distributors in round-robin fashion.

        Args:
            distributors: List of distributor slugs (default: all)
            batch_size: Items per distributor

        Returns:
            Dict mapping distributor slug to products
        """
        distributors = distributors or DISTRIBUTOR_SLUGS
        batch_size = batch_size or self.config.batch_size

        results: dict[str, list[RawProduct]] = {}

        for slug in distributors:
            # Check if still in business hours
            if not self.is_business_hours():
                logger.info("Round-robin stopped: Outside business hours")
                break

            # Scrape this distributor
            products = await self.scrape_distributor(slug, batch_size)
            results[slug] = products

            # Delay between distributors
            if slug != distributors[-1]:  # Not the last one
                delay = random.uniform(60, 180)  # 1-3 minutes between distributors
                logger.info(f"Waiting {delay:.0f}s before next distributor...")
                await asyncio.sleep(delay)

        return results

    async def get_daily_stats(self) -> dict[str, dict[str, Any]]:
        """Get today's scraping statistics for all distributors."""
        stats = {}

        for slug in DISTRIBUTOR_SLUGS:
            state = await self.get_state(slug)
            stats[slug] = {
                "items_scraped": state.items_scraped,
                "daily_limit": state.daily_limit,
                "remaining": state.daily_limit - state.items_scraped,
                "sessions": state.sessions_today,
                "last_offset": state.last_offset,
                "last_category": state.last_category,
                "last_session": state.last_session_at.isoformat() if state.last_session_at else None,
            }

        return stats

    def _get_credentials(self, distributor_slug: str) -> Optional[dict[str, Any]]:
        """Get credentials for a distributor from settings."""
        cred_map = {
            "libdib": {
                "email": settings.libdib_email,
                "password": settings.libdib_password,
                "entity_slug": settings.libdib_entity_slug,
                "session_id": settings.libdib_session_id,
                "csrf_token": settings.libdib_csrf_token,
            },
            "sgws": {
                "email": settings.sgws_email,
                "password": settings.sgws_password,
                "account_id": settings.sgws_account_id,
            },
            "rndc": {
                "email": settings.rndc_email,
                "password": settings.rndc_password,
                "account_id": settings.rndc_account_id,
            },
            "sipmarket": {
                "email": settings.sipmarket_email,
                "password": settings.sipmarket_password,
            },
            "parkstreet": {
                "email": settings.parkstreet_email,
                "password": settings.parkstreet_password,
            },
            "breakthru": {
                "email": settings.breakthru_email,
                "password": settings.breakthru_password,
            },
            "provi": {
                "email": settings.provi_email,
                "password": settings.provi_password,
            },
        }

        creds = cred_map.get(distributor_slug)
        if not creds:
            return None

        # Check if required credentials are present
        if not creds.get("email") or not creds.get("password"):
            return None

        return creds


# Singleton instance
stealth_scraper = StealthScraper()


async def run_stealth_session(
    distributors: Optional[list[str]] = None,
    batch_size: Optional[int] = None,
) -> dict[str, list[RawProduct]]:
    """
    Run a single stealth scraping session.

    This is the main entry point for scheduled scraping tasks.

    Args:
        distributors: List of distributor slugs to scrape (default: 2 random)
        batch_size: Items per distributor (default: from config)

    Returns:
        Dict mapping distributor slug to scraped products
    """
    scraper = StealthScraper()

    # If no distributors specified, pick 2 random ones
    if distributors is None:
        distributors = random.sample(DISTRIBUTOR_SLUGS, min(2, len(DISTRIBUTOR_SLUGS)))

    logger.info(f"Starting stealth session: {distributors}")

    return await scraper.scrape_round_robin(distributors, batch_size)


async def get_scraper_stats() -> dict[str, dict[str, Any]]:
    """Get current scraping statistics."""
    scraper = StealthScraper()
    return await scraper.get_daily_stats()
