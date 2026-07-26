"""Add active_topic_id and auto_reply_chance to chats

Revision ID: 20251205_160525
Revises: 
Create Date: 2025-12-05 16:05:25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251205_160525'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add active_topic_id column
    op.add_column('chats', sa.Column('active_topic_id', sa.Integer(), nullable=True))
    # Add auto_reply_chance column with default 0.0
    op.add_column('chats', sa.Column('auto_reply_chance', sa.Float(), nullable=True, server_default='0.0'))


def downgrade() -> None:
    op.drop_column('chats', 'auto_reply_chance')
    op.drop_column('chats', 'active_topic_id')
