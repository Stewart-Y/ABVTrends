"""
ABVTrends - BevMo Scraper

Scrapes product data from BevMo.com.
BevMo (Beverages & More) is a major West Coast spirits and wine retailer.
"""

import logging
import re
from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from app.models.signal import SignalType
from app.scrapers.utils.base_scraper import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class BevMoScraper(BaseScraper):
    """
    Scraper for BevMo.com product listings.

    Targets:
    - New arrivals
    - Top sellers
    - Weekly deals/promotions
    - Category pages

    BevMo is valuable for West Coast regional trend data.
    """

    SOURCE_NAME = "bevmo"
    BASE_URL = "https://www.bevmo.com"

    CATEGORY_URLS = [
        "/shop/spirits",
        "/shop/spirits/whiskey",
        "/shop/spirits/tequila",
        "/shop/spirits/vodka",
        "/shop/spirits/gin",
        "/shop/spirits/rum",
        "/shop/wine",
        "/shop/wine/red-wine",
        "/shop/wine/white-wine",
        "/shop/wine/sparkling-wine-champagne",
        "/shop/beer",
    ]

    SPECIAL_URLS = [
        "/shop/deals",
        "/shop/new-arrivals",
        "/shop/best-sellers",
    ]

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_base_url(self) -> str:
        return self.BASE_URL

    async def scrape(self) -> list[ScrapedItem]:
        """
        Scrape BevMo for product data.

        Returns:
            List of ScrapedItem objects
        """
        items: list[ScrapedItem] = []
        seen_products: set[str] = set()

        # Scrape special pages first
        for url_path in self.SPECIAL_URLS:
            try:
                url = self.build_url(url_path)
                logger.info(f"Scraping BevMo special: {url}")

                html = await self.fetch_html(
                    url,
                    use_browser=True,
                    wait_for_selector=".product-tile, .product-card",
                )
                soup = self.parse_html(html)

                is_deal = "deals" in url_path
                is_new = "new" in url_path

                products = self._extract_products(soup, is_new, is_deal)

                for product in products:
                    if product.title not in seen_products:
                        seen_products.add(product.title)
                        items.append(product)

            except Exception as e:
                logger.error(f"Error scraping BevMo {url_path}: {e}")
                continue

        # Scrape main categories
        for url_path in self.CATEGORY_URLS[:5]:  # Limit requests
            try:
                url = self.build_url(url_path)
                logger.info(f"Scraping BevMo category: {url}")

                html = await self.fetch_html(
                    url,
                    use_browser=True,
                    wait_for_selector=".product-tile, .product-card",
                )
                soup = self.parse_html(html)

                products = self._extract_products(soup)

                for product in products:
                    if product.title not in seen_products:
                        seen_products.add(product.title)
                        items.append(product)

            except Exception as e:
                logger.error(f"Error scraping BevMo {url_path}: {e}")
                continue

        logger.info(f"BevMo scraper found {len(items)} products")
        return items

    def _extract_products(
        self,
        soup: BeautifulSoup,
        is_new_arrival: bool = False,
        is_deal: bool = False,
    ) -> list[ScrapedItem]:
        """Extract products from page HTML."""
        items: list[ScrapedItem] = []

        # BevMo product selectors
        product_selectors = [
            ".product-tile",
            ".product-card",
            ".product-item",
            'div[class*="product"]',
            'article[class*="product"]',
        ]

        products: list[Tag] = []
        for selector in product_selectors:
            found = soup.select(selector)
            if found:
                products = found
                break

        for product in products[:30]:
            try:
                item = self._parse_product(product, is_new_arrival, is_deal)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing BevMo product: {e}")
                continue

        return items

    def _parse_product(
        self,
        product: Tag,
        is_new_arrival: bool = False,
        is_deal: bool = False,
    ) -> Optional[ScrapedItem]:
        """Parse a single product card."""
        # Extract product name
        name_elem = product.select_one(
            ".product-tile__name, .product-name, .title, h2, h3"
        )
        if not name_elem:
            link = product.select_one("a[href*='/p/']")
            if link:
                name_elem = link

        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        # Extract URL
        link_elem = product.select_one("a[href*='/p/'], a[href]")
        url = link_elem.get("href", "") if link_elem else ""
        if url and not url.startswith("http"):
            url = self.build_url(url)

        # Extract prices
        price_data = self._extract_price(product)

        # Extract brand
        brand_elem = product.select_one(".brand, .product-brand, [class*='brand']")
        brand = brand_elem.get_text(strip=True) if brand_elem else None

        if not brand:
            brand = self._extract_brand_from_name(name)

        # Extract rating
        rating_data = self._extract_rating(product)

        # Check availability
        out_of_stock = bool(product.select_one(
            ".out-of-stock, .unavailable, [class*='outofstock']"
        ))

        # Check for promotions
        promo_elem = product.select_one(
            ".promo, .promotion, .deal, .savings, [class*='promo']"
        )
        promo_text = promo_elem.get_text(strip=True) if promo_elem else None

        # Extract club price (BevMo has club membership)
        club_price = self._extract_club_price(product)

        # Extract image
        img_elem = product.select_one("img")
        image_url = None
        if img_elem:
            image_url = (
                img_elem.get("src")
                or img_elem.get("data-src")
                or img_elem.get("srcset", "").split()[0]
            )

        # Extract size
        size = self._extract_size(name, product)

        # Determine signal type
        signal_type = self._determine_signal_type(
            is_new_arrival, is_deal, out_of_stock, price_data
        )

        raw_data: dict[str, Any] = {
            "source": self.SOURCE_NAME,
            "brand": brand,
            "price": price_data.get("current"),
            "original_price": price_data.get("original"),
            "club_price": club_price,
            "discount_percent": price_data.get("discount_percent"),
            "promo_text": promo_text,
            "rating": rating_data.get("rating"),
            "review_count": rating_data.get("count"),
            "size": size,
            "is_new_arrival": is_new_arrival,
            "is_deal": is_deal,
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
        """Extract price information."""
        result: dict[str, Any] = {}

        # Current/sale price
        price_selectors = [
            ".product-tile__price", ".price", ".current-price",
            ".sale-price", "[class*='price']"
        ]

        for selector in price_selectors:
            elem = product.select_one(selector)
            if elem:
                # Exclude club price if present
                if "club" in (elem.get("class", "") or "").lower():
                    continue

                text = elem.get_text(strip=True)
                price = self._parse_price(text)
                if price:
                    result["current"] = price
                    break

        # Original/was price
        original_selectors = [
            ".was-price", ".original-price", ".regular-price",
            "del", "s", "[class*='was']", "[class*='original']"
        ]

        for selector in original_selectors:
            elem = product.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                price = self._parse_price(text)
                if price:
                    result["original"] = price
                    break

        # Calculate discount
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

    def _extract_club_price(self, product: Tag) -> Optional[str]:
        """Extract BevMo club member price."""
        club_elem = product.select_one(
            ".club-price, [class*='club'], [class*='member']"
        )
        if club_elem:
            text = club_elem.get_text(strip=True)
            return self._parse_price(text)
        return None

    def _parse_price(self, text: str) -> Optional[str]:
        """Parse price from text."""
        match = re.search(r"\$?\s*(\d+(?:\.\d{2})?)", text)
        if match:
            return match.group(1)
        return None

    def _extract_rating(self, product: Tag) -> dict[str, Any]:
        """Extract rating information."""
        result: dict[str, Any] = {}

        rating_elem = product.select_one(
            ".rating, .stars, [class*='rating']"
        )
        if rating_elem:
            # Try to extract numeric rating
            aria = rating_elem.get("aria-label", "")
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5", aria)
            if match:
                result["rating"] = float(match.group(1))
            else:
                # Count stars
                stars = rating_elem.select("[class*='filled'], [class*='full']")
                if stars:
                    result["rating"] = len(stars)

        # Review count
        count_elem = product.select_one(
            ".review-count, [class*='review'], [class*='count']"
        )
        if count_elem:
            text = count_elem.get_text(strip=True)
            match = re.search(r"(\d+)", text)
            if match:
                result["count"] = int(match.group(1))

        return result

    def _extract_brand_from_name(self, name: str) -> Optional[str]:
        """Extract brand from product name."""
        words = name.split()
        brand_words = []

        skip_words = {
            "whiskey", "bourbon", "scotch", "vodka", "gin", "rum",
            "tequila", "wine", "beer", "750ml", "1l", "1.75l"
        }

        for word in words[:3]:
            if word.lower() in skip_words:
                break
            if word[0].isupper():
                brand_words.append(word)

        return " ".join(brand_words) if brand_words else None

    def _extract_size(self, name: str, product: Tag) -> Optional[str]:
        """Extract bottle size."""
        # Try size element
        size_elem = product.select_one(".size, [class*='size']")
        if size_elem:
            return size_elem.get_text(strip=True)

        # Extract from name
        patterns = [
            r"(\d+(?:\.\d+)?\s*ml)",
            r"(\d+(?:\.\d+)?\s*L)",
            r"(\d+(?:\.\d+)?\s*liter)",
            r"(\d+(?:\.\d+)?\s*oz)",
        ]

        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _determine_signal_type(
        self,
        is_new_arrival: bool,
        is_deal: bool,
        out_of_stock: bool,
        price_data: dict,
    ) -> SignalType:
        """Determine signal type."""
        if out_of_stock:
            return SignalType.OUT_OF_STOCK

        if is_new_arrival:
            return SignalType.NEW_SKU

        if is_deal or price_data.get("discount_percent", 0) > 0:
            return SignalType.PROMOTION

        if price_data.get("discount_percent", 0) > 15:
            return SignalType.PRICE_DROP

        return SignalType.NEW_SKU

    async def scrape_weekly_deals(self) -> list[ScrapedItem]:
        """
        Scrape weekly deals specifically.

        BevMo has regular promotional cycles.
        """
        url = self.build_url("/shop/deals")

        try:
            html = await self.fetch_html(
                url,
                use_browser=True,
                wait_for_selector=".product-tile",
            )
            soup = self.parse_html(html)
            return self._extract_products(soup, is_deal=True)
        except Exception as e:
            logger.error(f"Error scraping BevMo deals: {e}")
            return []
