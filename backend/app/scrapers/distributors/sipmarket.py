"""
ABVTrends - SipMarket (Crest Beverage / Reyes) Scraper

Scrapes product data from sipmarket.com.

SipMarket is the B2B ordering platform for Crest Beverage, part of Reyes Holdings.
Reyes is one of the largest beverage distributors in the US.

API Discovery Notes:
- Base URL: https://www.sipmarket.com
- Product listing: /en/plp/?page=1&ascending=none
- API endpoints:
  - /ProductGridBlock/GetProducts?blockID=XXXXX - Returns products by block
  - /productlistingv3?page=1&ascending=none&loadAll=true - Product pagination
- JSON response structure: { "Success": true, "Result": { "products": [...] } }
- Product SKU structure includes: code, name, price (prefixed with "="), quantity, package info
- Server: Cloudflare
"""

import asyncio
import logging
import re
from typing import Any, Optional

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct
from app.scrapers.utils.stealth_context import StealthContextFactory

logger = logging.getLogger(__name__)


class SipMarketScraper(BaseDistributorScraper):
    """
    Scraper for SipMarket (Crest Beverage / Reyes) portal.

    SipMarket provides wholesale pricing and ordering for licensed retailers.
    Products include beer, wine, spirits, and non-alcoholic beverages.
    """

    name = "sipmarket"
    base_url = "https://www.sipmarket.com"

    # Categories to scrape - these may need adjustment based on site structure
    CATEGORIES = [
        {"name": "beer", "filter": "beer", "id": "beer"},
        {"name": "wine", "filter": "wine", "id": "wine"},
        {"name": "spirits", "filter": "spirits", "id": "spirits"},
        {"name": "na", "filter": "non-alcoholic", "id": "na"},
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize SipMarket scraper.

        Args:
            credentials: Dict with:
                - email: Login email
                - password: Login password
                - session_cookies: Pre-existing cookies dict (optional)
        """
        super().__init__(credentials)
        self.session_cookies = credentials.get("session_cookies", {})
        # Store Playwright objects for session reuse
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._playwright_cookies: list[dict] = []

    async def _handle_age_verification(self) -> None:
        """
        Handle the age verification popup that appears on SipMarket.

        The popup asks users to confirm they are 21+ and has a checkbox
        to not ask again for 31 days.
        """
        if not self._page:
            return

        try:
            # Wait a moment for the popup to appear
            await asyncio.sleep(3)

            # Take screenshot for debugging
            await self._page.screenshot(path="/tmp/sipmarket_before_age.png")

            # Try to find and click the "don't ask again" checkbox first
            checkbox_selectors = [
                'input[type="checkbox"]',
                '[class*="remember"]',
                '[class*="dont-ask"]',
                'label:has-text("31")',
                'label:has-text("remember")',
            ]

            # Try to check the "don't ask again" checkbox
            for selector in checkbox_selectors:
                try:
                    checkbox = self._page.locator(selector).first
                    if await checkbox.count() > 0 and await checkbox.is_visible():
                        # Check if it's a checkbox input
                        tag = await checkbox.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "input":
                            is_checked = await checkbox.is_checked()
                            if not is_checked:
                                await checkbox.check(timeout=3000)
                                logger.info(f"Checked 'don't ask again' using: {selector}")
                        elif tag == "label":
                            await checkbox.click(timeout=3000)
                            logger.info(f"Clicked label: {selector}")
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

            # Look for age verification popup elements - SipMarket uses an <a> tag
            # Found via inspection: <a class="btn--confirm yes-I-am-an-adult">Yes, continue</a>
            # Also seen: button with "YES, CONTINUE" text
            age_verify_selectors = [
                # SipMarket specific - found via inspection (most specific first)
                'a.yes-I-am-an-adult',
                'a.btn--confirm',
                '.yes-I-am-an-adult',
                '.btn--confirm',
                # Exact text matches for age verification buttons
                'a:has-text("Yes, continue")',
                'a:has-text("YES, CONTINUE")',
                'button:has-text("Yes, continue")',
                'button:has-text("YES, CONTINUE")',
                '.age-not-verified a',
                # Generic link/button matches (more specific)
                'a:has-text("I am 21")',
                'a:has-text("Enter")',
                'button:has-text("I am 21")',
                'button:has-text("I am over 21")',
                'button:has-text("Enter")',
                'button:has-text("Submit")',
                'button:has-text("Confirm")',
                # Class-based selectors
                '[class*="age-verify"] a',
                '[class*="age-gate"] a',
                '[class*="adult"] a',
                '[class*="age"] button',
                '.popup button',
                '[role="dialog"] button',
                'button[type="submit"]',
            ]

            # Now click the age verification button
            button_clicked = False
            for selector in age_verify_selectors:
                try:
                    button = self._page.locator(selector).first
                    if await button.count() > 0 and await button.is_visible():
                        await button.click(timeout=5000)
                        logger.info(f"Clicked age verification using: {selector}")
                        button_clicked = True
                        await asyncio.sleep(3)
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            if not button_clicked:
                # Last resort: try to find ANY visible button and click it
                try:
                    all_buttons = self._page.locator('button:visible')
                    count = await all_buttons.count()
                    logger.info(f"Found {count} visible buttons")
                    for i in range(count):
                        btn = all_buttons.nth(i)
                        btn_text = await btn.text_content()
                        logger.info(f"  Button {i}: '{btn_text}'")
                        # Click if it looks like an age verify button
                        if btn_text and any(x in btn_text.lower() for x in ['yes', 'enter', '21', 'confirm', 'submit']):
                            await btn.click(timeout=5000)
                            logger.info(f"Clicked button with text: {btn_text}")
                            button_clicked = True
                            await asyncio.sleep(3)
                            break
                except Exception as e:
                    logger.debug(f"Button search failed: {e}")

            # Take screenshot after
            await self._page.screenshot(path="/tmp/sipmarket_after_age.png")

            if button_clicked:
                logger.info("Age verification completed")
            else:
                logger.info("No age verification popup found or already dismissed")

        except Exception as e:
            logger.debug(f"Age verification handling: {e}")

    async def authenticate(self) -> bool:
        """
        Authenticate with SipMarket.

        SipMarket uses a standard login form. We use Playwright to handle
        the login and capture session cookies.

        Returns:
            True if authentication successful
        """
        # Check if we have pre-captured session cookies
        if self.session_cookies:
            logger.info("Using pre-captured session cookies")
            for name, value in self.session_cookies.items():
                self.session.cookies.set(name, value, domain="www.sipmarket.com")
            self.authenticated = True
            return True

        # Try Playwright-based login
        try:
            success = await self._login_with_playwright()
            if success:
                self.authenticated = True
                return True
        except Exception as e:
            logger.error(f"Playwright login failed: {e}")

        logger.warning("SipMarket authentication failed")
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
            logger.error("SipMarket credentials not provided")
            return False

        try:
            # Store playwright instance for later cleanup
            self._playwright = await async_playwright().start()

            # Use headless=False for debugging, set to True for production
            self._browser = await self._playwright.chromium.launch(headless=False)

            # Use stealth context factory for anti-detection
            self._context = await StealthContextFactory.create_context(self._browser)
            self._page = await self._context.new_page()

            # Navigate to login page - SipMarket may redirect to login on home page
            logger.info("Navigating to SipMarket...")
            await self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Handle age verification popup
            await self._handle_age_verification()

            current_url = self._page.url
            logger.info(f"Current URL: {current_url}")

            # Check if we need to log in or if already authenticated
            if "/plp" in current_url or "/shop" in current_url:
                logger.info("Already logged in!")
                return True

            # Navigate to actual login page
            # SipMarket's "Log In" link goes to an info page, the actual login form is at /en/login
            logger.info("Navigating to login page...")
            await self._page.goto(f"{self.base_url}/en/login", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Handle age verification again if it appears
            await self._handle_age_verification()

            # Fill login form
            logger.info("Filling login form...")
            await asyncio.sleep(3)

            # Take screenshot before filling form
            await self._page.screenshot(path="/tmp/sipmarket_before_fill.png")

            # Email/username field - SipMarket uses UserName (capital N) with id="userName"
            email_selectors = [
                '#userName',
                'input[name="UserName"]',
                'input[id="userName"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[name="Email"]',
                'input[name="Username"]',
                'input[type="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="username" i]',
                'input[id*="email" i]',
                'input[id*="user" i]',
                '#Email',
                '#Username',
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
                await self._page.screenshot(path="/tmp/sipmarket_login_debug.png")
                return False

            # Password field
            await asyncio.sleep(1)
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="Password"]',
                'input[placeholder*="password" i]',
                '#Password',
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
                await self._page.screenshot(path="/tmp/sipmarket_password_debug.png")
                return False

            # Click login button
            await asyncio.sleep(1)
            login_selectors = [
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
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

            # Wait for login to complete - SipMarket is slow
            logger.info("Waiting for login to complete (SipMarket is slow)...")
            await asyncio.sleep(15)

            current_url = self._page.url
            logger.info(f"Current URL after login: {current_url}")

            # Take screenshot for debugging
            await self._page.screenshot(path="/tmp/sipmarket_post_login.png")

            # Check login success
            is_logged_in = (
                "/plp" in current_url or
                "/shop" in current_url or
                "/en/plp" in current_url or
                await self._page.locator('text="My Account"').count() > 0 or
                await self._page.locator('text="Cart"').count() > 0 or
                await self._page.locator('[href*="cart"]').count() > 0 or
                await self._page.locator('[href*="logout"]').count() > 0
            )

            if not is_logged_in and ("login" in current_url.lower() or "signin" in current_url.lower()):
                # Check for error messages
                error_elem = self._page.locator('.error, .alert, [class*="error"], .validation-message')
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

            logger.info(f"Captured {len(cookies)} cookies from SipMarket")
            return True

        except Exception as e:
            logger.error(f"Playwright login error: {e}")
            try:
                if self._page:
                    await self._page.screenshot(path="/tmp/sipmarket_error.png")
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
        Fetch products from SipMarket using Playwright.

        SipMarket is a JS-heavy site, so we use Playwright to render
        the page and intercept API responses.

        Args:
            category: Category filter
            limit: Max products to fetch (None = all available)
            offset: Starting offset for pagination

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
        Use Playwright to scrape products from SipMarket.

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
                # SipMarket API endpoints
                if ("GetProducts" in url or "productlisting" in url or
                    "ProductGridBlock" in url or "products" in url.lower()):
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                # SipMarket returns { "Success": true, "Result": { "products": [...] } }
                                result = data.get("Result", data)
                                if isinstance(result, dict):
                                    products_data = result.get("products", [])
                                    if products_data:
                                        api_products.extend(products_data)
                                        logger.info(f"Captured {len(products_data)} products from API")
                                # Also check for direct arrays
                                for key in ["products", "items", "data", "Products", "Items"]:
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
            # Navigate to product listing page
            plp_url = f"{self.base_url}/en/plp/?page=1&ascending=none"

            logger.info(f"Navigating to: {plp_url}")
            await page.goto(plp_url, wait_until="domcontentloaded", timeout=90000)

            # Wait for content to load - SipMarket is slow
            logger.info("Waiting for page to load (SipMarket is slow)...")
            await asyncio.sleep(10)

            # Check if redirected to login
            if "login" in page.url.lower() or "signin" in page.url.lower():
                logger.warning("Session expired - redirected to login")
                await page.screenshot(path="/tmp/sipmarket_session_expired.png")
                return []

            # Scroll to trigger lazy loading
            logger.info("Scrolling to load more products...")
            for i in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)
                logger.info(f"Scroll {i+1}/5 - captured {len(api_products)} products so far")

            # Take screenshot for debugging
            await page.screenshot(path="/tmp/sipmarket_products.png")
            logger.info("Screenshot saved to /tmp/sipmarket_products.png")

            # Save page HTML for debugging
            html_content = await page.content()
            with open("/tmp/sipmarket_products.html", "w") as f:
                f.write(html_content)
            logger.info(f"Page HTML saved ({len(html_content)} chars)")

            # Extract products from HTML using regex (more reliable than JS evaluation)
            # SipMarket product cards have rich data attributes:
            # data-name, data-brand, data-category, data-price, data-sku, data-package-name, data-max-qty
            logger.info("Extracting products from HTML content...")

            # Parse products from HTML using regex
            dom_products = []
            # Match div elements with card newCard product class and data attributes
            card_pattern = re.compile(
                r'<div[^>]*class="card newCard product[^"]*"[^>]*'
                r'data-sku="([^"]*)"[^>]*'
                r'data-name="([^"]*)"[^>]*',
                re.IGNORECASE | re.DOTALL
            )

            # More comprehensive pattern to get all attributes
            for match in re.finditer(r'<div[^>]*class="card newCard product[^"]*"([^>]*)>', html_content):
                attrs_str = match.group(1)
                # Skip template placeholders
                if "<%=" in attrs_str:
                    continue

                def get_attr(name):
                    m = re.search(rf'{name}="([^"]*)"', attrs_str)
                    return m.group(1) if m else ""

                sku = get_attr("data-sku")
                if not sku:
                    continue

                dom_products.append({
                    "sku": sku,
                    "name": get_attr("data-name"),
                    "brand": get_attr("data-brand"),
                    "price": get_attr("data-price"),
                    "category": get_attr("data-category"),
                    "category2": get_attr("data-category2"),
                    "package": get_attr("data-package-name"),
                    "maxQty": get_attr("data-max-qty") or "0",
                    "href": ""  # URL not needed from attributes
                })

            logger.info(f"Found {len(dom_products)} products in HTML")

            seen_ids: set[str] = set()

            # Process API-captured products first (most reliable)
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

            # Extract from DOM data (primary method for SipMarket)
            if len(products) < (limit or 100) and dom_products:
                logger.info(f"Processing {len(dom_products)} DOM products...")
                for item in dom_products:
                    if limit and len(products) >= limit:
                        break

                    try:
                        sku = item.get("sku", "")
                        if not sku or sku in seen_ids:
                            continue

                        name = item.get("name", "")
                        brand = item.get("brand", "")
                        price_str = item.get("price", "")
                        cat = item.get("category", "")
                        cat2 = item.get("category2", "")
                        package = item.get("package", "")
                        max_qty_str = item.get("maxQty", "0")
                        href = item.get("href", "")

                        # Parse price
                        price = None
                        if price_str:
                            try:
                                price = float(price_str)
                            except ValueError:
                                pass

                        # Parse quantity
                        quantity = None
                        in_stock = False
                        if max_qty_str:
                            try:
                                quantity = int(max_qty_str)
                                in_stock = quantity > 0
                            except ValueError:
                                pass

                        # Determine category
                        prod_category = category or (cat2.lower() if cat2 else cat.lower() if cat else None)

                        seen_ids.add(sku)
                        products.append(RawProduct(
                            external_id=sku,
                            name=f"{name} - {package}" if package else name,
                            brand=brand if brand else None,
                            category=prod_category,
                            price=price,
                            price_type="unit",
                            in_stock=in_stock,
                            inventory=quantity,
                            url=href if href else None,
                        ))

                    except Exception as e:
                        logger.debug(f"Error extracting product: {e}")
                        continue

            logger.info(f"Scraped {len(products)} products from SipMarket")

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
        Parse product data from SipMarket API response.

        SipMarket product structure (from screenshots):
        {
            "imageURL": "...",
            "sKUs": [
                {
                    "code": "10467",
                    "name": "SIERRA NEVADA CELEBRATION K 1/2BBL - 10467",
                    "isCase": false,
                    "isSpirit": false,
                    "price": "=209.00",  # Note the = prefix
                    "quantity": 30,
                    "maxQuantity": 999,
                    "ePiPackage": "Half Barrel",
                    "ePiPackageType": "Keg - Large",
                    "title": "Half Barrel",
                    "deals": [],
                    "unitsPerCase": "1"
                }
            ]
        }

        Args:
            data: Raw product dict from API
            category: Category override

        Returns:
            RawProduct or None if parsing fails
        """
        try:
            # SipMarket has products with SKUs array
            skus = data.get("sKUs", data.get("skus", data.get("SKUs", [])))

            if skus and isinstance(skus, list) and len(skus) > 0:
                # Take the first SKU as the primary product
                sku = skus[0]

                external_id = str(sku.get("code", ""))
                name = sku.get("name", "")

                # Parse price - SipMarket prefixes with "="
                price = None
                price_str = sku.get("price", "")
                if price_str:
                    # Remove "=" prefix and parse
                    price_clean = str(price_str).replace("=", "").replace(",", "").replace("$", "").strip()
                    try:
                        price = float(price_clean)
                    except (ValueError, TypeError):
                        pass

                # Determine price type from SKU info
                price_type = "unit"
                if sku.get("isCase"):
                    price_type = "case"
                elif sku.get("ePiPackageType", "").lower().startswith("keg"):
                    price_type = "keg"
                elif sku.get("ePiPackage", ""):
                    price_type = sku.get("ePiPackage", "unit").lower()

                # Get quantity/stock
                quantity = sku.get("quantity") or sku.get("maxQuantity")

                # Determine if in stock
                in_stock = quantity is not None and quantity > 0

                # Get image URL
                image_url = data.get("imageURL") or data.get("image_url") or data.get("image")
                if image_url and not image_url.startswith("http"):
                    image_url = f"{self.base_url}{image_url}"

                # Determine category
                prod_category = category
                if not prod_category:
                    if sku.get("isSpirit"):
                        prod_category = "spirits"
                    elif "wine" in name.lower():
                        prod_category = "wine"
                    elif any(x in name.lower() for x in ["beer", "ale", "lager", "ipa", "stout"]):
                        prod_category = "beer"

                if external_id and name:
                    return RawProduct(
                        external_id=external_id,
                        name=name,
                        category=prod_category,
                        price=price,
                        price_type=price_type,
                        image_url=image_url,
                        in_stock=in_stock,
                        quantity=quantity,
                        raw_data=data,
                    )

            # Fallback: Try direct fields if no SKUs
            external_id = str(
                data.get("id") or
                data.get("productId") or
                data.get("product_id") or
                data.get("code") or
                ""
            )

            name = (
                data.get("name") or
                data.get("productName") or
                data.get("product_name") or
                data.get("title") or
                ""
            )

            if external_id and name:
                # Parse price
                price = None
                price_str = data.get("price", "")
                if price_str:
                    price_clean = str(price_str).replace("=", "").replace(",", "").replace("$", "").strip()
                    try:
                        price = float(price_clean)
                    except (ValueError, TypeError):
                        pass

                return RawProduct(
                    external_id=external_id,
                    name=name,
                    brand=data.get("brand"),
                    category=category,
                    price=price,
                    image_url=data.get("imageURL") or data.get("image_url"),
                    raw_data=data,
                )

            return None

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

        if not self._page:
            logger.error("No browser session available")
            return []

        products: list[RawProduct] = []
        page = self._page

        # Capture API responses
        api_products: list[dict] = []

        async def handle_response(response):
            try:
                url = response.url
                if "search" in url.lower() or "product" in url.lower():
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                result = data.get("Result", data)
                                if isinstance(result, dict):
                                    products_data = result.get("products", [])
                                    if products_data:
                                        api_products.extend(products_data)
                            elif isinstance(data, list):
                                api_products.extend(data)
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            # Navigate to search
            from urllib.parse import quote
            search_url = f"{self.base_url}/en/search/?q={quote(query)}"

            logger.info(f"Searching: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(10)

            # Check for login redirect
            if "login" in page.url.lower():
                logger.warning("Session expired")
                return []

            # Scroll to load results
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)

            # Process API-captured products
            seen_ids: set[str] = set()
            for item in api_products[:limit]:
                try:
                    product = self._parse_api_product(item)
                    if product and product.external_id not in seen_ids:
                        products.append(product)
                        seen_ids.add(product.external_id)
                except Exception as e:
                    logger.debug(f"Error parsing search result: {e}")

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
        """Async context manager exit - close browser and httpx session."""
        await self.close()
        await self.session.aclose()
