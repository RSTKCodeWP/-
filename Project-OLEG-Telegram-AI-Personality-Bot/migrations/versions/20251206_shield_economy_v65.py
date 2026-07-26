"""Shield & Economy v6.5 - New tables for token economy and protection

Revision ID: 20251206_shield_economy
Revises: 20251206_dailies
Create Date: 2025-12-06

New tables for OLEG v6.5 Shield & Economy Update:
- user_energy: Personal energy system for LLM request limiting (Requirements 1.1-1.4)
- chat_rate_limit_config: Global chat rate limit configuration (Requirements 2.1, 2.3)
- protection_profile_config: Protection profile settings per chat (Requirements 10.1-10.4)
- silent_bans: Silent ban tracking for suspicious users (Requirements 9.4, 9.5)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251206_shield_economy'
down_revision: Union[str, None] = '20251206_dailies'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === NEW TABLES ===
    
    # User energy - personal energy system for LLM request limiting
    op.create_table('user_energy',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('energy', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_request', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_energy')
    )
    op.create_index('ix_user_energy_user_id', 'user_energy', ['user_id'])
    op.create_index('ix_user_energy_chat_id', 'user_energy', ['chat_id'])

    # Chat rate limit config - global chat rate limit configuration
    op.create_table('chat_rate_limit_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('llm_requests_per_minute', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id', name='uq_chat_rate_limit_config_chat_id')
    )
    op.create_index('ix_chat_rate_limit_config_chat_id', 'chat_rate_limit_config', ['chat_id'])

    # Protection profile config - protection profile settings per chat
    op.create_table('protection_profile_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('profile', sa.String(length=20), nullable=False, server_default='standard'),
        sa.Column('anti_spam_links', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('captcha_type', sa.String(length=10), nullable=False, server_default='button'),
        sa.Column('profanity_allowed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('neural_ad_filter', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('block_forwards', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sticker_limit', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mute_newcomers', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('block_media_non_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('aggressive_profanity', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id', name='uq_protection_profile_config_chat_id')
    )
    op.create_index('ix_protection_profile_config_chat_id', 'protection_profile_config', ['chat_id'])

    # Silent bans - silent ban tracking for suspicious users
    op.create_table('silent_bans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('captcha_answer', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_silent_ban')
    )
    op.create_index('ix_silent_bans_user_id', 'silent_bans', ['user_id'])
    op.create_index('ix_silent_bans_chat_id', 'silent_bans', ['chat_id'])


def downgrade() -> None:
    # === DROP NEW TABLES ===
    
    op.drop_index('ix_silent_bans_chat_id', table_name='silent_bans')
    op.drop_index('ix_silent_bans_user_id', table_name='silent_bans')
    op.drop_table('silent_bans')
    
    op.drop_index('ix_protection_profile_config_chat_id', table_name='protection_profile_config')
    op.drop_table('protection_profile_config')
    
    op.drop_index('ix_chat_rate_limit_config_chat_id', table_name='chat_rate_limit_config')
    op.drop_table('chat_rate_limit_config')
    
    op.drop_index('ix_user_energy_chat_id', table_name='user_energy')
    op.drop_index('ix_user_energy_user_id', table_name='user_energy')
    op.drop_table('user_energy')
