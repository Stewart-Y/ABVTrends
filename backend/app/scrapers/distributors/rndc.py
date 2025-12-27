"""
ABVTrends - Republic National Distributing Company (RNDC) Scraper

Scrapes product data from eRNDC portal (app.erndc.com).

RNDC is the second-largest wine and spirits distributor in the United States.
The eRNDC platform provides B2B ordering for licensed retailers.

API Discovery Notes:
- Base URL: https://app.erndc.com
- Shop URL: /shop
- API endpoints appear to include:
  - /search (product search)
  - get_deals_by_sku?format=json (deal/product data)
- Uses React frontend with JSON API backend
"""

import asyncio
import logging
import re
from typing import Any, Optional

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct
from app.scrapers.utils.stealth_context import StealthContextFactory

logger = logging.getLogger(__name__)


class RNDCScraper(BaseDistributorScraper):
    """
    Scraper for Republic National Distributing Company (eRNDC) portal.

    eRNDC provides wholesale pricing and ordering for licensed retailers.
    Products include spirits, wine, beer, and RTD beverages.
    """

    name = "rndc"
    base_url = "https://app.erndc.com"

    # Categories to scrape
    CATEGORIES = [
        {"name": "spirits", "filter": "SPIRITS", "id": "spirits"},
        {"name": "wine", "filter": "WINE", "id": "wine"},
        {"name": "beer", "filter": "BEER", "id": "beer"},
        {"name": "rtds & more", "filter": "RTDS & MORE", "id": "rtd"},
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize RNDC scraper.

        Args:
            credentials: Dict with:
                - email: Login email
                - password: Login password
                - account_id: RNDC account number (optional)
                - session_cookies: Pre-existing cookies dict (optional)
        """
        super().__init__(credentials)
        self.account_id = credentials.get("account_id", "")
        self.session_cookies = credentials.get("session_cookies", {})
        # Store Playwright cookies in proper format for reuse
        self._playwright_cookies: list[dict] = []
        # Store browser context for session reuse
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def authenticate(self) -> bool:
        """
        Authenticate with eRNDC.

        eRNDC uses a complex auth flow. We use Playwright to handle
        the login and capture session cookies.

        Returns:
            True if authentication successful
        """
        # Check if we have pre-captured session cookies
        if self.session_cookies:
            logger.info("Using pre-captured session cookies")
            for name, value in self.session_cookies.items():
                self.session.cookies.set(name, value, domain="app.erndc.com")
            self.authenticated = True
            return True

        # Try Playwright-based login - this will keep the browser context
        try:
            success = await self._login_with_playwright()
            if success:
                self.authenticated = True
                return True
        except Exception as e:
            logger.error(f"Playwright login failed: {e}")

        logger.warning("RNDC authentication failed")
        return False

    async def _login_with_playwright(self) -> bool:
        """
        Use Playwright to automate login and keep session open for scraping.

        Returns:
            True if login successful, False otherwise
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install")
            return False

        email = self.credentials.get("email")
        password = self.credentials.get("password")

        if not email or not password:
            logger.error("RNDC credentials not provided")
            return False

        try:
            # Store playwright instance for later cleanup
            self._playwright = await async_playwright().start()

            # Use headless=False for debugging, set to True for production
            self._browser = await self._playwright.chromium.launch(headless=False)

            # Use stealth context factory for anti-detection
            self._context = await StealthContextFactory.create_context(self._browser)
            self._page = await self._context.new_page()

            # Navigate to login page
            logger.info("Navigating to eRNDC login page...")
            await self._page.goto(f"{self.base_url}/login", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Check if already logged in (redirected to shop)
            if "/shop" in self._page.url:
                logger.info("Already logged in!")
                return True

            # Fill login form
            logger.info("Filling login form...")

            # Email/username field
            email_selectors = [
                'input[name="email"]',
                'input[name="username"]',
                'input[type="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="username" i]',
                'input[type="text"]',
            ]

            email_filled = False
            for selector in email_selectors:
                try:
                    elem = self._page.locator(selector).first
                    if await elem.count() > 0 and await elem.is_visible():
                        await elem.fill(email, timeout=5000)
                        email_filled = True
                        logger.info(f"Email filled using selector: {selector}")
                        break
                except Exception:
                    continue

            if not email_filled:
                logger.error("Could not find email input field")
                await self._page.screenshot(path="/tmp/rndc_login_debug.png")
                return False

            # Password field
            await asyncio.sleep(1)
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
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
                logger.error("Could not find password input field")
                await self._page.screenshot(path="/tmp/rndc_password_debug.png")
                return False

            # Click login button
            await asyncio.sleep(1)
            login_selectors = [
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'button[type="submit"]',
                'input[type="submit"]',
            ]

            login_clicked = False
            for selector in login_selectors:
                try:
                    elem = self._page.locator(selector).first
                    if await elem.count() > 0 and await elem.is_visible():
                        await elem.click(timeout=5000)
                        login_clicked = True
                        logger.info(f"Login button clicked using: {selector}")
                        break
                except Exception:
                    continue

            if not login_clicked:
                await self._page.keyboard.press("Enter")
                logger.info("Pressed Enter to submit")

            # Wait for login to complete
            logger.info("Waiting for login to complete...")
            await asyncio.sleep(10)

            current_url = self._page.url
            logger.info(f"Current URL after login: {current_url}")

            # Take screenshot for debugging
            await self._page.screenshot(path="/tmp/rndc_post_login.png", timeout=60000)

            # Check login success - look for shop page indicators
            is_logged_in = (
                "/shop" in current_url or
                await self._page.locator('text="Hi, "').count() > 0 or
                await self._page.locator('[href*="cart"]').count() > 0 or
                await self._page.locator('text="Shop"').count() > 0
            )

            if not is_logged_in and "/login" in current_url:
                # Check for error messages
                error_elem = self._page.locator('.error, .alert, [class*="error"]')
                if await error_elem.count() > 0:
                    error_text = await error_elem.first.text_content()
                    logger.error(f"Login error: {error_text}")
                logger.error("Login failed - still on login page")
                return False

            logger.info("Login successful - browser session will be kept for scraping")

            # Extract cookies for reference
            cookies = await self._context.cookies()
            self._playwright_cookies = cookies
            for cookie in cookies:
                logger.info(f"Cookie: {cookie['name']} (domain: {cookie.get('domain', 'N/A')})")

            logger.info(f"Captured {len(cookies)} cookies from eRNDC")
            return True

        except Exception as e:
            logger.error(f"Playwright login error: {e}")
            try:
                if self._page:
                    await self._page.screenshot(path="/tmp/rndc_error.png", timeout=60000)
            except Exception:
                pass
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
        Fetch products from eRNDC using Playwright.

        eRNDC is a React SPA, so we use Playwright to render
        the page and extract product data.

        Args:
            category: Category filter (e.g., "SPIRITS", "WINE")
            limit: Max products to fetch (None = all available)
            offset: Starting offset for pagination

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        # Use Playwright to scrape since eRNDC is a JS SPA
        return await self._scrape_with_playwright(category, limit)

    async def _scrape_with_playwright(
        self,
        category: Optional[str],
        limit: Optional[int],
    ) -> list[RawProduct]:
        """
        Use Playwright to scrape products from eRNDC.

        Reuses the existing browser session from authentication.

        Args:
            category: Category filter
            limit: Max products to fetch

        Returns:
            List of RawProduct objects
        """
        if not self._page:
            logger.error("No browser session available - authenticate first")
            return []

        products: list[RawProduct] = []
        page = self._page

        # Capture API responses for product data
        api_products: list[dict] = []

        async def handle_response(response):
            """Intercept API responses to capture product data."""
            try:
                url = response.url
                if "search" in url or "products" in url or "deals" in url:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                # Look for product arrays in response
                                for key in ["products", "items", "deals", "results", "data"]:
                                    if key in data and isinstance(data[key], list):
                                        api_products.extend(data[key])
                                        logger.info(f"Captured {len(data[key])} items from {key}")
                            elif isinstance(data, list):
                                api_products.extend(data)
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            # Navigate to shop page using the same session
            search_url = f"{self.base_url}/shop"

            logger.info(f"Navigating to: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

            # Wait for content to load
            await asyncio.sleep(5)

            # Check if redirected to login
            if "/login" in page.url:
                logger.warning("Session expired - redirected to login")
                await page.screenshot(path="/tmp/rndc_search.png")
                return []

            # Click on category tab if specified
            if category:
                # Map our category names to eRNDC tab names
                category_map = {
                    "spirits": "Spirits",
                    "wine": "Wine",
                    "beer": "Beer",
                    "rtds & more": "RTDs & More",
                }
                tab_name = category_map.get(category.lower(), category)

                # Try to find and click the category tab
                # eRNDC uses tabs like: "Spirits", "Wine", "Beer", "RTDs & More"
                tab_selectors = [
                    f'button:has-text("{tab_name}")',
                    f'a:has-text("{tab_name}")',
                    f'[role="tab"]:has-text("{tab_name}")',
                    f'div:has-text("{tab_name}"):visible',
                ]

                tab_clicked = False
                for selector in tab_selectors:
                    try:
                        tab = page.locator(selector).first
                        if await tab.count() > 0 and await tab.is_visible():
                            await tab.click(timeout=5000)
                            tab_clicked = True
                            logger.info(f"Clicked category tab: {tab_name}")
                            await asyncio.sleep(3)  # Wait for content to load
                            break
                    except Exception as e:
                        logger.debug(f"Tab selector {selector} failed: {e}")
                        continue

                if not tab_clicked:
                    logger.warning(f"Could not find category tab for: {tab_name}")

            # Scroll to trigger lazy loading
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            # Take screenshot for debugging
            await page.screenshot(path="/tmp/rndc_search.png")
            logger.info("Screenshot saved to /tmp/rndc_search.png")

            # Save page HTML for debugging
            html_content = await page.content()
            with open("/tmp/rndc_search.html", "w") as f:
                f.write(html_content)
            logger.info(f"Page HTML saved ({len(html_content)} chars)")

            # eRNDC product cards have class "simple-product-card"
            # Inside each card:
            # - Link to /offering/off-{UUID}
            # - Brand: <h3 class="pdp-info-sub-title">
            # - Product name: <div class="semi-bold">
            product_cards = page.locator('div.simple-product-card')
            card_count = await product_cards.count()
            logger.info(f"Found {card_count} product cards")

            seen_ids: set[str] = set()

            for i in range(card_count):
                try:
                    card = product_cards.nth(i)

                    # Find the offering link within this card
                    offering_link = card.locator('a[href*="/offering/"]').first
                    if await offering_link.count() == 0:
                        continue

                    href = await offering_link.get_attribute("href") or ""

                    # Extract offering ID from URL
                    id_match = re.search(r'/offering/(off-[a-f0-9]+)', href)
                    if not id_match:
                        continue

                    product_id = id_match.group(1)
                    if product_id in seen_ids:
                        continue
                    seen_ids.add(product_id)

                    # Get product name from div with EXACTLY class="semi-bold"
                    # Note: There's another element with "text-small semi-bold" that contains &nbsp;
                    name_elem = card.locator('div[class="semi-bold"]').first
                    name = ""
                    if await name_elem.count() > 0:
                        name = await name_elem.text_content() or ""
                        name = name.strip()

                    # Get brand from h3.pdp-info-sub-title
                    brand = ""
                    brand_elem = card.locator('.pdp-info-sub-title').first
                    if await brand_elem.count() > 0:
                        brand = await brand_elem.text_content() or ""
                        brand = brand.strip()

                    # If name is empty, use brand or fallback
                    if not name or len(name) < 3:
                        name = brand if brand else f"Product {product_id}"

                    # Clean up name
                    name = re.sub(r'\s+', ' ', name).strip()
                    if len(name) > 200:
                        name = name[:200]

                    if name and len(name) > 2:
                        products.append(RawProduct(
                            external_id=product_id,
                            name=name,
                            brand=brand if brand else None,
                            category=category.lower() if category else None,
                            url=f"{self.base_url}{href}" if href.startswith("/") else href,
                        ))

                        if limit and len(products) >= limit:
                            break

                except Exception as e:
                    logger.debug(f"Error extracting card {i}: {e}")
                    continue

            # Also process any API-captured products
            if api_products:
                logger.info(f"Processing {len(api_products)} API-captured products")
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

            logger.info(f"Scraped {len(products)} products from eRNDC")

        except Exception as e:
            logger.error(f"Playwright scraping error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return products

    def _parse_api_product(
        self,
        data: dict[str, Any],
        category: Optional[str] = None,
    ) -> Optional[RawProduct]:
        """
        Parse product data from API response.

        Args:
            data: Raw product dict from API
            category: Category override

        Returns:
            RawProduct or None if parsing fails
        """
        try:
            # Try various field names for product ID
            external_id = (
                str(data.get("id") or
                data.get("product_id") or
                data.get("sku") or
                data.get("corp_prod_ids") or
                data.get("deal_id") or
                "")
            )

            if not external_id:
                return None

            # Try various field names for product name
            name = (
                data.get("name") or
                data.get("product_name") or
                data.get("title") or
                data.get("deal_desc") or
                data.get("description") or
                f"Product {external_id}"
            )

            # Extract brand
            brand = data.get("brand") or data.get("brand_names")
            if isinstance(brand, list):
                brand = brand[0] if brand else None

            # Extract price - eRNDC has bottle and case prices
            price = None
            price_type = "case"
            if data.get("case_list_price"):
                try:
                    price = float(str(data["case_list_price"]).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            elif data.get("bottle_list_price"):
                try:
                    price = float(str(data["bottle_list_price"]).replace(",", ""))
                    price_type = "bottle"
                except (ValueError, TypeError):
                    pass

            # Extract category
            prod_category = category
            if not prod_category:
                prod_category = data.get("category") or data.get("product_type")

            return RawProduct(
                external_id=external_id,
                name=name,
                brand=brand,
                category=prod_category.lower() if prod_category else None,
                price=price,
                price_type=price_type,
                image_url=data.get("image_url") or data.get("image"),
                raw_data=data,
            )

        except Exception as e:
            logger.debug(f"Error parsing product: {e}")
            return None

    async def search(
        self,
        query: str,
        limit: int = 50,
    ) -> list[RawProduct]:
        """
        Search for products by keyword.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of matching RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        # Use Playwright for search since eRNDC is a JS SPA
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed")
            return []

        products: list[RawProduct] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            # Use stealth context factory for anti-detection
            context = await StealthContextFactory.create_context(browser)

            if self._playwright_cookies:
                await context.add_cookies(self._playwright_cookies)

            page = await context.new_page()

            try:
                # Navigate to search
                from urllib.parse import quote
                search_url = f"{self.base_url}/search?text={quote(query)}"
                logger.info(f"Searching: {search_url}")

                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(8)

                # Check for login redirect
                if "/login" in page.url:
                    logger.warning("Session expired")
                    return []

                # Scroll to load results
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)

                # Extract products similar to regular scraping
                product_links = page.locator('a[href*="/product/"], a[href*="/p/"]')
                count = await product_links.count()
                logger.info(f"Found {count} product links in search results")

                seen_ids: set[str] = set()
                for i in range(min(count, limit)):
                    try:
                        link = product_links.nth(i)
                        href = await link.get_attribute("href") or ""

                        id_match = re.search(r'/(?:product|p)/([^/?]+)', href)
                        if not id_match:
                            continue

                        product_id = id_match.group(1)
                        if product_id in seen_ids:
                            continue
                        seen_ids.add(product_id)

                        name = await link.text_content() or f"Product {product_id}"
                        name = re.sub(r'\s+', ' ', name).strip()

                        products.append(RawProduct(
                            external_id=product_id,
                            name=name,
                            url=f"{self.base_url}{href}" if href.startswith("/") else href,
                        ))

                    except Exception as e:
                        logger.debug(f"Error extracting search result {i}: {e}")

                logger.info(f"Search returned {len(products)} products")

            except Exception as e:
                logger.error(f"Search error: {e}")

            finally:
                await browser.close()

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
        """Async context manager exit - close browser and httpx session."""
        await self.close()
        await self.session.aclose()
