"""
ABVTrends - TotalWine Scraper

Scrapes product data from TotalWine.com.
TotalWine is the largest independent retailer of fine wine and spirits in the US.
"""

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from app.models.signal import SignalType
from app.scrapers.utils.base_scraper import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class TotalWineScraper(BaseScraper):
    """
    Scraper for TotalWine.com product listings.

    Targets:
    - New arrivals
    - Best sellers
    - Category pages (spirits, wine, beer)
    - Sale/promotion items

    Extracts:
    - Product name and brand
    - Price and sale price
    - Rating and reviews
    - Availability status
    - Category classification
    """

    SOURCE_NAME = "totalwine"
    BASE_URL = "https://www.totalwine.com"

    # Category URLs for scraping
    CATEGORY_URLS = [
        "/spirits/c/spirits",
        "/spirits/whiskey/c/000882",
        "/spirits/tequila/c/000864",
        "/spirits/vodka/c/000865",
        "/spirits/gin/c/000866",
        "/spirits/rum/c/000867",
        "/wine/c/wine",
        "/wine/red-wine/c/000006",
        "/wine/white-wine/c/000009",
        "/wine/champagne-sparkling-wine/c/000010",
        "/beer/c/beer",
    ]

    # New arrivals and trending
    SPECIAL_URLS = [
        "/spirits/new-arrivals/c/spiritsnew",
        "/spirits/top-rated/c/spiritstoprated",
        "/wine/new-arrivals/c/winenew",
        "/wine/top-rated/c/winetoprated",
    ]

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_base_url(self) -> str:
        return self.BASE_URL

    async def scrape(self) -> list[ScrapedItem]:
        """
        Scrape TotalWine for product data.

        Note: TotalWine is heavily JS-rendered, so we use Playwright browser.

        Returns:
            List of ScrapedItem objects
        """
        items: list[ScrapedItem] = []
        seen_products: set[str] = set()

        # Scrape special pages first (new arrivals, top rated)
        for url_path in self.SPECIAL_URLS:
            try:
                url = self.build_url(url_path)
                logger.info(f"Scraping TotalWine special: {url}")

                html = await self.fetch_html(
                    url,
                    use_browser=True,
                    wait_for_selector=".product-card, .plp-product-card",
                )
                soup = self.parse_html(html)

                products = self._extract_products(soup, is_new_arrival="new" in url_path)

                for product in products:
                    product_key = f"{product.title}_{product.raw_data.get('price')}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        items.append(product)

            except Exception as e:
                logger.error(f"Error scraping TotalWine {url_path}: {e}")
                continue

        # Scrape main category pages
        for url_path in self.CATEGORY_URLS[:5]:  # Limit to avoid too many requests
            try:
                url = self.build_url(url_path)
                logger.info(f"Scraping TotalWine category: {url}")

                html = await self.fetch_html(
                    url,
                    use_browser=True,
                    wait_for_selector=".product-card, .plp-product-card",
                )
                soup = self.parse_html(html)

                products = self._extract_products(soup)

                for product in products:
                    product_key = f"{product.title}_{product.raw_data.get('price')}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        items.append(product)

            except Exception as e:
                logger.error(f"Error scraping TotalWine {url_path}: {e}")
                continue

        logger.info(f"TotalWine scraper found {len(items)} products")
        return items

    def _extract_products(
        self, soup: BeautifulSoup, is_new_arrival: bool = False
    ) -> list[ScrapedItem]:
        """Extract products from page HTML."""
        items: list[ScrapedItem] = []

        # TotalWine product card selectors
        product_selectors = [
            ".product-card",
            ".plp-product-card",
            '[data-testid="product-card"]',
            ".product-item",
            'div[class*="productCard"]',
        ]

        products: list[Tag] = []
        for selector in product_selectors:
            found = soup.select(selector)
            if found:
                products = found
                break

        for product in products[:30]:  # Limit per page
            try:
                item = self._parse_product(product, is_new_arrival)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing TotalWine product: {e}")
                continue

        return items

    def _parse_product(
        self, product: Tag, is_new_arrival: bool = False
    ) -> Optional[ScrapedItem]:
        """Parse a single product card."""
        # Extract product name
        name_elem = product.select_one(
            ".product-card__name, .product-name, h3, [data-testid='product-name']"
        )
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        # Extract URL
        link_elem = product.select_one("a[href]")
        url = link_elem.get("href", "") if link_elem else ""
        if url and not url.startswith("http"):
            url = self.build_url(url)

        # Extract price
        price_data = self._extract_price(product)

        # Extract rating
        rating_data = self._extract_rating(product)

        # Extract brand (often in a separate element)
        brand_elem = product.select_one(".brand, .product-brand, [class*='brand']")
        brand = brand_elem.get_text(strip=True) if brand_elem else None

        # If no brand element, try to extract from name
        if not brand:
            brand = self._extract_brand_from_name(name)

        # Extract size/volume
        size_elem = product.select_one(".size, .product-size, [class*='size']")
        size = size_elem.get_text(strip=True) if size_elem else None

        # Check for sale/promotion
        is_on_sale = bool(product.select_one(
            ".sale, .promotion, .discount, [class*='sale']"
        ))

        # Check availability
        out_of_stock = bool(product.select_one(
            ".out-of-stock, .unavailable, [class*='outOfStock']"
        ))

        # Extract image
        img_elem = product.select_one("img")
        image_url = None
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")

        # Determine signal type
        signal_type = self._determine_signal_type(
            is_new_arrival, is_on_sale, out_of_stock, price_data
        )

        raw_data: dict[str, Any] = {
            "source": self.SOURCE_NAME,
            "brand": brand,
            "price": price_data.get("current"),
            "original_price": price_data.get("original"),
            "discount_percent": price_data.get("discount_percent"),
            "rating": rating_data.get("rating"),
            "review_count": rating_data.get("count"),
            "size": size,
            "is_on_sale": is_on_sale,
            "is_new_arrival": is_new_arrival,
            "in_stock": not out_of_stock,
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
        """Extract price information from product card."""
        result: dict[str, Any] = {}

        # Look for current/sale price
        price_selectors = [
            ".price", ".product-price", ".current-price",
            '[data-testid="product-price"]', "[class*='price']"
        ]

        for selector in price_selectors:
            price_elem = product.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_value = self._parse_price(price_text)
                if price_value:
                    result["current"] = price_value
                    break

        # Look for original/crossed-out price
        original_selectors = [
            ".original-price", ".was-price", ".strikethrough",
            "del", "s", "[class*='original']"
        ]

        for selector in original_selectors:
            original_elem = product.select_one(selector)
            if original_elem:
                original_text = original_elem.get_text(strip=True)
                original_value = self._parse_price(original_text)
                if original_value:
                    result["original"] = original_value
                    break

        # Calculate discount percentage
        if result.get("current") and result.get("original"):
            try:
                current = float(result["current"])
                original = float(result["original"])
                if original > current:
                    discount = ((original - current) / original) * 100
                    result["discount_percent"] = round(discount, 1)
            except (ValueError, ZeroDivisionError):
                pass

        return result

    def _parse_price(self, text: str) -> Optional[str]:
        """Parse price from text string."""
        # Find price pattern like $29.99 or 29.99
        match = re.search(r"\$?\s*(\d+(?:\.\d{2})?)", text)
        if match:
            return match.group(1)
        return None

    def _extract_rating(self, product: Tag) -> dict[str, Any]:
        """Extract rating information."""
        result: dict[str, Any] = {}

        # Look for star rating
        rating_elem = product.select_one(
            ".rating, .stars, [class*='rating'], [class*='star']"
        )
        if rating_elem:
            # Try aria-label first
            aria_label = rating_elem.get("aria-label", "")
            rating_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5", aria_label)
            if rating_match:
                result["rating"] = float(rating_match.group(1))
            else:
                # Count filled stars
                filled_stars = rating_elem.select(".filled, .full, [class*='filled']")
                if filled_stars:
                    result["rating"] = len(filled_stars)

        # Look for review count
        count_elem = product.select_one(
            ".review-count, .ratings-count, [class*='review']"
        )
        if count_elem:
            count_text = count_elem.get_text(strip=True)
            count_match = re.search(r"(\d+)", count_text)
            if count_match:
                result["count"] = int(count_match.group(1))

        return result

    def _extract_brand_from_name(self, name: str) -> Optional[str]:
        """Try to extract brand from product name."""
        # Common pattern: "Brand Name Product Type Size"
        # Take first 1-3 capitalized words
        words = name.split()
        brand_words = []

        for word in words[:3]:
            if word[0].isupper() and word.lower() not in [
                "the", "a", "an", "and", "of", "or"
            ]:
                brand_words.append(word)
            else:
                break

        if brand_words:
            return " ".join(brand_words)
        return None

    def _determine_signal_type(
        self,
        is_new_arrival: bool,
        is_on_sale: bool,
        out_of_stock: bool,
        price_data: dict,
    ) -> SignalType:
        """Determine the appropriate signal type."""
        if is_new_arrival:
            return SignalType.NEW_SKU

        if out_of_stock:
            return SignalType.OUT_OF_STOCK

        if is_on_sale or price_data.get("discount_percent", 0) > 0:
            return SignalType.PROMOTION

        # Check for significant price change
        if price_data.get("discount_percent", 0) > 10:
            return SignalType.PRICE_DROP

        # Default to retailer presence signal
        return SignalType.NEW_SKU

    async def scrape_search(self, query: str) -> list[ScrapedItem]:
        """
        Search for specific products.

        Args:
            query: Search term

        Returns:
            List of matching products
        """
        search_url = f"{self.BASE_URL}/search/all?text={query}"

        try:
            html = await self.fetch_html(
                search_url,
                use_browser=True,
                wait_for_selector=".product-card",
            )
            soup = self.parse_html(html)
            return self._extract_products(soup)

        except Exception as e:
            logger.error(f"Error searching TotalWine for '{query}': {e}")
            return []
