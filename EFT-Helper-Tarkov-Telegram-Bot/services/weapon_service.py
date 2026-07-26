"""Weapon-related business logic."""
import logging
from typing import List, Optional
from database import Database, Weapon, WeaponCategory
from api_clients import TarkovAPIClient

logger = logging.getLogger(__name__)


class WeaponService:
    """Service for weapon operations."""
    
    def __init__(self, db: Database, api_client: TarkovAPIClient):
        self.db = db
        self.api = api_client
    
    async def search_weapons(self, query: str, language: str = "ru") -> List[Weapon]:
        """
        Search weapons by name using API for full weapon list with localization.
        Falls back to database if API fails.
        
        Args:
            query: Search term
            language: User's preferred language
            
        Returns:
            List of matching weapons
        """
        # Try to get weapons from API for comprehensive search
        try:
            api_weapons = await self.api.get_all_weapons(lang=language)
            if api_weapons:
                query_lower = query.lower()
                matching_weapons = []
                
                for api_weapon in api_weapons:
                    weapon_name = api_weapon.get("name", "").lower()
                    weapon_short = api_weapon.get("shortName", "").lower()
                    weapon_normalized = api_weapon.get("normalizedName", "").lower()
                    
                    # Check if query matches name, shortName, or normalized name
                    if (query_lower in weapon_name or 
                        query_lower in weapon_short or 
                        query_lower in weapon_normalized):
                        
                        # Try to find in database first
                        db_weapons = await self.db.search_weapons(query, language)
                        for db_weapon in db_weapons:
                            # Match by name
                            if (db_weapon.name_en.lower() == weapon_name or 
                                db_weapon.name_ru.lower() == weapon_name or
                                api_weapon.get("id") == str(db_weapon.id)):
                                matching_weapons.append(db_weapon)
                                break
                
                if matching_weapons:
                    return matching_weapons[:10]  # Limit to 10 results
        except Exception as e:
            logger.error(f"Error searching weapons via API: {e}")
        
        # Fallback to database search
        return await self.db.search_weapons(query, language)
    
    async def get_weapon_by_id(self, weapon_id: int) -> Optional[Weapon]:
        """Get weapon by ID."""
        return await self.db.get_weapon_by_id(weapon_id)
    
    async def get_weapons_by_category(self, category: WeaponCategory) -> List[Weapon]:
        """Get all weapons in a specific category."""
        all_weapons = await self.db.get_all_weapons()
        return [w for w in all_weapons if w.category == category]
    
    async def get_weapons_by_tier(self, tier_rating: str) -> List[Weapon]:
        """Get weapons by tier rating (S, A, B, C, D)."""
        all_weapons = await self.db.get_all_weapons()
        return [w for w in all_weapons if w.tier_rating and w.tier_rating.value == tier_rating]
    
    async def get_weapon_stats(self, weapon_id: int) -> dict:
        """
        Get comprehensive weapon statistics.
        
        Returns:
            Dictionary with weapon stats including caliber, ergonomics, recoil, etc.
        """
        weapon = await self.db.get_weapon_by_id(weapon_id)
        if not weapon:
            return {}
        
        return {
            "id": weapon.id,
            "name_ru": weapon.name_ru,
            "name_en": weapon.name_en,
            "category": weapon.category.value,
            "tier_rating": weapon.tier_rating.value if weapon.tier_rating else None,
            "base_price": weapon.base_price,
            "caliber": weapon.caliber,
            "ergonomics": weapon.ergonomics,
            "recoil_vertical": weapon.recoil_vertical,
            "recoil_horizontal": weapon.recoil_horizontal,
            "fire_rate": weapon.fire_rate,
            "effective_range": weapon.effective_range
        }
