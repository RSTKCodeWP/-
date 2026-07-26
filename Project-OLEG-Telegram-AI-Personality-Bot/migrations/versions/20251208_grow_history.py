"""Add grow_history column to game_stats for sparkline feature

Revision ID: 20251208_grow_history
Revises: 20251206_shield_economy
Create Date: 2025-12-08

Requirements: 7.4 - Store last 7 days of growth data
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251208_grow_history'
down_revision = '20251206_shield_economy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add grow_history JSON column to game_stats table."""
    op.add_column(
        'game_stats',
        sa.Column('grow_history', sa.JSON(), nullable=True, server_default='[]')
    )


def downgrade() -> None:
    """Remove grow_history column from game_stats table."""
    op.drop_column('game_stats', 'grow_history')
