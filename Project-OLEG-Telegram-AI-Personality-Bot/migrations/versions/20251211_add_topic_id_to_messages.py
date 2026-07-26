"""Add topic_id to messages table

Revision ID: 20251211_topic_id
Revises: 20251209_inv_fish
Create Date: 2025-12-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251211_topic_id'
down_revision: Union[str, None] = '20251209_inv_fish'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add topic_id column to messages table
    op.add_column('messages', sa.Column('topic_id', sa.BigInteger(), nullable=True))
    # Add index for faster queries by topic
    op.create_index('ix_messages_topic_id', 'messages', ['topic_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_messages_topic_id', table_name='messages')
    op.drop_column('messages', 'topic_id')
