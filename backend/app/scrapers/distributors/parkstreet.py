"""
ABVTrends - Park Street Imports Scraper

Scrapes product data from Park Street's marketplace platform.

Park Street is a major alcohol distributor and marketplace platform that connects
brands with distributors and retailers. They have a robust API that powers their
web marketplace.

API Discovery Notes:
- Base URL: https://app.parkstreet.com
- API Base: https://api.parkstreet.com/v1
- Product catalog: /marketplace/catalog
- Product details: /marketplace/catalog/details?product_id={sku}
- Authentication: Session-based with OAuth/token
- Response includes: price, category, ABV, size, country, bottles_per_case, discounts
"""

import asyncio
import logging
import re
from typing import Any, Optional
from decimal import Decimal

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct

logger = logging.getLogger(__name__)


class ParkStreetScraper(BaseDistributorScraper):
    """
    Scraper for Park Street Imports marketplace.

    Park Street provides a modern marketplace platform with a well-structured API.
    Products include spirits, wine, beer, and other alcoholic beverages.
    """

    name = "parkstreet"
    base_url = "https://app.parkstreet.com"
    api_base_url = "https://api.parkstreet.com/v1"

    CATEGORIES = [
        {"name": "spirits", "filter": "Spirits", "id": "spirits"},
        {"name": "wine", "filter": "Wine", "id": "wine"},
        {"name": "beer", "filter": "Beer", "id": "beer"},
        {"name": "malt", "filter": "Malt", "id": "malt"},
        {"name": "other", "filter": "Other", "id": "other"},
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize Park Street scraper.

        Args:
            credentials: Dict with:
                - email: Login email
                - password: Login password
        """
        super().__init__(credentials)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._auth_token: Optional[str] = None
        self._cookies: list[dict] = []

    async def authenticate(self) -> bool:
        """
        Authenticate with Park Street.

        Park Street uses a standard login flow. We use Playwright to handle
        authentication and capture the session.

        Returns:
            True if authentication successful
        """
        try:
            success = await self._login_with_playwright()
            if success:
                self.authenticated = True
                return True
        except Exception as e:
            logger.error(f"Park Street authentication failed: {e}")

        return False

    async def _login_with_playwright(self) -> bool:
        """
        Use Playwright to automate login.

        Returns:
            True if login successful
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed")
            return False

        email = self.credentials.get("email")
        password = self.credentials.get("password")

        if not email or not password:
            logger.error("Park Street credentials not provided")
            return False

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()

            # Navigate to Park Street login
            logger.info("Navigating to Park Street...")
            await self._page.goto(f"{self.base_url}/login", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

            # Take screenshot
            await self._page.screenshot(path="/tmp/parkstreet_login.png")

            current_url = self._page.url
            logger.info(f"Current URL: {current_url}")

            # Check if already logged in
            if "/marketplace" in current_url or "/dashboard" in current_url:
                logger.info("Already logged in!")
                return True

            # Fill login form
            logger.info("Filling login form...")

            # Email field
            email_selectors = [
                'input[name="email"]',
                'input[type="email"]',
                'input[placeholder*="email" i]',
                '#email',
                'input[name="username"]',
            ]

            email_filled = False
            for selector in email_selectors:
                try:
                    elem = self._page.locator(selector).first
                    if await elem.count() > 0 and await elem.is_visible():
                        await elem.fill(email, timeout=5000)
                        email_filled = True
                        logger.info(f"Email filled using: {selector}")
                        break
                except Exception:
                    continue

            if not email_filled:
                logger.error("Could not find email input")
                await self._page.screenshot(path="/tmp/parkstreet_email_debug.png")
                return False

            # Password field
            await asyncio.sleep(1)
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password',
            ]

            password_filled = False
            for selector in password_selectors:
                try:
                    elem = self._page.locator(selector).first
                    if await elem.count() > 0 and await elem.is_visible():
                        await elem.fill(password, timeout=5000)
                        password_filled = True
                        logger.info(f"Password filled using: {selector}")
                        break
                except Exception:
                    continue

            if not password_filled:
                logger.error("Could not find password input")
                return False

            # Click login button
            await asyncio.sleep(1)
            login_selectors = [
                'button[type="submit"]',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'input[type="submit"]',
            ]

            login_clicked = False
            for selector in login_selectors:
                try:
                    elem = self._page.locator(selector).first
                    if await elem.count() > 0 and await elem.is_visible():
                        await elem.click(timeout=5000)
                        login_clicked = True
                        logger.info(f"Login clicked using: {selector}")
                        break
                except Exception:
                    continue

            if not login_clicked:
                await self._page.keyboard.press("Enter")
                logger.info("Pressed Enter to submit")

            # Wait for login
            logger.info("Waiting for login to complete...")
            await asyncio.sleep(10)

            current_url = self._page.url
            logger.info(f"URL after login: {current_url}")
            await self._page.screenshot(path="/tmp/parkstreet_post_login.png")

            # Check login success
            is_logged_in = (
                "/marketplace" in current_url or
                "/dashboard" in current_url or
                "login" not in current_url.lower()
            )

            if is_logged_in:
                logger.info("Park Street login successful")
                # Capture cookies
                self._cookies = await self._context.cookies()
                logger.info(f"Captured {len(self._cookies)} cookies")
                return True
            else:
                logger.error("Login failed - still on login page")
                return False

        except Exception as e:
            logger.error(f"Playwright login error: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
        Fetch products from Park Street.

        Uses Playwright to navigate the marketplace and intercept API responses.

        Args:
            category: Category filter
            limit: Max products to fetch
            offset: Starting offset

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        return await self._scrape_with_playwright(category, limit)

    async def _scrape_with_playwright(
        self,
        category: Optional[str],
        limit: Optional[int],
    ) -> list[RawProduct]:
        """
        Use Playwright to scrape products from Park Street.

        Args:
            category: Category filter
            limit: Max products

        Returns:
            List of RawProduct objects
        """
        if not self._page:
            logger.error("No browser session available")
            return []

        products: list[RawProduct] = []
        page = self._page

        # Capture API responses
        api_products: list[dict] = []

        async def handle_response(response):
            """Intercept API responses."""
            try:
                url = response.url
                # Park Street API endpoints
                if "api.parkstreet.com" in url and response.status == 200:
                    if "catalog" in url or "products" in url or "marketplace" in url:
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                # Check for product data
                                if "data" in data and isinstance(data["data"], dict):
                                    product_data = data["data"]
                                    api_products.append(product_data)
                                    logger.info(f"Captured product details from API")
                                elif "items" in data:
                                    api_products.extend(data["items"])
                                    logger.info(f"Captured {len(data['items'])} products from API")
                                elif "products" in data:
                                    api_products.extend(data["products"])
                                    logger.info(f"Captured {len(data['products'])} products")
                            elif isinstance(data, list):
                                api_products.extend(data)
                                logger.info(f"Captured {len(data)} products from array")
                        except Exception as e:
                            logger.debug(f"Error parsing API response: {e}")
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            # Navigate to marketplace catalog
            marketplace_url = f"{self.base_url}/marketplace"
            logger.info(f"Navigating to: {marketplace_url}")
            await page.goto(marketplace_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Check for login redirect
            if "login" in page.url.lower():
                logger.warning("Session expired - redirected to login")
                return []

            await self._page.screenshot(path="/tmp/parkstreet_marketplace.png")
            logger.info("Screenshot saved to /tmp/parkstreet_marketplace.png")

            # Scroll to load more products
            logger.info("Scrolling to load products...")
            for i in range(10):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                logger.info(f"Scroll {i+1}/10 - captured {len(api_products)} products so far")

                # Click on products to get details
                if i < 3:  # Click on first few products for detailed data
                    try:
                        product_cards = page.locator('[class*="product"]').all()
                        cards = await product_cards
                        for j, card in enumerate(cards[:5]):
                            try:
                                await card.click(timeout=3000)
                                await asyncio.sleep(2)
                                # Close modal if opened
                                close_btn = page.locator('[class*="close"], button:has-text("×")').first
                                if await close_btn.count() > 0:
                                    await close_btn.click(timeout=2000)
                                    await asyncio.sleep(1)
                            except Exception:
                                pass
                    except Exception:
                        pass

            # Save HTML for debugging
            html_content = await page.content()
            with open("/tmp/parkstreet_products.html", "w") as f:
                f.write(html_content)
            logger.info(f"Page HTML saved ({len(html_content)} chars)")

            # Parse products from HTML as fallback
            dom_products = self._extract_products_from_html(html_content)
            logger.info(f"Found {len(dom_products)} products in HTML")

            seen_ids: set[str] = set()

            # Process API-captured products first (most detailed)
            if api_products:
                logger.info(f"Processing {len(api_products)} API products")
                for item in api_products:
                    try:
                        product = self._parse_api_product(item, category)
                        if product and product.external_id not in seen_ids:
                            products.append(product)
                            seen_ids.add(product.external_id)
                            if limit and len(products) >= limit:
                                break
                    except Exception as e:
                        logger.debug(f"Error parsing API product: {e}")

            # Process DOM products
            if len(products) < (limit or 100) and dom_products:
                logger.info(f"Processing {len(dom_products)} DOM products")
                for item in dom_products:
                    if limit and len(products) >= limit:
                        break

                    try:
                        sku = item.get("sku", "")
                        if not sku or sku in seen_ids:
                            continue

                        name = item.get("name", "")
                        price_str = item.get("price", "")

                        price = None
                        if price_str:
                            try:
                                price = float(re.sub(r'[^\d.]', '', price_str))
                            except ValueError:
                                pass

                        seen_ids.add(sku)
                        products.append(RawProduct(
                            external_id=sku,
                            name=name,
                            category=category or item.get("category"),
                            price=price,
                            price_type="case",
                            in_stock=True,
                            url=item.get("url"),
                        ))

                    except Exception as e:
                        logger.debug(f"Error extracting product: {e}")

            logger.info(f"Scraped {len(products)} products from Park Street")

        except Exception as e:
            logger.error(f"Scraping error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return products

    def _extract_products_from_html(self, html: str) -> list[dict]:
        """
        Extract product data from HTML content.

        Args:
            html: Page HTML content

        Returns:
            List of product dicts
        """
        products = []

        # Look for product cards with SKU and price info
        # Park Street uses SKU format like "SRN-SSPARAGSB-750"
        sku_pattern = re.compile(r'([A-Z]{2,4}-[A-Z0-9]+-[0-9]+)')

        # Find product containers
        card_matches = re.finditer(
            r'<div[^>]*class="[^"]*(?:product|card)[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL | re.IGNORECASE
        )

        for match in card_matches:
            card_html = match.group(1)

            # Extract SKU
            sku_match = sku_pattern.search(card_html)
            if not sku_match:
                continue

            sku = sku_match.group(1)

            # Extract name (usually in a heading or strong tag)
            name_match = re.search(r'<(?:h[1-6]|strong)[^>]*>([^<]+)</(?:h[1-6]|strong)>', card_html)
            name = name_match.group(1).strip() if name_match else sku

            # Extract price
            price_match = re.search(r'\$[\d,]+\.?\d*', card_html)
            price = price_match.group(0) if price_match else None

            products.append({
                "sku": sku,
                "name": name,
                "price": price,
            })

        return products

    def _parse_api_product(
        self,
        data: dict[str, Any],
        category: Optional[str] = None,
    ) -> Optional[RawProduct]:
        """
        Parse product data from Park Street API response.

        Based on the screenshot, Park Street API returns:
        {
            "hasError": false,
            "data": {
                "marketing_title": "Southern Star Paragon Cask Strength Single Barrel",
                "sku": "SRN-SSPARAGSB-750",
                "price": "204.50",
                "marketing_description": null,
                "tasting_notes": null,
                "category": "Bourbon",
                "vintage": null,
                "country": "United States",
                "alcohol_by_volume": "53.50",
                "bottles_per_case": "6",
                "size": "750 mL",
                "image_path": null,
                "client_name": "Southern Distilling Company",
                "catalog_management_discounts": {
                    "discounts_type": "case",
                    "discounts": [
                        {"tier_label": "1+", "price": "204.50", "start": 1, ...}
                    ]
                }
            }
        }

        Args:
            data: Raw product dict from API
            category: Category override

        Returns:
            RawProduct or None
        """
        try:
            # Handle wrapped response
            if "data" in data and isinstance(data["data"], dict):
                data = data["data"]

            # Get basic fields
            sku = data.get("sku", "")
            name = data.get("marketing_title") or data.get("name") or data.get("title") or ""

            if not sku or not name:
                return None

            # Parse price
            price = None
            price_str = data.get("price", "")
            if price_str:
                try:
                    price = float(str(price_str).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    pass

            # Get category
            prod_category = category or data.get("category", "").lower()
            if not prod_category:
                # Infer from name
                name_lower = name.lower()
                if any(x in name_lower for x in ["bourbon", "whiskey", "vodka", "gin", "rum", "tequila"]):
                    prod_category = "spirits"
                elif "wine" in name_lower:
                    prod_category = "wine"
                elif any(x in name_lower for x in ["beer", "ale", "lager"]):
                    prod_category = "beer"

            # Parse additional fields
            abv = None
            abv_str = data.get("alcohol_by_volume", "")
            if abv_str:
                try:
                    abv = float(str(abv_str).replace("%", ""))
                except (ValueError, TypeError):
                    pass

            volume_ml = None
            size_str = data.get("size", "")
            if size_str:
                # Parse "750 mL" -> 750
                size_match = re.search(r'(\d+)\s*m[lL]', size_str)
                if size_match:
                    volume_ml = int(size_match.group(1))

            brand = data.get("client_name") or data.get("brand")
            image_url = data.get("image_path")

            # Get discount/tier pricing
            discounts = data.get("catalog_management_discounts", {})
            price_type = discounts.get("discounts_type", "case")

            # Check stock (assume in stock if we got data)
            in_stock = True

            # Store full data including country in raw_data
            return RawProduct(
                external_id=sku,
                name=name,
                brand=brand,
                category=prod_category,
                price=price,
                price_type=price_type,
                image_url=image_url,
                in_stock=in_stock,
                abv=abv,
                volume_ml=volume_ml,
                raw_data=data,  # Contains country, size, etc.
            )

        except Exception as e:
            logger.debug(f"Error parsing product: {e}")
            return None

    async def get_product_details(self, product_id: str) -> Optional[dict]:
        """
        Get detailed product information.

        Args:
            product_id: Product SKU

        Returns:
            Product details dict or None
        """
        if not self._page:
            return None

        details = {}

        async def handle_response(response):
            try:
                url = response.url
                if f"product_id={product_id}" in url and response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict) and "data" in data:
                        details.update(data["data"])
            except Exception:
                pass

        self._page.on("response", handle_response)

        try:
            # Navigate to product details
            details_url = f"{self.api_base_url}/marketplace/catalog/details?product_id={product_id}"
            await self._page.goto(details_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            logger.debug(f"Error fetching details: {e}")

        return details if details else None

    async def search(
        self,
        query: str,
        limit: int = 50,
    ) -> list[RawProduct]:
        """
        Search for products by keyword.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching products
        """
        if not self.authenticated or not self._page:
            return []

        products: list[RawProduct] = []
        api_products: list[dict] = []

        async def handle_response(response):
            try:
                url = response.url
                if "search" in url.lower() or "catalog" in url.lower():
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            if "items" in data:
                                api_products.extend(data["items"])
                            elif "products" in data:
                                api_products.extend(data["products"])
                        elif isinstance(data, list):
                            api_products.extend(data)
            except Exception:
                pass

        self._page.on("response", handle_response)

        try:
            from urllib.parse import quote
            search_url = f"{self.base_url}/marketplace?search={quote(query)}"

            logger.info(f"Searching: {search_url}")
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Scroll to load results
            for _ in range(3):
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Process results
            seen_ids: set[str] = set()
            for item in api_products[:limit]:
                product = self._parse_api_product(item)
                if product and product.external_id not in seen_ids:
                    products.append(product)
                    seen_ids.add(product.external_id)

            logger.info(f"Search returned {len(products)} products")

        except Exception as e:
            logger.error(f"Search error: {e}")

        return products

    async def close(self) -> None:
        """Close the browser session."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._page = None
            self._context = None
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.close()
        await self.session.aclose()
