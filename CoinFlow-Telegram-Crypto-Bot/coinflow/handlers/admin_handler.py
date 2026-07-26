"""Admin panel handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from ..database.models import Announcement
from ..config import config
from ..utils.logger import setup_logger

logger = setup_logger('admin_handler')


class AdminHandler:
    """Handler for admin panel functionality."""
    
    def __init__(self, bot):
        self.bot = bot
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in config.ADMIN_IDS
    
    async def show_admin_panel(self, query, user):
        """Show main admin panel."""
        if not self.is_admin(user.telegram_id):
            await query.answer("❌ Access denied", show_alert=True)
            return
        
        await query.answer()
        
        # Get statistics
        stats = self.get_bot_statistics()
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data='admin_stats')],
            [InlineKeyboardButton("📢 Create Announcement", callback_data='admin_announce_create')],
            [InlineKeyboardButton("📋 Announcements History", callback_data='admin_announce_history')],
            [InlineKeyboardButton("👥 User Management", callback_data='admin_users')],
            [InlineKeyboardButton("◀️ Back", callback_data='back_main')]
        ]
        
        message = (
            "🔐 **Admin Panel**\n\n"
            f"Total Users: {stats['total_users']}\n"
            f"Active Users (24h): {stats['active_24h']}\n"
            f"Active Users (7d): {stats['active_7d']}\n"
            f"Total Conversions: {stats['total_conversions']}\n"
            f"Total Alerts: {stats['total_alerts']}\n"
            f"Announcements Sent: {stats['total_announcements']}"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    def get_bot_statistics(self) -> dict:
        """Get comprehensive bot statistics."""
        try:
            session = self.bot.db.Session()
            
            from ..database.models import User, ConversionHistory, Alert
            
            # Total users
            total_users = session.query(User).count()
            
            # Active users in last 24h
            day_ago = datetime.now() - timedelta(days=1)
            active_24h = session.query(User).filter(User.updated_at >= day_ago).count()
            
            # Active users in last 7 days
            week_ago = datetime.now() - timedelta(days=7)
            active_7d = session.query(User).filter(User.updated_at >= week_ago).count()
            
            # Total conversions
            total_conversions = session.query(ConversionHistory).count()
            
            # Total alerts
            total_alerts = session.query(Alert).count()
            
            # Total announcements sent
            total_announcements = session.query(Announcement).filter(
                Announcement.sent_at.isnot(None)
            ).count()
            
            session.close()
            
            return {
                'total_users': total_users,
                'active_24h': active_24h,
                'active_7d': active_7d,
                'total_conversions': total_conversions,
                'total_alerts': total_alerts,
                'total_announcements': total_announcements
            }
        
        except Exception as e:
            logger.error(f"Error getting bot statistics: {e}")
            return {
                'total_users': 0,
                'active_24h': 0,
                'active_7d': 0,
                'total_conversions': 0,
                'total_alerts': 0,
                'total_announcements': 0
            }
    
    async def show_statistics(self, query, user):
        """Show detailed statistics."""
        if not self.is_admin(user.telegram_id):
            await query.answer("❌ Access denied", show_alert=True)
            return
        
        await query.answer()
        
        stats = self.get_detailed_statistics()
        
        message = (
            "📊 **Detailed Statistics**\n\n"
            "**Users:**\n"
            f"• Total: {stats['total_users']}\n"
            f"• New (24h): {stats['new_users_24h']}\n"
            f"• Active (24h): {stats['active_24h']}\n"
            f"• Active (7d): {stats['active_7d']}\n"
            f"• Active (30d): {stats['active_30d']}\n\n"
            "**Activity:**\n"
            f"• Total Conversions: {stats['total_conversions']}\n"
            f"• Conversions (24h): {stats['conversions_24h']}\n"
            f"• Total Alerts: {stats['total_alerts']}\n"
            f"• Active Alerts: {stats['active_alerts']}\n\n"
            "**Portfolio:**\n"
            f"• Users with Portfolio: {stats['users_with_portfolio']}\n"
            f"• Total Portfolio Items: {stats['total_portfolio_items']}\n\n"
            "**Languages:**\n"
            f"• English: {stats['users_en']}\n"
            f"• Russian: {stats['users_ru']}\n\n"
            "**Announcements:**\n"
            f"• Total Sent: {stats['total_announcements']}\n"
            f"• Last 7 days: {stats['announcements_7d']}"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data='admin_panel')]]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    def get_detailed_statistics(self) -> dict:
        """Get detailed bot statistics."""
        try:
            session = self.bot.db.Session()
            
            from ..database.models import User, ConversionHistory, Alert, PortfolioItem
            
            # Users
            total_users = session.query(User).count()
            
            day_ago = datetime.now() - timedelta(days=1)
            new_users_24h = session.query(User).filter(User.created_at >= day_ago).count()
            active_24h = session.query(User).filter(User.updated_at >= day_ago).count()
            
            week_ago = datetime.now() - timedelta(days=7)
            active_7d = session.query(User).filter(User.updated_at >= week_ago).count()
            
            month_ago = datetime.now() - timedelta(days=30)
            active_30d = session.query(User).filter(User.updated_at >= month_ago).count()
            
            # Conversions
            total_conversions = session.query(ConversionHistory).count()
            conversions_24h = session.query(ConversionHistory).filter(
                ConversionHistory.timestamp >= day_ago
            ).count()
            
            # Alerts
            total_alerts = session.query(Alert).count()
            active_alerts = session.query(Alert).filter(Alert.is_active == True).count()
            
            # Portfolio
            users_with_portfolio = session.query(PortfolioItem.user_id).distinct().count()
            total_portfolio_items = session.query(PortfolioItem).count()
            
            # Languages
            users_en = session.query(User).filter(User.lang == 'en').count()
            users_ru = session.query(User).filter(User.lang == 'ru').count()
            
            # Announcements
            total_announcements = session.query(Announcement).filter(
                Announcement.sent_at.isnot(None)
            ).count()
            announcements_7d = session.query(Announcement).filter(
                Announcement.sent_at >= week_ago
            ).count()
            
            session.close()
            
            return {
                'total_users': total_users,
                'new_users_24h': new_users_24h,
                'active_24h': active_24h,
                'active_7d': active_7d,
                'active_30d': active_30d,
                'total_conversions': total_conversions,
                'conversions_24h': conversions_24h,
                'total_alerts': total_alerts,
                'active_alerts': active_alerts,
                'users_with_portfolio': users_with_portfolio,
                'total_portfolio_items': total_portfolio_items,
                'users_en': users_en,
                'users_ru': users_ru,
                'total_announcements': total_announcements,
                'announcements_7d': announcements_7d
            }
        
        except Exception as e:
            logger.error(f"Error getting detailed statistics: {e}")
            return {}
    
    async def start_announcement_creation(self, query, user):
        """Start announcement creation process."""
        if not self.is_admin(user.telegram_id):
            await query.answer("❌ Access denied", show_alert=True)
            return
        
        await query.answer()
        
        # Store state
        self.bot.temp_storage[user.telegram_id] = {
            'state': 'awaiting_announcement_content',
            'announcement': {}
        }
        
        message = (
            "📢 **Create Announcement**\n\n"
            "Send me the announcement content:\n\n"
            "• You can send text only\n"
            "• Or send photo/video/document with caption\n"
            "• Use Markdown formatting\n"
            "• Maximum 4096 characters\n\n"
            "After sending, you'll be able to preview before broadcasting."
        )
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='admin_panel')]]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_announcement_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle announcement content (text/media)."""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            return
        
        user_state = self.bot.temp_storage.get(user_id, {})
        
        if user_state.get('state') != 'awaiting_announcement_content':
            return
        
        message = update.message
        announcement = {}
        
        # Check for media
        if message.photo:
            announcement['media_type'] = 'photo'
            announcement['media_file_id'] = message.photo[-1].file_id
            announcement['text'] = message.caption or ''
        elif message.video:
            announcement['media_type'] = 'video'
            announcement['media_file_id'] = message.video.file_id
            announcement['text'] = message.caption or ''
        elif message.document:
            announcement['media_type'] = 'document'
            announcement['media_file_id'] = message.document.file_id
            announcement['text'] = message.caption or ''
        elif message.text:
            announcement['media_type'] = None
            announcement['media_file_id'] = None
            announcement['text'] = message.text
        else:
            await message.reply_text("❌ Unsupported content type. Please send text, photo, video, or document.")
            return
        
        # Store announcement
        self.bot.temp_storage[user_id]['announcement'] = announcement
        self.bot.temp_storage[user_id]['state'] = 'announcement_preview'
        
        # Show preview
        await self.show_announcement_preview(message, user_id)
    
    async def show_announcement_preview(self, message, user_id):
        """Show announcement preview before sending."""
        announcement = self.bot.temp_storage[user_id]['announcement']
        
        stats = self.get_bot_statistics()
        total_users = stats['total_users']
        
        keyboard = [
            [InlineKeyboardButton("✅ Send to All Users", callback_data='admin_announce_send')],
            [InlineKeyboardButton("🔄 Create New", callback_data='admin_announce_create')],
            [InlineKeyboardButton("❌ Cancel", callback_data='admin_panel')]
        ]
        
        preview_text = (
            "📢 **Announcement Preview**\n\n"
            f"Will be sent to: **{total_users}** users\n"
            f"Media: {announcement['media_type'] or 'None'}\n\n"
            "**Content:**\n"
            f"{announcement['text'][:200]}{'...' if len(announcement['text']) > 200 else ''}"
        )
        
        # Send preview with media if present
        if announcement['media_type'] == 'photo':
            await message.reply_photo(
                photo=announcement['media_file_id'],
                caption=preview_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif announcement['media_type'] == 'video':
            await message.reply_video(
                video=announcement['media_file_id'],
                caption=preview_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif announcement['media_type'] == 'document':
            await message.reply_document(
                document=announcement['media_file_id'],
                caption=preview_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await message.reply_text(
                preview_text + f"\n\n{announcement['text']}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def broadcast_announcement(self, query, user):
        """Broadcast announcement to all users."""
        if not self.is_admin(user.telegram_id):
            await query.answer("❌ Access denied", show_alert=True)
            return
        
        await query.answer()
        await query.edit_message_text("📤 Broadcasting announcement...")
        
        announcement_data = self.bot.temp_storage.get(user.telegram_id, {}).get('announcement', {})
        
        if not announcement_data:
            await query.edit_message_text("❌ No announcement data found")
            return
        
        # Save announcement to database
        session = self.bot.db.Session()
        announcement = Announcement(
            admin_id=user.telegram_id,
            text=announcement_data['text'],
            media_type=announcement_data.get('media_type'),
            media_file_id=announcement_data.get('media_file_id')
        )
        session.add(announcement)
        session.commit()
        announcement_id = announcement.id
        session.close()
        
        # Get all users
        all_users = self.bot.db.get_all_users()
        
        sent_count = 0
        failed_count = 0
        
        for db_user in all_users:
            try:
                # Send announcement
                if announcement_data.get('media_type') == 'photo':
                    await query.bot.send_photo(
                        chat_id=db_user.telegram_id,
                        photo=announcement_data['media_file_id'],
                        caption=announcement_data['text'],
                        parse_mode='Markdown'
                    )
                elif announcement_data.get('media_type') == 'video':
                    await query.bot.send_video(
                        chat_id=db_user.telegram_id,
                        video=announcement_data['media_file_id'],
                        caption=announcement_data['text'],
                        parse_mode='Markdown'
                    )
                elif announcement_data.get('media_type') == 'document':
                    await query.bot.send_document(
                        chat_id=db_user.telegram_id,
                        document=announcement_data['media_file_id'],
                        caption=announcement_data['text'],
                        parse_mode='Markdown'
                    )
                else:
                    await query.bot.send_message(
                        chat_id=db_user.telegram_id,
                        text=announcement_data['text'],
                        parse_mode='Markdown'
                    )
                
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send announcement to user {db_user.telegram_id}: {e}")
                failed_count += 1
        
        # Update announcement
        session = self.bot.db.Session()
        announcement = session.query(Announcement).filter(Announcement.id == announcement_id).first()
        if announcement:
            announcement.sent_count = sent_count
            announcement.sent_at = datetime.now()
            session.commit()
        session.close()
        
        # Clear temp storage
        self.bot.temp_storage.pop(user.telegram_id, None)
        
        # Show result
        result_message = (
            f"✅ **Announcement Sent!**\n\n"
            f"Successfully sent: {sent_count}\n"
            f"Failed: {failed_count}\n"
            f"Total: {sent_count + failed_count}"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Back to Admin Panel", callback_data='admin_panel')]]
        
        await query.bot.send_message(
            chat_id=user.telegram_id,
            text=result_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_announcements_history(self, query, user):
        """Show history of sent announcements."""
        if not self.is_admin(user.telegram_id):
            await query.answer("❌ Access denied", show_alert=True)
            return
        
        await query.answer()
        
        session = self.bot.db.Session()
        announcements = session.query(Announcement).filter(
            Announcement.sent_at.isnot(None)
        ).order_by(Announcement.sent_at.desc()).limit(10).all()
        
        if not announcements:
            message = "📋 **Announcements History**\n\nNo announcements sent yet."
        else:
            message = "📋 **Announcements History** (Last 10)\n\n"
            
            for ann in announcements:
                sent_date = ann.sent_at.strftime("%Y-%m-%d %H:%M")
                text_preview = ann.text[:50] + "..." if len(ann.text) > 50 else ann.text
                media_icon = ""
                if ann.media_type == 'photo':
                    media_icon = "🖼 "
                elif ann.media_type == 'video':
                    media_icon = "🎥 "
                elif ann.media_type == 'document':
                    media_icon = "📄 "
                
                message += f"{media_icon}**{sent_date}**\n"
                message += f"Sent to: {ann.sent_count} users\n"
                message += f"_{text_preview}_\n\n"
        
        session.close()
        
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data='admin_panel')]]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
