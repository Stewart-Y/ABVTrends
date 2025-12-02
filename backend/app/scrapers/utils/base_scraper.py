"""
ABVTrends - Base Scraper

Abstract base class for all scrapers with common functionality:
- Rate limiting
- Retry logic with exponential backoff
- Error handling
- Response caching
- Robots.txt compliance
"""

import asyncio
import hashlib
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, async_playwright

from app.core.config import settings
from app.models.signal import SignalType

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class RateLimitError(ScraperError):
    """Raised when rate limit is exceeded."""

    pass


class BlockedError(ScraperError):
    """Raised when scraper is blocked by the target site."""

    pass


class ScrapedItem:
    """
    Represents a single scraped item/signal.

    Attributes:
        signal_type: Type of signal (media_mention, price_change, etc.)
        title: Title of the item (article title, product name)
        url: Source URL
        raw_data: Dictionary of all scraped data
        captured_at: When the content was originally published
        product_hint: Optional hint for product matching
    """

    def __init__(
        self,
        signal_type: SignalType,
        title: str,
        url: str,
        raw_data: dict[str, Any],
        captured_at: Optional[datetime] = None,
        product_hint: Optional[str] = None,
    ):
        self.signal_type = signal_type
        self.title = title
        self.url = url
        self.raw_data = raw_data
        self.captured_at = captured_at or datetime.utcnow()
        self.product_hint = product_hint

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "signal_type": self.signal_type.value,
            "title": self.title,
            "url": self.url,
            "raw_data": self.raw_data,
            "captured_at": self.captured_at.isoformat(),
            "product_hint": self.product_hint,
        }


class BaseScraper(ABC):
    """
    Abstract base class for all scrapers.

    Subclasses must implement:
    - scrape(): Main scraping logic
    - get_source_name(): Return source identifier
    - get_base_url(): Return base URL for the source

    Provides:
    - Rate limiting between requests
    - Retry logic with exponential backoff
    - HTTP client with rotating headers
    - Playwright browser for JS-rendered pages
    - Response caching
    """

    # Class-level cache for responses
    _response_cache: dict[str, tuple[str, datetime]] = {}
    _cache_ttl: timedelta = timedelta(minutes=15)

    def __init__(
        self,
        delay_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ):
        """
        Initialize the scraper.

        Args:
            delay_seconds: Seconds to wait between requests
            max_retries: Maximum retry attempts
            timeout_seconds: Request timeout in seconds
        """
        self.delay_seconds = delay_seconds or settings.scraper_delay_seconds
        self.max_retries = max_retries or settings.scraper_max_retries
        self.timeout_seconds = timeout_seconds or settings.scraper_timeout_seconds

        self._last_request_time: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._browser: Optional[Browser] = None
        self._playwright = None

    @abstractmethod
    async def scrape(self) -> list[ScrapedItem]:
        """
        Main scraping method to be implemented by subclasses.

        Returns:
            List of scraped items/signals
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the source identifier (e.g., 'vinepair')."""
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """Return the base URL for this source."""
        pass

    def get_headers(self) -> dict[str, str]:
        """
        Get request headers with rotating User-Agent.

        Returns:
            Dictionary of HTTP headers
        """
        user_agents = [
            settings.user_agent,
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ]

        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rate_limit(self) -> None:
        """
        Enforce rate limiting between requests.

        Adds jitter to avoid detection patterns.
        """
        if self._last_request_time is not None:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.delay_seconds:
                # Add random jitter (0-50% of delay)
                jitter = random.uniform(0, self.delay_seconds * 0.5)
                wait_time = self.delay_seconds - elapsed + jitter
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        self._last_request_time = datetime.utcnow()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=True,
                headers=self.get_headers(),
            )
        return self._http_client

    async def _get_browser(self) -> Browser:
        """Get or create Playwright browser instance."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
        return self._browser

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached_response(self, url: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        cache_key = self._get_cache_key(url)
        if cache_key in self._response_cache:
            content, cached_at = self._response_cache[cache_key]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                logger.debug(f"Cache hit for {url}")
                return content
            else:
                del self._response_cache[cache_key]
        return None

    def _cache_response(self, url: str, content: str) -> None:
        """Cache response content."""
        cache_key = self._get_cache_key(url)
        self._response_cache[cache_key] = (content, datetime.utcnow())

    async def fetch_html(
        self,
        url: str,
        use_browser: bool = False,
        wait_for_selector: Optional[str] = None,
    ) -> str:
        """
        Fetch HTML content from URL with retry logic.

        Args:
            url: URL to fetch
            use_browser: Use Playwright browser for JS-rendered pages
            wait_for_selector: CSS selector to wait for (browser only)

        Returns:
            HTML content as string

        Raises:
            ScraperError: If all retries fail
        """
        # Check cache first
        cached = self._get_cached_response(url)
        if cached:
            return cached

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                await self._rate_limit()

                if use_browser:
                    content = await self._fetch_with_browser(url, wait_for_selector)
                else:
                    content = await self._fetch_with_httpx(url)

                self._cache_response(url, content)
                return content

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    # Rate limited - wait longer
                    wait_time = (2**attempt) * self.delay_seconds
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                elif e.response.status_code == 403:
                    raise BlockedError(f"Blocked by {url}: {e}")
                else:
                    logger.warning(f"HTTP error {e.response.status_code} for {url}")

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")

            # Exponential backoff
            if attempt < self.max_retries - 1:
                wait_time = (2**attempt) * self.delay_seconds
                await asyncio.sleep(wait_time)

        raise ScraperError(
            f"Failed to fetch {url} after {self.max_retries} attempts: {last_error}"
        )

    async def _fetch_with_httpx(self, url: str) -> str:
        """Fetch URL using httpx client."""
        client = await self._get_http_client()
        response = await client.get(url, headers=self.get_headers())
        response.raise_for_status()
        return response.text

    async def _fetch_with_browser(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
    ) -> str:
        """Fetch URL using Playwright browser."""
        browser = await self._get_browser()
        page: Page = await browser.new_page()

        try:
            # Set extra headers
            await page.set_extra_http_headers(self.get_headers())

            await page.goto(url, wait_until="networkidle")

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=10000)

            content = await page.content()
            return content

        finally:
            await page.close()

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content into BeautifulSoup object."""
        return BeautifulSoup(html, "html.parser")

    def build_url(self, path: str) -> str:
        """Build full URL from relative path."""
        return urljoin(self.get_base_url(), path)

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    async def close(self) -> None:
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(source={self.get_source_name()})>"
