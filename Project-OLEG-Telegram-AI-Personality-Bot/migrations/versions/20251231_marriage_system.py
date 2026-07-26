"""Add marriage system tables.

Revision ID: 20251231_marriage
Revises: 20251220_pvp_timeout
Create Date: 2025-12-31

Requirements: 9.1, 9.2 - Marriage and MarriageProposal tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251231_marriage'
down_revision: Union[str, None] = '20251220_pvp_timeout'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create marriages table if not exists
    if 'marriages' not in existing_tables:
        op.create_table(
            'marriages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user1_id', sa.BigInteger(), nullable=False),
            sa.Column('user2_id', sa.BigInteger(), nullable=False),
            sa.Column('chat_id', sa.BigInteger(), nullable=False),
            sa.Column('married_at', sa.DateTime(), nullable=True),
            sa.Column('divorced_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_marriages_user1_id', 'marriages', ['user1_id'])
        op.create_index('ix_marriages_user2_id', 'marriages', ['user2_id'])
        op.create_index('ix_marriages_chat_id', 'marriages', ['chat_id'])
    
    # Create marriage_proposals table if not exists
    if 'marriage_proposals' not in existing_tables:
        op.create_table(
            'marriage_proposals',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('from_user_id', sa.BigInteger(), nullable=False),
            sa.Column('to_user_id', sa.BigInteger(), nullable=False),
            sa.Column('chat_id', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(16), nullable=True, server_default='pending'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_marriage_proposals_from_user_id', 'marriage_proposals', ['from_user_id'])
        op.create_index('ix_marriage_proposals_to_user_id', 'marriage_proposals', ['to_user_id'])
        op.create_index('ix_marriage_proposals_chat_id', 'marriage_proposals', ['chat_id'])
        op.create_index('ix_marriage_proposals_status', 'marriage_proposals', ['status'])


def downgrade() -> None:
    op.drop_index('ix_marriage_proposals_status', 'marriage_proposals')
    op.drop_index('ix_marriage_proposals_chat_id', 'marriage_proposals')
    op.drop_index('ix_marriage_proposals_to_user_id', 'marriage_proposals')
    op.drop_index('ix_marriage_proposals_from_user_id', 'marriage_proposals')
    op.drop_table('marriage_proposals')
    
    op.drop_index('ix_marriages_chat_id', 'marriages')
    op.drop_index('ix_marriages_user2_id', 'marriages')
    op.drop_index('ix_marriages_user1_id', 'marriages')
    op.drop_table('marriages')
