"""Add missing columns to scrape_runs and scrape_errors

Revision ID: 004_scrape_columns
Revises: 003_add_product_columns
Create Date: 2024-12-11

Adds distributor_id and products_found columns.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_scrape_columns'
down_revision = '003_add_product_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add distributor_id to scrape_runs
    op.add_column(
        'scrape_runs',
        sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id'), nullable=True)
    )
    op.add_column(
        'scrape_runs',
        sa.Column('products_found', sa.Integer(), server_default='0', nullable=False)
    )

    # Add distributor_id to scrape_errors
    op.add_column(
        'scrape_errors',
        sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id'), nullable=True)
    )

    # Add index for faster lookups
    op.create_index('ix_scrape_runs_distributor', 'scrape_runs', ['distributor_id'])
    op.create_index('ix_scrape_errors_distributor', 'scrape_errors', ['distributor_id'])


def downgrade() -> None:
    op.drop_index('ix_scrape_errors_distributor', 'scrape_errors')
    op.drop_index('ix_scrape_runs_distributor', 'scrape_runs')
    op.drop_column('scrape_errors', 'distributor_id')
    op.drop_column('scrape_runs', 'products_found')
    op.drop_column('scrape_runs', 'distributor_id')
