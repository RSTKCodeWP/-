"""remove_quotes_and_stickers

Revision ID: 042d107b23a8
Revises: 5b6fe99ee596
Create Date: 2026-01-27 15:17:04.247522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '042d107b23a8'
down_revision: Union[str, None] = '5b6fe99ee596'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop quote_votes table first (foreign key dependency)
    op.drop_table('quote_votes')
    
    # Drop quotes table
    op.drop_table('quotes')
    
    # Drop sticker_packs table
    op.drop_table('sticker_packs')


def downgrade() -> None:
    # Recreate sticker_packs table
    op.create_table(
        'sticker_packs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('pack_name', sa.String(length=64), nullable=False),
        sa.Column('pack_title', sa.String(length=64), nullable=False),
        sa.Column('sticker_count', sa.Integer(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('owner_user_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sticker_packs_chat_id'), 'sticker_packs', ['chat_id'], unique=False)
    op.create_index(op.f('ix_sticker_packs_is_current'), 'sticker_packs', ['is_current'], unique=False)
    
    # Recreate quotes table
    op.create_table(
        'quotes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('image_data', sa.LargeBinary(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('likes_count', sa.Integer(), nullable=False),
        sa.Column('dislikes_count', sa.Integer(), nullable=False),
        sa.Column('is_golden_fund', sa.Boolean(), nullable=False),
        sa.Column('is_sticker', sa.Boolean(), nullable=False),
        sa.Column('sticker_file_id', sa.String(length=255), nullable=True),
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('sticker_pack_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['sticker_pack_id'], ['sticker_packs.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quotes_created_at'), 'quotes', ['created_at'], unique=False)
    op.create_index(op.f('ix_quotes_user_id'), 'quotes', ['user_id'], unique=False)
    
    # Recreate quote_votes table
    op.create_table(
        'quote_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('vote_type', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_votes_quote_id'), 'quote_votes', ['quote_id'], unique=False)
    op.create_index(op.f('ix_quote_votes_user_id'), 'quote_votes', ['user_id'], unique=False)
