"""Seed distributor and category data

Revision ID: 002_seed_distributors
Revises: 001_distributor_tables
Create Date: 2024-12-10

Seeds initial data:
- Distributor records for LibDib, SGWS, RNDC, etc.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_seed_distributors'
down_revision = '001_distributor_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insert distributors
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, is_active, scraper_class) VALUES
        ('LibDib', 'libdib', 'https://www.libdib.com', 'https://app.libdib.com/api/v1', true, 'LibDibScraper'),
        ('Southern Glazer''s Wine & Spirits', 'sgws', 'https://www.southernglazers.com', NULL, false, 'SGWSScraper'),
        ('Republic National Distributing Company', 'rndc', 'https://www.rndc-usa.com', NULL, false, 'RNDCScraper'),
        ('Breakthru Beverage Group', 'breakthru', 'https://www.breakthrubev.com', NULL, false, 'BreakthruScraper'),
        ('Provi', 'provi', 'https://www.provi.com', NULL, false, 'ProviScraper'),
        ('Park Street Imports', 'parkstreet', 'https://www.parkstreet.com', NULL, false, 'ParkStreetScraper'),
        ('Young''s Market Company', 'youngs', 'https://www.youngsmarket.com', NULL, false, 'YoungsScraper'),
        ('Johnson Brothers', 'johnsonbrothers', 'https://www.johnsonbrothers.com', NULL, false, 'JohnsonBrothersScraper')
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM distributors WHERE slug IN (
            'libdib', 'sgws', 'rndc', 'breakthru', 'provi',
            'parkstreet', 'youngs', 'johnsonbrothers'
        )
    """)
