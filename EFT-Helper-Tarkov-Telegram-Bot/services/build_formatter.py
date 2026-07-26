"""
Build formatting service for EFT Helper v2.0
Formats weapon builds with complete characteristics, cost, and trader loyalty info
"""
from typing import Dict, List, Optional, Tuple
from database.models import Weapon, Module, Build, User


class BuildFormatter:
    """Service for formatting weapon builds according to v2.0 specifications."""
    
    def __init__(self, db):
        """Initialize with database connection."""
        self.db = db
    
    async def format_build_display(
        self, 
        build: Build, 
        user: User,
        include_modules: bool = True
    ) -> str:
        """
        Format a complete build for display according to v2.0 specification.
        
        Expected format:
        🔫 Базовое оружие: [название]
        🔧 Модули:
          - [Слот]: [Модуль]
          - ...
        📊 Характеристики:
          - Эргономика: X
          - Отдача: Y
          - Скорость пули: Z м/с
        💰 Стоимость: N руб.
        🛒 Доступно при лояльности: [Торговец] Lvl X
        """
        language = user.language
        
        # Get weapon data
        weapon = await self.db.get_weapon_by_id(build.weapon_id)
        if not weapon:
            return "❌ Оружие не найдено" if language == "ru" else "❌ Weapon not found"
        
        # Start building the text
        weapon_name = weapon.name_ru if language == "ru" else weapon.name_en
        text = f"🔫 **Базовое оружие**: {weapon_name}\n" if language == "ru" else f"🔫 **Base Weapon**: {weapon_name}\n"
        
        total_cost = weapon.base_price or weapon.flea_price or 0
        min_loyalty_level = 1
        required_trader = None
        
        # Add modules if requested and available
        if include_modules and build.modules:
            modules = await self.db.get_modules_by_ids(build.modules)
            if modules:
                text += "\n🔧 **Модули:**\n" if language == "ru" else "\n🔧 **Modules:**\n"
                
                for module in modules:
                    module_name = module.name_ru if language == "ru" else module.name_en
                    text += f"  - **{module.slot_type}**: {module_name}\n"
                    
                    # Add to total cost
                    module_price = module.flea_price or module.price or 0
                    total_cost += module_price
                    
                    # Track highest loyalty requirement
                    if module.loyalty_level > min_loyalty_level:
                        min_loyalty_level = module.loyalty_level
                        required_trader = module.trader
        
        # Add weapon characteristics
        text += "\n📊 **Характеристики:**\n" if language == "ru" else "\n📊 **Characteristics:**\n"
        
        if weapon.caliber:
            text += f"  - Калибр: {weapon.caliber}\n" if language == "ru" else f"  - Caliber: {weapon.caliber}\n"
        
        if weapon.ergonomics:
            text += f"  - Эргономика: {weapon.ergonomics}\n" if language == "ru" else f"  - Ergonomics: {weapon.ergonomics}\n"
        
        if weapon.recoil_vertical:
            text += f"  - Отдача (верт): {weapon.recoil_vertical}\n" if language == "ru" else f"  - Recoil (vert): {weapon.recoil_vertical}\n"
        
        if weapon.recoil_horizontal:
            text += f"  - Отдача (гор): {weapon.recoil_horizontal}\n" if language == "ru" else f"  - Recoil (hor): {weapon.recoil_horizontal}\n"
        
        if weapon.fire_rate:
            text += f"  - Скорострельность: {weapon.fire_rate} в/м\n" if language == "ru" else f"  - Fire Rate: {weapon.fire_rate} RPM\n"
        
        # Add velocity if available (new field)
        if hasattr(weapon, 'velocity') and weapon.velocity:
            text += f"  - Скорость пули: {weapon.velocity} м/с\n" if language == "ru" else f"  - Velocity: {weapon.velocity} m/s\n"
        
        # Add cost information
        text += f"\n💰 **Стоимость**: {total_cost:,} ₽\n".replace(",", " ") if language == "ru" else f"\n💰 **Cost**: {total_cost:,} ₽\n".replace(",", " ")
        
        # Add trader loyalty requirement
        if min_loyalty_level > 1 and required_trader:
            text += f"🛒 **Доступно при лояльности**: {required_trader} Lvl {min_loyalty_level}\n" if language == "ru" else f"🛒 **Available at loyalty**: {required_trader} Lvl {min_loyalty_level}\n"
        
        return text
    
    async def format_weapon_search_result(
        self, 
        weapon: Weapon, 
        language: str = "ru"
    ) -> str:
        """Format weapon search result with basic info."""
        weapon_name = weapon.name_ru if language == "ru" else weapon.name_en
        
        text = f"🔫 **{weapon_name}**\n"
        
        if weapon.caliber:
            text += f"📦 {weapon.caliber}"
        
        if weapon.tier_rating:
            text += f" | 🏆 {weapon.tier_rating.value}-Tier"
        
        if weapon.category:
            category_name = self._get_category_name(weapon.category, language)
            text += f" | 📂 {category_name}"
        
        text += "\n"
        
        # Basic characteristics
        if weapon.ergonomics or weapon.recoil_vertical:
            text += "📊 "
            if weapon.ergonomics:
                text += f"Эрг: {weapon.ergonomics}" if language == "ru" else f"Erg: {weapon.ergonomics}"
            if weapon.recoil_vertical:
                if weapon.ergonomics:
                    text += " | "
                text += f"Отдача: {weapon.recoil_vertical}" if language == "ru" else f"Recoil: {weapon.recoil_vertical}"
            text += "\n"
        
        # Price
        price = weapon.flea_price or weapon.base_price or 0
        if price > 0:
            text += f"💰 {price:,} ₽\n".replace(",", " ")
        
        return text
    
    def _get_category_name(self, category, language: str) -> str:
        """Get localized category name."""
        category_names = {
            "assault_rifle": {"ru": "Штурмовая винтовка", "en": "Assault Rifle"},
            "smg": {"ru": "Пистолет-пулемёт", "en": "SMG"},
            "sniper": {"ru": "Снайперская винтовка", "en": "Sniper Rifle"},
            "dmr": {"ru": "Винтовка DMR", "en": "DMR"},
            "shotgun": {"ru": "Дробовик", "en": "Shotgun"},
            "pistol": {"ru": "Пистолет", "en": "Pistol"},
            "lmg": {"ru": "Пулемёт", "en": "LMG"}
        }
        
        return category_names.get(category.value, {}).get(language, category.value)
    
    async def format_build_list(
        self, 
        builds: List[Build], 
        user: User,
        title: str = None
    ) -> str:
        """Format a list of builds for display."""
        language = user.language
        
        if not builds:
            return "❌ Сборки не найдены" if language == "ru" else "❌ No builds found"
        
        text = ""
        if title:
            text += f"📋 **{title}**\n\n"
        
        for i, build in enumerate(builds[:10], 1):  # Limit to 10 builds
            weapon = await self.db.get_weapon_by_id(build.weapon_id)
            if weapon:
                weapon_name = weapon.name_ru if language == "ru" else weapon.name_en
                build_name = build.name_ru if language == "ru" else build.name_en
                
                if build_name and build_name != weapon_name:
                    text += f"{i}. **{build_name}** ({weapon_name})\n"
                else:
                    text += f"{i}. **{weapon_name}**\n"
                
                # Add quest name if it's a quest build
                if build.category.value == "quest" and build.quest_name_ru:
                    quest_name = build.quest_name_ru if language == "ru" else build.quest_name_en
                    text += f"   📜 {quest_name}\n"
                
                # Add basic info
                if weapon.caliber:
                    text += f"   📦 {weapon.caliber}"
                
                if build.total_cost > 0:
                    text += f" | 💰 {build.total_cost:,} ₽".replace(",", " ")
                
                text += "\n\n"
        
        return text
    
    async def format_random_build_result(
        self, 
        build_data: Dict, 
        language: str = "ru"
    ) -> str:
        """Format random build result from API data."""
        weapon = build_data.get("weapon", {})
        mods = build_data.get("mods", [])
        
        # Header
        weapon_name = weapon.get("name", "Unknown Weapon")
        text = f"🎲 **Случайная сборка**\n\n" if language == "ru" else f"🎲 **Random Build**\n\n"
        text += f"🔫 **Базовое оружие**: {weapon_name}\n" if language == "ru" else f"🔫 **Base Weapon**: {weapon_name}\n"
        
        # Modules
        if mods:
            text += "\n🔧 **Модули:**\n" if language == "ru" else "\n🔧 **Modules:**\n"
            total_mod_cost = 0
            
            for mod_data in mods:
                slot_name = mod_data.get("slot_name", "Unknown Slot")
                mod = mod_data.get("mod", {})
                mod_name = mod.get("shortName") or mod.get("name", "Unknown")
                mod_price = mod.get("avg24hPrice") or 0
                
                total_mod_cost += mod_price
                text += f"  - **{slot_name}**: {mod_name}\n"
        
        # Characteristics
        properties = weapon.get("properties", {})
        if properties:
            text += "\n📊 **Характеристики:**\n" if language == "ru" else "\n📊 **Characteristics:**\n"
            
            for prop_key, prop_value in [
                ("caliber", "Калибр" if language == "ru" else "Caliber"),
                ("ergonomics", "Эргономика" if language == "ru" else "Ergonomics"),
                ("recoilVertical", "Отдача (верт)" if language == "ru" else "Recoil (vert)"),
                ("fireRate", "Скорострельность" if language == "ru" else "Fire Rate"),
                ("velocity", "Скорость пули" if language == "ru" else "Velocity")
            ]:
                if prop_key in properties and properties[prop_key]:
                    value = properties[prop_key]
                    if prop_key == "fireRate":
                        value = f"{value} в/м" if language == "ru" else f"{value} RPM"
                    elif prop_key == "velocity":
                        value = f"{value} м/с" if language == "ru" else f"{value} m/s"
                    
                    text += f"  - {prop_value}: {value}\n"
        
        # Cost
        weapon_price = weapon.get("avg24hPrice", 0) or 0
        total_cost = weapon_price + (total_mod_cost if mods else 0)
        
        text += f"\n💰 **Стоимость**: {total_cost:,} ₽\n".replace(",", " ") if language == "ru" else f"\n💰 **Cost**: {total_cost:,} ₽\n".replace(",", " ")
        
        return text
