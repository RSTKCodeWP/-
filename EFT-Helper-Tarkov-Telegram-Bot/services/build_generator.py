"""Dynamic build generator with budget, loyalty, and flea market constraints."""
import logging
import random
from typing import Dict, List, Optional, Tuple
from database import TierRating
from api_clients import TarkovAPIClient
from .compatibility_checker import CompatibilityChecker
from .tier_evaluator import TierEvaluator

logger = logging.getLogger(__name__)


class BuildGeneratorConfig:
    """Configuration for build generation."""
    def __init__(
        self,
        budget: int,
        trader_levels: Dict[str, int],
        use_flea_only: bool = False,
        weapon_type: Optional[str] = None,
        prioritize_ergonomics: bool = False,
        prioritize_recoil: bool = True
    ):
        self.budget = budget
        self.trader_levels = trader_levels
        self.use_flea_only = use_flea_only
        self.weapon_type = weapon_type
        self.prioritize_ergonomics = prioritize_ergonomics
        self.prioritize_recoil = prioritize_recoil


class GeneratedBuild:
    """Generated build result."""
    def __init__(
        self,
        weapon_id: str,
        weapon_name: str,
        weapon_data: Dict,
        modules: Dict[str, Dict],  # slot_name -> module_data
        total_cost: int,
        remaining_budget: int,
        ergonomics: Optional[int],
        recoil_vertical: Optional[int],
        recoil_horizontal: Optional[int],
        tier_rating: TierRating,
        available_from: List[str]  # List of traders/flea
    ):
        self.weapon_id = weapon_id
        self.weapon_name = weapon_name
        self.weapon_data = weapon_data
        self.modules = modules
        self.total_cost = total_cost
        self.remaining_budget = remaining_budget
        self.ergonomics = ergonomics
        self.recoil_vertical = recoil_vertical
        self.recoil_horizontal = recoil_horizontal
        self.tier_rating = tier_rating
        self.available_from = available_from


