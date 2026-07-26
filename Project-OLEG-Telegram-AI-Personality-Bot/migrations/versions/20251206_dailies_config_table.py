"""Add dailies_configs table for Fortress Update

Revision ID: 20251206_dailies
Revises: 20251206_fortress_update_new_tables
Create Date: 2025-12-06

Requirements: 13.4, 13.5
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251206_dailies'
down_revision = '20251206_fortress'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create dailies_configs table for chat-specific daily message settings."""
    op.create_table(
        'dailies_configs',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('summary_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('quote_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('stats_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('summary_time_hour', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('quote_time_hour', sa.Integer(), nullable=False, server_default='21'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('chat_id')
    )


def downgrade() -> None:
    """Drop dailies_configs table."""
    op.drop_table('dailies_configs')
