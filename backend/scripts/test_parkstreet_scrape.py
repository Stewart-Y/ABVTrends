#!/usr/bin/env python3
"""
Test script for Park Street scraper.

Run from the backend directory:
    cd backend && python scripts/test_parkstreet_scrape.py
"""

import asyncio
import sys
import os

# Add backend directory to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.scrapers.distributors.parkstreet import ParkStreetScraper


async def main():
    """Test Park Street scraper."""
    # Park Street credentials
    credentials = {
        "email": "accounting@vistawinespirits.com",
        "password": "2hET2oBe#us",
    }

    print("=" * 60)
    print("Park Street Scraper Test")
    print("=" * 60)

    scraper = ParkStreetScraper(credentials)

    try:
        # Authenticate
        print("\n1. Authenticating...")
        auth_success = await scraper.authenticate()

        if not auth_success:
            print("   ❌ Authentication failed!")
            return

        print("   ✅ Authentication successful!")

        # Get products
        print("\n2. Fetching products (limit 30)...")
        products = await scraper.get_products(limit=30)

        print(f"   ✅ Found {len(products)} products")

        if products:
            print("\n3. Sample products:")
            print("-" * 60)
            for i, product in enumerate(products[:10]):
                print(f"\n   Product {i+1}:")
                print(f"      SKU: {product.external_id}")
                print(f"      Name: {product.name}")
                print(f"      Brand: {product.brand}")
                print(f"      Category: {product.category}")
                print(f"      Price: ${product.price:.2f}" if product.price else "      Price: N/A")
                print(f"      Price Type: {product.price_type}")
                if product.abv:
                    print(f"      ABV: {product.abv}%")
                if product.volume_ml:
                    print(f"      Volume: {product.volume_ml}ml")
                if product.raw_data and product.raw_data.get("country"):
                    print(f"      Country: {product.raw_data['country']}")

            # Save products to database
            print("\n4. Saving products to database...")
            from app.core.database import AsyncSessionLocal
            from app.models.product import Product
            from app.models.distributor import Distributor, ProductAlias, PriceHistory
            from sqlalchemy import select
            import uuid

            async with AsyncSessionLocal() as db:
                # Check if Park Street distributor exists
                result = await db.execute(
                    select(Distributor).where(Distributor.slug == "parkstreet")
                )
                distributor = result.scalar_one_or_none()

                if not distributor:
                    print("   Creating Park Street distributor...")
                    distributor = Distributor(
                        name="Park Street Imports",
                        slug="parkstreet",
                        website="https://app.parkstreet.com",
                        api_base_url="https://api.parkstreet.com/v1",
                        scraper_class="ParkStreetScraper",
                        is_active=True,
                    )
                    db.add(distributor)
                    await db.flush()
                    print(f"   ✅ Created distributor ID: {distributor.id}")
                else:
                    print(f"   ✅ Found existing distributor ID: {distributor.id}")

                # Save products
                saved_count = 0
                for product in products:
                    try:
                        # Check if product exists by alias
                        result = await db.execute(
                            select(ProductAlias).where(
                                ProductAlias.source == "parkstreet",
                                ProductAlias.external_id == product.external_id
                            )
                        )
                        existing_alias = result.scalar_one_or_none()

                        if existing_alias:
                            # Load the related product
                            result = await db.execute(
                                select(Product).where(Product.id == existing_alias.product_id)
                            )
                            db_product = result.scalar_one()
                        else:
                            # Create new product
                            country = product.raw_data.get("country") if product.raw_data else None
                            db_product = Product(
                                id=uuid.uuid4(),
                                name=product.name,
                                brand=product.brand,
                                category=product.category.upper() if product.category else "SPIRITS",
                                volume_ml=product.volume_ml,
                                abv=product.abv,
                                country=country,
                                is_active=True,
                            )
                            db.add(db_product)
                            await db.flush()

                            # Create alias
                            alias = ProductAlias(
                                product_id=db_product.id,
                                source="parkstreet",
                                external_id=product.external_id,
                                external_name=product.name,
                                confidence=1.0,
                            )
                            db.add(alias)

                        # Add price history
                        if product.price:
                            price_history = PriceHistory(
                                product_id=db_product.id,
                                distributor_id=distributor.id,
                                price=product.price,
                                price_type=product.price_type or "case",
                                currency="USD",
                            )
                            db.add(price_history)

                        saved_count += 1

                    except Exception as e:
                        print(f"   ⚠️  Error saving product {product.external_id}: {e}")
                        continue

                await db.commit()
                print(f"   ✅ Saved {saved_count} products to database")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Close scraper
        print("\n5. Closing scraper...")
        await scraper.close()
        print("   ✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
