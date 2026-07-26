"""add_game_balance_cooldowns

Revision ID: 5b6fe99ee596
Revises: beb16c1db81f
Create Date: 2026-01-27 14:30:59.418889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b6fe99ee596'
down_revision: Union[str, None] = 'beb16c1db81f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cooldown columns to game_stats table
    with op.batch_alter_table('game_stats', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_cream_use', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_cockfight', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_energy_drink_use', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove cooldown columns from game_stats table
    with op.batch_alter_table('game_stats', schema=None) as batch_op:
        batch_op.drop_column('last_energy_drink_use')
        batch_op.drop_column('last_cockfight')
        batch_op.drop_column('last_cream_use')
