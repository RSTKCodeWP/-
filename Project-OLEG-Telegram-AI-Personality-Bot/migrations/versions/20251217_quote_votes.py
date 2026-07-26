"""Add quote votes table and dislikes_count

Revision ID: 20251217_quote_votes
Revises: 20251211_topic_id
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa

revision = '20251217_quote_votes'
down_revision = '20251211_topic_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле dislikes_count в quotes
    op.add_column('quotes', sa.Column('dislikes_count', sa.Integer(), nullable=True, server_default='0'))
    
    # Создаём таблицу голосов
    op.create_table(
        'quote_votes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('vote_type', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quote_votes_quote_id', 'quote_votes', ['quote_id'])
    op.create_index('ix_quote_votes_user_id', 'quote_votes', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_quote_votes_user_id', 'quote_votes')
    op.drop_index('ix_quote_votes_quote_id', 'quote_votes')
    op.drop_table('quote_votes')
    op.drop_column('quotes', 'dislikes_count')
