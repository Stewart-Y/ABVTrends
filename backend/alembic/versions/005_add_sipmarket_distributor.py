"""Add SipMarket (Crest Beverage/Reyes) distributor

Revision ID: 005_sipmarket
Revises: 004_scrape_columns
Create Date: 2024-12-11

Adds SipMarket distributor to the database.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '005_sipmarket'
down_revision = '004_scrape_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insert SipMarket distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, is_active, scraper_class) VALUES
        ('SipMarket (Crest Beverage/Reyes)', 'sipmarket', 'https://www.sipmarket.com', NULL, true, 'SipMarketScraper')
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            is_active = EXCLUDED.is_active,
            scraper_class = EXCLUDED.scraper_class
    """)


def downgrade() -> None:
    op.execute("DELETE FROM distributors WHERE slug = 'sipmarket'")
