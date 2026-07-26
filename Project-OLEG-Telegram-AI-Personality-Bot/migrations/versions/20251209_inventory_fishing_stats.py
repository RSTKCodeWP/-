"""Add inventory and fishing stats tables

Revision ID: 20251209_inv_fish
Revises: 007_games_v75
Create Date: 2025-12-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251209_inv_fish'
down_revision = '007_games_v75'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_inventory table
    op.create_table(
        'user_inventory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('item_type', sa.String(64), nullable=False),
        sa.Column('item_name', sa.String(128), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1),
        sa.Column('equipped', sa.Boolean(), default=False),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('acquired_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', 'item_type', name='uq_user_chat_item')
    )
    op.create_index('ix_user_inventory_user_id', 'user_inventory', ['user_id'])
    op.create_index('ix_user_inventory_chat_id', 'user_inventory', ['chat_id'])
    op.create_index('ix_user_inventory_item_type', 'user_inventory', ['item_type'])
    
    # Create fishing_stats table
    op.create_table(
        'fishing_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('trash_caught', sa.Integer(), default=0),
        sa.Column('common_caught', sa.Integer(), default=0),
        sa.Column('uncommon_caught', sa.Integer(), default=0),
        sa.Column('rare_caught', sa.Integer(), default=0),
        sa.Column('epic_caught', sa.Integer(), default=0),
        sa.Column('legendary_caught', sa.Integer(), default=0),
        sa.Column('total_casts', sa.Integer(), default=0),
        sa.Column('total_earnings', sa.Integer(), default=0),
        sa.Column('biggest_catch_value', sa.Integer(), default=0),
        sa.Column('biggest_catch_name', sa.String(64), nullable=True),
        sa.Column('equipped_rod', sa.String(64), default='basic_rod'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_fishing')
    )
    op.create_index('ix_fishing_stats_user_id', 'fishing_stats', ['user_id'])
    op.create_index('ix_fishing_stats_chat_id', 'fishing_stats', ['chat_id'])


def downgrade() -> None:
    op.drop_table('fishing_stats')
    op.drop_table('user_inventory')
