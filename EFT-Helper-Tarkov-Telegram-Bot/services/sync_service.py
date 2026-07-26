"""Service for synchronizing data from tarkov.dev API to database."""
import logging
import aiosqlite
from typing import Dict, List, Optional
from database import Database, WeaponCategory
from api_clients import TarkovAPIClient

logger = logging.getLogger(__name__)


# Map tarkov.dev category names to internal categories
CATEGORY_MAPPING = {
    "Handgun": WeaponCategory.PISTOL,
    "SMG": WeaponCategory.SMG,
    "Assault rifle": WeaponCategory.ASSAULT_RIFLE,
    "Assault carbine": WeaponCategory.ASSAULT_RIFLE,
    "Marksman rifle": WeaponCategory.DMR,
    "Sniper rifle": WeaponCategory.SNIPER,
    "Shotgun": WeaponCategory.SHOTGUN,
    "Machinegun": WeaponCategory.LMG,
}

# Tier ratings (can be customized)
TIER_RATINGS = {
    # S-Tier weapons
    "M4A1": "S", "HK 416A5": "S", "SCAR-L": "S", "MCX": "S", "SVD": "S",
    # A-Tier weapons
    "AK-74N": "A", "AK-74M": "A", "AKM": "A", "MP5": "A", "MPX": "A", "SR-25": "A",
    # B-Tier weapons
    "AK-105": "B", "SKS": "B", "MP-153": "B", "Saiga-12": "B", "PP-19-01": "B",
    # C-Tier weapons
    "Mosin": "C", "VPO-215": "C", "TOZ-106": "C",
}

TRADER_EMOJIS = {
    "prapor": "🔫", "therapist": "💊", "fence": "🗑️", "skier": "💼",
    "peacekeeper": "🤝", "mechanic": "🔧", "ragman": "👕", "jaeger": "🌲"
}


