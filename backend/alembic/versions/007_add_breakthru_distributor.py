"""Add Breakthru Beverage distributor

Revision ID: 007_breakthru
Revises: 006_parkstreet
Create Date: 2024-12-14

Adds Breakthru Beverage Group distributor to the distributors table.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_breakthru'
down_revision = '006_parkstreet'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix sequence to avoid duplicate key conflicts
    op.execute("SELECT setval('distributors_id_seq', (SELECT COALESCE(MAX(id), 0) FROM distributors) + 1, false)")

    # Insert Breakthru Beverage distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, scraper_class, is_active)
        VALUES ('Breakthru Beverage Group', 'breakthru', 'https://now.breakthrubev.com', NULL, 'BreakthruScraper', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            api_base_url = EXCLUDED.api_base_url,
            scraper_class = EXCLUDED.scraper_class
    """)


def downgrade() -> None:
    op.execute("DELETE FROM distributors WHERE slug = 'breakthru'")
