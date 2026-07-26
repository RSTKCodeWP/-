"""Handler for CS2 market features with full 6-level hierarchy."""

import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from typing import Dict, List, Optional
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('cs2_handler')


class CS2Handler:
    """Handler for CS2 item market queries with hierarchical navigation."""
    
    def __init__(self, bot):
        self.bot = bot
        self.cs2_service = bot.cs2_service
        
        # Load CS2 items database
        self.items_data = self._load_items_database()
        
        # Navigation state storage (user_id -> state)
        self.user_states = {}
    
    def _load_items_database(self) -> Dict:
        """Load CS2 items database from JSON file."""
        try:
            data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cs2_items.json')
            with open(data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load CS2 items database: {e}")
            return {"categories": {}, "quality_mapping": {}, "wear_mapping": {}}
    
    def _get_user_state(self, user_id: int) -> Dict:
        """Get user's current navigation state."""
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        return self.user_states[user_id]
    
    def _update_user_state(self, user_id: int, **kwargs):
        """Update user's navigation state."""
        state = self._get_user_state(user_id)
        state.update(kwargs)
        self.user_states[user_id] = state
    
    def _clear_user_state(self, user_id: int):
        """Clear user's navigation state."""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    async def show_cs2_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main CS2 categories menu (Level 1)."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        # Clear navigation state
        self._clear_user_state(user_id)
        
        keyboard = [
            [InlineKeyboardButton('🔍 ' + get_text(user.lang, 'cs2_search'), callback_data='cs2_search')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_category_weapons'), callback_data='cs2_main_weapons')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_category_other'), callback_data='cs2_main_other')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_main')]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                get_text(user.lang, 'cs2_menu'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                get_text(user.lang, 'cs2_menu'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def show_weapon_categories(self, query, user):
        """Show weapon subcategories menu (Level 2)."""
        keyboard = [
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_knives'), callback_data='cs2_wcat_knives')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_gloves'), callback_data='cs2_wcat_gloves')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_rifles'), callback_data='cs2_wcat_rifles')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_pistols'), callback_data='cs2_wcat_pistols')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_smgs'), callback_data='cs2_wcat_smgs')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_snipers'), callback_data='cs2_wcat_snipers')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_shotguns'), callback_data='cs2_wcat_shotguns')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_weapons_machine_guns'), callback_data='cs2_wcat_machine_guns')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_menu')]
        ]
        
        await query.edit_message_text(
            get_text(user.lang, 'cs2_category_weapons'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_weapon_models(self, query, user, category: str, page: int = 0):
        """Show weapon models for selected category (Level 3)."""
        self._update_user_state(user.telegram_id, category=category)
        
        # Get models from database
        category_data = self.items_data['categories']['weapons'].get(category, {})
        models = category_data.get('models', [])
        
        if not models:
            await query.edit_message_text(
                get_text(user.lang, 'cs2_no_items'),
                parse_mode='Markdown'
            )
            return
        
        # Pagination
        items_per_page = 8
        total_pages = (len(models) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(models))
        
        keyboard = []
        for model in models[start_idx:end_idx]:
            model_text = get_text(user.lang, f'cs2_{category[:-1]}_{model}', default=model.upper())
            keyboard.append([InlineKeyboardButton(model_text, callback_data=f'cs2_model_{category}_{model}')])
        
        # Pagination buttons
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton('◀️ ' + get_text(user.lang, 'previous'), 
                                                       callback_data=f'cs2_wcat_{category}_p{page-1}'))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(get_text(user.lang, 'next') + ' ▶️', 
                                                       callback_data=f'cs2_wcat_{category}_p{page+1}'))
            if nav_buttons:
                keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_main_weapons')])
        
        category_name = get_text(user.lang, f'cs2_weapons_{category}')
        page_info = f" ({page+1}/{total_pages})" if total_pages > 1 else ""
        
        await query.edit_message_text(
            get_text(user.lang, 'cs2_select_model', category=category_name) + page_info,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_souvenir_question(self, query, user, category: str, model: str):
        """Ask if item is souvenir (Level 4)."""
        self._update_user_state(user.telegram_id, model=model)
        
        # Check if this category skips souvenir question
        category_data = self.items_data['categories']['weapons'].get(category, {})
        if category_data.get('skip_souvenir', False):
            # Skip to quality selection
            await self.show_quality_selection(query, user, category, model, souvenir=False)
            return
        
        keyboard = [
            [InlineKeyboardButton(get_text(user.lang, 'cs2_souvenir_yes'), callback_data=f'cs2_souv_{category}_{model}_yes')],
            [InlineKeyboardButton(get_text(user.lang, 'cs2_souvenir_no'), callback_data=f'cs2_souv_{category}_{model}_no')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data=f'cs2_wcat_{category}')]
        ]
        
        await query.edit_message_text(
            get_text(user.lang, 'cs2_souvenir_question'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_quality_selection(self, query, user, category: str, model: str, souvenir: bool = False):
        """Show quality/rarity selection (Level 5)."""
        self._update_user_state(user.telegram_id, souvenir=souvenir)
        
        # Check if this category skips quality
        category_data = self.items_data['categories']['weapons'].get(category, {})
        if category_data.get('skip_quality', False):
            # Skip to wear selection
            await self.show_wear_selection(query, user, category, model, souvenir, quality='default')
            return
        
        qualities = category_data.get('qualities', [])
        
        keyboard = []
        for quality in qualities:
            quality_text = get_text(user.lang, f'cs2_quality_{quality}')
            keyboard.append([InlineKeyboardButton(quality_text, callback_data=f'cs2_qual_{category}_{model}_{quality}')])
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data=f'cs2_model_{category}_{model}')])
        
        await query.edit_message_text(
            get_text(user.lang, 'cs2_select_quality'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_wear_selection(self, query, user, category: str, model: str, souvenir: bool, quality: str):
        """Show wear condition selection (Level 6)."""
        self._update_user_state(user.telegram_id, quality=quality)
        
        # Check if this category has wear conditions
        category_data = self.items_data['categories']['weapons'].get(category, {})
        wears = category_data.get('wears', [])
        
        if not wears:
            # No wear conditions, show final item
            await self.show_final_item(query, user, category, model, souvenir, quality, wear='none')
            return
        
        keyboard = []
        for wear in wears:
            wear_text = get_text(user.lang, f'cs2_wear_{wear}')
            keyboard.append([InlineKeyboardButton(wear_text, callback_data=f'cs2_wear_{category}_{model}_{wear}')])
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data=f'cs2_souv_{category}_{model}_no')])
        
        await query.edit_message_text(
            get_text(user.lang, 'cs2_select_wear'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_final_item(self, query, user, category: str, model: str, souvenir: bool, quality: str, wear: str):
        """Show final item with prices (Final Level)."""
        await query.edit_message_text(
            f"💎 {get_text(user.lang, 'loading')}...\n\n{get_text(user.lang, 'cs2_fetching_prices')}",
            parse_mode='Markdown'
        )
        
        # Build item name
        model_name = get_text(user.lang, f'cs2_{category[:-1]}_{model}', default=model.upper())
        quality_name = get_text(user.lang, f'cs2_quality_{quality}', default=quality.upper()) if quality != 'default' else ''
        wear_name = self.items_data['wear_mapping'].get(wear, {}).get(user.lang, '') if wear != 'none' else ''
        
        # Construct full item name
        item_parts = [model_name]
        if quality_name:
            item_parts.append(quality_name)
        
        full_name = ' | '.join(item_parts)
        if wear_name:
            full_name += f" ({wear_name})"
        if souvenir:
            full_name = "Souvenir " + full_name
        
        # Get prices (mock for now - integrate with real API)
        price_usd = 150.50  # Mock price
        
        # Convert to RUB
        try:
            rate_rub = self.bot.converter.get_rate('USD', 'RUB', user.telegram_id) or 95.0
            price_rub = price_usd * rate_rub
        except:
            price_rub = price_usd * 95.0
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        message = get_text(user.lang, 'cs2_item_details', 
                          name=full_name,
                          quality=quality_name or 'N/A',
                          wear=wear_name or 'N/A',
                          price_usd=price_usd,
                          price_rub=price_rub,
                          timestamp=timestamp)
        
        keyboard = [
            [InlineKeyboardButton('🔄 ' + get_text(user.lang, 'refresh'), callback_data=f'cs2_refresh')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data=f'cs2_wcat_{category}')],
            [InlineKeyboardButton('🏠 ' + get_text(user.lang, 'back') + ' (Menu)', callback_data='cs2_menu')]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Log metrics
        self.bot.metrics.log_cs2_query(user.telegram_id)
    
    async def show_category_items(self, query, user, category: str, page: int = 0):
        """Show items in a specific category with pagination."""
        items = self.cs2_service.get_items_by_category(category)
        
        if not items:
            await query.edit_message_text(
                get_text(user.lang, 'cs2_no_items'),
                parse_mode='Markdown'
            )
            return
        
        # Pagination settings
        items_per_page = 8
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(items))
        
        # Create keyboard with items on current page
        keyboard = []
        for item_id in items[start_idx:end_idx]:
            item_info = self.cs2_service.POPULAR_ITEMS[item_id]
            # Shorten name for button
            short_name = item_info['name'].split('|')[1].strip() if '|' in item_info['name'] else item_info['name']
            if len(short_name) > 20:
                short_name = short_name[:20] + '...'
            
            keyboard.append([InlineKeyboardButton(
                short_name,
                callback_data=f'cs2_item_{item_id}'
            )])
        
        # Add pagination buttons if needed
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(
                    '◀️ ' + get_text(user.lang, 'previous'),
                    callback_data=f'cs2_cat_{category}_page_{page-1}'
                ))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(
                    get_text(user.lang, 'next') + ' ▶️',
                    callback_data=f'cs2_cat_{category}_page_{page+1}'
                ))
            if nav_buttons:
                keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_menu')])
        
        category_name = get_text(user.lang, f'cs2_{category}')
        page_info = f" ({page+1}/{total_pages})" if total_pages > 1 else ""
        await query.edit_message_text(
            get_text(user.lang, 'cs2_select_item', category=category_name) + page_info,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_item_prices(self, query, user, item_id: str):
        """Show prices for a specific CS2 item."""
        await query.edit_message_text(
            f"💎 {get_text(user.lang, 'loading')}...\n\n{get_text(user.lang, 'cs2_fetching_prices')}",
            parse_mode='Markdown'
        )
        
        # Get item prices
        price_data = self.cs2_service.get_item_prices(item_id)
        
        if not price_data:
            await query.edit_message_text(
                get_text(user.lang, 'cs2_price_error', item=item_id),
                parse_mode='Markdown'
            )
            return
        
        # Format marketplace prices
        price_lines = []
        for marketplace, price in price_data['prices'].items():
            marketplace_name = marketplace.capitalize()
            if marketplace == price_data['min_marketplace']:
                price_lines.append(f"✅ **{marketplace_name}:** ${price:.2f} _← Best price!_")
            elif marketplace == price_data['max_marketplace']:
                price_lines.append(f"⚠️ **{marketplace_name}:** ${price:.2f}")
            else:
                price_lines.append(f"• **{marketplace_name}:** ${price:.2f}")
        
        prices_text = '\n'.join(price_lines)
        
        # Create detailed message
        message = (
            f"💎 **{price_data['name']}**\n"
            f"🏷️ Quality: {price_data['quality']}\n"
            f"📦 Category: {price_data['category']}\n\n"
            f"💰 **Prices:**\n"
            f"{prices_text}\n\n"
            f"📊 **Statistics:**\n"
            f"💵 Average: **${price_data['avg_price']:.2f}**\n"
            f"📈 Highest: ${price_data['max_price']:.2f} ({price_data['max_marketplace'].capitalize()})\n"
            f"📉 Lowest: ${price_data['min_price']:.2f} ({price_data['min_marketplace'].capitalize()})\n"
            f"📊 Spread: {price_data['spread_pct']:.2f}% (${price_data['spread_usd']:.2f})\n\n"
        )
        
        # Add recommendation
        if len(price_data['prices']) > 1:
            savings = price_data['max_price'] - price_data['min_price']
            message += (
                f"💡 **Recommendation:**\n"
                f"Buy on **{price_data['min_marketplace'].capitalize()}** "
                f"to save ${savings:.2f}!\n\n"
            )
        
        message += f"⏰ Updated: {datetime.fromisoformat(price_data['timestamp']).strftime('%H:%M')}"
        
        # Find category for back button
        item_info = self.cs2_service.POPULAR_ITEMS[item_id]
        category = item_info['category'].lower()
        if category == 'knife':
            category = 'knives'
        elif category == 'gloves':
            category = 'gloves'
        elif category == 'rifle':
            category = 'rifles'
        elif category == 'sniper':
            category = 'snipers'
        elif category == 'pistol':
            category = 'pistols'
        elif category == 'smg':
            category = 'smgs'
        
        keyboard = [
            [InlineKeyboardButton(
                '🔄 ' + get_text(user.lang, 'refresh'),
                callback_data=f'cs2_item_{item_id}'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data=f'cs2_cat_{category}'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Log metrics
        self.bot.metrics.log_cs2_query(user.telegram_id)
    
    async def start_search(self, query, user):
        """Start CS2 item search."""
        # Set user state to awaiting search
        self.bot.temp_storage[user.telegram_id] = {
            'state': 'awaiting_cs2_search'
        }
        
        keyboard = [[InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_menu')]]
        
        await query.edit_message_text(
            get_text(user.lang, 'cs2_search_prompt'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE, search_query: str):
        """Handle CS2 item search query."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        # Search items
        results = self.cs2_service.search_items(search_query, limit=10)
        
        if not results:
            keyboard = [[InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_menu')]]
            await update.message.reply_text(
                get_text(user.lang, 'cs2_search_no_results', query=search_query),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        # Display results
        keyboard = []
        for item_id in results:
            item_info = self.cs2_service.POPULAR_ITEMS[item_id]
            keyboard.append([InlineKeyboardButton(
                item_info['name'],
                callback_data=f'cs2_item_{item_id}'
            )])
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_menu')])
        
        await update.message.reply_text(
            get_text(user.lang, 'cs2_search_results', query=search_query, count=len(results)),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_cs2_callback(self, query, user, data: str):
        """Handle CS2-related callbacks with full hierarchy support."""
        if data == 'cs2_menu':
            # Return to main CS2 menu
            class FakeUpdate:
                callback_query = query
                effective_user = query.from_user
                message = query.message
            await self.show_cs2_menu(FakeUpdate(), None)
        
        elif data == 'cs2_search':
            await self.start_search(query, user)
        
        # Level 1: Main category selection
        elif data == 'cs2_main_weapons':
            await self.show_weapon_categories(query, user)
        
        elif data == 'cs2_main_other':
            # Other items (stickers, agents, patches) - simplified for now
            await query.edit_message_text(
                "🎨 Other items coming soon!\n\nStickers, Agents, and Patches will be available in future updates.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='cs2_menu')]]),
                parse_mode='Markdown'
            )
        
        # Level 2: Weapon category selection (with pagination support)
        elif data.startswith('cs2_wcat_'):
            parts = data.replace('cs2_wcat_', '').split('_p')
            category = parts[0]
            page = int(parts[1]) if len(parts) > 1 else 0
            await self.show_weapon_models(query, user, category, page)
        
        # Level 3: Model selection
        elif data.startswith('cs2_model_'):
            parts = data.replace('cs2_model_', '').split('_', 1)
            if len(parts) == 2:
                category, model = parts
                await self.show_souvenir_question(query, user, category, model)
        
        # Level 4: Souvenir selection
        elif data.startswith('cs2_souv_'):
            parts = data.replace('cs2_souv_', '').split('_')
            if len(parts) >= 3:
                category, model = parts[0], parts[1]
                souvenir = (parts[-1] == 'yes')
                await self.show_quality_selection(query, user, category, model, souvenir)
        
        # Level 5: Quality selection
        elif data.startswith('cs2_qual_'):
            parts = data.replace('cs2_qual_', '').split('_')
            if len(parts) >= 3:
                category, model, quality = parts[0], parts[1], parts[2]
                state = self._get_user_state(user.telegram_id)
                souvenir = state.get('souvenir', False)
                await self.show_wear_selection(query, user, category, model, souvenir, quality)
        
        # Level 6: Wear selection
        elif data.startswith('cs2_wear_'):
            parts = data.replace('cs2_wear_', '').split('_')
            if len(parts) >= 3:
                category, model, wear = parts[0], parts[1], parts[2]
                state = self._get_user_state(user.telegram_id)
                souvenir = state.get('souvenir', False)
                quality = state.get('quality', 'default')
                await self.show_final_item(query, user, category, model, souvenir, quality, wear)
        
        # Refresh current item
        elif data == 'cs2_refresh':
            state = self._get_user_state(user.telegram_id)
            if all(k in state for k in ['category', 'model', 'quality']):
                await self.show_final_item(query, user, 
                                          state['category'], 
                                          state['model'], 
                                          state.get('souvenir', False),
                                          state['quality'],
                                          state.get('wear', 'fn'))
        
        # Legacy support for old system
        elif data.startswith('cs2_cat_'):
            parts = data.replace('cs2_cat_', '').split('_page_')
            category = parts[0]
            page = int(parts[1]) if len(parts) > 1 else 0
            await self.show_category_items(query, user, category, page)
        
        elif data.startswith('cs2_item_'):
            item_id = data.replace('cs2_item_', '')
            await self.show_item_prices(query, user, item_id)