class SyncService:
    """Service for syncing data from tarkov.dev API to local database."""
    
    def __init__(self, db: Database, api_client: TarkovAPIClient):
        self.db = db
        self.api = api_client
    
    async def sync_traders(self) -> int:
        """Sync traders from API to database."""
        logger.info("Syncing traders from tarkov.dev API...")
        
        traders_data = await self.api.get_all_traders()
        if not traders_data:
            logger.warning("No traders data received from API")
            return 0
        
        async with aiosqlite.connect(self.db.db_path) as conn:
            added_count = 0
            for trader_data in traders_data:
                name = trader_data.get("name", "Unknown")
                normalized_name = trader_data.get("normalizedName", name.lower())
                emoji = TRADER_EMOJIS.get(normalized_name, "💼")
                
                try:
                    await conn.execute(
                        "INSERT OR IGNORE INTO traders (name, emoji) VALUES (?, ?)",
                        (name, emoji)
                    )
                    added_count += 1
                except Exception as e:
                    logger.error(f"Error adding trader {name}: {e}")
            
            await conn.commit()
            logger.info(f"Synced {added_count} traders")
            return added_count
    
    async def sync_weapons(self) -> int:
        """Sync weapons from API to database with full localization."""
        logger.info("Syncing weapons from tarkov.dev API with localization...")
        
        # Get weapons in both languages
        weapons_data_en = await self.api.get_all_weapons(lang="en")
        weapons_data_ru = await self.api.get_all_weapons(lang="ru")
        
        if not weapons_data_en:
            logger.warning("No weapons data received from API")
            return 0
        
        # Create mapping of weapon IDs to Russian names
        ru_names = {}
        for weapon in weapons_data_ru:
            weapon_id = weapon.get("id")
            if weapon_id:
                ru_names[weapon_id] = weapon.get("shortName", weapon.get("name", "Unknown"))
        
        async with aiosqlite.connect(self.db.db_path) as conn:
            added_count = 0
            for weapon_data in weapons_data_en:
                weapon_id = weapon_data.get("id")
                name_en = weapon_data.get("shortName", weapon_data.get("name", "Unknown"))
                name_ru = ru_names.get(weapon_id, name_en)  # Fallback to English if no Russian
                
                # Determine category from category.name field
                category = WeaponCategory.ASSAULT_RIFLE  # Default
                category_data = weapon_data.get("category", {})
                category_name = category_data.get("name", "")
                if category_name in CATEGORY_MAPPING:
                    category = CATEGORY_MAPPING[category_name]
                
                tier_rating = TIER_RATINGS.get(name_en, None)
                price = weapon_data.get("avg24hPrice", 0) or 0
                flea_price = weapon_data.get("avg24hPrice", None)
                
                # Extract properties
                properties = weapon_data.get("properties", {})
                caliber = properties.get("caliber", None)
                ergonomics = properties.get("ergonomics", None)
                recoil_vertical = properties.get("recoilVertical", None)
                recoil_horizontal = properties.get("recoilHorizontal", None)
                fire_rate = properties.get("fireRate", None)
                velocity = properties.get("velocity", None)
                default_width = properties.get("defaultWidth", None)
                default_height = properties.get("defaultHeight", None)
                
                # Calculate effective range based on caliber
                effective_range = self._calculate_effective_range(caliber)
                
                try:
                    await conn.execute(
                        """INSERT OR REPLACE INTO weapons 
                        (name_ru, name_en, category, tier_rating, base_price, flea_price, tarkov_id,
                         caliber, ergonomics, recoil_vertical, recoil_horizontal, fire_rate, 
                         effective_range, velocity, default_width, default_height) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (name_ru, name_en, category.value, tier_rating, price, flea_price, weapon_id,
                         caliber, ergonomics, recoil_vertical, recoil_horizontal, fire_rate, 
                         effective_range, velocity, default_width, default_height)
                    )
                    added_count += 1
                except Exception as e:
                    logger.error(f"Error adding weapon {name_en}: {e}")
            
            await conn.commit()
            logger.info(f"Synced {added_count} weapons with localization")
            return added_count
    
    async def sync_modules(self) -> int:
        """Sync weapon modules/attachments from API to database with localization."""
        logger.info("Syncing modules from tarkov.dev API with localization...")
        
        # Get modules in both languages
        mods_data_en = await self.api.get_all_mods(lang="en")
        mods_data_ru = await self.api.get_all_mods(lang="ru")
        
        if not mods_data_en:
            logger.warning("No mods data received from API")
            return 0
        
        # Create mapping of module IDs to Russian names
        ru_names = {}
        for mod in mods_data_ru:
            mod_id = mod.get("id")
            if mod_id:
                ru_names[mod_id] = mod.get("shortName", mod.get("name", "Unknown"))
        
        async with aiosqlite.connect(self.db.db_path) as conn:
            added_count = 0
            seen_ids = set()
            
            for mod in mods_data_en:
                mod_id = mod.get("id")
                if mod_id in seen_ids:
                    continue
                seen_ids.add(mod_id)
                
                name_en = mod.get("shortName", mod.get("name", "Unknown"))
                name_ru = ru_names.get(mod_id, name_en)  # Fallback to English if no Russian
                price = mod.get("avg24hPrice", 0) or 0
                flea_price = mod.get("avg24hPrice", None)
                
                # Determine slot type
                slot_type = self._determine_slot_type(name_en, mod.get("types", []))
                
                # Extract slot_name from properties (for export compatibility)
                # slot_name format: "mod_pistol_grip", "mod_stock", "mod_sight_rear", etc.
                slot_name = None
                properties = mod.get("properties", {})
                if properties:
                    # Try to get slot info from properties
                    slots = properties.get("slots", [])
                    if slots and len(slots) > 0:
                        # Use first slot's nameId if available
                        slot_name = slots[0].get("nameId")
                
                # If no slot_name from properties, try to infer from types
                if not slot_name:
                    mod_types = mod.get("types", [])
                    if "muzzle" in mod_types:
                        slot_name = "mod_muzzle"
                    elif "sight" in mod_types:
                        slot_name = "mod_sight_rear"
                    elif "pistol-grip" in mod_types:
                        slot_name = "mod_pistol_grip"
                    elif "stock" in mod_types:
                        slot_name = "mod_stock"
                    elif "handguard" in mod_types:
                        slot_name = "mod_handguard"
                    elif "barrel" in mod_types:
                        slot_name = "mod_barrel"
                    elif "magazine" in mod_types:
                        slot_name = "mod_magazine"
                    elif "tactical" in mod_types:
                        slot_name = "mod_tactical"
                
                # Get trader info from sellFor
                trader = "Mechanic"
                trader_price = price  # Default to avg price
                loyalty_level = 2
                sell_for = mod.get("sellFor", [])
                if sell_for:
                    # Find the first trader offer (not Fence)
                    for sale in sell_for:
                        vendor = sale.get("vendor", {})
                        if vendor and vendor.get("name") and vendor.get("name") != "Fence":
                            trader = vendor.get("name", "Mechanic")
                            trader_price = sale.get("priceRUB", sale.get("price", price))
                            # Infer loyalty level based on price (rough estimation)
                            # Lower priced items are typically LL1, higher priced are LL2-4
                            if trader_price < 10000:
                                loyalty_level = 1
                            elif trader_price < 50000:
                                loyalty_level = 2
                            elif trader_price < 150000:
                                loyalty_level = 3
                            else:
                                loyalty_level = 4
                            break
                
                try:
                    await conn.execute(
                        """INSERT OR REPLACE INTO modules 
                        (name_ru, name_en, price, trader, loyalty_level, slot_type, flea_price, tarkov_id, slot_name) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (name_ru, name_en, trader_price, trader, loyalty_level, slot_type, flea_price, mod_id, slot_name)
                    )
                    added_count += 1
                except Exception as e:
                    logger.debug(f"Error adding module {name_en}: {e}")
            
            await conn.commit()
            logger.info(f"Synced {added_count} modules with localization")
            return added_count
    
    async def sync_all(self) -> Dict[str, int]:
        """
        Sync all data from tarkov.dev API.
        
        Returns:
            Dictionary with counts of synced items
        """
        logger.info("Starting full sync from tarkov.dev API...")
        
        results = {
            "traders": 0,
            "weapons": 0,
            "modules": 0
        }
        
        # Sync in order: traders -> weapons -> modules
        results["traders"] = await self.sync_traders()
        results["weapons"] = await self.sync_weapons()
        results["modules"] = await self.sync_modules()
        
        # Load quest builds automatically after sync
        logger.info("Loading quest builds...")
        quest_count = await self._load_quest_builds()
        results["quest_builds"] = quest_count
        
        logger.info(f"Full sync completed: {results}")
        return results
    
    async def _load_quest_builds(self) -> int:
        """Load weapon assembly/modification quest builds from API into database."""
        import aiosqlite
        import json
        
        # Get weapon build tasks from Mechanic in both languages
        quest_tasks_en = await self.api.get_weapon_build_tasks(lang="en")
        quest_tasks_ru = await self.api.get_weapon_build_tasks(lang="ru")
        
        if not quest_tasks_en:
            logger.warning("No weapon build tasks received from API")
            return 0
        
        # Create mapping of quest IDs to Russian names
        ru_quest_names = {}
        for quest in quest_tasks_ru:
            quest_id = quest.get("id")
            if quest_id:
                ru_quest_names[quest_id] = quest.get("name", "Unknown Quest")
        
        added_count = 0
        
        async with aiosqlite.connect(self.db.db_path) as conn:
            for quest_data in quest_tasks_en:
                quest_id = quest_data.get("id")
                name_en = quest_data.get("name", "Unknown Quest")
                name_ru = ru_quest_names.get(quest_id, name_en)
                
                # Check if this quest has weapon-related objectives
                objectives = quest_data.get("objectives", [])
                weapon_related = False
                
                for obj in objectives:
                    obj_type = obj.get("type", "").lower()
                    obj_desc = obj.get("description", "").lower()
                    
                    # Check for weapon build/modification keywords
                    if any(keyword in obj_desc for keyword in [
                        "build", "modify", "assemble", "attach", "install",
                        "weapon", "gun", "rifle", "pistol", "shotgun",
                        "сборка", "модифицировать", "собрать", "установить",
                        "оружие", "винтовка", "пистолет", "дробовик"
                    ]):
                        weapon_related = True
                        break
                
                if not weapon_related:
                    continue
                
                # Try to find a matching weapon for this quest
                # This is a simplified approach - in reality, quest objectives would specify exact weapons
                weapon_id = None
                async with conn.execute(
                    "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                    ("%M4A1%", "%M4A1%")  # Default to M4A1 for Gunsmith quests
                ) as cursor:
                    weapon_row = await cursor.fetchone()
                    if weapon_row:
                        weapon_id = weapon_row[0]
                
                if not weapon_id:
                    continue
                
                # Check if this quest build already exists
                async with conn.execute(
                    "SELECT id FROM builds WHERE quest_name_en = ? AND category = ?",
                    (name_en, "quest")
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if not existing:
                    from database import BuildCategory
                    await conn.execute(
                        """INSERT INTO builds 
                        (weapon_id, category, name_ru, name_en, quest_name_ru, quest_name_en,
                         total_cost, min_loyalty_level, modules)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (weapon_id, BuildCategory.QUEST.value, name_ru, name_en, 
                         name_ru, name_en, 150000, 2, json.dumps([]))
                    )
                    added_count += 1
            
            await conn.commit()
        
        logger.info(f"Loaded {added_count} weapon build quest tasks from Mechanic")
        return added_count
    
    def _calculate_effective_range(self, caliber: Optional[str]) -> Optional[int]:
        """Calculate effective range based on caliber."""
        if not caliber:
            return None
        
        caliber_lower = caliber.lower()
        
        if any(x in caliber_lower for x in ["7.62x54", "7.62x51", ".308", "12.7x108"]):
            return 800  # Sniper calibers
        elif any(x in caliber_lower for x in ["5.56x45", "5.45x39", "7.62x39"]):
            return 400  # Rifle calibers
        elif any(x in caliber_lower for x in ["9x19", "9x18", ".45", "9x21"]):
            return 100  # Pistol calibers
        elif "12ga" in caliber_lower or "20ga" in caliber_lower:
            return 50   # Shotgun
        
        return None
    
    def _determine_slot_type(self, name: str, types: List[str]) -> str:
        """Determine module slot type from name and types."""
        name_lower = name.lower()
        
        if "sight" in name_lower or "scope" in name_lower or any(t in types for t in ["sight", "scope"]):
            return "sight"
        elif "stock" in name_lower or "приклад" in name_lower or "stock" in types:
            return "stock"
        elif "grip" in name_lower or "рукоят" in name_lower or "grip" in types:
            return "grip"
        elif "suppressor" in name_lower or "глушител" in name_lower or "suppressor" in types:
            return "muzzle"
        elif "handguard" in name_lower or "цевье" in name_lower:
            return "handguard"
        elif "magazine" in name_lower or "mag" in name_lower or "magazine" in types:
            return "magazine"
        
        return "universal"
