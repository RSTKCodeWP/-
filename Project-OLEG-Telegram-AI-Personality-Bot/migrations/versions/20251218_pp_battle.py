"""Add pvp_losses to game_stats for PP battle.

Revision ID: 20251218_pp_battle
Revises: 20251217_quote_votes
Create Date: 2025-12-18
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251218_pp_battle'
down_revision = '20251217_quote_votes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pvp_losses column to game_stats (pvp_wins already exists)
    # Check if column exists first to avoid errors
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('game_stats')]
    
    if 'pvp_losses' not in columns:
        op.add_column('game_stats', sa.Column('pvp_losses', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('game_stats', 'pvp_losses')
