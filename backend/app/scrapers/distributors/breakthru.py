"""
ABVTrends - Breakthru Beverage Group Scraper

Scrapes product data from Breakthru Now portal (now.breakthrubev.com).

Breakthru Beverage Group is one of the largest alcohol distributors in North America,
formed from the merger of Charmer Sunbelt Group and Wirtz Beverage Group.

API Discovery Notes:
- Base URL: https://now.breakthrubev.com
- Login URL: /bbg/en/login
- Product catalog: /bbg/en/Shop-All/Spirits/<Category>/c/<category-slug>
- Uses Gigya SDK for authentication (SAP Customer Identity)
- Uses Hybris/SAP Commerce Cloud backend
- API endpoint: cdns.us1.gigya.com for auth
- Customer account shown in header (e.g., "VISTA WINE & SPIRITS 700373179")
"""

import asyncio
import logging
import re
from typing import Any, Optional

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct
from app.scrapers.utils.stealth_context import StealthContextFactory

logger = logging.getLogger(__name__)


class BreakthruScraper(BaseDistributorScraper):
    """
    Scraper for Breakthru Beverage Group (Breakthru Now) portal.

    Breakthru Now provides wholesale pricing and ordering for licensed
    retailers. Products include spirits, wine, beer, and RTD beverages.
    """

    name = "breakthru"
    base_url = "https://now.breakthrubev.com"

    # Categories to scrape with their URL slugs
    CATEGORIES = [
        {"name": "spirits", "url_path": "Spirits", "slug": "spirits"},
        {"name": "wine", "url_path": "Wine", "slug": "wine"},
        {"name": "beer", "url_path": "Beer", "slug": "beer"},
        {"name": "rtd", "url_path": "Ready-to-Drink", "slug": "ready-to-drink"},
        {"name": "mixers", "url_path": "Mixers-More", "slug": "mixers-more"},
    ]

    # Spirit subcategories for granular scraping
    SPIRIT_SUBCATEGORIES = [
        {"name": "Vodka", "slug": "vodka"},
        {"name": "Whiskey", "slug": "whiskey"},
        {"name": "Tequila", "slug": "tequila"},
        {"name": "Rum", "slug": "rum"},
        {"name": "Gin", "slug": "gin"},
        {"name": "Brandy & Cognac", "slug": "brandy-cognac"},
        {"name": "Mezcal", "slug": "mezcal"},
        {"name": "Liqueurs & Cordials", "slug": "liqueurs-cordials"},
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize Breakthru scraper.

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

    async def authenticate(self) -> bool:
        """
        Authenticate with Breakthru Now.

        Breakthru uses Gigya (SAP Customer Identity) for authentication.
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
            logger.error(f"Breakthru authentication failed: {e}")

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
            logger.error("Breakthru credentials not provided")
            return False

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            # Use stealth context factory for anti-detection
            self._context = await StealthContextFactory.create_context(self._browser)
            self._page = await self._context.new_page()

            # Navigate to Breakthru login
            logger.info("Navigating to Breakthru Now...")
            await self._page.goto(
                f"{self.base_url}/bbg/en/login",
                wait_until="domcontentloaded",
                timeout=60000
            )
            await asyncio.sleep(3)

            current_url = self._page.url
            logger.info(f"Current URL: {current_url}")

            # Check if already logged in
            if "/Shop-All" in current_url or "My-Account" in current_url:
                logger.info("Already logged in!")
                self._cookies = await self._context.cookies()
                return True

            # Accept cookies if dialog appears
            try:
                accept_btn = await self._page.wait_for_selector(
                    'button:has-text("Accept")', timeout=5000
                )
                if accept_btn:
                    await accept_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass  # Cookie dialog may not appear

            # Fill login form - Gigya login form
            # NOTE: The visible login form uses 'username' field, not 'email'
            # Multiple hidden forms exist, so we need to find the visible one using bounding_box
            logger.info("Filling login form...")

            # Wait for form to fully load
            await asyncio.sleep(2)

            # Find visible username/email input (Gigya uses 'username' for email on visible form)
            email_filled = False
            for field_name in ['username', 'email', 'loginID']:
                inputs = self._page.locator(f'input[name="{field_name}"]')
                count = await inputs.count()
                for i in range(count):
                    try:
                        input_el = inputs.nth(i)
                        bbox = await input_el.bounding_box()
                        if bbox and bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
                            await input_el.fill(email)
                            email_filled = True
                            logger.info(f"Email filled using {field_name} input {i}")
                            break
                    except Exception:
                        continue
                if email_filled:
                    break

            if not email_filled:
                logger.error("Could not find visible email/username field")
                await self._page.screenshot(path="/tmp/breakthru_no_email.png")
                return False

            await asyncio.sleep(0.5)

            # Find visible password input
            password_filled = False
            password_inputs = self._page.locator('input[type="password"]')
            pwd_count = await password_inputs.count()
            for i in range(pwd_count):
                try:
                    input_el = password_inputs.nth(i)
                    bbox = await input_el.bounding_box()
                    if bbox and bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
                        await input_el.fill(password)
                        password_filled = True
                        logger.info(f"Password filled using input {i}")
                        break
                except Exception:
                    continue

            if not password_filled:
                logger.error("Could not find visible password field")
                await self._page.screenshot(path="/tmp/breakthru_no_password.png")
                return False

            await asyncio.sleep(0.5)

            # Find and click visible login button
            login_clicked = False
            login_btns = self._page.locator(
                'input[type="submit"].gigya-input-submit, button:has-text("Log In"), input[type="submit"][value*="Log"]'
            )
            btn_count = await login_btns.count()
            for i in range(btn_count):
                try:
                    btn_el = login_btns.nth(i)
                    bbox = await btn_el.bounding_box()
                    if bbox and bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
                        await btn_el.click()
                        login_clicked = True
                        logger.info(f"Login button clicked (button {i})")
                        break
                except Exception:
                    continue

            if not login_clicked:
                logger.error("Could not find visible login button")
                await self._page.screenshot(path="/tmp/breakthru_no_login_btn.png")
                return False

            # Wait for navigation after login
            logger.info("Waiting for login to complete...")
            await asyncio.sleep(5)

            # Check if login was successful
            current_url = self._page.url
            logger.info(f"Post-login URL: {current_url}")

            # Look for indicators of successful login
            if "login" not in current_url.lower() or "/bbg/en/" in current_url:
                # Check for account indicator in header
                try:
                    account_indicator = await self._page.query_selector('[class*="account"], [class*="user"], .my-account')
                    if account_indicator:
                        logger.info("Login successful - found account indicator")
                        self._cookies = await self._context.cookies()
                        return True
                except Exception:
                    pass

                # Check page content for logged-in state
                page_content = await self._page.content()
                if "My Account" in page_content or "Shop All" in page_content:
                    logger.info("Login successful - found logged-in content")
                    self._cookies = await self._context.cookies()
                    return True

            # Wait a bit more and try navigation
            await asyncio.sleep(3)
            await self._page.goto(f"{self.base_url}/bbg/en/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            page_content = await self._page.content()
            if "My Account" in page_content or "SPIRITS" in page_content:
                logger.info("Login confirmed after navigation")
                self._cookies = await self._context.cookies()
                return True

            logger.error("Login verification failed")
            await self._page.screenshot(path="/tmp/breakthru_login_failed.png")
            return False

        except Exception as e:
            logger.error(f"Playwright login error: {e}")
            if self._page:
                await self._page.screenshot(path="/tmp/breakthru_error.png")
            return False

    async def get_products(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[RawProduct]:
        """
        Fetch products from Breakthru Now.

        Args:
            category: Optional category filter (e.g., "spirits", "wine")
            limit: Max products to fetch
            offset: Pagination offset (not used, pagination handled internally)

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        products: list[RawProduct] = []

        # Determine category to scrape
        cat_to_use = "spirits"  # Default
        if category:
            cat_to_use = category.lower()

        # Scrape the category
        raw_products = await self._get_category_products(cat_to_use)

        for product in raw_products:
            raw_product = self._convert_to_raw_product(product, cat_to_use)
            if raw_product:
                products.append(raw_product)

                # Respect limit
                if limit and len(products) >= limit:
                    break

        logger.info(f"get_products returned {len(products)} products")
        return products

    async def _get_category_products(
        self,
        category: str,
        subcategory: Optional[str] = None,
        page: int = 0,
        page_size: int = 100
    ) -> list[dict]:
        """
        Get products from a category page.

        Args:
            category: Category slug (e.g., "spirits", "wine")
            subcategory: Optional subcategory slug (e.g., "vodka")
            page: Page number (0-indexed)
            page_size: Products per page

        Returns:
            List of raw product dictionaries
        """
        if not self._page:
            logger.error("No browser page available")
            return []

        # Build URL for category
        if subcategory:
            url = f"{self.base_url}/bbg/en/Shop-All/{category.title()}/{subcategory}/c/{subcategory.lower()}"
        else:
            url = f"{self.base_url}/bbg/en/Shop-All/{category.title()}/c/{category.lower()}"

        if page > 0:
            url += f"?page={page}"

        logger.info(f"Fetching products from: {url}")

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)  # Extra time for product grid to load

            # Take screenshot for debugging
            await self._page.screenshot(path="/tmp/breakthru_products.png")
            logger.info(f"Screenshot saved to /tmp/breakthru_products.png")

            # Check current URL after navigation
            current_url = self._page.url
            logger.info(f"After navigation, URL is: {current_url}")

            # Wait for products to load - try multiple selectors
            product_found = False
            selectors_to_try = [
                '[data-product-id]',
                '.m-product-card',
                '.product-card',
                '[class*="product"]',
                'a[href*="/p/"]',
            ]

            for selector in selectors_to_try:
                try:
                    await self._page.wait_for_selector(selector, timeout=5000)
                    count = await self._page.locator(selector).count()
                    logger.info(f"Found {count} elements matching selector: {selector}")
                    if count > 0:
                        product_found = True
                        break
                except Exception:
                    continue

            if not product_found:
                logger.warning(f"No products found at {url}")
                # Save HTML for debugging
                html = await self._page.content()
                with open("/tmp/breakthru_products.html", "w") as f:
                    f.write(html)
                logger.info(f"Saved HTML ({len(html)} chars) to /tmp/breakthru_products.html")
                return []

            # Extract product data from page
            products = await self._extract_products_from_page()
            logger.info(f"Extracted {len(products)} products from {url}")

            return products

        except Exception as e:
            logger.error(f"Error fetching category {category}: {e}")
            return []

    async def _extract_products_from_page(self) -> list[dict]:
        """
        Extract product data from current page.

        The Breakthru Now page uses a specific structure:
        - Product cards are in .m-product-card containers
        - Product IDs can be found in data-product-id attributes or extracted from URLs
        - Product names are in links with href containing /p/

        Returns:
            List of product dictionaries
        """
        if not self._page:
            return []

        try:
            # Extract products using the m-product-card class structure
            products = await self._page.evaluate("""
                () => {
                    const products = [];
                    const seen = new Set();

                    // Find product cards by traversing from data-product-id elements
                    const productElements = document.querySelectorAll('[data-product-id]');
                    const productCards = new Set();

                    productElements.forEach(el => {
                        // Traverse up to find a card-like container
                        let current = el;
                        for (let i = 0; i < 10; i++) {
                            if (current.parentElement) {
                                current = current.parentElement;
                                if (current.className && (
                                    current.className.includes('product') ||
                                    current.className.includes('card') ||
                                    current.className.includes('tile') ||
                                    current.className.includes('item')
                                )) {
                                    productCards.add(current);
                                    break;
                                }
                            }
                        }
                    });

                    productCards.forEach(card => {
                        try {
                            // Get product link which contains the product ID
                            const linkEl = card.querySelector('a[href*="/p/"]');
                            if (!linkEl) return;

                            const url = linkEl.href;

                            // Extract product ID from URL (e.g., /p/12345)
                            const urlMatch = url.match(/\\/p\\/([\\w-]+)/);
                            const productId = urlMatch ? urlMatch[1] : null;

                            if (productId && seen.has(productId)) return;
                            if (productId) seen.add(productId);

                            // Get product name from the link text or a specific name element
                            const nameLink = card.querySelector('a[href*="/p/"].a-text');
                            let name = nameLink ? nameLink.textContent.trim() : null;

                            // Fallback to other selectors if needed
                            if (!name) {
                                const h3 = card.querySelector('h3');
                                name = h3 ? h3.textContent.trim() : null;
                            }

                            if (!name) {
                                const nameEl = card.querySelector('[class*="name"]');
                                name = nameEl ? nameEl.textContent.trim() : null;
                            }

                            // Get price
                            const priceEl = card.querySelector('.a-price, [class*="price"]');
                            let priceText = priceEl ? priceEl.textContent.trim() : null;

                            // Get image
                            const imageEl = card.querySelector('img');
                            const image = imageEl ? imageEl.src : null;

                            // Parse price
                            let price = null;
                            if (priceText) {
                                const match = priceText.match(/\\$([\\d,]+\\.?\\d*)/);
                                if (match) {
                                    price = parseFloat(match[1].replace(',', ''));
                                }
                            }

                            // Only add if we have a valid name (not badges like "Out Of Stock")
                            if (name && name.length > 5 && !name.startsWith('Out Of') && !name.startsWith('New')) {
                                products.push({
                                    name,
                                    price,
                                    sku: productId,
                                    image_url: image,
                                    url,
                                    raw_price: priceText
                                });
                            }
                        } catch (e) {
                            console.error('Error parsing product:', e);
                        }
                    });

                    return products;
                }
            """)

            return products or []

        except Exception as e:
            logger.error(f"Error extracting products: {e}")
            return []

    async def scrape_products(
        self,
        categories: Optional[list[str]] = None,
        max_products: Optional[int] = None,
    ) -> list[RawProduct]:
        """
        Scrape products from Breakthru Now.

        Args:
            categories: List of categories to scrape (default: all)
            max_products: Maximum products to scrape (default: no limit)

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            if not await self.authenticate():
                logger.error("Failed to authenticate with Breakthru")
                return []

        all_products: list[RawProduct] = []

        # Filter categories if specified
        cats_to_scrape = self.CATEGORIES
        if categories:
            cats_to_scrape = [c for c in self.CATEGORIES if c["name"] in categories]

        for category in cats_to_scrape:
            cat_name = category["name"]
            cat_slug = category["slug"]

            logger.info(f"Scraping category: {cat_name}")

            # For spirits, scrape subcategories
            if cat_name == "spirits":
                for subcat in self.SPIRIT_SUBCATEGORIES:
                    if max_products and len(all_products) >= max_products:
                        break

                    subcat_products = await self._scrape_subcategory(
                        cat_slug, subcat["slug"], cat_name, subcat["name"]
                    )
                    all_products.extend(subcat_products)

                    if max_products and len(all_products) >= max_products:
                        all_products = all_products[:max_products]
                        break

                    await asyncio.sleep(2)  # Rate limiting
            else:
                # Scrape category pages
                page = 0
                while True:
                    if max_products and len(all_products) >= max_products:
                        break

                    products = await self._get_category_products(cat_slug, page=page)

                    if not products:
                        break

                    for product in products:
                        raw_product = self._convert_to_raw_product(product, cat_name)
                        if raw_product:
                            all_products.append(raw_product)

                    page += 1
                    await asyncio.sleep(2)  # Rate limiting

                    # Safety limit per category
                    if page >= 50:
                        break

        logger.info(f"Total products scraped from Breakthru: {len(all_products)}")
        return all_products

    async def _scrape_subcategory(
        self,
        category_slug: str,
        subcategory_slug: str,
        category_name: str,
        subcategory_name: str,
    ) -> list[RawProduct]:
        """
        Scrape a subcategory.

        Args:
            category_slug: Main category slug
            subcategory_slug: Subcategory slug
            category_name: Category name for product data
            subcategory_name: Subcategory name for product data

        Returns:
            List of RawProduct objects
        """
        products: list[RawProduct] = []
        page = 0

        while True:
            page_products = await self._get_category_products(
                category_slug, subcategory=subcategory_slug, page=page
            )

            if not page_products:
                break

            for product in page_products:
                raw_product = self._convert_to_raw_product(
                    product, category_name, subcategory_name
                )
                if raw_product:
                    products.append(raw_product)

            page += 1
            await asyncio.sleep(1)

            # Safety limit
            if page >= 20:
                break

        logger.info(f"Scraped {len(products)} products from {subcategory_name}")
        return products

    def _convert_to_raw_product(
        self,
        product: dict,
        category: str,
        subcategory: Optional[str] = None,
    ) -> Optional[RawProduct]:
        """
        Convert raw product dict to RawProduct object.

        Args:
            product: Raw product dictionary
            category: Category name
            subcategory: Subcategory name

        Returns:
            RawProduct object or None if invalid
        """
        name = product.get("name")
        if not name:
            return None

        # Generate external ID from SKU or name
        external_id = product.get("sku") or self._generate_id(name)

        # Parse size from name
        size = self._extract_size(name)

        # Parse ABV from name if present
        abv = self._extract_abv(name)

        # Extract brand from name (usually first part before product name)
        brand = self._extract_brand(name)

        return RawProduct(
            external_id=str(external_id),
            name=name,
            brand=brand,
            category=category,
            subcategory=subcategory,
            price=float(product.get("price")) if product.get("price") else None,
            price_type="case",
            volume_ml=self._parse_volume_ml(size) if size else None,
            abv=abv,
            image_url=product.get("image_url"),
            url=product.get("url"),
            in_stock=True,  # Assume in stock if shown
            raw_data=product,
        )

    def _generate_id(self, name: str) -> str:
        """Generate a unique ID from product name."""
        import hashlib
        return hashlib.md5(name.encode()).hexdigest()[:12]

    def _extract_size(self, name: str) -> Optional[str]:
        """Extract bottle size from product name."""
        patterns = [
            r'(\d+(?:\.\d+)?\s*(?:ml|ML|liter|L|oz|OZ))',
            r'(\d+(?:\.\d+)?(?:ml|ML|L))',
        ]
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _parse_volume_ml(self, size: str) -> Optional[int]:
        """Convert size string to volume in ml."""
        if not size:
            return None
        size_lower = size.lower().strip()
        match = re.search(r'(\d+(?:\.\d+)?)\s*(ml|l|liter|oz)', size_lower)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit == "l" or unit == "liter":
                return int(value * 1000)
            elif unit == "oz":
                return int(value * 29.5735)  # 1 oz = ~29.57 ml
            else:
                return int(value)
        return None

    def _extract_abv(self, name: str) -> Optional[float]:
        """Extract ABV percentage from product name."""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*%\s*(?:ABV|alc|alcohol)',
            r'(\d+(?:\.\d+)?)\s*%',
        ]
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _extract_brand(self, name: str) -> Optional[str]:
        """Extract brand name from product name."""
        # Usually the brand is the first few words
        parts = name.split()
        if len(parts) >= 2:
            # Return first 2-3 words as brand (heuristic)
            return " ".join(parts[:2])
        return None

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
