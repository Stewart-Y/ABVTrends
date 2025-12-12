#!/usr/bin/env python3
"""
Simple test to parse products from saved SipMarket HTML file.

This confirms the HTML parsing works before involving Playwright.
"""

import re
from html.parser import HTMLParser


class SipMarketHTMLParser(HTMLParser):
    """Extract products from SipMarket HTML."""

    def __init__(self):
        super().__init__()
        self.products = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return

        attrs_dict = dict(attrs)
        class_str = attrs_dict.get("class", "")

        # Check for product card
        if "card" in class_str and "newCard" in class_str and "product" in class_str:
            sku = attrs_dict.get("data-sku", "")
            name = attrs_dict.get("data-name", "")

            # Skip template placeholders
            if "<%=" in sku or not sku:
                return

            self.products.append({
                "sku": sku,
                "name": name,
                "brand": attrs_dict.get("data-brand", ""),
                "price": attrs_dict.get("data-price", ""),
                "category": attrs_dict.get("data-category", ""),
                "category2": attrs_dict.get("data-category2", ""),
                "package": attrs_dict.get("data-package-name", ""),
                "max_qty": attrs_dict.get("data-max-qty", "0"),
            })


def main():
    """Parse products from saved HTML."""
    html_file = "/tmp/sipmarket_products.html"

    print(f"Reading HTML from {html_file}")
    with open(html_file, "r") as f:
        html_content = f.read()

    print(f"HTML size: {len(html_content):,} bytes")

    # Parse with HTML parser
    parser = SipMarketHTMLParser()
    parser.feed(html_content)

    products = parser.products
    print(f"\nFound {len(products)} products:\n")

    for i, p in enumerate(products[:20]):
        print(f"{i+1}. {p['name']}")
        print(f"   SKU: {p['sku']}")
        print(f"   Brand: {p['brand']}")
        print(f"   Price: ${p['price']}")
        print(f"   Category: {p['category2']} / {p['category']}")
        print(f"   Package: {p['package']}")
        print(f"   Max Qty: {p['max_qty']}")
        print()


if __name__ == "__main__":
    main()
