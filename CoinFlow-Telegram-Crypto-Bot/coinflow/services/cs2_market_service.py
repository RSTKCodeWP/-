"""CS2 (Counter-Strike 2) items market data service."""

import requests
from typing import Optional, Dict, List
from datetime import datetime
from ..utils.logger import setup_logger
from ..utils.cache import Cache

logger = setup_logger('cs2_market')


class CS2MarketService:
    """Service for fetching CS2 item prices from various marketplaces."""
    
    # Popular CS2 items (30+ items across categories)
    POPULAR_ITEMS = {
        # Knives
        'knife_karambit_doppler': {'name': 'Karambit | Doppler', 'category': 'Knife', 'quality': 'Factory New'},
        'knife_karambit_fade': {'name': 'Karambit | Fade', 'category': 'Knife', 'quality': 'Factory New'},
        'knife_m9_doppler': {'name': 'M9 Bayonet | Doppler', 'category': 'Knife', 'quality': 'Factory New'},
        'knife_butterfly_fade': {'name': 'Butterfly Knife | Fade', 'category': 'Knife', 'quality': 'Factory New'},
        'knife_talon_doppler': {'name': 'Talon Knife | Doppler', 'category': 'Knife', 'quality': 'Factory New'},
        
        # Gloves
        'gloves_sport_vice': {'name': 'Sport Gloves | Vice', 'category': 'Gloves', 'quality': 'Factory New'},
        'gloves_specialist_crimson': {'name': 'Specialist Gloves | Crimson Kimono', 'category': 'Gloves', 'quality': 'Factory New'},
        'gloves_driver_king': {'name': 'Driver Gloves | King Snake', 'category': 'Gloves', 'quality': 'Factory New'},
        
        # Rifles (AK-47)
        'ak47_redline': {'name': 'AK-47 | Redline', 'category': 'Rifle', 'quality': 'Field-Tested'},
        'ak47_vulcan': {'name': 'AK-47 | Vulcan', 'category': 'Rifle', 'quality': 'Factory New'},
        'ak47_asiimov': {'name': 'AK-47 | Asiimov', 'category': 'Rifle', 'quality': 'Field-Tested'},
        'ak47_neon_revolution': {'name': 'AK-47 | Neon Revolution', 'category': 'Rifle', 'quality': 'Factory New'},
        'ak47_bloodsport': {'name': 'AK-47 | Bloodsport', 'category': 'Rifle', 'quality': 'Factory New'},
        
        # Rifles (M4A4/M4A1-S)
        'm4a4_howl': {'name': 'M4A4 | Howl', 'category': 'Rifle', 'quality': 'Factory New'},
        'm4a4_asiimov': {'name': 'M4A4 | Asiimov', 'category': 'Rifle', 'quality': 'Field-Tested'},
        'm4a1s_printstream': {'name': 'M4A1-S | Printstream', 'category': 'Rifle', 'quality': 'Factory New'},
        'm4a1s_hyper_beast': {'name': 'M4A1-S | Hyper Beast', 'category': 'Rifle', 'quality': 'Factory New'},
        
        # AWP
        'awp_dragon_lore': {'name': 'AWP | Dragon Lore', 'category': 'Sniper', 'quality': 'Factory New'},
        'awp_asiimov': {'name': 'AWP | Asiimov', 'category': 'Sniper', 'quality': 'Field-Tested'},
        'awp_hyper_beast': {'name': 'AWP | Hyper Beast', 'category': 'Sniper', 'quality': 'Factory New'},
        'awp_neo_noir': {'name': 'AWP | Neo-Noir', 'category': 'Sniper', 'quality': 'Factory New'},
        'awp_containment': {'name': 'AWP | Containment Breach', 'category': 'Sniper', 'quality': 'Factory New'},
        
        # Pistols
        'glock_fade': {'name': 'Glock-18 | Fade', 'category': 'Pistol', 'quality': 'Factory New'},
        'usp_kill_confirmed': {'name': 'USP-S | Kill Confirmed', 'category': 'Pistol', 'quality': 'Factory New'},
        'desert_eagle_blaze': {'name': 'Desert Eagle | Blaze', 'category': 'Pistol', 'quality': 'Factory New'},
        'desert_eagle_printstream': {'name': 'Desert Eagle | Printstream', 'category': 'Pistol', 'quality': 'Factory New'},
        
        # Other popular items
        'p90_asiimov': {'name': 'P90 | Asiimov', 'category': 'SMG', 'quality': 'Factory New'},
        'mac10_neon_rider': {'name': 'MAC-10 | Neon Rider', 'category': 'SMG', 'quality': 'Factory New'},
        'five_seven_hyper_beast': {'name': 'Five-SeveN | Hyper Beast', 'category': 'Pistol', 'quality': 'Factory New'}
    }
    
    # Categories for menu organization
    CATEGORIES = {
        'knives': 'Knives 🔪',
        'gloves': 'Gloves 🧤',
        'rifles': 'Rifles 🔫',
        'snipers': 'Snipers 🎯',
        'pistols': 'Pistols 🔫',
        'smgs': 'SMGs ⚡'
    }
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialize CS2 market service.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.cache = Cache(ttl_seconds=cache_ttl)
        logger.info("CS2MarketService initialized")
    
    def search_items(self, query: str, limit: int = 10) -> List[str]:
        """
        Search CS2 items by keyword.
        
        Args:
            query: Search query (e.g., 'karambit', 'ak47', 'doppler')
            limit: Maximum number of results to return
        
        Returns:
            List of item IDs matching the query
        """
        query_lower = query.lower().strip()
        results = []
        
        for item_id, item_info in self.POPULAR_ITEMS.items():
            item_name_lower = item_info['name'].lower()
            
            # Check if query matches item name
            if query_lower in item_name_lower or query_lower in item_id:
                results.append(item_id)
            
            # Stop if we have enough results
            if len(results) >= limit:
                break
        
        logger.info(f"Search '{query}' found {len(results)} items")
        return results
    
    def get_item_price_steam(self, item_name: str) -> Optional[float]:
        """
        Get item price from Steam Community Market.
        
        Args:
            item_name: Full item name (e.g., 'AK-47 | Redline (Field-Tested)')
        
        Returns:
            Price in USD or None if error
        """
        try:
            # Steam API endpoint
            url = 'https://steamcommunity.com/market/priceoverview/'
            params = {
                'appid': 730,  # CS2/CSGO app ID
                'currency': 1,  # USD
                'market_hash_name': item_name
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                # Parse price string (e.g., "$123.45")
                price_str = data.get('lowest_price') or data.get('median_price')
                if price_str:
                    price = float(price_str.replace('$', '').replace(',', ''))
                    logger.debug(f"Steam price for {item_name}: ${price:.2f}")
                    return price
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Steam price for {item_name}: {e}")
            return None
    
    def get_item_price_csmoney(self, item_id: str) -> Optional[float]:
        """
        Get item price from CS.Money (public pricing data).
        
        Note: CS.Money doesn't have a stable public API, so this is a simplified version.
        In production, you'd need to register for their API or use web scraping.
        
        Args:
            item_id: Item identifier
        
        Returns:
            Price in USD or None if error
        """
        try:
            # This is a placeholder - CS.Money requires API key or web scraping
            # For demo purposes, we'll return a simulated price
            # In production, implement proper CS.Money API integration
            
            logger.warning("CS.Money API integration is placeholder - implement real API")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching CS.Money price: {e}")
            return None
    
    def get_item_price_skinport(self, item_name: str) -> Optional[float]:
        """
        Get item price from Skinport API.
        
        Args:
            item_name: Item name
        
        Returns:
            Price in USD or None if error
        """
        try:
            # Skinport API endpoint (public, no auth needed for basic queries)
            url = 'https://api.skinport.com/v1/items'
            params = {
                'app_id': 730,  # CS2
                'currency': 'USD'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            items = response.json()
            
            # Search for matching item
            for item in items:
                if item.get('market_hash_name') == item_name:
                    min_price = item.get('min_price')
                    if min_price:
                        logger.debug(f"Skinport price for {item_name}: ${min_price:.2f}")
                        return float(min_price)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Skinport price for {item_name}: {e}")
            return None
    
    def get_item_prices(self, item_id: str) -> Optional[Dict]:
        """
        Get item prices from multiple marketplaces.
        
        Args:
            item_id: Item ID from POPULAR_ITEMS
        
        Returns:
            Dict with price data from multiple sources or None if error
        """
        cache_key = f'cs2_item_{item_id}'
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for CS2 item {item_id}")
            return cached
        
        if item_id not in self.POPULAR_ITEMS:
            logger.warning(f"Unknown CS2 item: {item_id}")
            return None
        
        item_info = self.POPULAR_ITEMS[item_id]
        item_name = item_info['name']
        quality = item_info['quality']
        
        # Construct full market name
        full_name = f"{item_name} ({quality})"
        
        try:
            prices = {}
            
            # Try Steam Community Market
            steam_price = self.get_item_price_steam(full_name)
            if steam_price:
                prices['steam'] = steam_price
            
            # Try Skinport (if Steam fails or for comparison)
            skinport_price = self.get_item_price_skinport(full_name)
            if skinport_price:
                prices['skinport'] = skinport_price
            
            # If no prices found, return None
            if not prices:
                logger.warning(f"No prices found for {full_name}")
                return None
            
            # Calculate statistics
            price_list = list(prices.values())
            avg_price = sum(price_list) / len(price_list)
            min_price = min(price_list)
            max_price = max(price_list)
            
            # Find which marketplace has min/max
            min_marketplace = [k for k, v in prices.items() if v == min_price][0]
            max_marketplace = [k for k, v in prices.items() if v == max_price][0]
            
            data = {
                'item_id': item_id,
                'name': item_name,
                'quality': quality,
                'full_name': full_name,
                'category': item_info['category'],
                'prices': prices,
                'avg_price': avg_price,
                'min_price': min_price,
                'max_price': max_price,
                'min_marketplace': min_marketplace,
                'max_marketplace': max_marketplace,
                'spread_usd': max_price - min_price,
                'spread_pct': ((max_price - min_price) / avg_price) * 100 if avg_price > 0 else 0,
                'timestamp': datetime.now().isoformat()
            }
            
            self.cache.set(cache_key, data)
            logger.info(f"Fetched prices for {full_name}: avg ${avg_price:.2f}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching prices for {item_id}: {e}")
            return None
    
    def get_items_by_category(self, category: str) -> List[str]:
        """
        Get list of item IDs by category.
        
        Args:
            category: Category name (knives, gloves, rifles, etc.)
        
        Returns:
            List of item IDs
        """
        category_lower = category.lower()
        items = []
        
        for item_id, item_info in self.POPULAR_ITEMS.items():
            item_category = item_info['category'].lower()
            
            if category_lower == 'knives' and item_category == 'knife':
                items.append(item_id)
            elif category_lower == 'gloves' and item_category == 'gloves':
                items.append(item_id)
            elif category_lower == 'rifles' and item_category == 'rifle':
                items.append(item_id)
            elif category_lower == 'snipers' and item_category == 'sniper':
                items.append(item_id)
            elif category_lower == 'pistols' and item_category == 'pistol':
                items.append(item_id)
            elif category_lower == 'smgs' and item_category == 'smg':
                items.append(item_id)
        
        return items
    
    def search_items(self, query: str) -> List[Dict]:
        """
        Search items by name.
        
        Args:
            query: Search query
        
        Returns:
            List of matching items
        """
        query_lower = query.lower()
        results = []
        
        for item_id, item_info in self.POPULAR_ITEMS.items():
            if query_lower in item_info['name'].lower():
                results.append({
                    'item_id': item_id,
                    **item_info
                })
        
        return results
