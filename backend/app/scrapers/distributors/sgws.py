"""
ABVTrends - Southern Glazer's Wine & Spirits (SGWS Proof) Scraper

Scrapes product data from SGWS Proof portal (shop.sgproof.com).

SGWS Proof is the B2B e-commerce platform for Southern Glazer's Wine & Spirits,
the largest wine and spirits distributor in North America.

API Discovery Notes:
- Base URL: https://shop.sgproof.com
- Search URL: /search?text=&f-category=Spirits
- Product URLs: /sgws/en/usd/{PRODUCT-NAME}/p/{SKU}
- Uses Hybris/SAP Commerce Cloud backend
"""

import asyncio
import logging
import random
import re
from typing import Any, Optional
from urllib.parse import quote, urlencode

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct

logger = logging.getLogger(__name__)


class SGWSScraper(BaseDistributorScraper):
    """
    Scraper for Southern Glazer's Wine & Spirits Proof portal.

    SGWS Proof provides wholesale pricing and ordering for licensed
    retailers. Products include spirits, wine, beer, and RTD beverages.
    """

    name = "sgws"
    base_url = "https://shop.sgproof.com"

    # Categories to scrape with their filter values
    CATEGORIES = [
        {"name": "spirits", "filter": "Spirits", "id": "spirits"},
        {"name": "wine", "filter": "Wine", "id": "wine"},
        {"name": "beer", "filter": "Beer", "id": "beer"},
        {"name": "rtd", "filter": "Ready to Drink", "id": "rtd"},
    ]

    # Subcategories for more granular scraping
    SPIRIT_SUBCATEGORIES = [
        "Vodka", "Whiskey", "Tequila", "Rum", "Gin", "Brandy",
        "Cognac", "Mezcal", "Liqueur", "Cordial",
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize SGWS scraper.

        Args:
            credentials: Dict with:
                - email: Login email
                - password: Login password
                - account_id: SGWS account number (e.g., "102376")
                - session_cookies: Pre-existing cookies dict (optional)
        """
        super().__init__(credentials)
        self.account_id = credentials.get("account_id", "")
        self.session_cookies = credentials.get("session_cookies", {})
        # Store Playwright cookies in proper format for reuse
        self._playwright_cookies: list[dict] = []

    async def authenticate(self) -> bool:
        """
        Authenticate with SGWS Proof.

        SGWS uses a complex auth flow with multiple cookies. For now,
        we'll use Playwright to capture session cookies after manual login.

        Returns:
            True if authentication successful
        """
        # Check if we have pre-captured session cookies
        if self.session_cookies:
            for name, value in self.session_cookies.items():
                self.session.cookies.set(name, value, domain="shop.sgproof.com")

            # Set common headers for authenticated requests
            self.session.headers.update({
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/search",
            })

            # Verify session is valid by making a test request
            try:
                response = await self.session.get(
                    f"{self.base_url}/sgws/en/usd/search",
                    params={"text": "", "f-category": "Spirits"},
                )
                if response.status_code == 200:
                    logger.info("SGWS session validated successfully")
                    self.authenticated = True
                    return True
                else:
                    logger.warning(f"SGWS session check failed: {response.status_code}")
            except Exception as e:
                logger.error(f"SGWS session verification failed: {e}")

        # Try Playwright-based login
        try:
            cookies = await self._login_with_playwright()
            if cookies:
                for name, value in cookies.items():
                    self.session.cookies.set(name, value, domain=".sgproof.com")

                # Also add critical headers for SGWS API
                self.session.headers.update({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                })

                logger.info(f"Set {len(cookies)} cookies on httpx session")
                self.authenticated = True
                return True
        except Exception as e:
            logger.error(f"Playwright login failed: {e}")

        logger.warning("SGWS authentication failed")
        return False

    async def _login_with_playwright(self) -> Optional[dict[str, str]]:
        """
        Use Playwright to automate login and capture session cookies.

        SGWS Proof uses a single-page login with username and password fields.

        Returns:
            Dict of session cookies or None if login fails
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install")
            return None

        email = self.credentials.get("email")
        password = self.credentials.get("password")

        if not email or not password:
            logger.error("SGWS credentials not provided")
            return None

        cookies_dict = {}

        async with async_playwright() as p:
            # Use headless=False for debugging, set to True for production
            browser = await p.chromium.launch(headless=False)

            # Store browser context for reuse during scraping
            self._playwright = p
            self._browser = browser
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                # Navigate to login page
                logger.info("Navigating to SGWS login page...")
                await page.goto(f"{self.base_url}/login", wait_until="networkidle")
                await asyncio.sleep(3)

                # SGWS has both username and password on single page
                logger.info("Filling login form...")

                # Fill username/email field
                email_selectors = [
                    'input[placeholder*="Username" i]',
                    'input[placeholder*="email" i]',
                    'input[name="userId"]',
                    'input[name="username"]',
                    'input[name="email"]',
                    'input[type="email"]',
                    'input[type="text"]',
                ]

                email_filled = False
                for selector in email_selectors:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.fill(email, timeout=5000)
                            email_filled = True
                            logger.info(f"Email filled using selector: {selector}")
                            break
                    except Exception:
                        continue

                if not email_filled:
                    logger.error("Could not find email input field")
                    await page.screenshot(path="/tmp/sgws_login_debug.png")
                    await browser.close()
                    return None

                # Fill password field - on same page
                await asyncio.sleep(1)
                logger.info("Filling password...")

                password_selectors = [
                    'input[placeholder*="Password" i]',
                    'input[type="password"]',
                    'input[name="password"]',
                ]

                password_filled = False
                for selector in password_selectors:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.fill(password, timeout=5000)
                            password_filled = True
                            logger.info(f"Password filled using: {selector}")
                            break
                    except Exception as e:
                        logger.debug(f"Password selector {selector} failed: {e}")
                        continue

                if not password_filled:
                    logger.error("Could not find password input field")
                    await page.screenshot(path="/tmp/sgws_password_debug.png")
                    await browser.close()
                    return None

                # Click Log In button
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
                        elem = page.locator(selector).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.click(timeout=5000)
                            login_clicked = True
                            logger.info(f"Login button clicked using: {selector}")
                            break
                    except Exception:
                        continue

                if not login_clicked:
                    await page.keyboard.press("Enter")
                    logger.info("Pressed Enter to submit")

                # Wait for login to complete
                logger.info("Waiting for login to complete...")
                await asyncio.sleep(10)

                current_url = page.url
                logger.info(f"Current URL after login: {current_url}")

                # Take screenshot for debugging (with longer timeout)
                await page.screenshot(path="/tmp/sgws_login_error.png", timeout=60000)

                # Check if login was successful by looking for account indicator
                # The page shows "Acct: XXXXX" when logged in
                account_indicator = page.locator('text=/Acct[:\.]?\s*\d+/i')
                cart_icon = page.locator('[class*="cart"], [href*="cart"]')
                shop_nav = page.locator('text="Shop"')

                is_logged_in = (
                    await account_indicator.count() > 0 or
                    await cart_icon.count() > 0 or
                    await shop_nav.count() > 0
                )

                if is_logged_in:
                    logger.info("Login successful - account/shop indicators found")
                elif "/login" in current_url.lower() and "error" in current_url.lower():
                    # Only fail if there's an actual error
                    error_elem = page.locator('.error, .alert-danger, [class*="error"]')
                    if await error_elem.count() > 0:
                        error_text = await error_elem.first.text_content()
                        logger.error(f"Login error: {error_text}")
                    logger.error("Login failed - still on login page with error")
                    await browser.close()
                    return None

                # Extract ALL cookies (not just sgproof domain)
                cookies = await context.cookies()
                # Store full cookie format for Playwright reuse
                self._playwright_cookies = cookies
                for cookie in cookies:
                    cookies_dict[cookie["name"]] = cookie["value"]
                    logger.debug(f"Cookie: {cookie['name']} = {cookie['value'][:20]}... (domain: {cookie.get('domain', 'N/A')})")

                logger.info(f"Captured {len(cookies_dict)} cookies from SGWS")

                # Verify we're logged in by checking page content
                if cookies_dict:
                    logger.info("Login appears successful!")

            except Exception as e:
                logger.error(f"Playwright login error: {e}")
                await page.screenshot(path="/tmp/sgws_error.png")

            finally:
                await browser.close()

        return cookies_dict if cookies_dict else None

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
        Fetch products from SGWS Proof using Playwright.

        SGWS is a JavaScript SPA, so we use Playwright to render
        the page and scrape product data from the DOM.

        Args:
            category: Category filter (e.g., "Spirits", "Wine")
            limit: Max products to fetch (None = all available)
            offset: Starting offset for pagination

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        # Use Playwright to scrape since SGWS is a JS SPA
        return await self._scrape_with_playwright(category, limit)

    async def _scrape_with_playwright(
        self,
        category: Optional[str],
        limit: Optional[int],
    ) -> list[RawProduct]:
        """
        Use Playwright to scrape products from SGWS (handles JS rendering).

        Args:
            category: Category filter
            limit: Max products to fetch

        Returns:
            List of RawProduct objects
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed")
            return []

        products: list[RawProduct] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            # Set cookies from authentication (use full Playwright cookie format)
            if self._playwright_cookies:
                await context.add_cookies(self._playwright_cookies)
                logger.info(f"Added {len(self._playwright_cookies)} cookies to Playwright context")

            page = await context.new_page()

            try:
                # Navigate to search page with category filter
                search_url = f"{self.base_url}/sgws/en/usd/search"
                if category:
                    search_url += f"?text=&f-category={category}"
                else:
                    search_url += "?text="

                logger.info(f"Navigating to: {search_url}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

                # Wait for JS to render products
                await asyncio.sleep(10)

                # Check current URL - if redirected to login, we need to log in again
                current_url = page.url
                logger.info(f"After navigation, current URL: {current_url}")

                if "/login" in current_url and "login=true" not in current_url:
                    logger.warning("Session expired - need to re-authenticate")
                    await page.screenshot(path="/tmp/sgws_search.png")
                    return []

                # Scroll down to trigger lazy loading
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)

                # Take screenshot for debugging
                await page.screenshot(path="/tmp/sgws_search.png")
                logger.info("Screenshot saved to /tmp/sgws_search.png")

                # Debug: save page HTML
                html_content = await page.content()
                with open("/tmp/sgws_search.html", "w") as f:
                    f.write(html_content)
                logger.info(f"Page HTML saved ({len(html_content)} chars)")

                # Handle cookie consent popup if present
                try:
                    accept_btn = page.locator('button:has-text("Accept All"), button:has-text("Accept"), [id*="accept"]')
                    if await accept_btn.count() > 0:
                        await accept_btn.first.click(timeout=5000)
                        logger.info("Clicked cookie accept button")
                        await asyncio.sleep(2)
                except Exception:
                    pass

                # SGWS uses React/MUI - product grid items use dynamic class names
                # We'll directly extract from product links which are consistent
                logger.info("Using product link extraction...")

                # Get all links that look like product links (with frompage param to filter search results)
                product_links = page.locator('a[href*="/p/"][href*="frompage"]')
                link_count = await product_links.count()
                logger.info(f"Found {link_count} product links with frompage param")

                # Track seen SKUs to avoid duplicates
                seen_skus: set[str] = set()

                # Extract product info from links
                for i in range(link_count):
                    try:
                        link = product_links.nth(i)
                        href = await link.get_attribute("href")

                        if not href:
                            continue

                        # Extract SKU from URL (/Product-Name/p/SKU?frompage=searchPage)
                        sku_match = re.search(r'/p/(\d+)', href)
                        if not sku_match:
                            continue

                        sku = sku_match.group(1)
                        if sku in seen_skus:
                            continue
                        seen_skus.add(sku)

                        # Extract product name from URL (before /p/)
                        name_match = re.search(r'/([^/]+)/p/\d+', href)
                        if name_match:
                            # Convert URL slug to readable name
                            raw_name = name_match.group(1)
                            name = raw_name.replace("-", " ").strip()
                        else:
                            name = f"Product {sku}"

                        products.append(RawProduct(
                            external_id=sku,
                            name=name,
                            category=category.lower() if category else None,
                            price=None,  # Price would need more complex extraction
                            price_type="case",
                            url=f"{self.base_url}{href}" if href.startswith("/") else href,
                        ))

                        # Respect limit
                        if limit and len(products) >= limit:
                            break

                    except Exception as e:
                        logger.debug(f"Error extracting product {i}: {e}")
                        continue

                logger.info(f"Scraped {len(products)} products from Playwright")

            except Exception as e:
                logger.error(f"Playwright scraping error: {e}")
                import traceback
                logger.error(traceback.format_exc())

            finally:
                await browser.close()

        return products

    async def _scrape_html_search(
        self,
        category: Optional[str],
        page: int,
    ) -> list[RawProduct]:
        """
        Fallback: Scrape product data from HTML search results.

        Args:
            category: Category filter
            page: Page number

        Returns:
            List of RawProduct objects
        """
        products: list[RawProduct] = []

        # Build search URL - SGWS uses /sgws/en/usd/search format
        params = {"text": "", "currentPage": page}
        if category:
            params["f-category"] = category

        try:
            # Try the shop search URL
            response = await self._request(
                "GET",
                f"{self.base_url}/sgws/en/usd/search",
                params=params,
            )
            html = response.text
            logger.info(f"HTML search response length: {len(html)} chars")

            # Extract product data from HTML using various patterns

            # Pattern for product SKUs in URLs (e.g., /p/563699 or /p/SKU123)
            sku_pattern = r'/p/([A-Za-z0-9-]+)'
            skus = list(set(re.findall(sku_pattern, html)))  # Dedupe

            # Pattern for product names (various formats)
            name_patterns = [
                r'data-product-name="([^"]+)"',
                r'class="product-name[^"]*"[^>]*>([^<]+)<',
                r'title="([^"]+)"\s+class="[^"]*product',
                r'<h[23][^>]*class="[^"]*product[^"]*"[^>]*>([^<]+)<',
            ]
            names = []
            for pattern in name_patterns:
                found = re.findall(pattern, html)
                if found:
                    names.extend(found)
                    break

            # Pattern for prices
            price_pattern = r'\$([0-9,]+\.\d{2})'
            prices = re.findall(price_pattern, html)

            logger.info(f"Found {len(skus)} SKUs, {len(names)} names, {len(prices)} prices")

            # Create products from extracted data
            for i, sku in enumerate(skus[:50]):  # Limit to first 50
                name = names[i] if i < len(names) else f"Product {sku}"
                price = float(prices[i].replace(",", "")) if i < len(prices) else None

                products.append(RawProduct(
                    external_id=sku,
                    name=name,
                    category=category.lower() if category else None,
                    price=price,
                    price_type="case",
                    url=f"{self.base_url}/sgws/en/usd/product/p/{sku}",
                ))

            # If no products found, log sample of HTML for debugging
            if not products:
                logger.warning(f"No products parsed from HTML. First 500 chars: {html[:500]}")

        except Exception as e:
            logger.error(f"HTML scrape failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return products

    def _parse_product(
        self,
        data: dict[str, Any],
        category: Optional[str] = None,
    ) -> Optional[RawProduct]:
        """
        Parse SGWS API response into RawProduct.

        Args:
            data: Product data from API
            category: Category filter string

        Returns:
            RawProduct or None if parsing fails
        """
        try:
            # Extract SKU/external ID
            external_id = str(
                data.get("code")
                or data.get("sku")
                or data.get("productCode")
                or data.get("id")
                or ""
            )
            if not external_id:
                logger.warning(f"Product missing ID: {data.get('name')}")
                return None

            # Extract name
            name = (
                data.get("name")
                or data.get("productName")
                or data.get("displayName")
                or "Unknown"
            )

            # Extract brand (often in name or separate field)
            brand = data.get("brand") or data.get("manufacturer")
            if not brand and name:
                # Try to extract brand from name (usually first word(s))
                parts = name.split()
                if len(parts) > 1:
                    brand = parts[0]

            # Parse category
            parsed_category = None
            if category:
                parsed_category = category.lower()
            elif data.get("category"):
                parsed_category = data["category"].lower()

            # Parse subcategory
            parsed_subcategory = data.get("subcategory") or data.get("productType")

            # Extract volume (in ml)
            volume_ml = None
            size_str = data.get("size") or data.get("volume") or ""
            if size_str:
                # Parse sizes like "750ML", "1L", "1.75L"
                size_match = re.search(r'(\d+\.?\d*)\s*(ML|L|ml|l)', str(size_str), re.I)
                if size_match:
                    value = float(size_match.group(1))
                    unit = size_match.group(2).upper()
                    volume_ml = int(value * 1000 if unit == "L" else value)

            # Extract ABV
            abv = None
            abv_str = data.get("abv") or data.get("alcoholContent") or data.get("proof")
            if abv_str:
                try:
                    abv_val = float(re.sub(r'[^\d.]', '', str(abv_str)))
                    # If it looks like proof, convert to ABV
                    if abv_val > 100:
                        abv = abv_val / 2
                    else:
                        abv = abv_val
                except (ValueError, TypeError):
                    pass

            # Extract prices
            price = None
            price_type = "case"

            # Try case price first
            case_price = data.get("casePrice") or data.get("price", {}).get("value")
            if case_price:
                try:
                    price = float(str(case_price).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Unit price as fallback
            if not price:
                unit_price = data.get("unitPrice") or data.get("bottlePrice")
                if unit_price:
                    try:
                        price = float(str(unit_price).replace("$", "").replace(",", ""))
                        price_type = "bottle"
                    except (ValueError, TypeError):
                        pass

            # Inventory/stock status
            inventory = None
            in_stock = True
            stock_data = data.get("stock") or data.get("availability") or {}
            if isinstance(stock_data, dict):
                inventory = stock_data.get("stockLevel")
                in_stock = stock_data.get("inStock", True)
            elif data.get("inStock") is not None:
                in_stock = data.get("inStock")

            # Image URL
            image_url = None
            images = data.get("images") or []
            if images and isinstance(images, list):
                image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
            elif data.get("imageUrl"):
                image_url = data["imageUrl"]
            elif data.get("thumbnailUrl"):
                image_url = data["thumbnailUrl"]

            # Build product URL
            url_slug = data.get("url") or data.get("slug")
            if url_slug:
                url = f"{self.base_url}{url_slug}" if url_slug.startswith("/") else url_slug
            else:
                url = f"{self.base_url}/sgws/en/usd/product/p/{external_id}"

            # Description
            description = data.get("description") or data.get("summary")

            # UPC
            upc = data.get("upc") or data.get("ean") or data.get("barcode")

            return RawProduct(
                external_id=external_id,
                name=name,
                brand=brand,
                category=parsed_category,
                subcategory=parsed_subcategory,
                volume_ml=volume_ml,
                abv=abv,
                price=price,
                price_type=price_type,
                inventory=inventory,
                in_stock=in_stock,
                available_states=None,  # SGWS doesn't expose this in search
                image_url=image_url,
                description=description,
                upc=upc,
                url=url,
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing SGWS product: {e}")
            return None

    async def search_products(
        self,
        query: str,
        limit: int = 50,
    ) -> list[RawProduct]:
        """
        Search for products by name/keyword.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        params = {
            "text": query,
            "pageSize": min(limit, 100),
        }

        try:
            response = await self._request(
                "GET",
                f"{self.base_url}/sgws/en/usd/search/results",
                params=params,
            )
            data = response.json()

            products = []
            for p in data.get("products", [])[:limit]:
                product = self._parse_product(p)
                if product:
                    products.append(product)

            return products

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
