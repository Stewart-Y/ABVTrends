"""Add updated_at column to users table

Revision ID: 010_users_updated_at
Revises: 009_auth_tables
Create Date: 2024-12-16

Adds the missing updated_at column to the users table that the
User model expects but was not included in the initial migration.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010_users_updated_at'
down_revision = '009_auth_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add updated_at column to users table
    op.add_column(
        'users',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'updated_at')
