"""Unified Tarkov API client with caching."""
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TarkovAPIClient:
    """
    Centralized client for tarkov.dev API.
    All external API calls MUST go through this client.
    """
    
    def __init__(self, api_url: str = "https://api.tarkov.dev/graphql", cache_duration_hours: int = 24):
        self.api_url = api_url
        self.cache = {}
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self._session: Optional[aiohttp.ClientSession] = None
        self._invalid_item_ids = set()  # Track items that don't exist in API
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.cache:
            return False
        
        cached_time = self.cache[cache_key].get("timestamp")
        if not cached_time:
            return False
        
        return datetime.now() - cached_time < self.cache_duration
    
    def _get_cached(self, cache_key: str) -> Optional[any]:
        """Get data from cache if valid."""
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        return None
    
    def _set_cache(self, cache_key: str, data: any):
        """Store data in cache."""
        self.cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now()
        }
    
    async def _make_graphql_request(self, query: str) -> Optional[Dict]:
        """Make GraphQL request to tarkov.dev API."""
        try:
            session = await self._get_session()
            async with session.post(
                self.api_url,
                json={"query": query},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Check for GraphQL errors
                    if "errors" in result:
                        logger.error(f"GraphQL errors: {result['errors']}")
                        return None
                    
                    data = result.get("data")
                    if not data:
                        logger.warning(f"API returned empty data. Full response: {result}")
                    return data
                else:
                    response_text = await response.text()
                    logger.warning(f"Tarkov.dev API returned status {response.status}: {response_text[:200]}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Tarkov.dev API connection error: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error("Tarkov.dev API request timeout")
            return None
        except Exception as e:
            logger.error(f"Tarkov.dev API unexpected error: {e}", exc_info=True)
            return None
    
    async def get_all_weapons(self, lang: str = "en") -> List[Dict]:
        """
        Get all weapons from tarkov.dev API with localized names.
        Result is cached for 24 hours per language.
        
        Args:
            lang: Language code ("ru" or "en")
        """
        cache_key = f"all_weapons_{lang}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug(f"Returning cached weapons data for lang={lang}")
            return cached
        
        query = f"""
        {{
            items(lang: {lang}, types: [gun], limit: 1000) {{
                id
                name
                shortName
                normalizedName
                types
                avg24hPrice
                category {{
                    id
                    name
                }}
                properties {{
                    ... on ItemPropertiesWeapon {{
                        caliber
                        ergonomics
                        recoilVertical
                        recoilHorizontal
                        fireRate
                        defaultWidth
                        defaultHeight
                        defaultPreset {{
                            id
                        }}
                        slots {{
                            id
                            name
                            nameId
                            required
                            filters {{
                                allowedCategories {{
                                    id
                                    name
                                }}
                                allowedItems {{
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
                                excludedItems {{
                                    id
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        data = await self._make_graphql_request(query)
        if data and "items" in data:
            weapons = data["items"]
            self._set_cache(cache_key, weapons)
            logger.info(f"Fetched {len(weapons)} weapons from API for lang={lang}")
            return weapons
        
        return []
    
    async def get_all_traders(self) -> List[Dict]:
        """Get all traders information."""
        cache_key = "traders"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        query = """
        {
            traders {
                id
                name
                normalizedName
                resetTime
                levels {
                    level
                    requiredPlayerLevel
                    requiredReputation
                }
            }
        }
        """
        
        data = await self._make_graphql_request(query)
        if data and "traders" in data:
            traders = data["traders"]
            self._set_cache(cache_key, traders)
            logger.info(f"Fetched {len(traders)} traders from API")
            return traders
        
        return []
    
    async def get_all_mods(self, lang: str = "en") -> List[Dict]:
        """Get all weapon modifications with localized names.
        
        Args:
            lang: Language code ("ru" or "en")
        """
        cache_key = f"all_mods_{lang}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        query = f"""
        {{
            items(lang: {lang}, limit: 10000, types: [mods]) {{
                id
                name
                shortName
                avg24hPrice
                types
                sellFor {{
                    vendor {{
                        name
                        normalizedName
                    }}
                    price
                    currency
                    priceRUB
                }}
            }}
        }}
        """
        
        data = await self._make_graphql_request(query)
        if data and "items" in data:
            mods = data["items"]
            self._set_cache(cache_key, mods)
            logger.info(f"Fetched {len(mods)} mods from API for lang={lang}")
            return mods
        
        return []
    
    async def get_market_prices(self) -> Dict[str, int]:
        """Get current flea market prices for all items."""
        cache_key = "market_prices"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        query = """
        {
            items {
                id
                name
                avg24hPrice
                lastLowPrice
            }
        }
        """
        
        data = await self._make_graphql_request(query)
        if data and "items" in data:
            prices = {
                item["id"]: item.get("avg24hPrice", 0) 
                for item in data["items"]
            }
            self._set_cache(cache_key, prices)
            logger.info(f"Fetched prices for {len(prices)} items from API")
            return prices
        
        return {}
    
    async def get_all_tasks(self, lang: str = "en") -> List[Dict]:
        """Get all tasks/quests from tarkov.dev API with localized names.
        
        Args:
            lang: Language code ("ru" or "en")
        """
        cache_key = f"all_tasks_{lang}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        query = f"""
        {{
            tasks(lang: {lang}) {{
                id
                name
                normalizedName
                trader {{
                    name
                    normalizedName
                }}
                map {{
                    name
                    normalizedName
                }}
                experience
                minPlayerLevel
                taskRequirements {{
                    task {{
                        id
                        name
                    }}
                }}
                objectives {{
                    id
                    type
                    description
                    optional
                    ... on TaskObjectiveBuildItem {{
                        item {{
                            id
                            name
                        }}
                        attributes {{
                            name
                            requirement {{
                                compareMethod
                                value
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        data = await self._make_graphql_request(query)
        if data and "tasks" in data:
            tasks = data["tasks"]
            self._set_cache(cache_key, tasks)
            logger.info(f"Fetched {len(tasks)} tasks from API for lang={lang}")
            return tasks
        
        return []
    
    async def get_weapon_build_tasks(self, lang: str = "en") -> List[Dict]:
        """Get only tasks/quests related to weapon builds from Mechanic (Gunsmith, etc.).
        
        Args:
            lang: Language code ("ru" or "en")
        """
        cache_key = f"weapon_build_tasks_{lang}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Get all tasks with language parameter
        all_tasks = await self.get_all_tasks(lang=lang)
        
        # Filter tasks that require weapon builds AND are from Mechanic
        build_tasks = []
        build_keywords = [
            "gunsmith",
            "оружейник",
            "build",
            "сборка",
            "modify",
            "модифицировать",
            "weapon",
            "оружие"
        ]
        
        for task in all_tasks:
            # Check if task is from Mechanic
            trader_data = task.get("trader")
            if not trader_data:
                continue
            trader_name = trader_data.get("name", "")
            if trader_name.lower() != "mechanic" and trader_name.lower() != "механик":
                continue
            
            task_name = task.get("name", "").lower()
            task_normalized = task.get("normalizedName", "").lower()
            
            # Check if task name contains build-related keywords
            is_build_quest = any(keyword in task_name or keyword in task_normalized for keyword in build_keywords)
            
            if not is_build_quest:
                # Also check objectives for "buildWeapon" type
                objectives = task.get("objectives", [])
                for obj in objectives:
                    obj_type = obj.get("type", "").lower()
                    obj_desc = obj.get("description", "").lower()
                    if "buildweapon" in obj_type or any(kw in obj_desc for kw in ["build", "modify", "assemble", "сборка", "модифицировать"]):
                        is_build_quest = True
                        break
            
            if is_build_quest:
                build_tasks.append(task)
        
        self._set_cache(cache_key, build_tasks)
        logger.info(f"Filtered {len(build_tasks)} weapon build tasks from Mechanic from {len(all_tasks)} total tasks for lang={lang}")
        return build_tasks
    
    async def search_items(self, search_term: str, item_types: Optional[List[str]] = None) -> List[Dict]:
        """Search items by name and optionally filter by types."""
        types_filter = ""
        if item_types:
            types_str = ", ".join([f'"{t}"' for t in item_types])
            types_filter = f"types: [{types_str}]"
        
        query = f"""
        {{
            items({types_filter}) {{
                id
                name
                shortName
                normalizedName
                types
                avg24hPrice
                category {{
                    name
                }}
            }}
        }}
        """
        
        data = await self._make_graphql_request(query)
        if data and "items" in data:
            items = data["items"]
            
            # Filter by search term
            if search_term:
                search_lower = search_term.lower()
                items = [
                    item for item in items
                    if (search_lower in item.get("name", "").lower() or
                        search_lower in item.get("shortName", "").lower() or
                        search_lower in item.get("normalizedName", "").lower())
                ]
            
            return items
        
        return []
    
    async def get_weapon_details(self, weapon_id: str) -> Optional[Dict]:
        """
        Get detailed weapon information including slots and compatible mods.
        
        Args:
            weapon_id: Weapon item ID
            
        Returns:
            Dictionary with weapon details including slots
        """
        cache_key = f"weapon_details_{weapon_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        query = f"""
        {{
            item(id: "{weapon_id}") {{
                id
                name
                shortName
                normalizedName
                types
                avg24hPrice
                category {{
                    name
                }}
                properties {{
                    ... on ItemPropertiesWeapon {{
                        caliber
                        ergonomics
                        recoilVertical
                        recoilHorizontal
                        fireRate
                        defaultHeight
                        defaultWidth
                        defaultPreset {{
                            id
                            name
                            containsItems {{
                                count
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
                        slots {{
                            id
                            name
                            nameId
                            required
                            filters {{
                                allowedCategories {{
                                    id
                                    name
                                }}
                                allowedItems {{
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
                                excludedItems {{
                                    id
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        data = await self._make_graphql_request(query)
        if data and "item" in data and data["item"]:
            weapon_data = data["item"]
            self._set_cache(cache_key, weapon_data)
            logger.info(f"Fetched details for weapon {weapon_id}")
            return weapon_data
        else:
            # Item doesn't exist, cache this info to avoid repeated requests
            self._invalid_item_ids.add(weapon_id)
            logger.debug(f"Weapon {weapon_id} not found in API, marked as invalid")
            return None
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        logger.info("API cache cleared")
