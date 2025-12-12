"""
ABVTrends - Distributor Scraper Base Classes

Provides abstract base class and data types for all distributor scrapers.
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RawProduct:
    """Raw product data from a distributor."""

    external_id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    volume_ml: Optional[int] = None
    abv: Optional[float] = None
    price: Optional[float] = None
    price_type: str = "wholesale"  # wholesale, retail, case, bottle
    inventory: Optional[int] = None
    in_stock: bool = True
    available_states: Optional[list[str]] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    upc: Optional[str] = None
    url: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


@dataclass
class ScrapeResult:
    """Result of a scrape run."""

    success: bool
    source: str
    products: list[RawProduct]
    products_count: int
    errors: list[str]
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseDistributorScraper(ABC):
    """
    Base class for all distributor scrapers.

    Each distributor scraper must implement:
    - authenticate(): Login and store session
    - get_products(): Fetch product catalog

    Optional overrides:
    - get_categories(): List available categories
    """

    name: str = "base"
    base_url: str = ""

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize scraper with credentials.

        Args:
            credentials: Dict with auth info (email, password, session_id, etc.)
        """
        self.credentials = credentials
        self.session = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            },
        )
        self.authenticated = False
        self.auth_cookies: dict[str, str] = {}

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the distributor.

        Returns:
            True if authentication successful, False otherwise.
        """
        pass

    @abstractmethod
    async def get_products(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[RawProduct]:
        """
        Fetch products from the distributor.

        Args:
            category: Optional category filter
            limit: Max products to fetch
            offset: Pagination offset

        Returns:
            List of RawProduct objects
        """
        pass

    async def get_categories(self) -> list[dict[str, Any]]:
        """
        Get available product categories.
        Override in subclass if supported.
        """
        return []

    async def run(
        self, categories: Optional[list[str]] = None
    ) -> ScrapeResult:
        """
        Main entry point - runs full scrape.

        Args:
            categories: List of categories to scrape. If None, scrape all.

        Returns:
            ScrapeResult with all products and metadata
        """
        started_at = datetime.utcnow()
        all_products: list[RawProduct] = []
        errors: list[str] = []

        try:
            # Authenticate
            if not await self.authenticate():
                return ScrapeResult(
                    success=False,
                    source=self.name,
                    products=[],
                    products_count=0,
                    errors=["Authentication failed"],
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Get categories to scrape
            if categories is None:
                available_cats = await self.get_categories()
                categories = [
                    c.get("id") or c.get("slug") or c.get("filter")
                    for c in available_cats
                ]

            # If no categories defined, do a single scrape
            if not categories:
                categories = [None]

            # Scrape each category
            for category in categories:
                try:
                    logger.info(f"Scraping category: {category}")
                    products = await self.get_products(category=category)
                    all_products.extend(products)
                    logger.info(
                        f"Category {category}: {len(products)} products"
                    )
                except Exception as e:
                    error_msg = f"Error scraping {category}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return ScrapeResult(
                success=len(errors) == 0,
                source=self.name,
                products=all_products,
                products_count=len(all_products),
                errors=errors,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                metadata={"categories_scraped": len(categories)},
            )

        except Exception as e:
            logger.exception(f"Scrape failed: {e}")
            return ScrapeResult(
                success=False,
                source=self.name,
                products=all_products,
                products_count=len(all_products),
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        finally:
            await self.session.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an authenticated request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            Exception: If all retries fail
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = await self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Session expired, re-authenticate
                    logger.warning("Session expired, re-authenticating...")
                    if not await self.authenticate():
                        raise Exception("Re-authentication failed")
                elif e.response.status_code == 429:
                    # Rate limited, wait and retry
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    logger.warning(
                        f"Request error, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

        raise Exception(f"Failed after {max_retries} retries")

    async def __aenter__(self) -> "BaseDistributorScraper":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.session.aclose()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"
