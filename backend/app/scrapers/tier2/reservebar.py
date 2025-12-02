"""
ABVTrends - ReserveBar Scraper

Scrapes product data from ReserveBar.com.
ReserveBar is a premium spirits e-commerce platform specializing in luxury and hard-to-find bottles.
"""

import logging
import re
from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from app.models.signal import SignalType
from app.scrapers.utils.base_scraper import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class ReserveBarScraper(BaseScraper):
    """
    Scraper for ReserveBar.com product listings.

    Targets:
    - New arrivals
    - Best sellers
    - Limited editions
    - Premium/luxury spirits
    - Gift sets

    ReserveBar is particularly valuable for tracking premium and collector spirits.
    """

    SOURCE_NAME = "reservebar"
    BASE_URL = "https://www.reservebar.com"

    CATEGORY_URLS = [
        "/collections/whats-new",
        "/collections/best-sellers",
        "/collections/limited-editions",
        "/collections/whiskey",
        "/collections/tequila",
        "/collections/vodka",
        "/collections/gin",
        "/collections/rum",
        "/collections/cognac-brandy",
        "/collections/champagne-wine",
    ]

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_base_url(self) -> str:
        return self.BASE_URL

    async def scrape(self) -> list[ScrapedItem]:
        """
        Scrape ReserveBar for product data.

        Returns:
            List of ScrapedItem objects
        """
        items: list[ScrapedItem] = []
        seen_products: set[str] = set()

        for url_path in self.CATEGORY_URLS:
            try:
                url = self.build_url(url_path)
                logger.info(f"Scraping ReserveBar: {url}")

                # ReserveBar may use some JS, try browser if needed
                try:
                    html = await self.fetch_html(url)
                except Exception:
                    html = await self.fetch_html(
                        url,
                        use_browser=True,
                        wait_for_selector=".product-card, .product-item",
                    )

                soup = self.parse_html(html)

                is_new = "whats-new" in url_path
                is_limited = "limited" in url_path

                products = self._extract_products(soup, is_new, is_limited)

                for product in products:
                    product_key = product.title
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        items.append(product)

            except Exception as e:
                logger.error(f"Error scraping ReserveBar {url_path}: {e}")
                continue

        logger.info(f"ReserveBar scraper found {len(items)} products")
        return items

    def _extract_products(
        self,
        soup: BeautifulSoup,
        is_new_arrival: bool = False,
        is_limited: bool = False,
    ) -> list[ScrapedItem]:
        """Extract products from page HTML."""
        items: list[ScrapedItem] = []

        # ReserveBar product selectors
        product_selectors = [
            ".product-card",
            ".product-item",
            ".collection-product",
            'div[class*="product"]',
            ".grid-item",
        ]

        products: list[Tag] = []
        for selector in product_selectors:
            found = soup.select(selector)
            if found:
                products = found
                break

        for product in products[:30]:
            try:
                item = self._parse_product(product, is_new_arrival, is_limited)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing ReserveBar product: {e}")
                continue

        return items

    def _parse_product(
        self,
        product: Tag,
        is_new_arrival: bool = False,
        is_limited: bool = False,
    ) -> Optional[ScrapedItem]:
        """Parse a single product card."""
        # Extract product name
        name_elem = product.select_one(
            ".product-card__title, .product-title, .product-name, h2, h3"
        )
        if not name_elem:
            # Try link text
            link = product.select_one("a[href*='/products/']")
            if link:
                name_elem = link

        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        # Extract URL
        link_elem = product.select_one("a[href*='/products/']")
        if not link_elem:
            link_elem = product.select_one("a[href]")

        url = link_elem.get("href", "") if link_elem else ""
        if url and not url.startswith("http"):
            url = self.build_url(url)

        # Extract price
        price_data = self._extract_price(product)

        # Extract brand
        brand_elem = product.select_one(".product-brand, .vendor, [class*='brand']")
        brand = brand_elem.get_text(strip=True) if brand_elem else None

        if not brand:
            brand = self._extract_brand_from_name(name)

        # Check for badges/tags
        badges = self._extract_badges(product)

        # Check availability
        sold_out = bool(product.select_one(
            ".sold-out, .out-of-stock, [class*='soldout']"
        ))

        # Extract image
        img_elem = product.select_one("img")
        image_url = None
        if img_elem:
            image_url = (
                img_elem.get("src")
                or img_elem.get("data-src")
                or img_elem.get("data-srcset", "").split()[0]
            )
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url

        # Extract size/volume
        size = self._extract_size(name, product)

        # Determine signal type
        signal_type = self._determine_signal_type(
            is_new_arrival, is_limited, sold_out, badges
        )

        raw_data: dict[str, Any] = {
            "source": self.SOURCE_NAME,
            "brand": brand,
            "price": price_data.get("current"),
            "original_price": price_data.get("original"),
            "size": size,
            "is_new_arrival": is_new_arrival,
            "is_limited_edition": is_limited or "limited" in badges,
            "is_exclusive": "exclusive" in badges,
            "in_stock": not sold_out,
            "badges": list(badges),
            "image_url": image_url,
            "scraped_at": datetime.utcnow().isoformat(),
        }

        return ScrapedItem(
            signal_type=signal_type,
            title=name,
            url=url,
            raw_data=raw_data,
            captured_at=datetime.utcnow(),
            product_hint=name,
        )

    def _extract_price(self, product: Tag) -> dict[str, Any]:
        """Extract price information."""
        result: dict[str, Any] = {}

        # Current price
        price_selectors = [
            ".product-price", ".price", ".money",
            "[class*='price']", "span[class*='Price']"
        ]

        for selector in price_selectors:
            elem = product.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                price = self._parse_price(text)
                if price:
                    result["current"] = price
                    break

        # Compare-at/original price
        compare_selectors = [
            ".compare-at-price", ".was-price", "s", "del",
            "[class*='compare']", "[class*='original']"
        ]

        for selector in compare_selectors:
            elem = product.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                price = self._parse_price(text)
                if price:
                    result["original"] = price
                    break

        return result

    def _parse_price(self, text: str) -> Optional[str]:
        """Parse price value from text."""
        match = re.search(r"\$?\s*(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)", text)
        if match:
            return match.group(1).replace(",", "")
        return None

    def _extract_badges(self, product: Tag) -> set[str]:
        """Extract product badges/tags."""
        badges: set[str] = set()

        badge_elems = product.select(
            ".badge, .tag, .label, [class*='badge'], [class*='tag']"
        )

        for elem in badge_elems:
            text = elem.get_text(strip=True).lower()
            if text:
                badges.add(text)

        # Check for specific indicators in the HTML
        if product.select_one("[class*='limited']"):
            badges.add("limited")
        if product.select_one("[class*='exclusive']"):
            badges.add("exclusive")
        if product.select_one("[class*='new']"):
            badges.add("new")

        return badges

    def _extract_brand_from_name(self, name: str) -> Optional[str]:
        """Extract brand from product name."""
        # ReserveBar often has format: "Brand Name - Product Details"
        if " - " in name:
            return name.split(" - ")[0].strip()

        # Take first 2-3 words if capitalized
        words = name.split()
        brand_words = []

        for word in words[:3]:
            # Skip common product type words
            skip_words = [
                "whiskey", "bourbon", "scotch", "vodka", "gin", "rum",
                "tequila", "mezcal", "cognac", "brandy", "750ml", "1l"
            ]
            if word.lower() in skip_words:
                break
            if word[0].isupper():
                brand_words.append(word)

        if brand_words:
            return " ".join(brand_words)
        return None

    def _extract_size(self, name: str, product: Tag) -> Optional[str]:
        """Extract bottle size."""
        # Try to find size element
        size_elem = product.select_one(".size, .variant, [class*='size']")
        if size_elem:
            return size_elem.get_text(strip=True)

        # Extract from name
        size_patterns = [
            r"(\d+(?:\.\d+)?\s*ml)",
            r"(\d+(?:\.\d+)?\s*L)",
            r"(\d+(?:\.\d+)?\s*liter)",
        ]

        for pattern in size_patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _determine_signal_type(
        self,
        is_new_arrival: bool,
        is_limited: bool,
        sold_out: bool,
        badges: set[str],
    ) -> SignalType:
        """Determine signal type."""
        if sold_out:
            return SignalType.OUT_OF_STOCK

        if is_new_arrival or "new" in badges:
            return SignalType.NEW_SKU

        # Limited editions are significant signals
        if is_limited or "limited" in badges:
            return SignalType.NEW_SKU

        return SignalType.NEW_SKU

    async def scrape_limited_editions(self) -> list[ScrapedItem]:
        """
        Specifically scrape limited edition products.

        These are high-value trend signals.
        """
        url = self.build_url("/collections/limited-editions")

        try:
            html = await self.fetch_html(url)
            soup = self.parse_html(html)
            return self._extract_products(soup, is_limited=True)
        except Exception as e:
            logger.error(f"Error scraping ReserveBar limited editions: {e}")
            return []

    async def scrape_gift_sets(self) -> list[ScrapedItem]:
        """
        Scrape gift sets - useful for seasonal trends.
        """
        url = self.build_url("/collections/gifts")

        try:
            html = await self.fetch_html(url)
            soup = self.parse_html(html)
            return self._extract_products(soup)
        except Exception as e:
            logger.error(f"Error scraping ReserveBar gifts: {e}")
            return []
