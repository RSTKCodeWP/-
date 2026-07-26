"""Build-related business logic."""
import logging
import random
from typing import List, Optional
from database import Database, Build, BuildCategory, Module, Weapon
from api_clients import TarkovAPIClient

logger = logging.getLogger(__name__)


class BuildService:
    """Service for weapon build operations."""
    
    def __init__(self, db: Database, api_client: TarkovAPIClient):
        self.db = db
        self.api = api_client
    
    async def get_build_with_details(self, build_id: int) -> Optional[dict]:
        """
        Get build with weapon and modules details.
        
        Returns:
            Dictionary with build, weapon, and modules data
        """
        build = await self.db.get_build_by_id(build_id)
        if not build:
            return None
        
        weapon = await self.db.get_weapon_by_id(build.weapon_id)
        modules = await self.db.get_modules_by_ids(build.modules)
        
        return {
            "build": build,
            "weapon": weapon,
            "modules": modules
        }
    
    async def get_builds_for_weapon(
        self, 
        weapon_id: int, 
        category: Optional[BuildCategory] = None
    ) -> List[dict]:
        """
        Get all builds for a weapon with full details.
        
        Args:
            weapon_id: Weapon ID
            category: Optional filter by build category
            
        Returns:
            List of builds with weapon and modules
        """
        builds = await self.db.get_builds_by_weapon(weapon_id, category)
        
        result = []
        for build in builds:
            weapon = await self.db.get_weapon_by_id(build.weapon_id)
            modules = await self.db.get_modules_by_ids(build.modules)
            result.append({
                "build": build,
                "weapon": weapon,
                "modules": modules
            })
        
        return result
    
    async def get_random_build(self) -> Optional[dict]:
        """Get a random build with details."""
        build = await self.db.get_random_build()
        if not build:
            return None
        
        weapon = await self.db.get_weapon_by_id(build.weapon_id)
        modules = await self.db.get_modules_by_ids(build.modules)
        
        return {
            "build": build,
            "weapon": weapon,
            "modules": modules
        }
    
    async def get_meta_builds(self) -> List[dict]:
        """Get all meta builds with details."""
        builds = await self.db.get_meta_builds()
        
        result = []
        for build in builds:
            weapon = await self.db.get_weapon_by_id(build.weapon_id)
            modules = await self.db.get_modules_by_ids(build.modules)
            result.append({
                "build": build,
                "weapon": weapon,
                "modules": modules
            })
        
        return result
    
    async def generate_meta_build_from_preset(self, weapon_search: str, language: str = "ru"):
        """Generate meta build from weapon's best preset using API.
        
        Args:
            weapon_search: Weapon name to search for (e.g. "AK-74M", "M4A1")
            language: Language for display
            
        Returns:
            Dict with weapon, modules, and stats
        """
        from api_clients import TarkovAPIClient
        import logging
        logger = logging.getLogger(__name__)
        
        # Search for weapon
        api = TarkovAPIClient()
        try:
            logger.info(f"Searching for weapon: {weapon_search}")
            
            # Search weapons by name
            search_query = f"""
            query {{
                items(name: "{weapon_search}") {{
                    id
                    name
                    shortName
                    avg24hPrice
                    properties {{
                        ... on ItemPropertiesWeapon {{
                            caliber
                            ergonomics
                            recoilVertical
                            slots {{
                                name
                                filters {{
                                    allowedItems {{
                                        id
                                    }}
                                }}
                            }}
                            defaultPreset {{
                                id
                                name
                                containsItems {{
                                    count
                                    attributes {{
                                        name
                                        value
                                    }}
                                    item {{
                                        id
                                        name
                                        shortName
                                        avg24hPrice
                                        buyFor {{
                                            vendor {{
                                                name
                                            }}
                                            priceRUB
                                            requirements {{
                                                type
                                                value
                                            }}
                                        }}
                                        properties {{
                                            ... on ItemPropertiesWeaponMod {{
                                                ergonomics
                                                recoilModifier
                                            }}
                                            ... on ItemPropertiesMagazine {{
                                                capacity
                                                ergonomics
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            data = await api._make_graphql_request(search_query)
            
            if not data:
                logger.error(f"No data returned from API for weapon: {weapon_search}")
                return None
            
            if not data.get('items'):
                logger.error(f"No items found for weapon: {weapon_search}")
                logger.debug(f"API response: {data}")
                return None
            
            logger.info(f"Found {len(data['items'])} items for {weapon_search}")
            
            # Filter to only items with defaultPreset (weapons, not modules)
            weapon_data = None
            for item in data['items']:
                item_props = item.get('properties', {})
                if item_props.get('defaultPreset'):
                    weapon_data = item
                    break
            
            if not weapon_data:
                logger.error(f"No weapon with preset found for {weapon_search}")
                return None
            
            logger.info(f"Selected weapon: {weapon_data.get('name')}")
            
            weapon_props = weapon_data.get('properties', {})
            default_preset = weapon_props.get('defaultPreset')
            
            logger.info(f"Found preset: {default_preset.get('name')}")
            
            # Build item ID to slot name mapping
            item_to_slot = {}
            weapon_slots = weapon_props.get('slots', [])
            for slot in weapon_slots:
                slot_name = slot.get('name')
                filters = slot.get('filters', {})
                allowed_items = filters.get('allowedItems', [])
                for allowed_item in allowed_items:
                    item_to_slot[allowed_item.get('id')] = slot_name
            
            # Extract modules from preset
            contained_items = default_preset.get('containsItems', [])
            modules = []
            total_cost = weapon_data.get('avg24hPrice', 0)
            
            for item in contained_items:
                item_data = item.get('item')
                if item_data:
                    from services.quest_build_service import QuestBuildService
                    quest_service = QuestBuildService(api)
                    trader_info = quest_service._get_best_trader(item_data.get('buyFor', []))
                    
                    # Get slot name from item_to_slot mapping
                    item_id = item_data.get('id')
                    slot_name = item_to_slot.get(item_id, 'Unknown')
                    
                    price = item_data.get('avg24hPrice') or 0
                    modules.append({
                        'id': item_data.get('id'),
                        'name': item_data.get('name', 'Unknown'),
                        'price': price,
                        'slot': slot_name or 'Unknown',
                        'trader': trader_info['trader'],
                        'trader_level': trader_info['level'],
                        'trader_price': trader_info['price']
                    })
                    total_cost += price
            
            logger.info(f"Generated build with {len(modules)} modules, total cost: {total_cost:,}₽")
            
            return {
                'weapon': weapon_data,
                'modules': modules,
                'preset_name': default_preset.get('name', 'Default'),
                'total_cost': total_cost
            }
            
        except Exception as e:
            logger.error(f"Error generating meta build for {weapon_search}: {e}", exc_info=True)
            return None
        finally:
            await api.close()
    
    async def get_quest_builds(self) -> List[dict]:
        """Get all quest builds with details."""
        builds = await self.db.get_quest_builds()
        
        result = []
        for build in builds:
            weapon = await self.db.get_weapon_by_id(build.weapon_id)
            modules = await self.db.get_modules_by_ids(build.modules)
            result.append({
                "build": build,
                "weapon": weapon,
                "modules": modules
            })
        
        return result
    
    async def get_builds_by_loyalty(
        self, 
        trader_levels: dict
    ) -> List[dict]:
        """
        Get builds available based on user's trader loyalty levels.
        
        Args:
            trader_levels: Dictionary of trader loyalty levels
            
        Returns:
            List of available builds
        """
        all_builds = await self.db.get_meta_builds()
        available_builds = []
        
        for build in all_builds:
            modules = await self.db.get_modules_by_ids(build.modules)
            
            # Check if all modules are available at user's loyalty levels
            is_available = True
            for module in modules:
                trader_name_lower = module.trader.lower()
                user_level = trader_levels.get(trader_name_lower, 1)
                
                if module.loyalty_level > user_level:
                    is_available = False
                    break
            
            if is_available:
                weapon = await self.db.get_weapon_by_id(build.weapon_id)
                available_builds.append({
                    "build": build,
                    "weapon": weapon,
                    "modules": modules
                })
        
        return available_builds
    
    async def calculate_build_cost(self, module_ids: List[int]) -> int:
        """Calculate total cost of a build."""
        modules = await self.db.get_modules_by_ids(module_ids)
        return sum(m.price for m in modules)
