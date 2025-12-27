"""
ABVTrends - Stealth Scraper Service

Orchestrates distributor scraping with human-like behavior to avoid detection.
Features:
- Daily budget tracking per distributor
- Random delays between requests (3-8 seconds)
- "Noise" actions (homepage visits, random product clicks, idle pauses)
- Round-robin scheduling across distributors
- Business hours only (8 AM - 6 PM PT, weekdays)
- Per-distributor logging for issue tracking
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
from app.services.scraper_logger import ScraperLogContext, get_scraper_logger
from app.services.discord_notifier import get_discord_notifier
from app.services.data_pipeline import DataPipeline

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

        # Use per-distributor logging
        with ScraperLogContext(distributor_slug) as log:
            # Check business hours
            if not self.is_business_hours():
                log.info("Skipping: Outside business hours")
                return []

            # Get current state
            state = await self.get_state(distributor_slug)

            # Check daily budget
            if state.items_scraped >= state.daily_limit:
                log.budget_status(state.items_scraped, state.daily_limit)
                log.info("Skipping: Daily limit reached")
                return []

            # Calculate how many items we can scrape
            remaining_budget = state.daily_limit - state.items_scraped
            items_to_scrape = min(batch_size, remaining_budget)

            # Start session logging
            log.start_session(batch_size=items_to_scrape, offset=state.last_offset)
            log.budget_status(state.items_scraped, state.daily_limit)

            # Get scraper class and credentials
            scraper_class = DISTRIBUTOR_SCRAPERS.get(distributor_slug)
            if not scraper_class:
                log.error(f"Unknown distributor: {distributor_slug}")
                return []

            credentials = self._get_credentials(distributor_slug)
            if not credentials:
                log.error("No credentials configured")
                return []

            products: list[RawProduct] = []

            try:
                scraper = scraper_class(credentials)

                # Authenticate
                log.info("Authenticating...")
                if not await scraper.authenticate():
                    log.auth_failed("Authentication returned False")
                    # Discord notification for auth failure
                    discord = get_discord_notifier()
                    await discord.auth_failed(distributor_slug, "Authentication returned False")
                    return []
                log.auth_success()

                # Discord notification - scraper is now running
                discord = get_discord_notifier()
                await discord.scraper_running(
                    distributor=distributor_slug,
                    batch_size=items_to_scrape,
                    offset=state.last_offset,
                    budget_used=state.items_scraped,
                    budget_limit=state.daily_limit,
                )

                # Maybe start with noise (20% chance)
                if self.should_do_noise():
                    log.noise_action("pre-scrape browsing")
                    await self.perform_noise_action(scraper)
                    await self.random_delay()

                # Get categories for rotation
                categories = await scraper.get_categories()
                if categories:
                    # Rotate through categories
                    cat_index = state.sessions_today % len(categories)
                    category = categories[cat_index]
                    category_id = category.get("id") or category.get("slug")
                    log.info(f"Category: {category_id} (session {state.sessions_today + 1})")
                else:
                    category_id = None
                    log.info("No categories - fetching all products")

                # Scrape with stealth delays
                log.info(f"Fetching up to {items_to_scrape} products from offset {state.last_offset}...")
                products = await scraper.get_products(
                    category=category_id,
                    limit=items_to_scrape,
                    offset=state.last_offset,
                )

                log.products_scraped(len(products), category_id)

                # Store products in database via pipeline
                if products:
                    async with get_db_context() as db:
                        pipeline = DataPipeline(db)
                        pipeline_stats = await pipeline.process_raw_products(
                            products=products,
                            distributor_slug=distributor_slug,
                        )
                        log.info(
                            f"Pipeline: {pipeline_stats.products_matched} matched, "
                            f"{pipeline_stats.products_created} new, "
                            f"{pipeline_stats.price_records} prices"
                        )

                # Random noise actions during scraping
                if self.should_do_noise() and len(products) > 5:
                    log.noise_action("mid-scrape idle")
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

                log.budget_status(new_total, state.daily_limit)

                # Discord notification for session complete
                discord = get_discord_notifier()
                await discord.session_complete(
                    distributor=distributor_slug,
                    products=len(products),
                    total_today=new_total,
                    daily_limit=state.daily_limit,
                )

                # Check if budget exhausted
                if new_total >= state.daily_limit:
                    await discord.budget_exhausted(distributor_slug)

            except Exception as e:
                log.error(f"Scrape failed: {str(e)}", exception=e)
                # Discord notification for error
                discord = get_discord_notifier()
                await discord.scraper_error(
                    distributor=distributor_slug,
                    error=str(e),
                    context={"offset": state.last_offset, "category": state.last_category},
                )

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


async def run_test_scrape(
    items_per_distributor: int = 10,
    distributors: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Run a test scrape for all distributors with Discord notifications.

    This bypasses business hours checks and stealth delays for quick testing.
    Sends notifications:
    - When test starts (all scrapers)
    - When each scraper fails (individual errors)
    - Final summary with results per distributor

    Args:
        items_per_distributor: Number of items to scrape per distributor (default: 10)
        distributors: List of distributor slugs (default: all 7)

    Returns:
        Dict with results per distributor and summary
    """
    discord = get_discord_notifier()
    distributors = distributors or DISTRIBUTOR_SLUGS

    logger.info(f"=== TEST SCRAPE STARTING ===")
    logger.info(f"Distributors: {distributors}")
    logger.info(f"Items per distributor: {items_per_distributor}")

    # 1. Send START notification
    await discord.send(
        title="🧪 Test Scrape Started",
        description=f"Running test scrape for **{len(distributors)}** distributors",
        color=0x5865F2,  # Blurple
        fields=[
            {"name": "Distributors", "value": ", ".join(d.upper() for d in distributors), "inline": False},
            {"name": "Items Each", "value": str(items_per_distributor), "inline": True},
            {"name": "Total Target", "value": str(len(distributors) * items_per_distributor), "inline": True},
        ],
        footer="ABVTrends Test Run",
    )

    # Create a test config that bypasses business hours
    test_config = StealthConfig(
        daily_limit=items_per_distributor,
        batch_size=items_per_distributor,
        min_delay=1.0,  # Faster delays for testing
        max_delay=2.0,
        noise_ratio=0.0,  # No noise for testing
        business_hours_start=0,  # Always in business hours
        business_hours_end=24,
        skip_weekends=False,  # Don't skip weekends
    )

    scraper = StealthScraper(config=test_config)

    # 2. Run each scraper and collect results
    results: dict[str, dict[str, Any]] = {}
    total_scraped = 0
    total_errors = 0
    start_time = datetime.utcnow()

    for slug in distributors:
        logger.info(f"\n--- Testing {slug.upper()} ---")

        try:
            # Get scraper class and credentials
            scraper_class = DISTRIBUTOR_SCRAPERS.get(slug)
            if not scraper_class:
                error_msg = f"Unknown distributor: {slug}"
                logger.error(error_msg)
                results[slug] = {"success": False, "error": error_msg, "products": 0}
                total_errors += 1
                await discord.scraper_error(slug, error_msg)
                continue

            credentials = scraper._get_credentials(slug)
            if not credentials:
                error_msg = "No credentials configured"
                logger.error(f"{slug}: {error_msg}")
                results[slug] = {"success": False, "error": error_msg, "products": 0}
                total_errors += 1
                await discord.scraper_error(slug, error_msg)
                continue

            # Create scraper instance
            scraper_instance = scraper_class(credentials)

            # Authenticate
            logger.info(f"{slug}: Authenticating...")
            if not await scraper_instance.authenticate():
                error_msg = "Authentication failed"
                logger.error(f"{slug}: {error_msg}")
                results[slug] = {"success": False, "error": error_msg, "products": 0}
                total_errors += 1
                await discord.auth_failed(slug, "Authentication returned False")
                continue

            logger.info(f"{slug}: ✓ Authenticated")

            # Scrape products
            logger.info(f"{slug}: Fetching up to {items_per_distributor} products...")
            products = await scraper_instance.get_products(limit=items_per_distributor)

            product_count = len(products) if products else 0
            logger.info(f"{slug}: ✓ Scraped {product_count} products")

            # Store products in database via pipeline
            if products:
                async with get_db_context() as db:
                    pipeline = DataPipeline(db)
                    pipeline_stats = await pipeline.process_raw_products(
                        products=products,
                        distributor_slug=slug,
                    )
                    logger.info(
                        f"{slug}: Pipeline - {pipeline_stats.products_matched} matched, "
                        f"{pipeline_stats.products_created} new"
                    )

            results[slug] = {
                "success": True,
                "products": product_count,
                "error": None,
            }
            total_scraped += product_count

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"{slug}: Scrape failed - {error_msg}")
            results[slug] = {"success": False, "error": error_msg, "products": 0}
            total_errors += 1

            # 3. Send FAILURE notification for this scraper
            await discord.scraper_error(
                distributor=slug,
                error=error_msg,
                context={"test_run": True},
            )

        # Small delay between distributors
        if slug != distributors[-1]:
            await asyncio.sleep(2)

    # Calculate duration
    duration = (datetime.utcnow() - start_time).total_seconds()

    # 4. Send SUMMARY notification
    breakdown_lines = []
    for slug, data in results.items():
        if data["success"]:
            breakdown_lines.append(f"✅ **{slug.upper()}**: {data['products']} products")
        else:
            breakdown_lines.append(f"❌ **{slug.upper()}**: Failed - {data['error'][:50]}")

    success_count = sum(1 for r in results.values() if r["success"])
    color = 0x57F287 if total_errors == 0 else (0xFEE75C if success_count > 0 else 0xED4245)

    await discord.send(
        title="🧪 Test Scrape Complete",
        description="\n".join(breakdown_lines),
        color=color,
        fields=[
            {"name": "Total Products", "value": str(total_scraped), "inline": True},
            {"name": "Successful", "value": f"{success_count}/{len(distributors)}", "inline": True},
            {"name": "Duration", "value": f"{duration:.0f}s", "inline": True},
        ],
        footer=f"ABVTrends Test Run • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    )

    logger.info(f"\n=== TEST SCRAPE COMPLETE ===")
    logger.info(f"Total: {total_scraped} products from {success_count}/{len(distributors)} distributors")
    logger.info(f"Duration: {duration:.0f}s")

    return {
        "results": results,
        "total_scraped": total_scraped,
        "successful_count": success_count,
        "error_count": total_errors,
        "duration_seconds": duration,
    }
