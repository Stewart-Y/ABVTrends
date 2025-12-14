"""Add Park Street distributor

Revision ID: 006_parkstreet
Revises: 005_sipmarket
Create Date: 2024-12-14

Adds Park Street distributor to the distributors table.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_parkstreet'
down_revision = '005_sipmarket'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix sequence to avoid duplicate key conflicts
    op.execute("SELECT setval('distributors_id_seq', (SELECT COALESCE(MAX(id), 0) FROM distributors) + 1, false)")

    # Insert Park Street distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, scraper_class, is_active)
        VALUES ('Park Street Imports', 'parkstreet', 'https://app.parkstreet.com', 'https://api.parkstreet.com/v1', 'ParkStreetScraper', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            api_base_url = EXCLUDED.api_base_url,
            scraper_class = EXCLUDED.scraper_class
    """)


def downgrade() -> None:
    op.execute("DELETE FROM distributors WHERE slug = 'parkstreet'")
