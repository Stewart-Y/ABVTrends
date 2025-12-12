#!/usr/bin/env python3
"""
Migrate local database data to production AWS RDS.

This script copies products, aliases, and price history from the local database
to the production database on AWS RDS.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/migrate_to_prod.py

Note: You may need to run this from within your AWS VPC (e.g., from an EC2 instance
or through a VPN) if the RDS is not publicly accessible.
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Migrate data from local to production database."""
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import sessionmaker

    # Get database URLs
    local_url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    prod_url = os.getenv("PROD_DATABASE_URL", "")

    if not local_url:
        logger.error("DATABASE_URL not set")
        return

    if not prod_url:
        logger.error("PROD_DATABASE_URL not set")
        return

    logger.info("Connecting to local database...")
    local_engine = create_engine(local_url)
    LocalSession = sessionmaker(bind=local_engine)

    logger.info("Connecting to production database...")
    try:
        prod_engine = create_engine(prod_url, connect_args={"connect_timeout": 10})
        ProdSession = sessionmaker(bind=prod_engine)

        # Test connection
        with prod_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Production database connection successful!")
    except Exception as e:
        logger.error(f"Failed to connect to production database: {e}")
        logger.info("\nIf you're getting a connection timeout, the RDS may not be publicly accessible.")
        logger.info("Options:")
        logger.info("  1. Run this script from an EC2 instance in the same VPC")
        logger.info("  2. Set up a bastion host or VPN")
        logger.info("  3. Temporarily make RDS publicly accessible (not recommended for production)")
        return

    # Import models
    from app.models.product import Product, ProductCategory
    from app.models.distributor import Distributor, ProductAlias, PriceHistory

    with LocalSession() as local_db:
        # Get SipMarket data
        logger.info("Reading SipMarket data from local database...")

        # Get distributor
        sipmarket_dist = local_db.execute(
            select(Distributor).where(Distributor.slug == "sipmarket")
        ).scalar_one_or_none()

        if not sipmarket_dist:
            logger.error("SipMarket distributor not found in local database")
            return

        # Get all SipMarket product aliases
        aliases = local_db.execute(
            select(ProductAlias).where(ProductAlias.source == "sipmarket")
        ).scalars().all()

        logger.info(f"Found {len(aliases)} SipMarket products to migrate")

        if not aliases:
            logger.info("No products to migrate")
            return

        # Collect all data
        products_data = []
        for alias in aliases:
            product = local_db.get(Product, alias.product_id)
            if not product:
                continue

            # Get price history
            price_hist = local_db.execute(
                select(PriceHistory)
                .where(PriceHistory.product_id == alias.product_id)
                .order_by(PriceHistory.recorded_at.desc())
            ).scalars().first()

            products_data.append({
                "product": product,
                "alias": alias,
                "price": price_hist.price if price_hist else None,
                "price_type": price_hist.price_type if price_hist else "unit"
            })

    # Migrate to production
    with ProdSession() as prod_db:
        logger.info("Starting migration to production...")

        # First, ensure SipMarket distributor exists
        existing_dist = prod_db.execute(
            select(Distributor).where(Distributor.slug == "sipmarket")
        ).scalar_one_or_none()

        if not existing_dist:
            logger.info("Creating SipMarket distributor in production...")
            new_dist = Distributor(
                id=sipmarket_dist.id,
                name=sipmarket_dist.name,
                slug=sipmarket_dist.slug,
                website=sipmarket_dist.website,
                description=sipmarket_dist.description,
                api_type=sipmarket_dist.api_type,
                requires_auth=sipmarket_dist.requires_auth,
                rate_limit=sipmarket_dist.rate_limit,
                is_active=sipmarket_dist.is_active,
            )
            prod_db.add(new_dist)
            prod_db.flush()
            distributor_id = new_dist.id
        else:
            distributor_id = existing_dist.id
            logger.info(f"SipMarket distributor already exists (ID: {distributor_id})")

        # Migrate products
        added = 0
        updated = 0

        for data in products_data:
            product = data["product"]
            alias = data["alias"]
            price = data["price"]
            price_type = data["price_type"]

            now = datetime.now(timezone.utc)

            # Check if product exists
            existing_product = prod_db.get(Product, product.id)

            if existing_product:
                # Update
                existing_product.name = product.name
                existing_product.brand = product.brand
                existing_product.category = product.category
                existing_product.updated_at = now
                updated += 1
                logger.info(f"Updated: {product.name[:50]}...")
            else:
                # Insert
                new_product = Product(
                    id=product.id,
                    name=product.name,
                    brand=product.brand,
                    category=product.category,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                prod_db.add(new_product)
                added += 1
                logger.info(f"Added: {product.name[:50]}...")

            # Check if alias exists
            existing_alias = prod_db.get(ProductAlias, alias.id)
            if not existing_alias:
                new_alias = ProductAlias(
                    id=alias.id,
                    product_id=product.id,
                    source="sipmarket",
                    external_id=alias.external_id,
                    external_name=alias.external_name,
                    external_url=alias.external_url,
                    confidence=alias.confidence,
                    created_at=now,
                )
                prod_db.add(new_alias)

            # Add price history
            if price:
                import uuid
                new_price = PriceHistory(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    distributor_id=distributor_id,
                    price=price,
                    price_type=price_type,
                    recorded_at=now,
                )
                prod_db.add(new_price)

        prod_db.commit()

        logger.info(f"\n{'='*50}")
        logger.info(f"Migration complete!")
        logger.info(f"Added: {added} products")
        logger.info(f"Updated: {updated} products")
        logger.info(f"Total: {added + updated} products migrated")
        logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
