"""Add Provi marketplace distributor

Revision ID: 011_provi
Revises: 010_users_updated
Create Date: 2024-12-16

Adds Provi B2B marketplace to the distributors table.
Provi is one of the largest B2B alcohol marketplaces with 1,400+ distributors.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_provi'
down_revision = '010_users_updated_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix sequence to avoid duplicate key conflicts
    op.execute("SELECT setval('distributors_id_seq', (SELECT COALESCE(MAX(id), 0) FROM distributors) + 1, false)")

    # Insert Provi distributor
    op.execute("""
        INSERT INTO distributors (name, slug, website, api_base_url, scraper_class, is_active)
        VALUES ('Provi', 'provi', 'https://app.provi.com', 'https://app.provi.com/api/retailer', 'ProviScraper', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            api_base_url = EXCLUDED.api_base_url,
            scraper_class = EXCLUDED.scraper_class
    """)


def downgrade() -> None:
    op.execute("DELETE FROM distributors WHERE slug = 'provi'")
