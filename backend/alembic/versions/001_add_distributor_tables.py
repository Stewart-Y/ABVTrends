"""Add distributor scraping tables

Revision ID: 001_distributor_tables
Revises:
Create Date: 2024-12-10

Adds tables for:
- distributors: Distributor sources (LibDib, SGWS, etc.)
- product_aliases: Maps external IDs to unified products
- price_history: Timeseries price data
- inventory_history: Timeseries inventory data
- scrape_runs: Audit log of scraper runs
- scrape_errors: Error tracking
- raw_product_data: Staging table for incoming data
- articles: Media articles
- article_mentions: Product mentions in articles
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_distributor_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm extension for fuzzy search
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # ================================================================
    # DISTRIBUTORS TABLE
    # ================================================================
    op.create_table(
        'distributors',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('api_base_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('scraper_class', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_distributors_slug', 'distributors', ['slug'])
    op.create_index('ix_distributors_active', 'distributors', ['is_active'])

    # ================================================================
    # PRODUCT_ALIASES TABLE
    # ================================================================
    op.create_table(
        'product_aliases',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),  # 'libdib', 'sgws', 'vinepair', etc.
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('external_name', sa.String(500), nullable=True),
        sa.Column('external_url', sa.String(500), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), default=1.0),  # match confidence 0-1
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('source', 'external_id', name='uq_product_aliases_source_external'),
    )
    op.create_index('ix_product_aliases_product', 'product_aliases', ['product_id'])
    op.create_index('ix_product_aliases_source', 'product_aliases', ['source', 'external_id'])

    # ================================================================
    # PRICE_HISTORY TABLE
    # ================================================================
    op.create_table(
        'price_history',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id'), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_type', sa.String(50), default='wholesale'),  # wholesale, retail, case, bottle
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_price_history_product', 'price_history', ['product_id', 'recorded_at'])
    op.create_index('ix_price_history_recorded', 'price_history', ['recorded_at'])

    # ================================================================
    # INVENTORY_HISTORY TABLE
    # ================================================================
    op.create_table(
        'inventory_history',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('in_stock', sa.Boolean(), default=True),
        sa.Column('available_states', postgresql.ARRAY(sa.String()), nullable=True),  # array of state codes
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_inventory_history_product', 'inventory_history', ['product_id', 'recorded_at'])

    # ================================================================
    # SCRAPE_RUNS TABLE (Audit log)
    # ================================================================
    op.create_table(
        'scrape_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('scraper_name', sa.String(100), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),  # distributor, media
        sa.Column('status', sa.String(20), nullable=False),  # running, success, failed, partial
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('products_scraped', sa.Integer(), default=0),
        sa.Column('products_new', sa.Integer(), default=0),
        sa.Column('products_updated', sa.Integer(), default=0),
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_scrape_runs_scraper', 'scrape_runs', ['scraper_name', 'started_at'])
    op.create_index('ix_scrape_runs_status', 'scrape_runs', ['status'])

    # ================================================================
    # SCRAPE_ERRORS TABLE
    # ================================================================
    op.create_table(
        'scrape_errors',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('scrape_run_id', sa.Integer(), sa.ForeignKey('scrape_runs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('context', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scrape_errors_run', 'scrape_errors', ['scrape_run_id'])

    # ================================================================
    # RAW_PRODUCT_DATA TABLE (Staging)
    # ================================================================
    op.create_table(
        'raw_product_data',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('scrape_run_id', sa.Integer(), sa.ForeignKey('scrape_runs.id'), nullable=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(), nullable=False),
        sa.Column('processed', sa.Boolean(), default=False),
        sa.Column('matched_product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_raw_data_source', 'raw_product_data', ['source', 'external_id'])
    op.create_index('ix_raw_data_processed', 'raw_product_data', ['processed'], postgresql_where=sa.text('processed = false'))

    # ================================================================
    # MATCH_QUEUE TABLE (Manual review)
    # ================================================================
    op.create_table(
        'match_queue',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('raw_data_id', sa.BigInteger(), sa.ForeignKey('raw_product_data.id'), nullable=True),
        sa.Column('candidate_product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id'), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),  # pending, approved, rejected, new_product
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_match_queue_status', 'match_queue', ['status'])

    # ================================================================
    # ARTICLES TABLE
    # ================================================================
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('source', sa.String(100), nullable=False),  # vinepair, liquor.com, etc.
        sa.Column('url', sa.String(1000), nullable=False, unique=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('author', sa.String(255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),  # AI-generated summary
        sa.Column('sentiment', sa.Numeric(3, 2), nullable=True),  # -1 to 1
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_articles_source', 'articles', ['source'])
    op.create_index('ix_articles_published', 'articles', ['published_at'])
    op.create_index('ix_articles_url', 'articles', ['url'])

    # ================================================================
    # ARTICLE_MENTIONS TABLE
    # ================================================================
    op.create_table(
        'article_mentions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mention_type', sa.String(50), nullable=True),  # featured, mentioned, reviewed, listed
        sa.Column('sentiment', sa.Numeric(3, 2), nullable=True),
        sa.Column('excerpt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_mentions_product', 'article_mentions', ['product_id'])
    op.create_index('ix_mentions_article', 'article_mentions', ['article_id'])

    # ================================================================
    # ADD COLUMNS TO PRODUCTS TABLE
    # ================================================================
    # Add new columns to existing products table
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

    # Add trigram index for fuzzy search (requires pg_trgm extension)
    op.execute('CREATE INDEX IF NOT EXISTS ix_products_name_trgm ON products USING gin(name gin_trgm_ops)')

    # ================================================================
    # CURRENT_TREND_SCORES TABLE (Fast lookup)
    # ================================================================
    op.create_table(
        'current_trend_scores',
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('tier', sa.String(20), nullable=False),
        sa.Column('momentum', sa.Integer(), nullable=True),
        sa.Column('media_score', sa.Integer(), nullable=True),
        sa.Column('retail_score', sa.Integer(), nullable=True),
        sa.Column('price_score', sa.Integer(), nullable=True),
        sa.Column('inventory_score', sa.Integer(), nullable=True),
        sa.Column('search_score', sa.Integer(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_current_scores_score', 'current_trend_scores', ['score'])
    op.create_index('ix_current_scores_tier', 'current_trend_scores', ['tier'])


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table('current_trend_scores')
    op.drop_table('article_mentions')
    op.drop_table('articles')
    op.drop_table('match_queue')
    op.drop_table('raw_product_data')
    op.drop_table('scrape_errors')
    op.drop_table('scrape_runs')
    op.drop_table('inventory_history')
    op.drop_table('price_history')
    op.drop_table('product_aliases')
    op.drop_table('distributors')

    # Drop added columns from products
    op.drop_index('ix_products_name_trgm', 'products')
    op.drop_index('ix_products_upc', 'products')
    op.drop_index('ix_products_slug', 'products')
    op.drop_column('products', 'is_active')
    op.drop_column('products', 'upc')
    op.drop_column('products', 'region')
    op.drop_column('products', 'country')
    op.drop_column('products', 'abv')
    op.drop_column('products', 'volume_ml')
    op.drop_column('products', 'slug')

    # Drop extension
    op.execute('DROP EXTENSION IF EXISTS pg_trgm')