class BuildGenerator:
    """Service for dynamic weapon build generation."""
    
    def __init__(
        self, 
        api_client: TarkovAPIClient,
        compatibility_checker: CompatibilityChecker,
        tier_evaluator: TierEvaluator
    ):
        self.api = api_client
        self.compatibility = compatibility_checker
        self.tier_eval = tier_evaluator
    
    async def generate_random_build(
        self,
        config: BuildGeneratorConfig,
        language: str = "en"
    ) -> Optional[GeneratedBuild]:
        """
        Generate a random build based on configuration.
        
        Args:
            config: Build generation configuration
            language: Language for names (ru/en)
            
        Returns:
            GeneratedBuild or None if generation failed
        """
        # 1. Select weapon within budget
        weapon_data = await self._select_weapon(config, language)
        if not weapon_data:
            logger.warning("No suitable weapon found for build generation")
            return None
        
        weapon_price = weapon_data.get("avg24hPrice", 0) or 0
        
        # Handle unlimited budget (None)
        if config.budget is None or config.budget <= 0:
            remaining_budget = 999999999  # Effectively unlimited
        else:
            remaining_budget = config.budget - weapon_price
            
            if remaining_budget < 0:
                logger.warning(f"Weapon price {weapon_price} exceeds budget {config.budget}")
                return None
        
        weapon_id = weapon_data.get("id")
        weapon_name = weapon_data.get("name", "Unknown")
        
        # 2. Get weapon slots and default modules
        slots = await self.compatibility.get_weapon_slots(weapon_id)
        if not slots:
            logger.warning(f"No slots found for weapon {weapon_id}")
            return None
        
        # Get default preset to know which modules are pre-installed
        default_preset = weapon_data.get("properties", {}).get("defaultPreset", {})
        default_modules = {}
        default_modules_cost = 0
        
        if default_preset:
            contained_items = default_preset.get("containsItems", [])
            for item in contained_items:
                # Map default modules to slots
                item_id = item.get("item", {}).get("id")
                # Store for comparison later
                if item_id:
                    default_modules[item_id] = item.get("item", {})
        
        # 3. Generate modules for each slot
        selected_modules = {}
        total_module_cost = 0
        replaced_default_cost = 0  # Track cost of replaced default modules
        
        # Prioritize required slots first
        required_slots = [s for s in slots if s.get("required", False)]
        optional_slots = [s for s in slots if not s.get("required", False)]
        
        # Process required slots
        for slot in required_slots:
            module = await self._select_module_for_slot(
                slot, remaining_budget - total_module_cost, config, language
            )
            if module:
                slot_name = slot.get("nameId") or slot.get("name")
                selected_modules[slot_name] = module
                module_price = self._get_module_price(module, config.use_flea_only)
                total_module_cost += module_price
                
                # Check if we're replacing a default module
                module_id = module.get("id")
                if module_id in default_modules:
                    default_mod_price = default_modules[module_id].get("avg24hPrice", 0) or 0
                    replaced_default_cost += default_mod_price
                    logger.debug(f"Replaced default module {module_id}, subtracting {default_mod_price} from total")
        
        # Process optional slots with remaining budget
        random.shuffle(optional_slots)  # Randomize order
        for slot in optional_slots:
            if total_module_cost >= remaining_budget:
                break
            
            # 10% chance to skip optional slots for variety (reduced to add more mods)
            if random.random() < 0.1:
                continue
            
            module = await self._select_module_for_slot(
                slot, remaining_budget - total_module_cost, config, language
            )
            if module:
                slot_name = slot.get("nameId") or slot.get("name")
                selected_modules[slot_name] = module
                module_price = self._get_module_price(module, config.use_flea_only)
                total_module_cost += module_price
                
                # Check if we're replacing a default module
                module_id = module.get("id")
                if module_id in default_modules:
                    # This module was in the default preset, so weapon price already includes it
                    default_mod_price = default_modules[module_id].get("avg24hPrice", 0) or 0
                    replaced_default_cost += default_mod_price
                    logger.debug(f"Replaced default module {module_id}, subtracting {default_mod_price} from total")
        
        # Adjust total cost to account for replaced default modules
        # Weapon price includes default modules, so subtract those we replaced
        actual_total_cost = weapon_price + total_module_cost - replaced_default_cost
        logger.info(f"Cost breakdown: weapon={weapon_price}, new_modules={total_module_cost}, replaced_defaults={replaced_default_cost}, actual_total={actual_total_cost}")
        
        # 4. Calculate final stats
        base_props = weapon_data.get("properties", {})
        base_ergo = base_props.get("ergonomics", 0)
        base_recoil = base_props.get("recoilVertical", 100)
        
        final_ergo, final_recoil_v, final_recoil_h = self._calculate_build_stats(
            base_ergo, base_recoil, selected_modules
        )
        
        # 5. Evaluate tier
        has_sight = any("sight" in slot.lower() or "scope" in slot.lower() 
                       for slot in selected_modules.keys())
        has_stock = any("stock" in slot.lower() 
                       for slot in selected_modules.keys())
        has_grip = any("grip" in slot.lower() or "pistol" in slot.lower()
                      for slot in selected_modules.keys())
        
        required_slot_names = [s.get("nameId") or s.get("name") for s in required_slots]
        has_all_required = all(
            slot_name in selected_modules for slot_name in required_slot_names
        )
        
        tier = self.tier_eval.evaluate_build(
            ergonomics=final_ergo,
            recoil_vertical=final_recoil_v,
            recoil_horizontal=final_recoil_h,
            total_cost=actual_total_cost,
            has_all_required_slots=has_all_required,
            has_sight=has_sight,
            has_stock=has_stock,
            has_grip=has_grip,
            weapon_base_ergonomics=base_ergo,
            weapon_base_recoil=base_recoil
        )
        
        # 6. Determine availability
        available_from = self._get_availability(weapon_data, selected_modules, config)
        
        return GeneratedBuild(
            weapon_id=weapon_id,
            weapon_name=weapon_name,
            weapon_data=weapon_data,
            modules=selected_modules,
            total_cost=actual_total_cost,
            remaining_budget=remaining_budget - (total_module_cost - replaced_default_cost),
            ergonomics=final_ergo,
            recoil_vertical=final_recoil_v,
            recoil_horizontal=final_recoil_h,
            tier_rating=tier,
            available_from=available_from
        )
    
    async def generate_build_for_weapon(
        self,
        weapon_id: str,
        config: BuildGeneratorConfig,
        language: str = "en"
    ) -> Optional[GeneratedBuild]:
        """
        Generate a build for a specific weapon.
        
        Args:
            weapon_id: Tarkov.dev API weapon ID
            config: Build generation configuration
            language: Language for names (ru/en)
            
        Returns:
            GeneratedBuild or None if generation failed
        """
        # Get weapon details
        weapon_data = await self.api.get_weapon_details(weapon_id)
        if not weapon_data:
            logger.warning(f"Could not fetch weapon details for {weapon_id}")
            return None
        
        weapon_price = weapon_data.get("avg24hPrice", 0) or 0
        
        # Handle unlimited budget (None)
        if config.budget is None or config.budget <= 0:
            remaining_budget = 999999999  # Effectively unlimited
        else:
            remaining_budget = config.budget - weapon_price
            
            if remaining_budget < 0:
                logger.warning(f"Weapon price {weapon_price} exceeds budget {config.budget}")
                return None
        
        weapon_name = weapon_data.get("name", "Unknown")
        
        # Get weapon slots
        slots = await self.compatibility.get_weapon_slots(weapon_id)
        if not slots:
            logger.warning(f"No slots found for weapon {weapon_id}")
            return None
        
        # Generate modules for each slot
        selected_modules = {}
        total_module_cost = 0
        
        # Prioritize required slots first
        required_slots = [s for s in slots if s.get("required", False)]
        optional_slots = [s for s in slots if not s.get("required", False)]
        
        # Process required slots
        for slot in required_slots:
            module = await self._select_module_for_slot(
                slot, remaining_budget - total_module_cost, config, language
            )
            if module:
                slot_name = slot.get("nameId") or slot.get("name")
                selected_modules[slot_name] = module
                module_price = self._get_module_price(module, config.use_flea_only)
                total_module_cost += module_price
        
        # Process optional slots with remaining budget
        random.shuffle(optional_slots)  # Randomize order
        for slot in optional_slots:
            if total_module_cost >= remaining_budget:
                break
            
            # 10% chance to skip optional slots for variety (reduced to add more mods)
            if random.random() < 0.1:
                continue
            
            module = await self._select_module_for_slot(
                slot, remaining_budget - total_module_cost, config, language
            )
            if module:
                slot_name = slot.get("nameId") or slot.get("name")
                selected_modules[slot_name] = module
                module_price = self._get_module_price(module, config.use_flea_only)
                total_module_cost += module_price
        
        # Calculate final stats
        base_props = weapon_data.get("properties", {})
        base_ergo = base_props.get("ergonomics", 0)
        base_recoil = base_props.get("recoilVertical", 100)
        
        final_ergo, final_recoil_v, final_recoil_h = self._calculate_build_stats(
            base_ergo, base_recoil, selected_modules
        )
        
        # Evaluate tier
        has_sight = any("sight" in slot.lower() or "scope" in slot.lower() 
                       for slot in selected_modules.keys())
        has_stock = any("stock" in slot.lower() 
                       for slot in selected_modules.keys())
        has_grip = any("grip" in slot.lower() or "pistol" in slot.lower()
                      for slot in selected_modules.keys())
        
        required_slot_names = [s.get("nameId") or s.get("name") for s in required_slots]
        has_all_required = all(
            slot_name in selected_modules for slot_name in required_slot_names
        )
        
        tier = self.tier_eval.evaluate_build(
            ergonomics=final_ergo,
            recoil_vertical=final_recoil_v,
            recoil_horizontal=final_recoil_h,
            total_cost=weapon_price + total_module_cost,
            has_all_required_slots=has_all_required,
            has_sight=has_sight,
            has_stock=has_stock,
            has_grip=has_grip,
            weapon_base_ergonomics=base_ergo,
            weapon_base_recoil=base_recoil
        )
        
        # Determine availability
        available_from = self._get_availability(weapon_data, selected_modules, config)
        
        return GeneratedBuild(
            weapon_id=weapon_id,
            weapon_name=weapon_name,
            weapon_data=weapon_data,
            modules=selected_modules,
            total_cost=weapon_price + total_module_cost,
            remaining_budget=remaining_budget - total_module_cost,
            ergonomics=final_ergo,
            recoil_vertical=final_recoil_v,
            recoil_horizontal=final_recoil_h,
            tier_rating=tier,
            available_from=available_from
        )
    
    async def _select_weapon(
        self, 
        config: BuildGeneratorConfig,
        language: str
    ) -> Optional[Dict]:
        """Select a suitable weapon within budget."""
        weapons = await self.api.get_all_weapons(lang=language)
        
        # Filter by type if specified - be more flexible with matching
        if config.weapon_type:
            # Log unique categories for debugging
            unique_cats = set()
            for w in weapons:
                cat_name = w.get("category", {}).get("name", "")
                if cat_name:
                    unique_cats.add(cat_name)
            logger.info(f"Available categories: {sorted(unique_cats)}")
            
            filtered = []
            search_term = config.weapon_type.lower().replace(" ", "")
            for w in weapons:
                cat_name = w.get("category", {}).get("name", "").lower().replace(" ", "")
                # Match if weapon_type is in category name or vice versa (without spaces)
                if search_term in cat_name or cat_name in search_term:
                    filtered.append(w)
                    logger.debug(f"Matched weapon: {w.get('name')} with category: {w.get('category', {}).get('name')}")
            weapons = filtered
            logger.info(f"Filtered to {len(weapons)} weapons for category '{config.weapon_type}'")
        
        # Handle unlimited budget (None)
        if not config.budget or config.budget <= 0:
            # No budget limit - select any weapon with valid price
            suitable_weapons = [w for w in weapons if w.get("avg24hPrice")]
            if suitable_weapons:
                # Sort by price and pick from top tier
                suitable_weapons.sort(key=lambda w: w.get("avg24hPrice"), reverse=True)
                top_tier_count = max(1, len(suitable_weapons) // 3)
                return random.choice(suitable_weapons[:top_tier_count])
            return None
        
        # Universal smart budget allocation for ANY budget:
        # - Weapon takes 30-50% of budget (leaves 50-70% for mods)
        # - Higher budgets slightly increase minimum percentage
        # - This works for budgets from 100k to 100M+
        
        # Calculate min percentage based on budget (scales with budget size)
        # 100k budget: 25% min
        # 500k budget: 30% min  
        # 1M budget: 33% min
        # 5M+ budget: 35% min
        if config.budget < 200000:
            min_percentage = 0.25
        elif config.budget < 500000:
            min_percentage = 0.28
        elif config.budget < 1000000:
            min_percentage = 0.32
        else:
            min_percentage = 0.35
        
        max_percentage = 0.50  # Always 50% max to leave room for mods
        
        min_weapon_price = int(config.budget * min_percentage)
        max_weapon_price = int(config.budget * max_percentage)
        
        logger.info(f"Budget range for weapon: {min_weapon_price:,} - {max_weapon_price:,}")
        
        # Filter weapons in appropriate price range
        # Only include weapons with valid prices (not None)
        suitable_weapons = [
            w for w in weapons 
            if w.get("avg24hPrice") and min_weapon_price <= w.get("avg24hPrice") <= max_weapon_price
        ]
        
        # If no weapons in range, fall back to most expensive affordable weapon
        if not suitable_weapons:
            logger.info(f"No weapons in price range {min_weapon_price}-{max_weapon_price}, using most expensive affordable weapon")
            affordable_weapons = [
                w for w in weapons 
                if w.get("avg24hPrice") and w.get("avg24hPrice") <= max_weapon_price
            ]
            
            if not affordable_weapons:
                logger.warning("No affordable weapons found")
                return None
            
            # Sort by price descending and pick the most expensive (best value for budget)
            affordable_weapons.sort(key=lambda w: w.get("avg24hPrice"), reverse=True)
            # Take top 5 most expensive and randomly pick one
            return random.choice(affordable_weapons[:5])
        
        if not suitable_weapons:
            logger.warning("No weapons with valid prices found")
            return None
        
        # Prefer more expensive weapons within range (better base stats)
        # Sort by price descending and pick from top 30%
        suitable_weapons.sort(key=lambda w: w.get("avg24hPrice"), reverse=True)
        top_tier_count = max(1, len(suitable_weapons) // 3)
        top_tier_weapons = suitable_weapons[:top_tier_count]
        
        return random.choice(top_tier_weapons)
    
    async def _select_module_for_slot(
        self,
        slot: Dict,
        remaining_budget: int,
        config: BuildGeneratorConfig,
        language: str
    ) -> Optional[Dict]:
        """Select a module for a specific slot."""
        compatible_modules = await self.compatibility.get_compatible_modules(
            slot.get("id", ""), 
            slot.get("nameId", ""),
            language
        )
        
        if not compatible_modules:
            # Use allowed items from filters
            filters = slot.get("filters", {})
            compatible_modules = filters.get("allowedItems", [])
        
        # Filter out modules without valid ID
        compatible_modules = [
            m for m in compatible_modules
            if m.get("id")
        ]
        
        logger.debug(f"Found {len(compatible_modules)} compatible modules for slot {slot.get('nameId')}")
        
        if not compatible_modules:
            logger.debug(f"No compatible modules for slot {slot.get('nameId')}")
            return None
        
        # For unlimited budget, skip budget filtering
        if not config.budget or config.budget <= 0:
            affordable = compatible_modules
        else:
            # Filter by budget
            affordable = [
                m for m in compatible_modules
                if self._get_module_price(m, config.use_flea_only) <= remaining_budget
            ]
        
        logger.debug(f"After budget filter: {len(affordable)} modules")
        
        if not affordable:
            logger.debug(f"No affordable modules for budget {remaining_budget}")
            return None
        
        # Filter by trader loyalty if not using flea only
        trader_available = affordable
        if not config.use_flea_only:
            trader_available = [
                m for m in affordable
                if self._is_module_available(m, config.trader_levels)
            ]
        
        logger.debug(f"After loyalty filter: {len(trader_available)} modules")
        
        # If no modules available from traders, use flea market
        if not trader_available:
            logger.debug("No trader modules available, using flea market")
            trader_available = affordable
        
        if not affordable:
            return None
        
        # Select based on priorities
        if config.prioritize_ergonomics:
            # Sort by ergonomics (if available in module data)
            return random.choice(affordable)  # Simplified
        elif config.prioritize_recoil:
            return random.choice(affordable)  # Simplified
        else:
            return random.choice(affordable)
    
    def _get_module_price(self, module: Dict, use_flea: bool) -> int:
        """Get module price (flea or trader)."""
        if use_flea:
            return module.get("avg24hPrice", 0) or 0
        
        # Try to get trader price from sellFor
        sell_for = module.get("sellFor", [])
        if sell_for:
            trader_prices = [
                s.get("price", 0) for s in sell_for
                if s.get("vendor", {}).get("name") != "Flea Market"
            ]
            if trader_prices:
                return min(trader_prices)
        
        # Fallback to flea price
        return module.get("avg24hPrice", 0) or 0
    
    def _is_module_available(self, module: Dict, trader_levels: Dict[str, int]) -> bool:
        """Check if module is available from traders."""
        sell_for = module.get("sellFor", [])
        
        for seller in sell_for:
            vendor = seller.get("vendor", {})
            vendor_name = vendor.get("normalizedName", "").lower()
            min_level = vendor.get("minTraderLevel", 1)
            
            if vendor_name in trader_levels:
                if trader_levels[vendor_name] >= min_level:
                    return True
        
        return False
    
    def _calculate_build_stats(
        self,
        base_ergo: int,
        base_recoil: int,
        modules: Dict[str, Dict]
    ) -> Tuple[int, int, int]:
        """
        Calculate final build statistics.
        Note: This is a simplified calculation. Real calculation requires 
        module properties which may not be available in all API responses.
        """
        # This is simplified - in reality, each module affects stats differently
        final_ergo = base_ergo
        final_recoil_v = base_recoil
        final_recoil_h = base_recoil
        
        # Apply module modifiers (if available)
        for slot_name, module in modules.items():
            props = module.get("properties", {})
            if props:
                ergo_mod = props.get("ergonomics", 0)
                recoil_mod = props.get("recoil", 0)
                
                final_ergo += ergo_mod
                final_recoil_v += recoil_mod
        
        return final_ergo, final_recoil_v, final_recoil_h
    
    def _get_availability(
        self,
        weapon_data: Dict,
        modules: Dict[str, Dict],
        config: BuildGeneratorConfig
    ) -> List[str]:
        """Get list of where build components are available."""
        sources = set()
        
        if config.use_flea_only:
            sources.add("Flea Market")
        else:
            # Check weapon availability
            weapon_sell = weapon_data.get("sellFor", [])
            for seller in weapon_sell:
                vendor_name = seller.get("vendor", {}).get("name")
                if vendor_name:
                    sources.add(vendor_name)
            
            # Check modules
            for module in modules.values():
                sell_for = module.get("sellFor", [])
                for seller in sell_for:
                    vendor_name = seller.get("vendor", {}).get("name")
                    if vendor_name:
                        sources.add(vendor_name)
        
        return sorted(list(sources))
