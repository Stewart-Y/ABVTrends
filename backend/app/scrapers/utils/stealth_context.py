"""
Stealth Browser Context Factory

Creates browser contexts with anti-detection measures to avoid CAPTCHA triggers
and bot detection on distributor websites.

Uses playwright-stealth to patch browser fingerprints and applies human-like
browser configurations.
"""

import random
import logging
from typing import Optional, Any
from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# Try to import playwright-stealth, fall back gracefully if not installed
# Note: playwright-stealth 2.0.0+ uses Stealth class instead of stealth_async
STEALTH_AVAILABLE = False
STEALTH_INSTANCE = None
try:
    from playwright_stealth import Stealth
    # Create a single Stealth instance with optimal settings
    STEALTH_INSTANCE = Stealth(
        # Enable all anti-detection features
        navigator_webdriver=True,  # Hide navigator.webdriver
        chrome_app=True,
        chrome_csi=True,
        chrome_load_times=True,
        chrome_runtime=True,  # Enable chrome.runtime spoofing
        navigator_plugins=True,
        navigator_languages=True,
        navigator_platform=True,
        navigator_vendor=True,
        navigator_permissions=True,
        navigator_hardware_concurrency=True,
        webgl_vendor=True,
        media_codecs=True,
        hairline=True,
        iframe_content_window=True,
        sec_ch_ua=True,
    )
    STEALTH_AVAILABLE = True
    logger.info("playwright-stealth 2.0 initialized with anti-detection features")
except ImportError:
    logger.warning(
        "playwright-stealth not installed. Install with: pip install playwright-stealth"
    )


class StealthContextFactory:
    """Factory for creating stealth browser contexts with anti-detection measures."""

    # Common desktop viewports (realistic distribution)
    VIEWPORTS = [
        {"width": 1920, "height": 1080},  # Full HD - most common
        {"width": 1440, "height": 900},   # MacBook Pro 15"
        {"width": 1536, "height": 864},   # Windows laptop
        {"width": 1366, "height": 768},   # Common laptop
        {"width": 2560, "height": 1440},  # QHD monitor
    ]

    # Realistic user agents (Chrome on Windows/Mac - 2024/2025 versions)
    USER_AGENTS = [
        # Chrome 120+ on Windows 10/11
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        # Chrome 120+ on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

    # Common timezones for US-based scrapers
    TIMEZONES = [
        "America/Los_Angeles",
        "America/Denver",
        "America/Chicago",
        "America/New_York",
    ]

    @classmethod
    async def create_context(
        cls,
        browser: Browser,
        storage_state: Optional[str] = None,
        viewport: Optional[dict] = None,
        user_agent: Optional[str] = None,
        timezone_id: Optional[str] = None,
        locale: str = "en-US",
        **extra_context_options: Any,
    ) -> BrowserContext:
        """
        Create a stealth browser context with anti-detection measures.

        Args:
            browser: Playwright browser instance
            storage_state: Path to storage state JSON or dict
            viewport: Custom viewport (random if not specified)
            user_agent: Custom user agent (random if not specified)
            timezone_id: Custom timezone (random US if not specified)
            locale: Browser locale (default: en-US)
            **extra_context_options: Additional options passed to new_context()

        Returns:
            BrowserContext with stealth patches applied
        """
        # Select random or use provided values
        selected_viewport = viewport or random.choice(cls.VIEWPORTS)
        selected_user_agent = user_agent or random.choice(cls.USER_AGENTS)
        selected_timezone = timezone_id or random.choice(cls.TIMEZONES)

        logger.debug(
            f"Creating stealth context: viewport={selected_viewport}, "
            f"timezone={selected_timezone}"
        )

        # Build context options
        context_options = {
            "viewport": selected_viewport,
            "user_agent": selected_user_agent,
            "locale": locale,
            "timezone_id": selected_timezone,
            # Additional anti-detection settings
            "java_script_enabled": True,
            "bypass_csp": False,
            "ignore_https_errors": False,
            # Geolocation based on timezone (approximate US locations)
            "geolocation": cls._get_geolocation_for_timezone(selected_timezone),
            "permissions": ["geolocation"],
        }

        # Add storage state if provided
        if storage_state:
            context_options["storage_state"] = storage_state

        # Merge with extra options
        context_options.update(extra_context_options)

        # Create context
        context = await browser.new_context(**context_options)

        # Apply stealth patches if available
        if STEALTH_AVAILABLE and STEALTH_INSTANCE:
            try:
                await STEALTH_INSTANCE.apply_stealth_async(context)
                logger.debug("Applied playwright-stealth 2.0 patches to context")
            except Exception as e:
                logger.warning(f"Failed to apply stealth patches: {e}")
                # Fall back to manual stealth
                await cls._apply_manual_stealth(context)
        else:
            # Manual stealth measures as fallback
            await cls._apply_manual_stealth(context)

        return context

    @classmethod
    async def apply_stealth_to_page(cls, page: Page) -> None:
        """
        Apply additional stealth measures to an individual page.

        Call this after navigating to a new page for extra protection.
        """
        try:
            # Override navigator.webdriver
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Override chrome.runtime for headless detection
            await page.add_init_script("""
                window.chrome = {
                    runtime: {}
                };
            """)

            # Override permissions query
            await page.add_init_script("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            logger.debug("Applied page-level stealth scripts")
        except Exception as e:
            logger.warning(f"Failed to apply page stealth scripts: {e}")

    @classmethod
    async def _apply_manual_stealth(cls, context: BrowserContext) -> None:
        """Apply manual stealth measures when playwright-stealth is not available."""
        try:
            # Add init script to hide webdriver
            await context.add_init_script("""
                // Hide webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ]
                });

                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Fix permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            logger.debug("Applied manual stealth scripts (fallback)")
        except Exception as e:
            logger.warning(f"Failed to apply manual stealth scripts: {e}")

    @classmethod
    def _get_geolocation_for_timezone(cls, timezone: str) -> dict:
        """Get approximate geolocation coordinates for a timezone."""
        # Approximate city centers for common US timezones
        locations = {
            "America/Los_Angeles": {"latitude": 34.0522, "longitude": -118.2437},  # LA
            "America/Denver": {"latitude": 39.7392, "longitude": -104.9903},       # Denver
            "America/Chicago": {"latitude": 41.8781, "longitude": -87.6298},       # Chicago
            "America/New_York": {"latitude": 40.7128, "longitude": -74.0060},      # NYC
        }
        return locations.get(timezone, locations["America/Los_Angeles"])


async def create_stealth_context(
    browser: Browser,
    storage_state: Optional[str] = None,
    **kwargs: Any,
) -> BrowserContext:
    """
    Convenience function to create a stealth browser context.

    This is a shortcut for StealthContextFactory.create_context().
    """
    return await StealthContextFactory.create_context(
        browser=browser,
        storage_state=storage_state,
        **kwargs,
    )
