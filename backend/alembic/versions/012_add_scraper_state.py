"""Add scraper_state table for stealth scraping

Revision ID: 012_scraper_state
Revises: 011_provi
Create Date: 2024-12-16

Tracks daily scraping progress per distributor for stealth mode:
- Daily item budget tracking
- Offset/cursor management for resume capability
- Category rotation tracking
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_scraper_state'
down_revision = '011_provi'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scraper_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('distributor_slug', sa.String(50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('items_scraped', sa.Integer(), default=0, nullable=False),
        sa.Column('daily_limit', sa.Integer(), default=150, nullable=False),
        sa.Column('last_offset', sa.Integer(), default=0, nullable=False),
        sa.Column('last_category', sa.String(100), nullable=True),
        sa.Column('last_session_at', sa.DateTime(), nullable=True),
        sa.Column('sessions_today', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create unique index on distributor_slug + date for fast lookups
    op.create_index(
        'ix_scraper_state_distributor_date',
        'scraper_state',
        ['distributor_slug', 'date'],
        unique=True
    )

    # Index for querying by date (daily cleanup, reporting)
    op.create_index(
        'ix_scraper_state_date',
        'scraper_state',
        ['date']
    )


def downgrade() -> None:
    op.drop_index('ix_scraper_state_date', table_name='scraper_state')
    op.drop_index('ix_scraper_state_distributor_date', table_name='scraper_state')
    op.drop_table('scraper_state')
