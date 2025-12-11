"""Add missing product columns

Revision ID: 003_add_product_columns
Revises: 002_seed_distributors
Create Date: 2024-12-11

Adds columns that were missing from products table.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_product_columns'
down_revision = '002_seed_distributors'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to products table
    op.add_column('products', sa.Column('slug', sa.String(500), nullable=True))
    op.add_column('products', sa.Column('volume_ml', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('abv', sa.Numeric(5, 2), nullable=True))
    op.add_column('products', sa.Column('country', sa.String(100), nullable=True))
    op.add_column('products', sa.Column('region', sa.String(100), nullable=True))
    op.add_column('products', sa.Column('upc', sa.String(50), nullable=True))
    op.add_column('products', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))

    # Add indexes
    op.create_index('ix_products_slug', 'products', ['slug'])
    op.create_index('ix_products_upc', 'products', ['upc'], postgresql_where=sa.text('upc IS NOT NULL'))

    # Add trigram index for fuzzy search
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute('CREATE INDEX IF NOT EXISTS ix_products_name_trgm ON products USING gin(name gin_trgm_ops)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_products_name_trgm')
    op.drop_index('ix_products_upc', 'products')
    op.drop_index('ix_products_slug', 'products')
    op.drop_column('products', 'is_active')
    op.drop_column('products', 'upc')
    op.drop_column('products', 'region')
    op.drop_column('products', 'country')
    op.drop_column('products', 'abv')
    op.drop_column('products', 'volume_ml')
    op.drop_column('products', 'slug')
