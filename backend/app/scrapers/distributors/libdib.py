"""
ABVTrends - LibDib Scraper

Scrapes product data from LibDib distributor portal.

API Endpoints (discovered):
- POST /api/v1/offering/query/?format=json - Get product IDs
- POST /api/v1/offering/query_digest/?format=json - Get product details
- GET /api/v1/userAccount/?format=json - Account info
"""

import asyncio
import logging
import random
import time
from typing import Any, Optional

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct

logger = logging.getLogger(__name__)


class LibDibScraper(BaseDistributorScraper):
    """
    Scraper for LibDib distributor portal.

    LibDib is a three-tier compliant alcohol distributor that allows
    producers to list products for sale to licensed retailers.
    """

    name = "libdib"
    base_url = "https://app.libdib.com"

    # Categories to scrape with their filter strings
    CATEGORIES = [
        {"name": "vodka", "filter": "spirits$spirits|type|vodka"},
        {"name": "whiskey", "filter": "spirits$spirits|type|whiskey"},
        {"name": "gin", "filter": "spirits$spirits|type|gin"},
        {"name": "rum", "filter": "spirits$spirits|type|rum"},
        {"name": "tequila", "filter": "spirits$spirits|type|tequila"},
        {"name": "mezcal", "filter": "spirits$spirits|type|mezcal"},
        {"name": "brandy", "filter": "spirits$spirits|type|brandy"},
        {"name": "liqueur", "filter": "spirits$spirits|type|liqueur"},
        {"name": "red_wine", "filter": "wine$wine|type|red"},
        {"name": "white_wine", "filter": "wine$wine|type|white"},
        {"name": "rose_wine", "filter": "wine$wine|type|rose"},
        {"name": "sparkling", "filter": "wine$wine|type|sparkling"},
        {"name": "rtd", "filter": "rtd$rtd"},
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize LibDib scraper.

        Args:
            credentials: Dict with:
                - email: Login email
                - password: Login password
                - session_id: Pre-existing session ID (optional)
                - csrf_token: CSRF token (optional)
                - entity_slug: Entity slug (e.g., "vista-wine-and-spirits-santee")
        """
        super().__init__(credentials)
        self.entity_slug = credentials.get("entity_slug", "")
        self.csrf_token = credentials.get("csrf_token", "")

    async def authenticate(self) -> bool:
        """
        Authenticate with LibDib.

        If session_id and csrf_token are provided in credentials, use those.
        Otherwise, would need Playwright for full login flow (handled by SessionManager).

        Returns:
            True if authentication successful
        """
        session_id = self.credentials.get("session_id")
        csrf_token = self.credentials.get("csrf_token")

        if session_id and csrf_token:
            # Use provided session
            self.session.cookies.set(
                "sessionid", session_id, domain="app.libdib.com"
            )
            self.session.cookies.set(
                "csrftoken", csrf_token, domain="app.libdib.com"
            )
            self.csrf_token = csrf_token

            # Update headers for authenticated requests
            self.session.headers.update({
                "X-CSRFToken": csrf_token,
                "Currententityslug": self.entity_slug,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/search/",
            })

            # Verify session is valid
            try:
                response = await self.session.get(
                    f"{self.base_url}/api/v1/userAccount/?format=json"
                )
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(
                        f"LibDib authenticated as: {user_data.get('email', 'unknown')}"
                    )
                    self.authenticated = True
                    return True
                else:
                    logger.warning(
                        f"LibDib auth check failed: {response.status_code}"
                    )
            except Exception as e:
                logger.error(f"LibDib auth verification failed: {e}")

        # If no valid session, authentication failed
        # SessionManager should handle refresh via Playwright
        logger.warning("LibDib authentication failed - no valid session")
        return False

    async def get_categories(self) -> list[dict[str, Any]]:
        """Return predefined categories."""
        return self.CATEGORIES

    async def get_products(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[RawProduct]:
        """
        Fetch products for a category.

        Uses LibDib's two-step API:
        1. Query to get product IDs
        2. Query digest to get full product details

        Args:
            category: Category filter string (e.g., "spirits$spirits|type|vodka")
            limit: Max products to fetch (None = all)
            offset: Starting offset for pagination

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        all_products: list[RawProduct] = []
        page_limit = 100
        current_offset = offset

        while True:
            # Step 1: Get product IDs
            hash_key = f"?f={category}&nav=1" if category else "?nav=1"
            query_payload = {
                "hashKey": hash_key,
                "limit": page_limit,
                "offset": current_offset,
                "order_by": "default",
                "storeViewType": "product",
            }

            try:
                response = await self._request(
                    "POST",
                    f"{self.base_url}/api/v1/offering/query/?format=json",
                    json=query_payload,
                )
            except Exception as e:
                logger.error(f"Query request failed: {e}")
                break

            query_data = response.json()

            # Extract product IDs
            product_ids = []
            if "objects" in query_data:
                product_ids = [
                    obj.get("id") or obj.get("pk")
                    for obj in query_data["objects"]
                    if obj.get("id") or obj.get("pk")
                ]

            if not product_ids:
                logger.debug(f"No more products for category {category}")
                break

            # Step 2: Get product details via query_digest
            digest_payload = {
                "fetch": [[pid, time.time()] for pid in product_ids],
                "hashKey": hash_key,
                "order_by": "default",
                "storeViewType": "product",
            }

            try:
                response = await self._request(
                    "POST",
                    f"{self.base_url}/api/v1/offering/query_digest/?format=json",
                    json=digest_payload,
                )
            except Exception as e:
                logger.error(f"Query digest request failed: {e}")
                break

            digest_data = response.json()

            # Parse products
            products_data = digest_data.get("objects", [])
            for p in products_data:
                product = self._parse_product(p, category)
                if product:
                    all_products.append(product)

            # Check pagination
            total_count = query_data.get("total_count", 0)
            logger.debug(
                f"Fetched {len(all_products)}/{total_count} products "
                f"for category {category}"
            )

            if limit and len(all_products) >= limit:
                break
            if current_offset + page_limit >= total_count:
                break
            if len(product_ids) < page_limit:
                break

            current_offset += page_limit

            # Polite delay between pages
            await asyncio.sleep(random.uniform(1.0, 2.0))

        return all_products[:limit] if limit else all_products

    def _parse_product(
        self, data: dict[str, Any], category: Optional[str] = None
    ) -> Optional[RawProduct]:
        """
        Parse LibDib API response into RawProduct.

        Args:
            data: Product data from API
            category: Category filter string

        Returns:
            RawProduct or None if parsing fails
        """
        try:
            # Extract volume from container_volume (in ml)
            volume_ml = None
            if data.get("container_volume"):
                try:
                    volume_ml = int(data["container_volume"])
                except (ValueError, TypeError):
                    pass
            elif data.get("sub_container_volume"):
                try:
                    volume_ml = int(data["sub_container_volume"])
                except (ValueError, TypeError):
                    pass

            # Parse category from filter string
            parsed_category = None
            parsed_subcategory = None
            if category:
                if "$" in category:
                    parsed_category = category.split("$")[0]
                if "|" in category:
                    parts = category.split("|")
                    if len(parts) >= 3:
                        parsed_subcategory = parts[-1]

            # Parse ABV from percent_alcohol
            abv = None
            if data.get("percent_alcohol"):
                try:
                    abv = float(data["percent_alcohol"])
                except (ValueError, TypeError):
                    pass
            elif data.get("abv"):
                try:
                    abv = float(data["abv"])
                except (ValueError, TypeError):
                    pass

            # Parse price
            price = None
            if data.get("seller_price"):
                try:
                    price = float(data["seller_price"])
                except (ValueError, TypeError):
                    pass

            # Parse inventory
            inventory = None
            if data.get("total_inventory"):
                try:
                    inventory = int(data["total_inventory"])
                except (ValueError, TypeError):
                    pass

            # Parse available states
            available_states = None
            if data.get("sold_in_states"):
                states_str = data["sold_in_states"]
                if isinstance(states_str, str):
                    available_states = [
                        s.strip() for s in states_str.split(",") if s.strip()
                    ]

            # Build product URL
            slug = data.get("slug")
            url = f"{self.base_url}/product/{slug}" if slug else None

            # Get external ID
            external_id = str(
                data.get("id") or data.get("pk") or data.get("slug") or ""
            )
            if not external_id:
                logger.warning(f"Product missing ID: {data.get('name')}")
                return None

            return RawProduct(
                external_id=external_id,
                name=(
                    data.get("label_name")
                    or data.get("name")
                    or data.get("product_name")
                    or data.get("fanciful_name")
                    or "Unknown"
                ),
                brand=data.get("brandName") or data.get("brand") or data.get("producer"),
                category=parsed_category,
                subcategory=parsed_subcategory,
                volume_ml=volume_ml,
                abv=abv,
                price=price,
                price_type="wholesale",
                inventory=inventory,
                in_stock=bool(inventory and inventory > 0),
                available_states=available_states,
                image_url=(
                    data.get("primary_picture")
                    or data.get("image_url")
                    or data.get("bottle_image")
                ),
                description=data.get("story") or data.get("description"),
                upc=data.get("UPC") or data.get("upc"),
                url=url,
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing product: {e}")
            return None
