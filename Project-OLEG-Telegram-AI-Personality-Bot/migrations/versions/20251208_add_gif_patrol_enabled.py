"""Add gif_patrol_enabled to citadel_configs

Revision ID: 20251208_gif_patrol
Revises: 20251208_grow_history
Create Date: 2025-12-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251208_gif_patrol'
down_revision: Union[str, None] = '20251208_grow_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add gif_patrol_enabled column to citadel_configs
    # Default is False (disabled) - GIF patrol is work in progress
    op.add_column(
        'citadel_configs',
        sa.Column('gif_patrol_enabled', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('citadel_configs', 'gif_patrol_enabled')
