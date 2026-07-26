"""Module compatibility checker for weapon builds."""
import logging
from typing import List, Dict, Optional, Set
from api_clients import TarkovAPIClient

logger = logging.getLogger(__name__)


class CompatibilityChecker:
    """Service for checking module compatibility with weapon slots."""
    
    def __init__(self, api_client: TarkovAPIClient):
        self.api = api_client
        self._weapon_slots_cache = {}
    
    async def get_weapon_slots(self, weapon_id: str) -> List[Dict]:
        """
        Get weapon slots with compatibility information from API.
        
        Args:
            weapon_id: Weapon item ID from tarkov.dev
            
        Returns:
            List of slot dictionaries with filters
        """
        if weapon_id in self._weapon_slots_cache:
            return self._weapon_slots_cache[weapon_id]
        
        weapon_data = await self.api.get_weapon_details(weapon_id)
        
        if not weapon_data or "properties" not in weapon_data:
            logger.warning(f"No weapon data found for {weapon_id}")
            return []
        
        properties = weapon_data.get("properties", {})
        slots = properties.get("slots", [])
        
        self._weapon_slots_cache[weapon_id] = slots
        return slots
    
    async def is_module_compatible(
        self, 
        weapon_id: str, 
        slot_name: str, 
        module_id: str
    ) -> bool:
        """
        Check if a module is compatible with a weapon slot.
        
        Args:
            weapon_id: Weapon item ID
            slot_name: Slot name (e.g., "mod_stock", "mod_sight_rear")
            module_id: Module item ID to check
            
        Returns:
            True if compatible, False otherwise
        """
        slots = await self.get_weapon_slots(weapon_id)
        
        for slot in slots:
            if slot.get("nameId") == slot_name or slot.get("name") == slot_name:
                filters = slot.get("filters", {})
                
                # Check allowed items
                allowed_items = filters.get("allowedItems", [])
                if allowed_items:
                    allowed_ids = {item.get("id") for item in allowed_items}
                    if module_id in allowed_ids:
                        # Check excluded items
                        excluded_items = filters.get("excludedItems", [])
                        excluded_ids = {item.get("id") for item in excluded_items}
                        return module_id not in excluded_ids
                    return False
                
                # If no specific items, check categories
                allowed_categories = filters.get("allowedCategories", [])
                if allowed_categories:
                    # Would need to check module category - for now assume compatible
                    return True
        
        return False
    
    async def get_compatible_modules(
        self, 
        weapon_id: str, 
        slot_name: str,
        language: str = "en"
    ) -> List[Dict]:
        """
        Get all compatible modules for a weapon slot.
        
        Args:
            weapon_id: Weapon item ID
            slot_name: Slot name
            language: Language for module names
            
        Returns:
            List of compatible module data
        """
        slots = await self.get_weapon_slots(weapon_id)
        
        for slot in slots:
            if slot.get("nameId") == slot_name or slot.get("name") == slot_name:
                filters = slot.get("filters", {})
                allowed_items = filters.get("allowedItems", [])
                excluded_items = filters.get("excludedItems", [])
                excluded_ids = {item.get("id") for item in excluded_items}
                
                # Filter out excluded items
                compatible = [
                    item for item in allowed_items 
                    if item.get("id") not in excluded_ids
                ]
                
                return compatible
        
        return []
    
    async def get_required_slots(self, weapon_id: str) -> List[str]:
        """
        Get list of required slot names for a weapon.
        
        Args:
            weapon_id: Weapon item ID
            
        Returns:
            List of required slot nameIds
        """
        slots = await self.get_weapon_slots(weapon_id)
        required = []
        
        for slot in slots:
            if slot.get("required", False):
                slot_id = slot.get("nameId") or slot.get("name")
                if slot_id:
                    required.append(slot_id)
        
        return required
    
    async def validate_build(
        self, 
        weapon_id: str, 
        modules: Dict[str, str]
    ) -> tuple[bool, List[str]]:
        """
        Validate a complete build configuration.
        
        Args:
            weapon_id: Weapon item ID
            modules: Dictionary mapping slot names to module IDs
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Check required slots
        required_slots = await self.get_required_slots(weapon_id)
        for slot_name in required_slots:
            if slot_name not in modules:
                errors.append(f"Required slot '{slot_name}' is not filled")
        
        # Check compatibility of each module
        for slot_name, module_id in modules.items():
            if not await self.is_module_compatible(weapon_id, slot_name, module_id):
                errors.append(f"Module {module_id} is not compatible with slot {slot_name}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def clear_cache(self):
        """Clear the weapon slots cache."""
        self._weapon_slots_cache.clear()
