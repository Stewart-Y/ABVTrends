#!/usr/bin/env python3
"""
Test script to scrape products from SipMarket and add them to the database.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/test_sipmarket_scrape.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def map_category_to_enum(category_str: Optional[str]):
    """Map scraped category string to ProductCategory enum."""
    from app.models.product import ProductCategory

    if not category_str:
        return ProductCategory.SPIRITS  # Default

    cat_lower = category_str.lower()

    if "spirit" in cat_lower or "liquor" in cat_lower:
        return ProductCategory.SPIRITS
    elif "wine" in cat_lower:
        return ProductCategory.WINE
    elif "beer" in cat_lower or "ale" in cat_lower or "lager" in cat_lower:
        return ProductCategory.BEER
    elif "rtd" in cat_lower or "ready" in cat_lower or "seltzer" in cat_lower:
        return ProductCategory.RTD
    else:
        return ProductCategory.SPIRITS  # Default


async def main():
    """Scrape 20 products from SipMarket and add to database."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.scrapers.distributors.sipmarket import SipMarketScraper
    from app.models.product import Product, ProductCategory
    from app.models.distributor import Distributor, PriceHistory, ProductAlias

    print("=" * 60)
    print("SipMarket Scraper Test - Scrape 20 Products")
    print("=" * 60)

    # Database connection
    database_url = str(settings.database_url).replace("+asyncpg", "")
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)

    # Get SipMarket distributor
    with Session() as db:
        result = db.execute(select(Distributor).where(Distributor.slug == "sipmarket"))
        distributor = result.scalar_one_or_none()

        if not distributor:
            print("ERROR: SipMarket distributor not found in database!")
            print("Run the migration: alembic upgrade head")
            return

        print(f"Found distributor: {distributor.name} (ID: {distributor.id})")
        distributor_id = distributor.id

    # Initialize scraper with credentials
    credentials = {
        "email": settings.sipmarket_email,
        "password": settings.sipmarket_password,
    }

    if not credentials["email"] or not credentials["password"]:
        print("ERROR: SipMarket credentials not configured!")
        print("Set SIPMARKET_EMAIL and SIPMARKET_PASSWORD in .env")
        return

    print(f"Using email: {credentials['email']}")

    scraper = SipMarketScraper(credentials)

    try:
        # Authenticate
        print("\n--- Authenticating with SipMarket ---")
        auth_success = await scraper.authenticate()

        if not auth_success:
            print("ERROR: Authentication failed!")
            return

        print("Authentication successful!")

        # Scrape products (limit to 20)
        print("\n--- Scraping Products (limit: 20) ---")
        products = await scraper.get_products(limit=20)

        print(f"\nScraped {len(products)} products")

        if not products:
            print("No products scraped. Check screenshots at /tmp/sipmarket_*.png")
            return

        # Display scraped products
        print("\n--- Scraped Products ---")
        for i, p in enumerate(products):
            print(f"{i+1}. {p.name}")
            print(f"   SKU: {p.external_id}")
            print(f"   Brand: {p.brand or 'N/A'}")
            print(f"   Category: {p.category or 'N/A'}")
            print(f"   Price: ${p.price:.2f}" if p.price else "   Price: N/A")
            print(f"   In Stock: {p.in_stock}")
            print()

        # Add to database
        print("\n--- Adding Products to Database ---")

        with Session() as db:
            added_count = 0
            updated_count = 0

            for raw_product in products:
                now = datetime.now(timezone.utc)

                # Check if product already exists (via ProductAlias)
                alias = db.execute(
                    select(ProductAlias).where(
                        ProductAlias.source == "sipmarket",
                        ProductAlias.external_id == raw_product.external_id
                    )
                ).scalar_one_or_none()

                if alias:
                    # Update existing product
                    existing = db.get(Product, alias.product_id)
                    if existing:
                        existing.name = raw_product.name
                        existing.brand = raw_product.brand
                        existing.image_url = raw_product.image_url
                        existing.updated_at = now
                        updated_count += 1
                        product_id = existing.id
                        print(f"Updated: {raw_product.name[:50]}...")

                        # Add price history if price available
                        if raw_product.price:
                            price_entry = PriceHistory(
                                product_id=product_id,
                                distributor_id=distributor_id,
                                price=raw_product.price,
                                price_type=raw_product.price_type or "unit",
                                recorded_at=now,
                            )
                            db.add(price_entry)
                        continue

                # Create new product
                category_enum = map_category_to_enum(raw_product.category)

                product = Product(
                    name=raw_product.name,
                    brand=raw_product.brand,
                    category=category_enum,
                    image_url=raw_product.image_url,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(product)
                db.flush()  # Get the ID
                product_id = product.id
                added_count += 1
                print(f"Added: {raw_product.name[:50]}...")

                # Create product alias for this distributor
                alias = ProductAlias(
                    product_id=product_id,
                    source="sipmarket",
                    external_id=raw_product.external_id,
                    external_name=raw_product.name,
                    external_url=raw_product.url,
                    confidence=1.0,
                    created_at=now,
                )
                db.add(alias)

                # Add price history entry
                if raw_product.price:
                    price_entry = PriceHistory(
                        product_id=product_id,
                        distributor_id=distributor_id,
                        price=raw_product.price,
                        price_type=raw_product.price_type or "unit",
                        recorded_at=now,
                    )
                    db.add(price_entry)

            db.commit()

            print(f"\n--- Summary ---")
            print(f"Added: {added_count} products")
            print(f"Updated: {updated_count} products")
            print(f"Total: {added_count + updated_count} products processed")

            # Count total products in database
            total_products = db.execute(select(Product)).scalars().all()
            print(f"\nTotal products in database: {len(total_products)}")

            # Count SipMarket aliases
            sipmarket_aliases = db.execute(
                select(ProductAlias).where(ProductAlias.source == "sipmarket")
            ).scalars().all()
            print(f"Total SipMarket products: {len(sipmarket_aliases)}")

    finally:
        # Close browser session
        print("\n--- Closing browser session ---")
        await scraper.close()

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
