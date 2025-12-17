"""
ABVTrends - Provi Scraper

Scrapes product data from Provi marketplace (app.provi.com).

Provi is one of the largest B2B alcohol marketplaces with 1,400+ distributors.
It provides wholesale pricing and ordering for bars, restaurants, and retailers.

API Discovery Notes:
- Base URL: https://app.provi.com
- API Base: /api/retailer/...
- Product listing: /api/retailer/product_lines?category=X
- Available filters: /api/retailer/available_filters?category_id=X
- Uses XSRF-TOKEN cookie for authentication
- Categories identified by numeric IDs (e.g., 157 = White Wine)
"""

import asyncio
import logging
import re
from typing import Any, Optional

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct

logger = logging.getLogger(__name__)


class ProviScraper(BaseDistributorScraper):
    """
    Scraper for Provi B2B alcohol marketplace.

    Provi connects retailers with distributors across multiple states.
    Products include spirits, wine, beer, and non-alcoholic beverages.
    """

    name = "provi"
    base_url = "https://app.provi.com"

    # Provi is a marketplace - products available depend on distributor coverage
    # We use a single "all" category to fetch all available products
    # The API returns all products for the logged-in retailer regardless of category
    CATEGORIES = [
        {"name": "All Products", "id": "all", "slug": "all"},
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize Provi scraper.

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
        self._cookies: list[dict] = []
        self._xsrf_token: str = ""

    async def authenticate(self) -> bool:
        """
        Authenticate with Provi.

        Provi uses a modern React SPA with XSRF token protection.
        We use Playwright to handle the login flow and capture session cookies.

        Returns:
            True if authentication successful
        """
        try:
            success = await self._login_with_playwright()
            if success:
                self.authenticated = True
                return True
        except Exception as e:
            logger.error(f"Provi authentication failed: {e}")

        return False

    async def _login_with_playwright(self) -> bool:
        """
        Use Playwright to automate login.

        Provi uses Auth0 for authentication. The flow is:
        1. Go to app.provi.com
        2. Handle cookie consent popup
        3. Click "Log In" button to go to Auth0
        4. Fill email/password on Auth0 login form
        5. Handle redirect back to Provi

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
            logger.error("Provi credentials not provided")
            return False

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()

            # Navigate to Provi main page
            logger.info("Navigating to Provi...")
            await self._page.goto(
                self.base_url,
                wait_until="networkidle",
                timeout=60000
            )
            await asyncio.sleep(3)

            current_url = self._page.url
            logger.info(f"Current URL: {current_url}")

            # Check if already logged in (redirected to product listing)
            if "/product_listing" in current_url or "/marketplace" in current_url:
                logger.info("Already logged in!")
                self._cookies = await self._context.cookies()
                self._extract_xsrf_token()
                await self._setup_session()
                return True

            # Handle cookie consent popup if present
            try:
                accept_btn = await self._page.wait_for_selector(
                    'button:has-text("Accept All")',
                    timeout=5000
                )
                if accept_btn:
                    await accept_btn.click()
                    logger.info("Accepted cookie consent")
                    await asyncio.sleep(1)
            except Exception:
                logger.debug("No cookie consent popup found")

            # Click "Log In" button to go to Auth0
            logger.info("Looking for Log In button...")
            try:
                login_link = await self._page.wait_for_selector(
                    'a:has-text("Log In"), button:has-text("Log In")',
                    timeout=10000
                )
                if login_link:
                    await login_link.click()
                    logger.info("Clicked Log In button")
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Could not find Log In button: {e}")
                return False

            # Wait for Auth0 login page to load
            await self._page.wait_for_load_state("networkidle")
            current_url = self._page.url
            logger.info(f"Auth URL: {current_url}")

            # Fill Auth0 login form (two-step: email first, then password)
            # Using keyboard Enter for form submission as it's more reliable with Auth0
            logger.info("Filling Auth0 login form...")

            # Step 1: Fill email field
            try:
                email_input = await self._page.wait_for_selector(
                    'input[type="email"], input[name="email"], input[name="username"], input#username',
                    timeout=15000
                )
                if email_input:
                    await email_input.click()  # Focus on input
                    await email_input.fill(email)
                    logger.info("Email filled")
                else:
                    logger.error("Could not find email field")
                    return False
            except Exception as e:
                logger.error(f"Error finding email field: {e}")
                return False

            await asyncio.sleep(0.5)

            # Step 2: Press Enter to submit email and go to password step
            await self._page.keyboard.press("Enter")
            logger.info("Submitted email (pressed Enter)")

            # Wait for password page to load
            await asyncio.sleep(4)
            await self._page.wait_for_load_state("networkidle")

            # Step 3: Fill password field (now visible)
            try:
                password_input = await self._page.wait_for_selector(
                    'input[type="password"]:visible',
                    timeout=15000
                )
                if password_input:
                    await password_input.click()  # Focus on input
                    await password_input.fill(password)
                    logger.info("Password filled")
                else:
                    logger.error("Could not find password field")
                    return False
            except Exception as e:
                logger.error(f"Error finding password field: {e}")
                return False

            await asyncio.sleep(0.5)

            # Step 4: Press Enter to submit login
            await self._page.keyboard.press("Enter")
            logger.info("Submitted login (pressed Enter)")

            # Wait for redirect back to Provi
            logger.info("Waiting for authentication to complete...")
            await asyncio.sleep(10)
            await self._page.wait_for_load_state("networkidle")

            # Check for successful login
            current_url = self._page.url
            logger.info(f"Post-login URL: {current_url}")

            # Check for error messages first (user doesn't exist, wrong password, etc.)
            error_selectors = [
                '[class*="error"]',
                '[class*="Error"]',
                '.alert-danger',
                '[data-error]',
                'span[id*="error"]',
            ]
            for selector in error_selectors:
                error_els = await self._page.query_selector_all(selector)
                for error_el in error_els:
                    error_text = await error_el.text_content()
                    if error_text and error_text.strip():
                        error_text = error_text.strip()
                        if any(phrase in error_text.lower() for phrase in [
                            "does not exist", "not found", "invalid", "incorrect",
                            "wrong", "failed", "error"
                        ]):
                            logger.error(f"Login error: {error_text}")
                            return False

            # Check if we're still on auth0 (login failed)
            if "auth0" in current_url.lower() or "/users/auth0" in current_url:
                logger.error("Login failed - still on auth page")
                return False

            # Capture cookies
            self._cookies = await self._context.cookies()
            logger.info(f"Captured {len(self._cookies)} cookies")

            # Extract XSRF token
            self._extract_xsrf_token()

            # Setup httpx session with cookies
            await self._setup_session()

            logger.info("Provi authentication successful!")
            return True

        except Exception as e:
            logger.error(f"Playwright login error: {e}")
            return False

        finally:
            # Close browser after getting cookies
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()

    def _extract_xsrf_token(self) -> None:
        """Extract XSRF token from cookies."""
        for cookie in self._cookies:
            if cookie.get("name") == "XSRF-TOKEN":
                self._xsrf_token = cookie.get("value", "")
                logger.info(f"XSRF token extracted: {self._xsrf_token[:20]}...")
                break

    async def _setup_session(self) -> None:
        """Setup httpx session with captured cookies and headers."""
        # Add cookies to session
        for cookie in self._cookies:
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", "app.provi.com").lstrip("."),
            )

        # Update headers for API requests
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/product_listing",
            "X-XSRF-TOKEN": self._xsrf_token,
        })

    async def get_categories(self) -> list[dict[str, Any]]:
        """
        Get available product categories.

        Provi returns all products for a retailer regardless of category,
        so we return a single "all" category for the scraper to iterate.
        """
        return self.CATEGORIES

    async def get_products(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[RawProduct]:
        """
        Fetch all products from Provi.

        Provi is a marketplace where products depend on distributor coverage.
        The API returns all available products for the logged-in retailer
        regardless of the category parameter.

        Each response contains product_lines (brands) with nested products (variants).
        We flatten this to individual products.

        Args:
            category: Ignored - Provi returns all products for retailer
            limit: Max products to fetch (None for all)
            offset: Starting offset for pagination

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        all_products: list[RawProduct] = []
        page_size = 100  # Fetch larger pages for efficiency
        current_page = 1

        # Calculate starting page from offset
        if offset > 0:
            current_page = (offset // page_size) + 1

        while True:
            try:
                # Build API URL - no category filter, just pagination
                api_url = (
                    f"{self.base_url}/api/retailer/product_lines"
                    f"?page={current_page}"
                    f"&page_size={page_size}"
                )

                logger.info(f"Fetching page {current_page}: {api_url}")

                response = await self._request("GET", api_url)
                data = response.json()

                # API returns a list directly
                if isinstance(data, list):
                    products_data = data
                else:
                    products_data = data.get("results", data.get("products", data.get("items", [])))

                if not products_data:
                    logger.info("No more product lines available")
                    break

                # Each item is a product_line with nested products (variants)
                for product_line in products_data:
                    parsed_products = self._parse_product_line(product_line)
                    all_products.extend(parsed_products)

                    if limit and len(all_products) >= limit:
                        break

                # Log progress
                logger.info(
                    f"Page {current_page}: {len(products_data)} product lines, "
                    f"total variants: {len(all_products)}"
                )

                # Check if we've hit limit
                if limit and len(all_products) >= limit:
                    break

                # Check if we have more pages
                if len(products_data) < page_size:
                    logger.info("Reached last page of products")
                    break

                current_page += 1

                # Polite delay between pages
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"Error fetching products (page {current_page}): {e}")
                break

        logger.info(f"Total products fetched: {len(all_products)}")
        return all_products[:limit] if limit else all_products

    def _parse_product(
        self, data: dict[str, Any], category_id: Optional[str] = None
    ) -> Optional[RawProduct]:
        """
        Parse Provi API response into RawProduct.

        Args:
            data: Product data from API
            category_id: Category ID for context

        Returns:
            RawProduct or None if parsing fails
        """
        try:
            # Extract product ID
            external_id = str(
                data.get("id")
                or data.get("product_id")
                or data.get("sku")
                or ""
            )
            if not external_id:
                logger.warning(f"Product missing ID: {data.get('name')}")
                return None

            # Parse name
            name = (
                data.get("name")
                or data.get("product_name")
                or data.get("title")
                or "Unknown"
            )

            # Parse brand
            brand = (
                data.get("brand")
                or data.get("brand_name")
                or data.get("producer")
                or data.get("supplier")
            )

            # Parse category
            category = data.get("category") or data.get("category_name")
            subcategory = data.get("subcategory") or data.get("type")

            # Parse volume (in ml)
            volume_ml = None
            size = data.get("size") or data.get("volume") or data.get("pack_size")
            if size:
                volume_ml = self._parse_volume(size)

            # Parse ABV
            abv = None
            abv_str = data.get("abv") or data.get("alcohol") or data.get("percent_alcohol")
            if abv_str:
                try:
                    # Remove % sign and convert
                    abv = float(str(abv_str).replace("%", "").strip())
                except (ValueError, TypeError):
                    pass

            # Parse price
            price = None
            price_val = (
                data.get("price")
                or data.get("unit_price")
                or data.get("wholesale_price")
                or data.get("case_price")
            )
            if price_val:
                try:
                    # Remove currency symbols
                    price = float(str(price_val).replace("$", "").replace(",", "").strip())
                except (ValueError, TypeError):
                    pass

            # Parse inventory/availability
            inventory = data.get("inventory") or data.get("quantity_available")
            in_stock = data.get("in_stock", data.get("available", True))
            if isinstance(in_stock, str):
                in_stock = in_stock.lower() in ("true", "yes", "1", "available")

            # Parse image URL
            image_url = (
                data.get("image_url")
                or data.get("image")
                or data.get("thumbnail")
                or data.get("primary_image")
            )
            if image_url and not image_url.startswith("http"):
                image_url = f"https:{image_url}" if image_url.startswith("//") else f"{self.base_url}{image_url}"

            # Parse UPC
            upc = data.get("upc") or data.get("gtin") or data.get("barcode")

            # Build product URL
            product_slug = data.get("slug") or data.get("url_key")
            url = None
            if product_slug:
                url = f"{self.base_url}/product/{product_slug}"
            elif external_id:
                url = f"{self.base_url}/product/{external_id}"

            # Parse description
            description = data.get("description") or data.get("short_description")

            # Distributor info (Provi aggregates multiple distributors)
            distributor = data.get("distributor") or data.get("supplier_name")

            return RawProduct(
                external_id=external_id,
                name=name,
                brand=brand,
                category=category,
                subcategory=subcategory,
                volume_ml=volume_ml,
                abv=abv,
                price=price,
                price_type="wholesale",
                inventory=inventory,
                in_stock=in_stock,
                image_url=image_url,
                description=description,
                upc=upc,
                url=url,
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing product: {e}")
            return None

    def _parse_product_line(self, product_line: dict[str, Any]) -> list[RawProduct]:
        """
        Parse a Provi product_line (brand) with nested products (variants).

        Provi API returns product_lines that contain:
        - id, name (brand/product line name)
        - category_name, subcategory_name
        - distributor_info
        - products: list of variants (different sizes/containers)
        - cloudinary_image_url

        Args:
            product_line: Product line data from API

        Returns:
            List of RawProduct objects (one per variant)
        """
        products = []

        try:
            # Extract common info from product_line
            line_id = product_line.get("id")
            line_name = product_line.get("name", "Unknown")
            category = product_line.get("category_name")
            subcategory = product_line.get("subcategory_name")
            product_type = product_line.get("product_type_name")  # Beer, Wine, Spirits
            country = product_line.get("wine_country_name")
            region = product_line.get("wine_region_name")

            # Build image URL from cloudinary
            image_url = None
            cloudinary_path = product_line.get("cloudinary_image_url")
            if cloudinary_path:
                image_url = f"https://res.cloudinary.com/provi/image/upload{cloudinary_path}"

            # Extract distributor info
            dist_info = product_line.get("distributor_info", {})
            distributor_name = dist_info.get("distributor_name") if dist_info else None

            # Parse each product variant
            variants = product_line.get("products", [])
            for variant in variants:
                try:
                    variant_id = variant.get("id")
                    if not variant_id:
                        continue

                    # Build external ID combining line and variant
                    external_id = f"{line_id}_{variant_id}"

                    # Parse container info
                    container_type = variant.get("container_type", "")  # can, bottle, keg
                    container_size = variant.get("container_size", "")  # 12 oz, 750 ml
                    case_size = variant.get("container_case_size")  # 24, 12, etc.

                    # Build descriptive name
                    name = f"{line_name}"
                    if container_size:
                        name = f"{line_name} ({container_size})"
                    if container_type:
                        name = f"{line_name} {container_type.title()} ({container_size})"

                    # Parse volume
                    volume_ml = self._parse_volume(container_size) if container_size else None

                    # Check inventory for stock status
                    inventory_list = variant.get("inventory", [])
                    in_stock = any(
                        inv.get("verified_in_stock", False)
                        for inv in inventory_list
                    ) if inventory_list else None

                    # Build product URL
                    url = f"{self.base_url}/product/{line_id}"

                    # Build description
                    description_parts = []
                    if product_type:
                        description_parts.append(product_type)
                    if category:
                        description_parts.append(category)
                    if subcategory:
                        description_parts.append(subcategory)
                    if country:
                        description_parts.append(f"Origin: {country}")
                    if region:
                        description_parts.append(region)
                    if case_size:
                        description_parts.append(f"Case of {case_size}")
                    description = " | ".join(description_parts) if description_parts else None

                    products.append(RawProduct(
                        external_id=external_id,
                        name=name,
                        brand=line_name,  # Use product line name as brand
                        category=product_type or category,
                        subcategory=subcategory,
                        volume_ml=volume_ml,
                        abv=None,  # Not available in this API response
                        price=None,  # Price requires separate API call or login
                        price_type="wholesale",
                        inventory=None,
                        in_stock=in_stock,
                        image_url=image_url,
                        description=description,
                        upc=None,
                        url=url,
                        raw_data={
                            "product_line_id": line_id,
                            "variant_id": variant_id,
                            "container_type": container_type,
                            "container_size": container_size,
                            "case_size": case_size,
                            "distributor": distributor_name,
                            **variant,
                        },
                    ))

                except Exception as e:
                    logger.warning(f"Error parsing variant: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing product_line: {e}")

        return products

    def _parse_volume(self, size_str: str) -> Optional[int]:
        """
        Parse volume string to milliliters.

        Args:
            size_str: Size string (e.g., "750ml", "1L", "12oz")

        Returns:
            Volume in ml or None
        """
        if not size_str:
            return None

        size_str = str(size_str).lower().strip()

        try:
            # Handle ml
            if "ml" in size_str:
                return int(float(re.sub(r"[^\d.]", "", size_str.replace("ml", ""))))

            # Handle liters
            if "l" in size_str and "ml" not in size_str:
                liters = float(re.sub(r"[^\d.]", "", size_str.replace("l", "")))
                return int(liters * 1000)

            # Handle oz
            if "oz" in size_str:
                oz = float(re.sub(r"[^\d.]", "", size_str.replace("oz", "")))
                return int(oz * 29.5735)  # oz to ml

            # Try to parse as plain number (assume ml)
            num = float(re.sub(r"[^\d.]", "", size_str))
            if num > 0:
                return int(num) if num < 100 else int(num)  # Small numbers might be liters

        except (ValueError, TypeError):
            pass

        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on exit."""
        await super().__aexit__(exc_type, exc_val, exc_tb)
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
