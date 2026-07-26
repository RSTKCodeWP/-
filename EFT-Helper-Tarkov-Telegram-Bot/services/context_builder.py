"""Context builder for AI assistant - prepares data from tarkov.dev for LLM."""
import logging
from typing import Dict, List, Optional
from api_clients import TarkovAPIClient
from database import Database

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds contextual data for LLM prompts."""
    
    def __init__(self, api_client: TarkovAPIClient, db: Database):
        self.api = api_client
        self.db = db
    
    async def build_weapon_context(self, weapon_id: Optional[str] = None, language: str = "ru") -> str:
        """
        Build context about weapons for LLM.
        
        Args:
            weapon_id: Specific weapon ID to focus on (optional)
            language: Language for names (ru/en)
            
        Returns:
            Formatted string with weapon information
        """
        if weapon_id:
            weapon_data = await self.api.get_weapon_details(weapon_id)
            if not weapon_data:
                return ""
            
            return self._format_weapon_details(weapon_data, language)
        
        # Get all weapons for general context (limited to avoid token overflow)
        weapons = await self.api.get_all_weapons(lang=language)
        
        # Group by category and get top weapons per category
        categories = {}
        for weapon in weapons[:50]:  # Limit to 50 weapons
            cat_name = weapon.get("category", {}).get("name", "Unknown")
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(weapon)
        
        context = "Available weapons by category:\n\n"
        for cat, weaps in categories.items():
            context += f"**{cat}:**\n"
            for w in weaps[:5]:  # Top 5 per category
                price = w.get("avg24hPrice", 0) or 0
                context += f"  - {w.get('name', 'Unknown')} (Price: {price:,} ₽)\n"
            context += "\n"
        
        return context
    
    async def build_modules_context(self, weapon_id: str, language: str = "ru") -> str:
        """
        Build context about available modules for a weapon.
        
        Args:
            weapon_id: Weapon ID to get modules for
            language: Language for names (ru/en)
            
        Returns:
            Formatted string with module information
        """
        weapon_data = await self.api.get_weapon_details(weapon_id)
        if not weapon_data:
            return ""
        
        props = weapon_data.get("properties", {})
        slots = props.get("slots", [])
        
        if not slots:
            return "No modification slots available for this weapon."
        
        context = f"Modification slots for {weapon_data.get('name', 'weapon')}:\n\n"
        
        for slot in slots:
            slot_name = slot.get("name", "Unknown slot")
            required = slot.get("required", False)
            
            context += f"**{slot_name}** (Required: {required}):\n"
            
            filters = slot.get("filters", {})
            allowed_items = filters.get("allowedItems", [])
            
            # List available modules with compatibility info (limit to avoid token overflow)
            for item in allowed_items[:15]:  # Top 15 per slot for better variety
                item_name = item.get("name", "Unknown")
                item_id = item.get("id", "")
                item_price = item.get("avg24hPrice", 0) or 0
                
                # Get mod properties
                item_props = item.get("properties", {})
                ergo = item_props.get("ergonomics", 0)
                recoil_mod = item_props.get("recoilModifier", 0)
                
                # Get trader info with localization
                buy_for = item.get("buyFor", [])
                
                # Trader names localization
                trader_names_ru = {
                    "Prapor": "Прапор",
                    "Therapist": "Терапевт",
                    "Fence": "Скупщик",
                    "Skier": "Лыжник",
                    "Peacekeeper": "Миротворец",
                    "Mechanic": "Механик",
                    "Ragman": "Барахольщик",
                    "Jaeger": "Егерь",
                    "Lightkeeper": "Смотритель",
                    "Flea Market": "Барахолка"
                }
                
                trader_info = "Барахолка" if language == "ru" else "Flea"
                for offer in buy_for:
                    vendor = offer.get("vendor", {})
                    vendor_name = vendor.get("name", "")
                    if vendor_name != "Flea Market":
                        requirements = offer.get("requirements", [])
                        level = next((r.get("value") for r in requirements if r.get("type") == "loyaltyLevel"), 1)
                        # Localize trader name
                        localized_name = trader_names_ru.get(vendor_name, vendor_name) if language == "ru" else vendor_name
                        trader_info = f"{localized_name} LL{level}"
                        break
                
                stats = []
                if ergo != 0:
                    stats.append(f"Ergo: {ergo:+d}")
                if recoil_mod != 0:
                    stats.append(f"Recoil: {recoil_mod:+d}")
                
                stats_str = f" [{', '.join(stats)}]" if stats else ""
                
                context += f"  - {item_name} ({item_price:,} ₽, {trader_info}){stats_str}\n"
            
            if len(allowed_items) > 15:
                context += f"  ... and {len(allowed_items) - 15} more compatible options\n"
            
            context += "\n"
        
        return context
    
    async def build_quest_context(self, quest_name: Optional[str] = None, language: str = "ru") -> str:
        """
        Build context about quests (all quests from tarkov.dev API).
        
        Args:
            quest_name: Specific quest to focus on (optional)
            language: Language for names (ru/en)
            
        Returns:
            Formatted string with quest information
        """
        quests = await self.api.get_all_tasks(lang=language)
        
        if not quests:
            return "No quest information available."
        
        if quest_name:
            # Find specific quest
            quest_lower = quest_name.lower()
            matching_quests = [
                q for q in quests
                if quest_lower in q.get("name", "").lower() or
                   quest_lower in q.get("normalizedName", "").lower()
            ]
            
            if matching_quests:
                return self._format_quest_details(matching_quests[0], language)
            return f"Quest '{quest_name}' not found."
        
        # Return summary of all quests grouped by trader
        context = "Available quests from tarkov.dev API:\n\n"
        
        # Group by trader
        trader_quests = {}
        for quest in quests:
            trader = quest.get("trader", {}).get("name", "Unknown")
            if trader not in trader_quests:
                trader_quests[trader] = []
            trader_quests[trader].append(quest)
        
        # Show quests per trader (limit output)
        for trader, trader_quest_list in list(trader_quests.items())[:10]:  # Top 10 traders
            context += f"**{trader}** ({len(trader_quest_list)} quests):\n"
            for quest in trader_quest_list[:5]:  # First 5 quests per trader
                quest_name = quest.get("name", "Unknown")
                level = quest.get("minPlayerLevel", 0)
                context += f"  - {quest_name} (Level {level})\n"
            if len(trader_quest_list) > 5:
                context += f"  ... and {len(trader_quest_list) - 5} more\n"
            context += "\n"
        
        return context
    
    async def build_user_context(self, user_id: int) -> str:
        """
        Build context about user preferences and trader levels.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Formatted string with user information
        """
        user = await self.db.get_user(user_id)
        if not user:
            return "New user (no preferences set)."
        
        context = f"User settings:\n"
        context += f"  - Language: {user.language}\n"
        
        if user.trader_levels:
            context += f"  - Trader Loyalty Levels:\n"
            for trader, level in user.trader_levels.items():
                context += f"    • {trader.capitalize()}: Level {level}\n"
        else:
            context += f"  - Trader levels: Not configured\n"
        
        return context
    
    async def build_market_context(self, language: str = "en") -> str:
        """
        Build context about market/economy.
        
        Args:
            language: Language for names (ru/en)
            
        Returns:
            Formatted string with market information
        """
        # This is lightweight - just general info
        return "Market information:\n  - Prices are from Flea Market (24h average)\n  - Trader prices may be lower with loyalty levels\n  - All prices in Rubles (₽)\n"
    
    async def build_quest_info_context(self, quest_name_or_id: str, language: str = "ru") -> str:
        """
        Build detailed quest information context for general queries (v5.3).
        Not just for builds, but for answering quest-related questions.
        
        Args:
            quest_name_or_id: Quest name or ID
            language: Language for localization
            
        Returns:
            Formatted quest info including objectives, rewards, requirements
        """
        # Try to find quest in all tasks
        tasks = await self.api.get_all_tasks(lang=language)
        
        quest = None
        for task in tasks:
            if (task.get("name", "").lower() == quest_name_or_id.lower() or 
                task.get("id") == quest_name_or_id or
                quest_name_or_id.lower() in task.get("name", "").lower()):
                quest = task
                break
        
        if not quest:
            return f"Quest '{quest_name_or_id}' not found."
        
        # Format comprehensive quest info
        name = quest.get("name", "Unknown")
        trader = quest.get("trader", {}).get("name", "Unknown")
        min_level = quest.get("minPlayerLevel", 0)
        
        # Localized labels
        trader_label = "Торговец" if language == "ru" else "Trader"
        level_label = "Требуемый уровень" if language == "ru" else "Required Level"
        objectives_label = "Цели" if language == "ru" else "Objectives"
        
        context = f"# {name}\n\n"
        context += f"**{trader_label}:** {trader}\n"
        context += f"**{level_label}:** {min_level}\n\n"
        
        # Objectives
        objectives = quest.get("objectives", [])
        if objectives:
            context += f"## {objectives_label}:\n"
            for i, obj in enumerate(objectives, 1):
                obj_type = obj.get("type", "")
                desc = obj.get("description", "No description")
                optional = obj.get("optional", False)
                opt_text = " (Optional)" if optional else ""
                
                context += f"{i}. {desc}{opt_text}\n"
                
                # Add specific details for build objectives
                if "buildWeapon" in obj_type:
                    item = obj.get("item", {})
                    if item:
                        base_weapon_label = "Базовое оружие" if language == "ru" else "Base weapon"
                        context += f"   {base_weapon_label}: {item.get('name', 'Unknown')}\n"
                    
                    # Required modules
                    contains_all = obj.get("containsAll", [])
                    if contains_all:
                        must_include_all = "Обязательно включить ВСЕ" if language == "ru" else "Must include ALL"
                        context += f"   {must_include_all}:\n"
                        for req in contains_all:
                            context += f"     - {req.get('name', 'Unknown')}\n"
                    
                    contains_one = obj.get("containsOne", [])
                    if contains_one:
                        must_include_one = "Обязательно включить ОДИН из" if language == "ru" else "Must include ONE of"
                        context += f"   {must_include_one}:\n"
                        for req in contains_one:
                            context += f"     - {req.get('name', 'Unknown')}\n"
                    
                    # Stat requirements
                    attributes = obj.get("attributes", [])
                    if attributes:
                        req_stats_label = "Требуемые характеристики" if language == "ru" else "Required stats"
                        context += f"   {req_stats_label}:\n"
                        
                        # Attribute name translations
                        attr_translations = {
                            "ergonomics": "Эргономика",
                            "recoilVertical": "Вертикальная отдача",
                            "recoilHorizontal": "Горизонтальная отдача",
                            "weight": "Вес",
                            "height": "Высота",
                            "width": "Ширина",
                            "effectiveDistance": "Эффективная дальность",
                            "sightingRange": "Дальность прицеливания",
                            "centerOfImpact": "Точка прицеливания",
                            "durability": "Прочность",
                            "magazineCapacity": "Емкость магазина",
                            "convergence": "Сходимость",
                            "recoilAngle": "Угол отдачи",
                            "recoilDispersion": "Разброс отдачи",
                            "cameraRecoil": "Отдача камеры",
                            "accuracyModifier": "Модификатор точности",
                            "velocity": "Скорость пули"
                        }
                        
                        for attr in attributes:
                            attr_name = attr.get("name", "")
                            req = attr.get("requirement", {})
                            compare = req.get("compareMethod", "")
                            value = req.get("value", "")
                            
                            if attr_name and value:
                                # Translate attribute name if Russian
                                if language == "ru":
                                    attr_name_lower = attr_name.lower()
                                    localized_attr = attr_translations.get(attr_name_lower, attr_name)
                                else:
                                    localized_attr = attr_name
                                
                                # Translate comparison operators
                                compare_translations = {
                                    ">=": "≥" if language == "en" else "не менее",
                                    "<=": "≤" if language == "en" else "не более",
                                    ">": ">" if language == "en" else "больше",
                                    "<": "<" if language == "en" else "меньше",
                                    "=": "=" if language == "en" else "ровно"
                                }
                                localized_compare = compare_translations.get(compare, compare)
                                
                                context += f"     - {localized_attr}: {localized_compare} {value}\n"
            context += "\n"
        
        # Rewards
        rewards = quest.get("finishRewards", {})
        if rewards:
            rewards_label = "Награды" if language == "ru" else "Rewards"
            context += f"## {rewards_label}:\n"
            
            # Experience
            exp = rewards.get("traderStanding", [])
            if exp:
                for standing in exp:
                    trader_name = standing.get("trader", {}).get("name", "Unknown")
                    value = standing.get("standing", 0)
                    context += f"  - {trader_name}: +{value} reputation\n"
            
            # Items
            items = rewards.get("items", [])
            if items:
                items_label = "  Предметы" if language == "ru" else "  Items"
                context += f"{items_label}:\n"
                for item in items[:5]:  # Limit to 5 items
                    item_name = item.get("item", {}).get("name", "Unknown")
                    count = item.get("count", 1)
                    context += f"    - {item_name} x{count}\n"
            
            context += "\n"
        
        return context
    
    def _format_weapon_details(self, weapon_data: Dict, language: str) -> str:
        """Format weapon details for context with all available characteristics."""
        name = weapon_data.get("name", "Unknown")
        props = weapon_data.get("properties", {})
        
        details = f"**{name}**\n"
        details += f"Price: {weapon_data.get('avg24hPrice', 0):,} ₽\n"
        
        if props:
            # Core stats
            if props.get("caliber"):
                details += f"Caliber: {props['caliber']}\n"
            if props.get("ergonomics") is not None:
                details += f"Ergonomics: {props['ergonomics']}\n"
            if props.get("recoilVertical") is not None:
                details += f"Vertical Recoil: {props['recoilVertical']}\n"
            if props.get("recoilHorizontal") is not None:
                details += f"Horizontal Recoil: {props['recoilHorizontal']}\n"
            if props.get("fireRate"):
                details += f"Fire Rate: {props['fireRate']} RPM\n"
            
            # Additional characteristics
            if props.get("defaultAmmo"):
                ammo = props['defaultAmmo']
                details += f"Default Ammo: {ammo.get('name', 'Unknown')}\n"
            if props.get("effectiveDistance"):
                details += f"Effective Distance: {props['effectiveDistance']}m\n"
            if props.get("sightingRange"):
                details += f"Sighting Range: {props['sightingRange']}m\n"
            if props.get("convergence") is not None:
                details += f"Convergence: {props['convergence']}\n"
            if props.get("recoilAngle") is not None:
                details += f"Recoil Angle: {props['recoilAngle']}°\n"
            if props.get("recoilDispersion") is not None:
                details += f"Recoil Dispersion: {props['recoilDispersion']}\n"
            if props.get("cameraRecoil") is not None:
                details += f"Camera Recoil: {props['cameraRecoil']}\n"
        
        return details
    
    def _format_quest_details(self, quest: Dict, language: str) -> str:
        """Format quest details for context with exact required items."""
        name = quest.get("name", "Unknown")
        trader = quest.get("trader", {}).get("name", "Unknown")
        level = quest.get("minPlayerLevel", 0)
        
        context = f"**{name}**\n"
        context += f"  - Trader: {trader}\n"
        context += f"  - Required Level: {level}\n\n"
        
        objectives = quest.get("objectives", [])
        
        # Look for buildWeapon objectives
        build_objectives = [obj for obj in objectives if obj.get("type") == "buildWeapon"]
        
        if build_objectives:
            context += f"BUILD REQUIREMENTS (MUST BE EXACTLY FOLLOWED):\n\n"
            
            for build_obj in build_objectives:
                # Get target weapon
                item = build_obj.get("item", {})
                if item:
                    context += f"Base Weapon: {item.get('name', 'Unknown')}\n\n"
                
                # Get REQUIRED modules (containsAll or containsOne)
                contains_all = build_obj.get("containsAll", [])
                contains_one = build_obj.get("containsOne", [])
                
                if contains_all:
                    context += f"REQUIRED MODULES (MUST INCLUDE ALL):\n"
                    for req_item in contains_all:
                        item_name = req_item.get("name", "Unknown")
                        context += f"  - {item_name} [REQUIRED]\n"
                    context += "\n"
                
                if contains_one:
                    context += f"REQUIRED MODULES (MUST INCLUDE AT LEAST ONE):\n"
                    for req_item in contains_one:
                        item_name = req_item.get("name", "Unknown")
                        context += f"  - {item_name} [CHOOSE ONE]\n"
                    context += "\n"
                
                # Get attributes (stat requirements)
                attributes = build_obj.get("attributes", [])
                if attributes:
                    context += f"STAT REQUIREMENTS:\n"
                    for attr in attributes:
                        attr_name = attr.get("name", "")
                        req = attr.get("requirement", {})
                        compare = req.get("compareMethod", "")
                        value = req.get("value", "")
                        
                        if attr_name and value:
                            # Translate comparison method
                            compare_text = {
                                ">=": "at least",
                                "<=": "at most",
                                ">": "greater than",
                                "<": "less than",
                                "=": "exactly"
                            }.get(compare, compare)
                            context += f"  - {attr_name}: {compare_text} {value}\n"
                    context += "\n"
        else:
            context += f"Objectives:\n"
            for i, obj in enumerate(objectives, 1):
                obj_desc = obj.get("description", "No description")
                optional = obj.get("optional", False)
                opt_marker = " (Optional)" if optional else ""
                context += f"{i}. {obj_desc}{opt_marker}\n"
        
        return context
