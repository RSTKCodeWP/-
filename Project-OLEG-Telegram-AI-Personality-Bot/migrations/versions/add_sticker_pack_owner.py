"""Add owner_user_id to sticker_packs table.

Revision ID: add_sticker_pack_owner
Revises: 20251231_marriage
Create Date: 2024-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_sticker_pack_owner'
down_revision = '20251231_marriage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add owner_user_id column to sticker_packs if not exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'sticker_packs' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('sticker_packs')]
        if 'owner_user_id' not in columns:
            op.add_column(
                'sticker_packs',
                sa.Column('owner_user_id', sa.BigInteger(), nullable=True)
            )


def downgrade() -> None:
    op.drop_column('sticker_packs', 'owner_user_id')
