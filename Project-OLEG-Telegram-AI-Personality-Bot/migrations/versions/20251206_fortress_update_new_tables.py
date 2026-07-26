"""fortress_update_new_tables

Revision ID: 20251206_fortress
Revises: 08724a3d75f5
Create Date: 2025-12-06

New tables for OLEG v6.0 Fortress Update:
- citadel_configs: DEFCON protection levels per chat
- user_reputations: User reputation scores per chat
- reputation_history: Reputation change history
- tournaments: Tournament tracking
- tournament_scores: Tournament scores per user/discipline
- user_elo: ELO ratings for league system
- notification_configs: Owner notification settings
- sticker_packs: Sticker pack management
- security_blacklist: Security blacklist for abuse prevention

Also adds new columns to existing tables:
- users: reputation_score
- game_stats: elo_rating, league, season_multiplier
- quotes: sticker_pack_id
- chats: defcon_level, owner_notifications_enabled
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251206_fortress'
down_revision: Union[str, None] = '08724a3d75f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === NEW TABLES ===
    
    # Citadel configs - DEFCON protection levels per chat
    op.create_table('citadel_configs',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('defcon_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('raid_mode_until', sa.DateTime(), nullable=True),
        sa.Column('anti_spam_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('profanity_filter_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sticker_limit', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('forward_block_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('new_user_restriction_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('hard_captcha_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('chat_id')
    )
    op.create_index('ix_citadel_configs_defcon_level', 'citadel_configs', ['defcon_level'])

    # User reputations - reputation scores per user per chat
    op.create_table('user_reputations',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('is_read_only', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_change_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id', 'chat_id')
    )
    op.create_index('ix_user_reputations_chat_id', 'user_reputations', ['chat_id'])
    op.create_index('ix_user_reputations_score', 'user_reputations', ['score'])

    # Reputation history - track all reputation changes
    op.create_table('reputation_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('change_amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reputation_history_user_id', 'reputation_history', ['user_id'])
    op.create_index('ix_reputation_history_chat_id', 'reputation_history', ['chat_id'])
    op.create_index('ix_reputation_history_created_at', 'reputation_history', ['created_at'])

    # Tournaments - tournament tracking
    op.create_table('tournaments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('end_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tournaments_type', 'tournaments', ['type'])
    op.create_index('ix_tournaments_status', 'tournaments', ['status'])
    op.create_index('ix_tournaments_start_at', 'tournaments', ['start_at'])

    # Tournament scores - scores per user per discipline
    op.create_table('tournament_scores',
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('discipline', sa.String(length=20), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tournament_id', 'user_id', 'discipline')
    )
    op.create_index('ix_tournament_scores_user_id', 'tournament_scores', ['user_id'])
    op.create_index('ix_tournament_scores_score', 'tournament_scores', ['score'])

    # User ELO - ELO ratings for league system
    op.create_table('user_elo',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('elo', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('league', sa.String(length=20), nullable=False, server_default='scrap'),
        sa.Column('season_wins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index('ix_user_elo_elo', 'user_elo', ['elo'])
    op.create_index('ix_user_elo_league', 'user_elo', ['league'])

    # Notification configs - owner notification settings per chat
    op.create_table('notification_configs',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('owner_id', sa.BigInteger(), nullable=False),
        sa.Column('raid_alert', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ban_notification', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('toxicity_warning', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('defcon_recommendation', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('repeated_violator', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('daily_tips', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('chat_id')
    )
    op.create_index('ix_notification_configs_owner_id', 'notification_configs', ['owner_id'])

    # Sticker packs - sticker pack management per chat
    op.create_table('sticker_packs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('pack_name', sa.String(length=64), nullable=False),
        sa.Column('pack_title', sa.String(length=64), nullable=False),
        sa.Column('sticker_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pack_name', name='uq_sticker_packs_pack_name')
    )
    op.create_index('ix_sticker_packs_chat_id', 'sticker_packs', ['chat_id'])
    op.create_index('ix_sticker_packs_is_current', 'sticker_packs', ['is_current'])

    # Security blacklist - temporary blacklist for abuse prevention
    op.create_table('security_blacklist',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('blacklisted_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index('ix_security_blacklist_expires_at', 'security_blacklist', ['expires_at'])

    # Rate limits table (fallback when Redis unavailable)
    op.create_table('rate_limits',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('user_id', 'window_start')
    )

    # === UPDATES TO EXISTING TABLES ===
    
    # Add reputation_score to users table
    op.add_column('users', sa.Column('reputation_score', sa.Integer(), nullable=False, server_default='1000'))
    
    # Add elo_rating, league, season_multiplier to game_stats table
    op.add_column('game_stats', sa.Column('elo_rating', sa.Integer(), nullable=False, server_default='1000'))
    op.add_column('game_stats', sa.Column('league', sa.String(length=20), nullable=False, server_default='scrap'))
    op.add_column('game_stats', sa.Column('season_multiplier', sa.Float(), nullable=False, server_default='1.0'))
    
    # Add sticker_pack_id to quotes table
    op.add_column('quotes', sa.Column('sticker_pack_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_quotes_sticker_pack_id', 'quotes', 'sticker_packs', ['sticker_pack_id'], ['id'])
    
    # Add defcon_level, owner_notifications_enabled to chats table
    op.add_column('chats', sa.Column('defcon_level', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('chats', sa.Column('owner_notifications_enabled', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # === REMOVE UPDATES TO EXISTING TABLES ===
    
    # Remove columns from chats
    op.drop_column('chats', 'owner_notifications_enabled')
    op.drop_column('chats', 'defcon_level')
    
    # Remove foreign key and column from quotes
    op.drop_constraint('fk_quotes_sticker_pack_id', 'quotes', type_='foreignkey')
    op.drop_column('quotes', 'sticker_pack_id')
    
    # Remove columns from game_stats
    op.drop_column('game_stats', 'season_multiplier')
    op.drop_column('game_stats', 'league')
    op.drop_column('game_stats', 'elo_rating')
    
    # Remove column from users
    op.drop_column('users', 'reputation_score')
    
    # === DROP NEW TABLES ===
    
    op.drop_table('rate_limits')
    
    op.drop_index('ix_security_blacklist_expires_at', table_name='security_blacklist')
    op.drop_table('security_blacklist')
    
    op.drop_index('ix_sticker_packs_is_current', table_name='sticker_packs')
    op.drop_index('ix_sticker_packs_chat_id', table_name='sticker_packs')
    op.drop_table('sticker_packs')
    
    op.drop_index('ix_notification_configs_owner_id', table_name='notification_configs')
    op.drop_table('notification_configs')
    
    op.drop_index('ix_user_elo_league', table_name='user_elo')
    op.drop_index('ix_user_elo_elo', table_name='user_elo')
    op.drop_table('user_elo')
    
    op.drop_index('ix_tournament_scores_score', table_name='tournament_scores')
    op.drop_index('ix_tournament_scores_user_id', table_name='tournament_scores')
    op.drop_table('tournament_scores')
    
    op.drop_index('ix_tournaments_start_at', table_name='tournaments')
    op.drop_index('ix_tournaments_status', table_name='tournaments')
    op.drop_index('ix_tournaments_type', table_name='tournaments')
    op.drop_table('tournaments')
    
    op.drop_index('ix_reputation_history_created_at', table_name='reputation_history')
    op.drop_index('ix_reputation_history_chat_id', table_name='reputation_history')
    op.drop_index('ix_reputation_history_user_id', table_name='reputation_history')
    op.drop_table('reputation_history')
    
    op.drop_index('ix_user_reputations_score', table_name='user_reputations')
    op.drop_index('ix_user_reputations_chat_id', table_name='user_reputations')
    op.drop_table('user_reputations')
    
    op.drop_index('ix_citadel_configs_defcon_level', table_name='citadel_configs')
    op.drop_table('citadel_configs')
