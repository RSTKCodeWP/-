"""Service for generating builds based on quest requirements."""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QuestRequirement:
    """Quest build requirement."""
    name: str
    compare_method: str  # ">=", "<=", "==", etc.
    value: float


@dataclass
class QuestBuildRequirements:
    """All requirements for a quest build."""
    weapon_id: str
    weapon_name: str
    requirements: List[QuestRequirement]


class QuestBuildService:
    """Service for generating builds that meet quest requirements."""
    
    def __init__(self, api_client):
        """Initialize the service."""
        self.api = api_client
    
    def parse_quest_requirements(self, quest_objective: Dict) -> Optional[QuestBuildRequirements]:
        """Parse quest objective to extract build requirements.
        
        Args:
            quest_objective: Quest objective dict with attributes
            
        Returns:
            QuestBuildRequirements or None if not a build quest
        """
        if quest_objective.get('type') != 'buildWeapon':
            return None
        
        # Get weapon info
        item = quest_objective.get('item')
        if not item:
            return None
        
        weapon_id = item.get('id')
        weapon_name = item.get('name')
        
        # Parse attributes
        attributes = quest_objective.get('attributes', [])
        requirements = []
        
        for attr in attributes:
            name = attr.get('name')
            requirement = attr.get('requirement', {})
            compare_method = requirement.get('compareMethod')
            value = requirement.get('value')
            
            if name and compare_method and value is not None:
                requirements.append(QuestRequirement(
                    name=name,
                    compare_method=compare_method,
                    value=float(value)
                ))
        
        if not requirements:
            return None
        
        return QuestBuildRequirements(
            weapon_id=weapon_id,
            weapon_name=weapon_name,
            requirements=requirements
        )
    
    async def generate_quest_build(
        self,
        requirements: QuestBuildRequirements,
        language: str = "en"
    ) -> Optional[Dict]:
        """Generate a build that meets quest requirements.
        
        Args:
            requirements: Quest build requirements
            language: Language for names
            
        Returns:
            Build dict or None if cannot satisfy requirements
        """
        # Get weapon details
        weapon_details = await self.api.get_weapon_details(requirements.weapon_id)
        if not weapon_details:
            logger.warning(f"Could not get weapon details for {requirements.weapon_id}")
            return None
        
        # Get base weapon stats
        props = weapon_details.get('properties', {})
        
        # Start with base weapon stats
        current_stats = {
            'ergonomics': props.get('ergonomics', 0),
            'recoil': props.get('recoilVertical', 0),
            'weight': 0,  # Weight not available in API, set to 0
            'height': props.get('defaultHeight', 0),
            'width': props.get('defaultWidth', 0),
            'durability': 100,  # Default durability
            'accuracy': 0,
            'effectiveDistance': 0,
            'magazineCapacity': 30,  # Default mag capacity
            'muzzleVelocity': 0
        }
        
        selected_modules = []
        total_cost = weapon_details.get('avg24hPrice', 0)
        
        # Get all available slots
        slots = props.get('slots', [])
        
        # Start with default preset as base
        default_preset = props.get('defaultPreset')
        if default_preset:
            contained_items = default_preset.get('containsItems', [])
            if contained_items:
                # Create a mapping of item IDs to slot names
                item_to_slot = {}
                for slot in slots:
                    slot_name = slot.get('name')
                    filters = slot.get('filters', {})
                    allowed_items = filters.get('allowedItems', [])
                    for allowed_item in allowed_items:
                        item_to_slot[allowed_item.get('id')] = slot_name
                
                for item in contained_items:
                    item_data = item.get('item')
                    if item_data:
                        item_id = item_data.get('id')
                        slot_name = item_to_slot.get(item_id)
                        
                        # Store properties with module for later stat calculations
                        item_props = item_data.get('properties', {})
                        
                        # Extract trader info
                        trader_info = self._get_best_trader(item_data.get('buyFor', []))
                        
                        module_info = {
                            'id': item_id,
                            'name': item_data.get('name', 'Unknown'),
                            'price': item_data.get('avg24hPrice') or 0,
                            'slot': slot_name,
                            'ergonomics': item_props.get('ergonomics', 0),
                            'recoilModifier': item_props.get('recoilModifier', 0),
                            'capacity': item_props.get('capacity', 0),
                            'trader': trader_info['trader'],
                            'trader_level': trader_info['level'],
                            'trader_price': trader_info['price']
                        }
                        selected_modules.append(module_info)
                        total_cost += module_info['price']
                        
                        # Apply module stats
                        if module_info['ergonomics']:
                            current_stats['ergonomics'] += module_info['ergonomics']
                        if module_info['recoilModifier']:
                            modifier = module_info['recoilModifier']
                            current_stats['recoil'] = int(current_stats['recoil'] * (1 + modifier / 100))
                
                logger.info(f"Loaded {len(selected_modules)} modules from default preset")
        
        # Check which requirements are not met
        unmet_requirements = []
        for req in requirements.requirements:
            stat_value = current_stats.get(req.name, 0)
            is_met = self._check_single_requirement(stat_value, req)
            if not is_met:
                unmet_requirements.append(req)
        
        # If requirements not met, try to improve with better modules
        if unmet_requirements:
            logger.info(f"Trying to meet {len(unmet_requirements)} unmet requirements")
            logger.info(f"Current stats: ergonomics={current_stats.get('ergonomics', 0)}, recoil={current_stats.get('recoil', 0)}")
            
            improved_modules, improved_stats, improved_cost = await self._optimize_modules(
                weapon_details,
                slots,
                current_stats.copy(),
                unmet_requirements,
                selected_modules.copy()
            )
            
            if improved_modules:
                # Replace selected modules with optimized ones
                selected_modules = improved_modules
                current_stats = improved_stats
                total_cost = improved_cost
                logger.info(f"Optimized build with {len(selected_modules)} modules")
                logger.info(f"New stats: ergonomics={current_stats.get('ergonomics', 0)}, recoil={current_stats.get('recoil', 0)}")
        
        # Check if current stats meet requirements
        meets_requirements = self._check_requirements(current_stats, requirements.requirements)
        
        if not meets_requirements:
            logger.warning(f"Cannot meet quest requirements for {requirements.weapon_name}")
            logger.warning(f"Current stats: {current_stats}")
            logger.warning(f"Requirements: {requirements.requirements}")
        
        return {
            'weapon': weapon_details,
            'modules': selected_modules,
            'total_cost': total_cost,
            'stats': current_stats,
            'meets_requirements': meets_requirements,
            'requirements': requirements
        }
    
    def _get_best_trader(self, buy_for: list) -> dict:
        """Extract best trader offer (cheapest with lowest loyalty level).
        
        Args:
            buy_for: List of vendor offers from API
            
        Returns:
            Dict with trader name, level, and price
        """
        if not buy_for:
            return {'trader': 'Flea Market', 'level': 15, 'price': 0}
        
        # Find cheapest trader offer
        best_offer = None
        for offer in buy_for:
            vendor = offer.get('vendor', {})
            vendor_name = vendor.get('name', 'Unknown')
            price = offer.get('priceRUB', 0)
            
            # Extract loyalty level from requirements
            requirements = offer.get('requirements', [])
            loyalty_level = 1
            for req in requirements:
                if req.get('type') == 'loyaltyLevel':
                    loyalty_level = req.get('value', 1)
                    break
            
            if vendor_name and vendor_name != 'Flea Market':
                if not best_offer or price < best_offer['price']:
                    best_offer = {
                        'trader': vendor_name,
                        'level': loyalty_level,
                        'price': price
                    }
        
        return best_offer or {'trader': 'Flea Market', 'level': 15, 'price': 0}
    
    def _check_single_requirement(
        self,
        stat_value: float,
        requirement: QuestRequirement
    ) -> bool:
        """Check if a single stat meets its requirement."""
        if requirement.compare_method == '>=':
            return stat_value >= requirement.value
        elif requirement.compare_method == '<=':
            return stat_value <= requirement.value
        elif requirement.compare_method == '==':
            return stat_value == requirement.value
        elif requirement.compare_method == '>':
            return stat_value > requirement.value
        elif requirement.compare_method == '<':
            return stat_value < requirement.value
        return True
    
    def _check_requirements(
        self,
        stats: Dict[str, float],
        requirements: List[QuestRequirement]
    ) -> bool:
        """Check if current stats meet all requirements.
        
        Args:
            stats: Current weapon stats
            requirements: List of requirements
            
        Returns:
            True if all requirements met
        """
        for req in requirements:
            stat_value = stats.get(req.name, 0)
            if not self._check_single_requirement(stat_value, req):
                return False
        return True
    
    async def _optimize_modules(
        self,
        weapon_details: Dict,
        slots: List[Dict],
        current_stats: Dict[str, float],
        unmet_requirements: List[QuestRequirement],
        current_modules: List[Dict]
    ) -> tuple:
        """Try to optimize module selection to meet requirements.
        
        Args:
            weapon_details: Weapon details from API
            slots: Available slots for modules
            current_stats: Current weapon stats
            unmet_requirements: Requirements not yet met
            current_modules: Current modules from preset
            
        Returns:
            (modules, stats, cost) tuple or (None, None, None) if can't optimize
        """
        working_stats = current_stats.copy()
        working_modules = current_modules.copy()
        weapon_price = weapon_details.get('avg24hPrice', 0)
        
        # Track used slots to avoid conflicts
        used_slots = set()
        
        # Calculate total cost from current modules
        working_cost = weapon_price + sum(m.get('price', 0) for m in working_modules)
        
        # For each unmet requirement, find best upgrades
        # Process ergonomics/recoil first, then magazineCapacity
        improvements_made = False
        
        priority_order = ['ergonomics', 'recoil', 'magazineCapacity']
        sorted_requirements = sorted(
            [r for r in unmet_requirements if r.name in priority_order],
            key=lambda r: priority_order.index(r.name)
        )
        
        for req in sorted_requirements:
            
            logger.info(f"Looking for modules to improve {req.name}")
            logger.info(f"Current {req.name}: {working_stats.get(req.name, 0)}, Required: {req.compare_method} {req.value}")
            
            # Find all modules that improve this stat, sorted by improvement
            candidates = []
            
            for slot in slots:
                slot_name = slot.get('name')
                if slot_name in used_slots:
                    continue
                    
                slot_filters = slot.get('filters', {})
                allowed_items = slot_filters.get('allowedItems', [])
                
                for item in allowed_items:
                    item_props = item.get('properties', {})
                    
                    # Calculate improvement
                    improvement = 0
                    if req.name == 'ergonomics':
                        ergo = item_props.get('ergonomics', 0)
                        if ergo > 0:
                            improvement = ergo
                    elif req.name == 'recoil':
                        recoil_mod = item_props.get('recoilModifier', 0)
                        if recoil_mod < 0:
                            improvement = abs(recoil_mod)
                    elif req.name == 'magazineCapacity':
                        capacity = item_props.get('capacity', 0)
                        current_capacity = working_stats.get('magazineCapacity', 0)
                        if capacity >= req.value and capacity > current_capacity:
                            # For magazines that meet capacity requirement, prioritize ERGONOMICS
                            # Since both 60-round and 95-round mags meet requirement,
                            # choose the one with least negative impact on ergonomics
                            ergo_impact = item_props.get('ergonomics', 0)
                            # Higher ergonomics = better. Add 50 to make it always positive.
                            # A mag with -3 ergo gets score 47, a mag with -21 ergo gets score 29
                            improvement = 50 + ergo_impact
                            # If ergonomics are equal, prefer slightly higher capacity
                            improvement += (capacity - req.value) * 0.01
                    
                    if improvement > 0:
                        trader_info = self._get_best_trader(item.get('buyFor', []))
                        candidates.append({
                            'id': item.get('id'),
                            'name': item.get('name', 'Unknown'),
                            'price': item.get('avg24hPrice') or 0,
                            'slot': slot_name,
                            'improvement': improvement,
                            'ergonomics': item_props.get('ergonomics', 0),
                            'recoilModifier': item_props.get('recoilModifier', 0),
                            'capacity': item_props.get('capacity', 0),
                            'trader': trader_info['trader'],
                            'trader_level': trader_info['level'],
                            'trader_price': trader_info['price']
                        })
            
            # Sort by improvement (best first)
            candidates.sort(key=lambda x: x['improvement'], reverse=True)
            logger.info(f"Found {len(candidates)} candidates for {req.name}")
            if req.name == 'magazineCapacity' and candidates:
                for i, cand in enumerate(candidates[:3], 1):
                    logger.info(f"  {i}. {cand['name']}: capacity={cand.get('capacity', 0)}, ergo={cand.get('ergonomics', 0)}, improvement={cand['improvement']:.1f}")
            
            # Take top candidates until requirement is met
            for candidate in candidates[:5]:  # Limit to top 5 per requirement
                if self._check_single_requirement(working_stats.get(req.name, 0), req):
                    break
                
                # Special handling for magazines with negative ergonomics
                will_need_compensation = False
                if req.name == 'magazineCapacity' and candidate.get('ergonomics', 0) < 0:
                    # Check if this will cause ergonomics to drop below requirement
                    ergo_req = next((r for r in unmet_requirements if r.name == 'ergonomics'), None)
                    if ergo_req:
                        projected_ergo = working_stats.get('ergonomics', 0) + candidate.get('ergonomics', 0)
                        if projected_ergo < ergo_req.value:
                            will_need_compensation = True
                            logger.info(f"Magazine {candidate['name']} will reduce ergonomics, will compensate")
                
                # Check if we're replacing an existing module in this slot
                replaced_module = None
                for i, existing_mod in enumerate(working_modules):
                    if existing_mod.get('slot') == candidate['slot']:
                        replaced_module = existing_mod
                        working_modules[i] = {
                            'id': candidate['id'],
                            'name': candidate['name'],
                            'price': candidate['price'],
                            'slot': candidate['slot'],
                            'ergonomics': candidate['ergonomics'],
                            'recoilModifier': candidate['recoilModifier'],
                            'capacity': candidate.get('capacity', 0),
                            'trader': candidate.get('trader', 'Flea Market'),
                            'trader_level': candidate.get('trader_level', 15),
                            'trader_price': candidate.get('trader_price', 0)
                        }
                        working_cost = working_cost - replaced_module.get('price', 0) + candidate['price']
                        break
                
                # If not replacing, add new module
                if not replaced_module:
                    module_info = {
                        'id': candidate['id'],
                        'name': candidate['name'],
                        'price': candidate['price'],
                        'slot': candidate['slot'],
                        'ergonomics': candidate['ergonomics'],
                        'recoilModifier': candidate['recoilModifier'],
                        'capacity': candidate.get('capacity', 0),
                        'trader': candidate.get('trader', 'Flea Market'),
                        'trader_level': candidate.get('trader_level', 15),
                        'trader_price': candidate.get('trader_price', 0)
                    }
                    working_modules.append(module_info)
                    working_cost += candidate['price']
                
                used_slots.add(candidate['slot'])
                
                # Update stats
                if replaced_module:
                    # Subtract old module's stats
                    old_ergo = replaced_module.get('ergonomics', 0)
                    if old_ergo:
                        working_stats['ergonomics'] -= old_ergo
                    
                    # Add new module's stats
                    if candidate['ergonomics']:
                        working_stats['ergonomics'] += candidate['ergonomics']
                    
                    # Update capacity
                    if candidate.get('capacity'):
                        working_stats['magazineCapacity'] = candidate['capacity']
                else:
                    # New module - just add stats
                    if candidate['ergonomics']:
                        working_stats['ergonomics'] += candidate['ergonomics']
                    if candidate['recoilModifier']:
                        modifier = candidate['recoilModifier']
                        working_stats['recoil'] = int(working_stats['recoil'] * (1 + modifier / 100))
                    if candidate.get('capacity'):
                        working_stats['magazineCapacity'] = candidate['capacity']
                
                improvements_made = True
                logger.info(f"Added {candidate['name']} (+{candidate['improvement']} {req.name})")
                
                # If we need compensation, add ergonomics-boosting modules
                if will_need_compensation:
                    ergo_req = next((r for r in unmet_requirements if r.name == 'ergonomics'), None)
                    if ergo_req and not self._check_single_requirement(working_stats.get('ergonomics', 0), ergo_req):
                        logger.info("Adding ergonomics compensation modules...")
                        # Find ergonomics-boosting modules from unused slots
                        ergo_candidates = []
                        for comp_slot in slots:
                            comp_slot_name = comp_slot.get('name')
                            if comp_slot_name in used_slots:
                                continue
                            comp_filters = comp_slot.get('filters', {})
                            comp_allowed = comp_filters.get('allowedItems', [])
                            for comp_item in comp_allowed:
                                comp_props = comp_item.get('properties', {})
                                comp_ergo = comp_props.get('ergonomics', 0)
                                if comp_ergo > 0:
                                    ergo_candidates.append({
                                        'id': comp_item.get('id'),
                                        'name': comp_item.get('name', 'Unknown'),
                                        'price': comp_item.get('avg24hPrice') or 0,
                                        'slot': comp_slot_name,
                                        'ergonomics': comp_ergo,
                                        'recoilModifier': comp_props.get('recoilModifier', 0),
                                        'capacity': 0
                                    })
                        
                        # Sort by ergonomics (best first)
                        ergo_candidates.sort(key=lambda x: x['ergonomics'], reverse=True)
                        
                        # Add top ergonomics modules until requirement is met
                        for ergo_mod in ergo_candidates[:3]:  # Add up to 3 modules
                            if self._check_single_requirement(working_stats.get('ergonomics', 0), ergo_req):
                                break
                            
                            working_modules.append({
                                'id': ergo_mod['id'],
                                'name': ergo_mod['name'],
                                'price': ergo_mod['price'],
                                'slot': ergo_mod['slot'],
                                'ergonomics': ergo_mod['ergonomics'],
                                'recoilModifier': ergo_mod['recoilModifier'],
                                'capacity': 0,
                                'trader': ergo_mod.get('trader', 'Flea Market'),
                                'trader_level': ergo_mod.get('trader_level', 15),
                                'trader_price': ergo_mod.get('trader_price', 0)
                            })
                            working_cost += ergo_mod['price']
                            used_slots.add(ergo_mod['slot'])
                            working_stats['ergonomics'] += ergo_mod['ergonomics']
                            logger.info(f"Compensation: Added {ergo_mod['name']} (+{ergo_mod['ergonomics']} ergonomics)")
        
        if improvements_made:
            return (working_modules, working_stats, working_cost)
        
        return (None, None, None)
    
    def format_requirements_text(
        self,
        requirements: QuestBuildRequirements,
        language: str = "ru"
    ) -> str:
        """Format requirements as readable text.
        
        Args:
            requirements: Quest build requirements
            language: Language code
            
        Returns:
            Formatted text
        """
        # Translate attribute names
        attr_names = {
            'ergonomics': 'Эргономика' if language == 'ru' else 'Ergonomics',
            'recoil': 'Отдача' if language == 'ru' else 'Recoil',
            'durability': 'Прочность' if language == 'ru' else 'Durability',
            'weight': 'Вес' if language == 'ru' else 'Weight',
            'height': 'Высота' if language == 'ru' else 'Height',
            'width': 'Ширина' if language == 'ru' else 'Width',
            'accuracy': 'Точность' if language == 'ru' else 'Accuracy',
            'effectiveDistance': 'Дистанция' if language == 'ru' else 'Effective Distance',
            'magazineCapacity': 'Емкость магазина' if language == 'ru' else 'Magazine Capacity',
            'muzzleVelocity': 'Начальная скорость' if language == 'ru' else 'Muzzle Velocity'
        }
        
        text = f"🎯 **{'Требования' if language == 'ru' else 'Requirements'}:**\n"
        
        for req in requirements.requirements:
            # Skip requirements with value 0 (usually not important)
            if req.value == 0 and req.compare_method == '>=':
                continue
            
            attr_name = attr_names.get(req.name, req.name)
            operator = req.compare_method
            value = int(req.value) if req.value == int(req.value) else req.value
            
            text += f"  • {attr_name} {operator} {value}\n"
        
        return text
