"""Add pvp_accept_timeout to bot_configs.

Revision ID: 20251220_pvp_timeout
Revises: 
Create Date: 2025-12-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251220_pvp_timeout'
down_revision: Union[str, None] = '20251218_pp_battle'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pvp_accept_timeout column to bot_configs
    # Check if column exists first to avoid errors
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if table exists
    if 'bot_configs' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('bot_configs')]
        
        if 'pvp_accept_timeout' not in columns:
            op.add_column('bot_configs', sa.Column('pvp_accept_timeout', sa.Integer(), nullable=True, server_default='60'))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'bot_configs' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('bot_configs')]
        
        if 'pvp_accept_timeout' in columns:
            op.drop_column('bot_configs', 'pvp_accept_timeout')
