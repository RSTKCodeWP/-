"""Games v7.5 - New mini games and economy tables

Revision ID: 007_games_v75
Revises: 20251208_gif_patrol
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_games_v75'
down_revision = '20251208_gif_patrol'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # User Inventory table
    op.create_table(
        'user_inventory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('item_type', sa.String(64), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1),
        sa.Column('acquired_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', 'item_type', name='uq_user_chat_item')
    )
    op.create_index('ix_user_inventory_user_id', 'user_inventory', ['user_id'])
    op.create_index('ix_user_inventory_chat_id', 'user_inventory', ['chat_id'])
    op.create_index('ix_user_inventory_item_type', 'user_inventory', ['item_type'])
    
    # Fishing Stats table
    op.create_table(
        'fishing_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('total_catches', sa.Integer(), default=0),
        sa.Column('legendary_catches', sa.Integer(), default=0),
        sa.Column('total_earnings', sa.Integer(), default=0),
        sa.Column('equipped_rod', sa.String(64), default='basic'),
        sa.Column('last_cast', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_fishing')
    )
    op.create_index('ix_fishing_stats_user_id', 'fishing_stats', ['user_id'])
    op.create_index('ix_fishing_stats_chat_id', 'fishing_stats', ['chat_id'])

    
    # Cockfight Stats table
    op.create_table(
        'cockfight_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('total_earnings', sa.Integer(), default=0),
        sa.Column('owned_roosters', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_cockfight')
    )
    op.create_index('ix_cockfight_stats_user_id', 'cockfight_stats', ['user_id'])
    op.create_index('ix_cockfight_stats_chat_id', 'cockfight_stats', ['chat_id'])
    
    # Game History table
    op.create_table(
        'game_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('game_type', sa.String(32), nullable=False),
        sa.Column('bet_amount', sa.Integer(), default=0),
        sa.Column('result_amount', sa.Integer(), default=0),
        sa.Column('won', sa.Boolean(), default=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('played_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_game_history_user_id', 'game_history', ['user_id'])
    op.create_index('ix_game_history_chat_id', 'game_history', ['chat_id'])
    op.create_index('ix_game_history_game_type', 'game_history', ['game_type'])
    op.create_index('ix_game_history_played_at', 'game_history', ['played_at'])


def downgrade() -> None:
    op.drop_table('game_history')
    op.drop_table('cockfight_stats')
    op.drop_table('fishing_stats')
    op.drop_table('user_inventory')
