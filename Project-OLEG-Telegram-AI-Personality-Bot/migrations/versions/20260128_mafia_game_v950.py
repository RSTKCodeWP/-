"""Add mafia game tables v9.5.0

Revision ID: 20260128_mafia_game_v950
Revises: 71b4acfaa9ed
Create Date: 2026-01-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260128_mafia_game_v950'
down_revision: Union[str, None] = '71b4acfaa9ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create mafia_games table
    op.create_table('mafia_games',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('phase_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('winner', sa.String(length=20), nullable=True),
        sa.Column('phase_started_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mafia_games_chat_id'), 'mafia_games', ['chat_id'], unique=False)
    op.create_index(op.f('ix_mafia_games_status'), 'mafia_games', ['status'], unique=False)
    
    # Create mafia_players table
    op.create_table('mafia_players',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_alive', sa.Boolean(), nullable=False),
        sa.Column('death_phase', sa.Integer(), nullable=True),
        sa.Column('death_reason', sa.String(length=20), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['mafia_games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'user_id', name='uq_mafia_game_user')
    )
    op.create_index(op.f('ix_mafia_players_game_id'), 'mafia_players', ['game_id'], unique=False)
    op.create_index(op.f('ix_mafia_players_user_id'), 'mafia_players', ['user_id'], unique=False)
    
    # Create mafia_night_actions table
    op.create_table('mafia_night_actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('phase_number', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('action_type', sa.String(length=20), nullable=False),
        sa.Column('target_user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['mafia_games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'phase_number', 'user_id', name='uq_mafia_night_action')
    )
    op.create_index(op.f('ix_mafia_night_actions_game_id'), 'mafia_night_actions', ['game_id'], unique=False)
    op.create_index(op.f('ix_mafia_night_actions_user_id'), 'mafia_night_actions', ['user_id'], unique=False)
    
    # Create mafia_votes table
    op.create_table('mafia_votes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('phase_number', sa.Integer(), nullable=False),
        sa.Column('voter_id', sa.BigInteger(), nullable=False),
        sa.Column('target_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['mafia_games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'phase_number', 'voter_id', name='uq_mafia_vote')
    )
    op.create_index(op.f('ix_mafia_votes_game_id'), 'mafia_votes', ['game_id'], unique=False)
    op.create_index(op.f('ix_mafia_votes_voter_id'), 'mafia_votes', ['voter_id'], unique=False)
    
    # Create mafia_stats table
    op.create_table('mafia_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('games_played', sa.Integer(), nullable=False),
        sa.Column('games_won', sa.Integer(), nullable=False),
        sa.Column('games_survived', sa.Integer(), nullable=False),
        sa.Column('mafia_wins', sa.Integer(), nullable=False),
        sa.Column('mafia_games', sa.Integer(), nullable=False),
        sa.Column('citizen_wins', sa.Integer(), nullable=False),
        sa.Column('citizen_games', sa.Integer(), nullable=False),
        sa.Column('detective_checks', sa.Integer(), nullable=False),
        sa.Column('detective_games', sa.Integer(), nullable=False),
        sa.Column('doctor_saves', sa.Integer(), nullable=False),
        sa.Column('doctor_games', sa.Integer(), nullable=False),
        sa.Column('correct_votes', sa.Integer(), nullable=False),
        sa.Column('total_votes', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='uq_mafia_user_chat_stats')
    )
    op.create_index(op.f('ix_mafia_stats_user_id'), 'mafia_stats', ['user_id'], unique=False)
    op.create_index(op.f('ix_mafia_stats_chat_id'), 'mafia_stats', ['chat_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mafia_stats_chat_id'), table_name='mafia_stats')
    op.drop_index(op.f('ix_mafia_stats_user_id'), table_name='mafia_stats')
    op.drop_table('mafia_stats')
    
    op.drop_index(op.f('ix_mafia_votes_voter_id'), table_name='mafia_votes')
    op.drop_index(op.f('ix_mafia_votes_game_id'), table_name='mafia_votes')
    op.drop_table('mafia_votes')
    
    op.drop_index(op.f('ix_mafia_night_actions_user_id'), table_name='mafia_night_actions')
    op.drop_index(op.f('ix_mafia_night_actions_game_id'), table_name='mafia_night_actions')
    op.drop_table('mafia_night_actions')
    
    op.drop_index(op.f('ix_mafia_players_user_id'), table_name='mafia_players')
    op.drop_index(op.f('ix_mafia_players_game_id'), table_name='mafia_players')
    op.drop_table('mafia_players')
    
    op.drop_index(op.f('ix_mafia_games_status'), table_name='mafia_games')
    op.drop_index(op.f('ix_mafia_games_chat_id'), table_name='mafia_games')
    op.drop_table('mafia_games')
