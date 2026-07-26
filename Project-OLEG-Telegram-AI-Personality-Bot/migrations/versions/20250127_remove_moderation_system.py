"""remove_moderation_system

Revision ID: 20250127_remove_moderation
Revises: 20251231_marriage_system
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250127_remove_moderation'
down_revision = '20251231_marriage'
branch_labels = None
depends_on = None


def upgrade():
    """Remove all moderation-related tables and columns."""
    
    # Drop tables
    op.drop_table('warnings')
    op.drop_table('toxicity_logs')
    op.drop_table('toxicity_configs')
    op.drop_table('moderation_configs')
    op.drop_table('citadel_configs')
    op.drop_table('user_reputations')
    op.drop_table('reputation_history')
    op.drop_table('spam_patterns')
    op.drop_table('blacklist')
    op.drop_table('security_blacklist')
    op.drop_table('rate_limits')
    op.drop_table('protection_profile_config')
    op.drop_table('silent_bans')
    
    # Drop columns from users table
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('strikes')
    
    # Drop columns from chats table
    with op.batch_alter_table('chats') as batch_op:
        batch_op.drop_column('defcon_level')
        batch_op.drop_column('owner_notifications_enabled')
        batch_op.drop_column('moderation_mode')
    
    # Drop columns from notification_configs table
    with op.batch_alter_table('notification_configs') as batch_op:
        batch_op.drop_column('raid_alert')
        batch_op.drop_column('ban_notification')
        batch_op.drop_column('toxicity_warning')
        batch_op.drop_column('defcon_recommendation')
        batch_op.drop_column('repeated_violator')


def downgrade():
    """Restore moderation system (not implemented)."""
    pass
