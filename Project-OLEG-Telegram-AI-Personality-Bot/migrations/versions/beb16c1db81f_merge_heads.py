"""merge_heads

Revision ID: beb16c1db81f
Revises: 20250127_remove_moderation, add_sticker_pack_owner
Create Date: 2026-01-27 14:30:52.714723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'beb16c1db81f'
down_revision: Union[str, None] = ('20250127_remove_moderation', 'add_sticker_pack_owner')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
