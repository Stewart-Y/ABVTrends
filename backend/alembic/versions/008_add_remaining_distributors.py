"""Add remaining distributors (LibDib, RNDC, SGWS)

Revision ID: 008_remaining_distributors
Revises: 007_breakthru
Create Date: 2024-12-14

Adds the remaining distributor scrapers that are implemented in the codebase
but not yet registered in the production database.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '008_remaining_distributors'
down_revision = '007_breakthru'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix sequence to avoid duplicate key conflicts
    op.execute("SELECT setval('distributors_id_seq', (SELECT COALESCE(MAX(id), 0) FROM distributors) + 1, false)")

    # Insert LibDib distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, scraper_class, is_active)
        VALUES ('LibDib', 'libdib', 'https://app.libdib.com', 'https://app.libdib.com/api/v1', 'LibDibScraper', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            api_base_url = EXCLUDED.api_base_url,
            scraper_class = EXCLUDED.scraper_class,
            is_active = true
    """)

    # Insert SGWS distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, scraper_class, is_active)
        VALUES ('Southern Glazer''s Wine & Spirits', 'sgws', 'https://www.southernglazers.com', NULL, 'SGWSScraper', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            scraper_class = EXCLUDED.scraper_class,
            is_active = true
    """)

    # Insert RNDC distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, scraper_class, is_active)
        VALUES ('Republic National Distributing Company', 'rndc', 'https://www.rndc-usa.com', NULL, 'RNDCScraper', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            scraper_class = EXCLUDED.scraper_class,
            is_active = true
    """)


def downgrade() -> None:
    op.execute("DELETE FROM distributors WHERE slug IN ('libdib', 'sgws', 'rndc')")
