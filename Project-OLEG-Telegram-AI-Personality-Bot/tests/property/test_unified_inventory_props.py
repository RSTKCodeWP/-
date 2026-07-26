"""Property-based tests for Unified Inventory functionality.

Feature: unified-inventory
Tests the unified inventory system for correct behavior.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# ============================================================================
# Simplified models for isolated testing (no database dependencies)
# ============================================================================

@dataclass
class MockInventoryItem:
    """Mock inventory item for testing."""
    item_type: str
    item_name: str
    quantity: int
    equipped: bool = False
    item_data: Optional[str] = None


@dataclass
class MockItemInfo:
    """Mock item info from catalog."""
    item_type: str
    name: str
    emoji: str
    effect: Dict[str, Any]


# Mock item catalog
MOCK_ITEM_CATALOG = {
    "basic_rod": MockItemInfo("basic_rod", "Базовая удочка", "🎣", {"rod_bonus": 0.0}),
    "silver_rod": MockItemInfo("silver_rod", "Серебряная удочка", "🥈", {"rod_bonus": 0.1}),
    "golden_rod": MockItemInfo("golden_rod", "Золотая удочка", "🥇", {"rod_bonus": 0.25}),
    "pp_cream_small": MockItemInfo("pp_cream_small", "Мазь 'Подрастай'", "🧴", {"pp_boost_min": 1, "pp_boost_max": 3}),
    "pp_cream_medium": MockItemInfo("pp_cream_medium", "Крем 'Титан'", "🧴", {"pp_boost_min": 2, "pp_boost_max": 5}),
    "pp_cage": MockItemInfo("pp_cage", "Пенис-клетка", "🔒", {"protection": True, "duration_hours": 24}),
    "energy_drink": MockItemInfo("energy_drink", "Энергетик", "🥤", {"reset_fishing_cooldown": True}),
    "lucky_charm": MockItemInfo("lucky_charm", "Талисман удачи", "🍀", {"luck_bonus": 0.1}),
    "lootbox_common": MockItemInfo("lootbox_common", "Обычный лутбокс", "📦", {"lootbox_tier": "common"}),
}


# Item type categories
INVENTORY_CATEGORIES = {
    "rods": ["basic_rod", "silver_rod", "golden_rod", "legendary_rod"],
    "pp_items": ["pp_cream_small", "pp_cream_medium", "pp_cream_large", "pp_cream_titan", "pp_cage"],
    "boosters": ["energy_drink", "lucky_charm", "shield", "vip_status", "double_xp"],
    "lootboxes": ["lootbox_common", "lootbox_rare", "lootbox_epic", "lootbox_legendary"],
    "roosters": ["rooster_common", "rooster_rare", "rooster_epic"],
}


def get_item_category(item_type: str) -> str:
    """Get category for an item type."""
    for cat_id, items in INVENTORY_CATEGORIES.items():
        if item_type in items:
            return cat_id
    return "other"


def is_rod(item_type: str) -> bool:
    """Check if item is a fishing rod."""
    return item_type.endswith("_rod")


def filter_zero_quantity_items(items: List[MockInventoryItem]) -> List[MockInventoryItem]:
    """
    Filter out items with zero or negative quantity.
    
    This is the core logic being tested - inventory display should
    exclude items with quantity <= 0.
    """
    return [item for item in items if item.quantity > 0]


def build_inventory_display(items: List[MockInventoryItem]) -> str:
    """
    Build inventory display text.
    
    Mirrors the logic from app/handlers/inventory.py build_inventory_text()
    """
    # Filter out zero-quantity items
    filtered_items = filter_zero_quantity_items(items)
    
    if not filtered_items:
        return "📭 Пусто!"
    
    # Group items by category
    categorized: Dict[str, List[MockInventoryItem]] = {cat_id: [] for cat_id in INVENTORY_CATEGORIES}
    categorized["other"] = []
    
    for item in filtered_items:
        cat = get_item_category(item.item_type)
        categorized[cat].append(item)
    
    # Build text
    text_parts = ["🎒 ИНВЕНТАРЬ\n"]
    
    for cat_id, cat_items in categorized.items():
        if not cat_items:
            continue
        
        text_parts.append(f"\n{cat_id.upper()}:")
        for item in cat_items:
            item_info = MOCK_ITEM_CATALOG.get(item.item_type)
            if not item_info:
                # Use item name from inventory if not in catalog
                text_parts.append(f"  {item.item_name} x{item.quantity}")
                continue
            
            emoji = item_info.emoji
            name = item_info.name
            qty = item.quantity
            
            # Show equipped status for rods
            equipped_mark = ""
            if is_rod(item.item_type):
                bonus = item_info.effect.get("rod_bonus", 0)
                bonus_str = f" (+{int(bonus * 100)}%)" if bonus > 0 else ""
                if item.equipped:
                    equipped_mark = f" ✅{bonus_str}"
                else:
                    equipped_mark = bonus_str
            
            qty_str = f" x{qty}" if qty > 1 else ""
            text_parts.append(f"  {emoji} {name}{qty_str}{equipped_mark}")
    
    return "\n".join(text_parts)


def build_inventory_keyboard_items(items: List[MockInventoryItem]) -> List[str]:
    """
    Build list of item types that would appear in keyboard.
    
    Returns list of item_types that would have action buttons.
    """
    # Filter out zero-quantity items
    filtered_items = filter_zero_quantity_items(items)
    
    return [item.item_type for item in filtered_items]


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for generating valid item types
item_type_strategy = st.sampled_from([
    "basic_rod", "silver_rod", "golden_rod",
    "pp_cream_small", "pp_cream_medium", "pp_cage",
    "energy_drink", "lucky_charm", "lootbox_common"
])

# Strategy for generating inventory items with various quantities
inventory_item_strategy = st.builds(
    MockInventoryItem,
    item_type=item_type_strategy,
    item_name=st.text(min_size=1, max_size=20),
    quantity=st.integers(min_value=-5, max_value=10),  # Include negative and zero
    equipped=st.booleans()
)

# Strategy for generating a list of inventory items
inventory_list_strategy = st.lists(inventory_item_strategy, min_size=0, max_size=15)


# ============================================================================
# Property Tests
# ============================================================================

class TestInventoryDisplayExcludesZeroQuantity:
    """
    Property 7: Inventory display excludes zero-quantity items
    
    *For any* inventory display, no item with quantity ≤ 0 SHALL appear in the result.
    
    **Validates: Requirements 1.4**
    """

    @given(items=inventory_list_strategy)
    @settings(max_examples=100)
    def test_zero_quantity_items_excluded_from_display(self, items: List[MockInventoryItem]):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        For any inventory, items with quantity <= 0 should not appear in display text.
        """
        display_text = build_inventory_display(items)
        
        # Check that no zero-quantity item names appear in display
        for item in items:
            if item.quantity <= 0:
                item_info = MOCK_ITEM_CATALOG.get(item.item_type)
                if item_info:
                    # The item name should not appear in the display
                    # (unless another item with same name has positive quantity)
                    same_type_positive = any(
                        i.item_type == item.item_type and i.quantity > 0 
                        for i in items
                    )
                    if not same_type_positive:
                        # Item name should not be in display
                        assert item_info.name not in display_text or display_text == "📭 Пусто!", \
                            f"Item '{item_info.name}' with quantity {item.quantity} should not appear in display"

    @given(items=inventory_list_strategy)
    @settings(max_examples=100)
    def test_zero_quantity_items_excluded_from_keyboard(self, items: List[MockInventoryItem]):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        For any inventory, items with quantity <= 0 should not have action buttons.
        """
        keyboard_items = build_inventory_keyboard_items(items)
        
        # Check that no zero-quantity items are in keyboard
        for item in items:
            if item.quantity <= 0:
                # This specific item instance should not be in keyboard
                # But another item of same type with positive quantity could be
                same_type_positive = any(
                    i.item_type == item.item_type and i.quantity > 0 
                    for i in items
                )
                if not same_type_positive:
                    assert item.item_type not in keyboard_items, \
                        f"Item type '{item.item_type}' with quantity {item.quantity} should not have action button"

    @given(items=inventory_list_strategy)
    @settings(max_examples=100)
    def test_positive_quantity_items_included(self, items: List[MockInventoryItem]):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        For any inventory, items with quantity > 0 should appear in keyboard.
        """
        keyboard_items = build_inventory_keyboard_items(items)
        
        # Check that all positive-quantity items are in keyboard
        for item in items:
            if item.quantity > 0:
                assert item.item_type in keyboard_items, \
                    f"Item type '{item.item_type}' with quantity {item.quantity} should have action button"

    @given(
        positive_qty=st.integers(min_value=1, max_value=99),
        item_type=item_type_strategy
    )
    @settings(max_examples=100)
    def test_single_positive_item_appears(self, positive_qty: int, item_type: str):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        A single item with positive quantity should appear in display.
        """
        items = [MockInventoryItem(
            item_type=item_type,
            item_name="Test Item",
            quantity=positive_qty,
            equipped=False
        )]
        
        display_text = build_inventory_display(items)
        keyboard_items = build_inventory_keyboard_items(items)
        
        # Should not be empty
        assert display_text != "📭 Пусто!", "Display should not be empty for positive quantity item"
        assert len(keyboard_items) == 1, "Keyboard should have exactly one item"
        assert keyboard_items[0] == item_type, f"Keyboard should contain {item_type}"

    @given(
        zero_or_negative_qty=st.integers(min_value=-100, max_value=0),
        item_type=item_type_strategy
    )
    @settings(max_examples=100)
    def test_single_zero_or_negative_item_excluded(self, zero_or_negative_qty: int, item_type: str):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        A single item with zero or negative quantity should result in empty display.
        """
        items = [MockInventoryItem(
            item_type=item_type,
            item_name="Test Item",
            quantity=zero_or_negative_qty,
            equipped=False
        )]
        
        display_text = build_inventory_display(items)
        keyboard_items = build_inventory_keyboard_items(items)
        
        # Should be empty
        assert display_text == "📭 Пусто!", f"Display should be empty for quantity {zero_or_negative_qty}"
        assert len(keyboard_items) == 0, "Keyboard should be empty"

    @given(items=inventory_list_strategy)
    @settings(max_examples=100)
    def test_filter_function_removes_all_non_positive(self, items: List[MockInventoryItem]):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        The filter function should remove all items with quantity <= 0.
        """
        filtered = filter_zero_quantity_items(items)
        
        # All filtered items should have positive quantity
        for item in filtered:
            assert item.quantity > 0, f"Filtered item should have positive quantity, got {item.quantity}"
        
        # Count should match
        expected_count = sum(1 for item in items if item.quantity > 0)
        assert len(filtered) == expected_count, \
            f"Expected {expected_count} items after filter, got {len(filtered)}"

    @given(items=inventory_list_strategy)
    @settings(max_examples=100)
    def test_filter_preserves_positive_items(self, items: List[MockInventoryItem]):
        """
        Feature: unified-inventory, Property 7: Inventory display excludes zero-quantity items
        **Validates: Requirements 1.4**
        
        The filter function should preserve all items with quantity > 0.
        """
        filtered = filter_zero_quantity_items(items)
        filtered_types = [item.item_type for item in filtered]
        
        # All positive-quantity items should be preserved
        for item in items:
            if item.quantity > 0:
                assert item.item_type in filtered_types, \
                    f"Item type '{item.item_type}' with quantity {item.quantity} should be preserved"


# ============================================================================
# PP Cream Effect Functions (for isolated testing)
# ============================================================================

import random


def is_pp_cream(item_type: str) -> bool:
    """Check if item is a PP cream."""
    return item_type.startswith("pp_cream_")


@dataclass
class MockGameStat:
    """Mock game stat for testing."""
    size_cm: int


@dataclass
class MockEffectResult:
    """Mock effect result for testing."""
    success: bool
    message: str
    details: Dict[str, Any]


def apply_pp_cream_logic(
    item_type: str,
    current_size: int,
    has_item: bool,
    has_active_cage: bool,
    item_catalog: Dict[str, MockItemInfo]
) -> MockEffectResult:
    """
    Pure function implementing PP cream application logic.
    
    This mirrors the logic from app/handlers/inventory.py apply_pp_cream()
    but without database dependencies for isolated testing.
    
    Args:
        item_type: Type of PP cream item
        current_size: Current PP size in cm
        has_item: Whether user has the item in inventory
        has_active_cage: Whether user has active PP cage
        item_catalog: Item catalog to look up effect ranges
        
    Returns:
        MockEffectResult with success status and details
    """
    # Validate item type is a PP cream
    if not is_pp_cream(item_type):
        return MockEffectResult(
            success=False,
            message="❌ Это не мазь для PP!",
            details={}
        )
    
    # Get item info from catalog
    item_info = item_catalog.get(item_type)
    if not item_info:
        return MockEffectResult(
            success=False,
            message="❌ Неизвестный предмет",
            details={}
        )
    
    # Check if user has the item
    if not has_item:
        return MockEffectResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!",
            details={}
        )
    
    # Check for active PP Cage (blocks cream usage)
    if has_active_cage:
        return MockEffectResult(
            success=False,
            message="🔒 Клетка не даёт использовать мази! Сними через инвентарь.",
            details={"blocked_by": "pp_cage"}
        )
    
    # Get effect range from item catalog
    pp_boost_min = item_info.effect.get("pp_boost_min", 1)
    pp_boost_max = item_info.effect.get("pp_boost_max", 3)
    
    # Generate random increase within range
    increase = random.randint(pp_boost_min, pp_boost_max)
    
    # Calculate new size
    new_size = current_size + increase
    
    return MockEffectResult(
        success=True,
        message=f"🧴 Ты использовал {item_info.emoji} {item_info.name}!\n\n"
                f"📈 Твой PP вырос на +{increase} см!\n"
                f"📏 Новый размер: {new_size} см",
        details={
            "increase": increase,
            "old_size": current_size,
            "new_size": new_size,
            "item_type": item_type,
            "pp_boost_min": pp_boost_min,
            "pp_boost_max": pp_boost_max
        }
    )


# Extended mock catalog with all PP cream types
EXTENDED_MOCK_ITEM_CATALOG = {
    **MOCK_ITEM_CATALOG,
    "pp_cream_large": MockItemInfo("pp_cream_large", "Гель 'Мегамен'", "🧴", {"pp_boost_min": 5, "pp_boost_max": 10}),
    "pp_cream_titan": MockItemInfo("pp_cream_titan", "Эликсир 'Годзилла'", "🧪", {"pp_boost_min": 10, "pp_boost_max": 20}),
}


# ============================================================================
# Strategies for PP Cream Tests
# ============================================================================

# Strategy for PP cream types
pp_cream_type_strategy = st.sampled_from([
    "pp_cream_small",
    "pp_cream_medium",
    "pp_cream_large",
    "pp_cream_titan"
])

# Strategy for current PP size
pp_size_strategy = st.integers(min_value=0, max_value=1000)


# ============================================================================
# Property Tests for PP Cream
# ============================================================================

class TestPPCreamIncreasesWithinRange:
    """
    Property 2: PP cream increases size within defined range
    
    *For any* PP cream with effect range [min, max], using it SHALL increase 
    user's PP size by a value V where min ≤ V ≤ max.
    
    **Validates: Requirements 2.1**
    """

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_pp_cream_increase_within_range(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 2: PP cream increases size within defined range
        **Validates: Requirements 2.1**
        
        For any PP cream, the increase should be within the defined range.
        """
        # Apply cream (user has item, no cage)
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=False,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        # Should succeed
        assert result.success, f"PP cream application should succeed, got: {result.message}"
        
        # Get expected range from catalog
        item_info = EXTENDED_MOCK_ITEM_CATALOG[cream_type]
        expected_min = item_info.effect["pp_boost_min"]
        expected_max = item_info.effect["pp_boost_max"]
        
        # Verify increase is within range
        actual_increase = result.details["increase"]
        assert expected_min <= actual_increase <= expected_max, \
            f"Increase {actual_increase} should be in range [{expected_min}, {expected_max}]"
        
        # Verify new size calculation
        expected_new_size = current_size + actual_increase
        assert result.details["new_size"] == expected_new_size, \
            f"New size {result.details['new_size']} should be {expected_new_size}"

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_pp_cream_always_increases_size(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 2: PP cream increases size within defined range
        **Validates: Requirements 2.1**
        
        For any PP cream, the new size should always be greater than the old size.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=False,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        assert result.success
        assert result.details["new_size"] > result.details["old_size"], \
            f"New size {result.details['new_size']} should be greater than old size {result.details['old_size']}"

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_pp_cream_increase_is_positive(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 2: PP cream increases size within defined range
        **Validates: Requirements 2.1**
        
        For any PP cream, the increase should always be positive.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=False,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        assert result.success
        assert result.details["increase"] > 0, \
            f"Increase should be positive, got {result.details['increase']}"

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_pp_cream_details_contain_range_info(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 2: PP cream increases size within defined range
        **Validates: Requirements 2.1**
        
        For any successful PP cream usage, the result should contain range info.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=False,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        assert result.success
        assert "pp_boost_min" in result.details
        assert "pp_boost_max" in result.details
        assert "increase" in result.details
        assert "old_size" in result.details
        assert "new_size" in result.details

    @given(current_size=pp_size_strategy)
    @settings(max_examples=100)
    def test_non_cream_item_rejected(self, current_size: int):
        """
        Feature: unified-inventory, Property 2: PP cream increases size within defined range
        **Validates: Requirements 2.1**
        
        Non-cream items should be rejected.
        """
        result = apply_pp_cream_logic(
            item_type="energy_drink",  # Not a cream
            current_size=current_size,
            has_item=True,
            has_active_cage=False,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        assert not result.success, "Non-cream item should be rejected"
        assert "не мазь" in result.message.lower() or "не мазь" in result.message

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_missing_item_rejected(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 2: PP cream increases size within defined range
        **Validates: Requirements 2.1**
        
        If user doesn't have the item, usage should be rejected.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=False,  # User doesn't have item
            has_active_cage=False,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        assert not result.success, "Missing item should be rejected"
        assert "нет" in result.message.lower()



class TestPPCageBlocksCreamUsage:
    """
    Property 3: Active PP Cage blocks PP cream usage
    
    *For any* user with active PP Cage, attempting to use any PP cream SHALL fail 
    with error message and not change PP size.
    
    **Validates: Requirements 2.3**
    """

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_active_cage_blocks_cream_usage(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 3: Active PP Cage blocks PP cream usage
        **Validates: Requirements 2.3**
        
        For any user with active PP cage, cream usage should fail.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=True,  # Cage is active
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        # Should fail
        assert not result.success, "Cream usage should fail when cage is active"
        
        # Should mention cage blocking
        assert "клетка" in result.message.lower(), \
            f"Error message should mention cage, got: {result.message}"
        
        # Should have blocked_by detail
        assert result.details.get("blocked_by") == "pp_cage", \
            "Details should indicate blocked by pp_cage"

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_cage_blocking_does_not_change_size(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 3: Active PP Cage blocks PP cream usage
        **Validates: Requirements 2.3**
        
        When cage blocks cream usage, PP size should not change.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=True,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        # Should fail
        assert not result.success
        
        # Should not have size change details
        assert "new_size" not in result.details, \
            "Failed result should not contain new_size"
        assert "increase" not in result.details, \
            "Failed result should not contain increase"

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_no_cage_allows_cream_usage(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 3: Active PP Cage blocks PP cream usage
        **Validates: Requirements 2.3**
        
        When cage is not active, cream usage should succeed.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=False,  # No cage
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        # Should succeed
        assert result.success, f"Cream usage should succeed without cage, got: {result.message}"
        
        # Should have size change details
        assert "new_size" in result.details
        assert "increase" in result.details

    @given(current_size=pp_size_strategy)
    @settings(max_examples=100)
    def test_all_cream_types_blocked_by_cage(self, current_size: int):
        """
        Feature: unified-inventory, Property 3: Active PP Cage blocks PP cream usage
        **Validates: Requirements 2.3**
        
        All PP cream types should be blocked by active cage.
        """
        cream_types = ["pp_cream_small", "pp_cream_medium", "pp_cream_large", "pp_cream_titan"]
        
        for cream_type in cream_types:
            result = apply_pp_cream_logic(
                item_type=cream_type,
                current_size=current_size,
                has_item=True,
                has_active_cage=True,
                item_catalog=EXTENDED_MOCK_ITEM_CATALOG
            )
            
            assert not result.success, f"{cream_type} should be blocked by cage"
            assert result.details.get("blocked_by") == "pp_cage", \
                f"{cream_type} should indicate blocked by pp_cage"

    @given(
        cream_type=pp_cream_type_strategy,
        current_size=pp_size_strategy
    )
    @settings(max_examples=100)
    def test_cage_blocking_message_is_helpful(self, cream_type: str, current_size: int):
        """
        Feature: unified-inventory, Property 3: Active PP Cage blocks PP cream usage
        **Validates: Requirements 2.3**
        
        The blocking message should be helpful and mention how to remove cage.
        """
        result = apply_pp_cream_logic(
            item_type=cream_type,
            current_size=current_size,
            has_item=True,
            has_active_cage=True,
            item_catalog=EXTENDED_MOCK_ITEM_CATALOG
        )
        
        assert not result.success
        # Message should mention how to remove cage
        assert "сними" in result.message.lower() or "инвентарь" in result.message.lower(), \
            f"Message should mention how to remove cage, got: {result.message}"



# ============================================================================
# PP Cage Expiration Functions (for isolated testing)
# ============================================================================

from datetime import datetime, timezone, timedelta
import json


@dataclass
class MockCageActivationResult:
    """Mock result for cage activation."""
    success: bool
    message: str
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


def activate_cage_logic(
    has_cage: bool,
    is_already_active: bool,
    duration_hours: int = 24
) -> MockCageActivationResult:
    """
    Pure function implementing PP Cage activation logic.
    
    This mirrors the logic from app/services/inventory.py activate_item()
    but without database dependencies for isolated testing.
    
    Args:
        has_cage: Whether user has the cage in inventory
        is_already_active: Whether cage is already active
        duration_hours: Duration in hours for cage activation
        
    Returns:
        MockCageActivationResult with activation timestamps
    """
    if not has_cage:
        return MockCageActivationResult(
            success=False,
            message="❌ У тебя нет клетки!"
        )
    
    if is_already_active:
        return MockCageActivationResult(
            success=False,
            message="⚠️ Клетка уже активна!"
        )
    
    # Calculate activation and expiration times
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=duration_hours)
    
    return MockCageActivationResult(
        success=True,
        message=f"🔒 Клетка активирована на {duration_hours} часов!",
        activated_at=now,
        expires_at=expires_at
    )


def calculate_expiration(activated_at: datetime, duration_hours: int) -> datetime:
    """
    Calculate expiration time from activation time and duration.
    
    Args:
        activated_at: When the cage was activated
        duration_hours: Duration in hours
        
    Returns:
        Expiration datetime
    """
    return activated_at + timedelta(hours=duration_hours)


def is_cage_expired(expires_at: datetime, current_time: datetime) -> bool:
    """
    Check if cage has expired.
    
    Args:
        expires_at: Expiration datetime
        current_time: Current datetime to check against
        
    Returns:
        True if expired, False otherwise
    """
    # Ensure both have timezone info
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    
    return current_time > expires_at


def get_remaining_time(expires_at: datetime, current_time: datetime) -> timedelta:
    """
    Get remaining time until expiration.
    
    Args:
        expires_at: Expiration datetime
        current_time: Current datetime
        
    Returns:
        Remaining time as timedelta (can be negative if expired)
    """
    # Ensure both have timezone info
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    
    return expires_at - current_time


# ============================================================================
# Strategies for PP Cage Expiration Tests
# ============================================================================

# Strategy for duration hours (typical values)
duration_hours_strategy = st.integers(min_value=1, max_value=168)  # 1 hour to 1 week

# Strategy for time offsets (for testing expiration)
time_offset_hours_strategy = st.floats(min_value=-48, max_value=48, allow_nan=False, allow_infinity=False)


# ============================================================================
# Property Tests for PP Cage Expiration
# ============================================================================

class TestPPCageExpirationSetsCorrectTime:
    """
    Property 4: PP Cage activation sets correct expiration
    
    *For any* PP Cage activation, the expires_at timestamp SHALL be exactly 
    24 hours from activation time.
    
    **Validates: Requirements 3.2**
    """

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_expiration_is_exactly_duration_from_activation(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        For any cage activation, expiration should be exactly duration_hours from activation.
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=duration_hours
        )
        
        assert result.success, "Activation should succeed"
        assert result.activated_at is not None, "Should have activation time"
        assert result.expires_at is not None, "Should have expiration time"
        
        # Calculate expected expiration
        expected_expires_at = result.activated_at + timedelta(hours=duration_hours)
        
        # Verify expiration is exactly as expected
        assert result.expires_at == expected_expires_at, \
            f"Expiration {result.expires_at} should be exactly {duration_hours}h from activation {result.activated_at}"

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_default_duration_is_24_hours(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        The default duration should be 24 hours as per requirements.
        """
        # Test with default duration (24 hours)
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=24  # Default
        )
        
        assert result.success
        
        # Verify it's exactly 24 hours
        time_diff = result.expires_at - result.activated_at
        assert time_diff == timedelta(hours=24), \
            f"Default duration should be 24 hours, got {time_diff}"

    @given(
        duration_hours=duration_hours_strategy,
        offset_hours=time_offset_hours_strategy
    )
    @settings(max_examples=100)
    def test_cage_active_before_expiration(self, duration_hours: int, offset_hours: float):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        Cage should be active before expiration time and inactive after.
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=duration_hours
        )
        
        assert result.success
        
        # Check at various times relative to activation
        check_time = result.activated_at + timedelta(hours=offset_hours)
        
        is_expired = is_cage_expired(result.expires_at, check_time)
        
        if offset_hours < duration_hours:
            # Before expiration - should NOT be expired
            assert not is_expired, \
                f"Cage should be active at {offset_hours}h (before {duration_hours}h expiration)"
        else:
            # At or after expiration - should be expired
            assert is_expired, \
                f"Cage should be expired at {offset_hours}h (after {duration_hours}h expiration)"

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_remaining_time_decreases_correctly(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        Remaining time should decrease as time passes.
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=duration_hours
        )
        
        assert result.success
        
        # Check remaining time at activation
        remaining_at_start = get_remaining_time(result.expires_at, result.activated_at)
        assert remaining_at_start == timedelta(hours=duration_hours), \
            f"Remaining time at start should be {duration_hours}h, got {remaining_at_start}"
        
        # Check remaining time after half the duration
        half_time = result.activated_at + timedelta(hours=duration_hours / 2)
        remaining_at_half = get_remaining_time(result.expires_at, half_time)
        expected_half = timedelta(hours=duration_hours / 2)
        
        # Allow small floating point tolerance
        diff = abs(remaining_at_half.total_seconds() - expected_half.total_seconds())
        assert diff < 1, \
            f"Remaining time at half should be ~{expected_half}, got {remaining_at_half}"

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_expiration_time_has_timezone(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        Expiration time should have timezone info (UTC).
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=duration_hours
        )
        
        assert result.success
        assert result.expires_at.tzinfo is not None, \
            "Expiration time should have timezone info"
        assert result.activated_at.tzinfo is not None, \
            "Activation time should have timezone info"

    @settings(max_examples=100)
    @given(duration_hours=st.just(24))
    def test_24_hour_expiration_per_requirements(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        Per Requirements 3.2: PP Cage SHALL set 24-hour expiration.
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=24
        )
        
        assert result.success
        
        # Verify exactly 24 hours
        duration = result.expires_at - result.activated_at
        assert duration.total_seconds() == 24 * 3600, \
            f"Duration should be exactly 24 hours (86400 seconds), got {duration.total_seconds()} seconds"

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_calculate_expiration_is_consistent(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        The calculate_expiration helper should be consistent with activation logic.
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=False,
            duration_hours=duration_hours
        )
        
        assert result.success
        
        # Calculate using helper
        calculated = calculate_expiration(result.activated_at, duration_hours)
        
        assert calculated == result.expires_at, \
            f"Helper calculation {calculated} should match activation result {result.expires_at}"

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_no_cage_activation_fails(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        Activation should fail if user doesn't have cage.
        """
        result = activate_cage_logic(
            has_cage=False,
            is_already_active=False,
            duration_hours=duration_hours
        )
        
        assert not result.success, "Activation should fail without cage"
        assert result.expires_at is None, "Should not have expiration time"
        assert result.activated_at is None, "Should not have activation time"

    @given(duration_hours=duration_hours_strategy)
    @settings(max_examples=100)
    def test_already_active_cage_fails(self, duration_hours: int):
        """
        Feature: unified-inventory, Property 4: PP Cage activation sets correct expiration
        **Validates: Requirements 3.2**
        
        Activation should fail if cage is already active.
        """
        result = activate_cage_logic(
            has_cage=True,
            is_already_active=True,
            duration_hours=duration_hours
        )
        
        assert not result.success, "Activation should fail if already active"
        assert result.expires_at is None, "Should not have new expiration time"
        assert result.activated_at is None, "Should not have new activation time"


# ============================================================================
# Booster Effect Functions (for isolated testing)
# ============================================================================

@dataclass
class MockBoosterEffectResult:
    """Mock result for booster effect application."""
    success: bool
    message: str
    effect_type: Optional[str] = None
    effect_value: Optional[any] = None
    duration: Optional[str] = None


# Extended mock catalog with all booster types
BOOSTER_MOCK_CATALOG = {
    "energy_drink": MockItemInfo("energy_drink", "Энергетик", "🥤", {"reset_fishing_cooldown": True}),
    "lucky_charm": MockItemInfo("lucky_charm", "Талисман удачи", "🍀", {"luck_bonus": 0.1}),
    "shield": MockItemInfo("shield", "Щит", "🛡️", {"loss_protection": True}),
    "vip_status": MockItemInfo("vip_status", "VIP статус", "👑", {"win_bonus": 0.2, "duration_hours": 24}),
    "double_xp": MockItemInfo("double_xp", "Энергетик x2", "⚡", {"xp_bonus": 2.0, "duration_hours": 1}),
}


def is_booster_type(item_type: str) -> bool:
    """Check if item is a booster type."""
    return item_type in BOOSTER_MOCK_CATALOG


def apply_booster_logic(
    item_type: str,
    has_item: bool,
    item_catalog: Dict[str, MockItemInfo]
) -> MockBoosterEffectResult:
    """
    Pure function implementing booster application logic.
    
    This mirrors the logic from app/handlers/inventory.py apply_booster()
    but without database/Redis dependencies for isolated testing.
    
    Args:
        item_type: Type of booster item
        has_item: Whether user has the item in inventory
        item_catalog: Item catalog to look up effect info
        
    Returns:
        MockBoosterEffectResult with effect details
        
    Requirements: 4.1, 4.2, 4.3
    """
    # Validate item type is a booster
    if not is_booster_type(item_type):
        return MockBoosterEffectResult(
            success=False,
            message="❌ Это не бустер!"
        )
    
    # Get item info from catalog
    item_info = item_catalog.get(item_type)
    if not item_info:
        return MockBoosterEffectResult(
            success=False,
            message="❌ Неизвестный предмет"
        )
    
    # Check if user has the item
    if not has_item:
        return MockBoosterEffectResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!"
        )
    
    # Apply effect based on item type
    if item_type == "energy_drink":
        # Requirement 4.1: Reset fishing cooldown
        return MockBoosterEffectResult(
            success=True,
            message=f"🥤 Использован {item_info.emoji} {item_info.name}!",
            effect_type="reset_fishing_cooldown",
            effect_value=True,
            duration="immediate"
        )
    
    elif item_type == "lucky_charm":
        # Requirement 4.2: Set luck bonus for next game
        luck_bonus = item_info.effect.get("luck_bonus", 0.1)
        return MockBoosterEffectResult(
            success=True,
            message=f"🍀 Использован {item_info.emoji} {item_info.name}!",
            effect_type="luck_bonus",
            effect_value=luck_bonus,
            duration="1 game"
        )
    
    elif item_type == "shield":
        # Requirement 4.3: Set loss protection for next game
        return MockBoosterEffectResult(
            success=True,
            message=f"🛡️ Использован {item_info.emoji} {item_info.name}!",
            effect_type="loss_protection",
            effect_value=True,
            duration="1 game"
        )
    
    elif item_type == "vip_status":
        # VIP status: +20% to winnings for 24 hours
        win_bonus = item_info.effect.get("win_bonus", 0.2)
        duration_hours = item_info.effect.get("duration_hours", 24)
        return MockBoosterEffectResult(
            success=True,
            message=f"👑 Использован {item_info.emoji} {item_info.name}!",
            effect_type="vip_status",
            effect_value={"win_bonus": win_bonus, "duration_hours": duration_hours},
            duration=f"{duration_hours} hours"
        )
    
    elif item_type == "double_xp":
        # Double XP for 1 hour
        xp_bonus = item_info.effect.get("xp_bonus", 2.0)
        duration_hours = item_info.effect.get("duration_hours", 1)
        return MockBoosterEffectResult(
            success=True,
            message=f"⚡ Использован {item_info.emoji} {item_info.name}!",
            effect_type="double_xp",
            effect_value={"xp_bonus": xp_bonus, "duration_hours": duration_hours},
            duration=f"{duration_hours} hours"
        )
    
    return MockBoosterEffectResult(
        success=False,
        message=f"❌ Неизвестный тип бустера: {item_type}"
    )


# ============================================================================
# Strategies for Booster Tests
# ============================================================================

# Strategy for booster types
booster_type_strategy = st.sampled_from([
    "energy_drink",
    "lucky_charm",
    "shield",
    "vip_status",
    "double_xp"
])

# Strategy for core boosters (energy drink, lucky charm, shield)
core_booster_type_strategy = st.sampled_from([
    "energy_drink",
    "lucky_charm",
    "shield"
])


# ============================================================================
# Property Tests for Booster Effects
# ============================================================================

class TestBoosterUsageSetsCorrectStateFlags:
    """
    Property 8: Booster usage sets correct state flags
    
    *For any* booster usage (energy drink, lucky charm, shield), the corresponding 
    effect flag SHALL be set in user state.
    
    **Validates: Requirements 4.1, 4.2, 4.3**
    """

    @given(booster_type=booster_type_strategy)
    @settings(max_examples=100)
    def test_booster_usage_succeeds_with_item(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        For any booster type, usage should succeed when user has the item.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success, f"Booster {booster_type} usage should succeed, got: {result.message}"
        assert result.effect_type is not None, "Should have effect type"
        assert result.effect_value is not None, "Should have effect value"

    @given(booster_type=booster_type_strategy)
    @settings(max_examples=100)
    def test_booster_usage_fails_without_item(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        For any booster type, usage should fail when user doesn't have the item.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=False,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert not result.success, f"Booster {booster_type} usage should fail without item"
        assert "нет" in result.message.lower(), "Error message should indicate missing item"

    @settings(max_examples=100)
    @given(st.just("energy_drink"))
    def test_energy_drink_resets_fishing_cooldown(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1**
        
        Energy Drink SHALL reset fishing cooldown immediately.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.effect_type == "reset_fishing_cooldown", \
            f"Energy drink should set reset_fishing_cooldown effect, got {result.effect_type}"
        assert result.effect_value == True, \
            "Effect value should be True"
        assert result.duration == "immediate", \
            f"Duration should be 'immediate', got {result.duration}"

    @settings(max_examples=100)
    @given(st.just("lucky_charm"))
    def test_lucky_charm_sets_luck_bonus(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.2**
        
        Lucky Charm SHALL apply +10% luck bonus to next game.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.effect_type == "luck_bonus", \
            f"Lucky charm should set luck_bonus effect, got {result.effect_type}"
        assert result.effect_value == 0.1, \
            f"Luck bonus should be 0.1 (10%), got {result.effect_value}"
        assert result.duration == "1 game", \
            f"Duration should be '1 game', got {result.duration}"

    @settings(max_examples=100)
    @given(st.just("shield"))
    def test_shield_sets_loss_protection(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.3**
        
        Shield SHALL activate loss protection for next game.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.effect_type == "loss_protection", \
            f"Shield should set loss_protection effect, got {result.effect_type}"
        assert result.effect_value == True, \
            "Effect value should be True"
        assert result.duration == "1 game", \
            f"Duration should be '1 game', got {result.duration}"

    @given(booster_type=core_booster_type_strategy)
    @settings(max_examples=100)
    def test_core_boosters_have_correct_effect_types(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        Each core booster should set its specific effect type.
        """
        expected_effects = {
            "energy_drink": "reset_fishing_cooldown",
            "lucky_charm": "luck_bonus",
            "shield": "loss_protection"
        }
        
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.effect_type == expected_effects[booster_type], \
            f"Booster {booster_type} should set {expected_effects[booster_type]} effect, got {result.effect_type}"

    @given(booster_type=booster_type_strategy)
    @settings(max_examples=100)
    def test_booster_message_contains_item_name(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        Success message should contain the item emoji.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        item_info = BOOSTER_MOCK_CATALOG[booster_type]
        assert item_info.emoji in result.message, \
            f"Message should contain emoji {item_info.emoji}, got: {result.message}"

    @given(booster_type=booster_type_strategy)
    @settings(max_examples=100)
    def test_booster_has_duration_info(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        Successful booster usage should include duration information.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.duration is not None, "Should have duration info"
        assert len(result.duration) > 0, "Duration should not be empty"

    @settings(max_examples=100)
    @given(st.just("vip_status"))
    def test_vip_status_sets_win_bonus(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        VIP Status should set win bonus for 24 hours.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.effect_type == "vip_status"
        assert isinstance(result.effect_value, dict)
        assert result.effect_value.get("win_bonus") == 0.2
        assert result.effect_value.get("duration_hours") == 24
        assert "24 hours" in result.duration

    @settings(max_examples=100)
    @given(st.just("double_xp"))
    def test_double_xp_sets_xp_bonus(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        Double XP should set XP bonus for 1 hour.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        assert result.effect_type == "double_xp"
        assert isinstance(result.effect_value, dict)
        assert result.effect_value.get("xp_bonus") == 2.0
        assert result.effect_value.get("duration_hours") == 1
        assert "1 hours" in result.duration

    @given(non_booster=st.sampled_from(["basic_rod", "pp_cream_small", "lootbox_common"]))
    @settings(max_examples=100)
    def test_non_booster_items_rejected(self, non_booster: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        Non-booster items should be rejected.
        """
        result = apply_booster_logic(
            item_type=non_booster,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert not result.success, f"Non-booster {non_booster} should be rejected"
        assert "не бустер" in result.message.lower() or "неизвестн" in result.message.lower()

    @given(booster_type=core_booster_type_strategy)
    @settings(max_examples=100)
    def test_core_boosters_are_one_time_use(self, booster_type: str):
        """
        Feature: unified-inventory, Property 8: Booster usage sets correct state flags
        **Validates: Requirements 4.1, 4.2, 4.3**
        
        Core boosters (energy drink, lucky charm, shield) should be one-time use.
        """
        result = apply_booster_logic(
            item_type=booster_type,
            has_item=True,
            item_catalog=BOOSTER_MOCK_CATALOG
        )
        
        assert result.success
        # One-time use boosters have "immediate" or "1 game" duration
        assert result.duration in ["immediate", "1 game"], \
            f"Core booster {booster_type} should be one-time use, got duration: {result.duration}"


# ============================================================================
# Rod Equipping Functions (for isolated testing)
# ============================================================================

@dataclass
class MockRodEquipResult:
    """Mock result for rod equipping."""
    success: bool
    message: str
    equipped_rod: Optional[str] = None
    rod_bonus: Optional[float] = None


# Extended mock catalog with all rod types
ROD_MOCK_CATALOG = {
    "basic_rod": MockItemInfo("basic_rod", "Базовая удочка", "🎣", {"rod_bonus": 0.0}),
    "silver_rod": MockItemInfo("silver_rod", "Серебряная удочка", "🥈", {"rod_bonus": 0.1}),
    "golden_rod": MockItemInfo("golden_rod", "Золотая удочка", "🥇", {"rod_bonus": 0.25}),
    "legendary_rod": MockItemInfo("legendary_rod", "Легендарная удочка", "👑", {"rod_bonus": 0.5}),
    "fishing_rod_basic": MockItemInfo("fishing_rod_basic", "Удочка новичка", "🎣", {"rod_bonus": 0.0}),
    "fishing_rod_pro": MockItemInfo("fishing_rod_pro", "Про удочка", "🎣", {"rod_bonus": 0.2}),
    "fishing_rod_golden": MockItemInfo("fishing_rod_golden", "Золотая удочка", "🎣", {"rod_bonus": 0.5}),
}

# All rod types
ALL_ROD_TYPES = list(ROD_MOCK_CATALOG.keys())


def is_rod_type(item_type: str) -> bool:
    """Check if item type is a rod (using the catalog)."""
    return item_type in ALL_ROD_TYPES


@dataclass
class MockInventoryState:
    """Mock inventory state for testing rod equipping."""
    items: Dict[str, MockInventoryItem]  # item_type -> item
    
    def has_item(self, item_type: str) -> bool:
        """Check if item exists with quantity > 0."""
        item = self.items.get(item_type)
        return item is not None and item.quantity > 0
    
    def get_equipped_rod(self) -> Optional[str]:
        """Get currently equipped rod type."""
        for item_type, item in self.items.items():
            if is_rod_type(item_type) and item.equipped:
                return item_type
        return None
    
    def count_equipped_rods(self) -> int:
        """Count number of equipped rods."""
        count = 0
        for item_type, item in self.items.items():
            if is_rod_type(item_type) and item.equipped:
                count += 1
        return count


def equip_rod_logic(
    item_type: str,
    inventory_state: MockInventoryState,
    item_catalog: Dict[str, MockItemInfo]
) -> tuple[MockRodEquipResult, MockInventoryState]:
    """
    Pure function implementing rod equipping logic.
    
    This mirrors the logic from app/handlers/inventory.py equip_rod()
    and app/services/inventory.py equip_item() but without database 
    dependencies for isolated testing.
    
    The key invariant: after equipping, exactly ONE rod should be equipped,
    and it should be the selected rod.
    
    Args:
        item_type: Type of rod to equip
        inventory_state: Current inventory state
        item_catalog: Item catalog to look up rod info
        
    Returns:
        Tuple of (MockRodEquipResult, new MockInventoryState)
        
    Requirements: 5.1
    """
    # Validate item type is a rod (check against catalog)
    if not is_rod_type(item_type):
        return MockRodEquipResult(
            success=False,
            message="❌ Это не удочка!"
        ), inventory_state
    
    # Get item info from catalog
    item_info = item_catalog.get(item_type)
    if not item_info:
        return MockRodEquipResult(
            success=False,
            message="❌ Неизвестный предмет"
        ), inventory_state
    
    # Check if user has the rod
    if not inventory_state.has_item(item_type):
        return MockRodEquipResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!"
        ), inventory_state
    
    # Create new inventory state with updated equipped status
    new_items = {}
    for it, item in inventory_state.items.items():
        # Create a copy of the item
        new_item = MockInventoryItem(
            item_type=item.item_type,
            item_name=item.item_name,
            quantity=item.quantity,
            equipped=False if is_rod_type(it) else item.equipped,  # Unequip all rods
            item_data=item.item_data
        )
        new_items[it] = new_item
    
    # Equip the selected rod
    if item_type in new_items:
        new_items[item_type].equipped = True
    
    new_state = MockInventoryState(items=new_items)
    
    rod_bonus = item_info.effect.get("rod_bonus", 0)
    
    return MockRodEquipResult(
        success=True,
        message=f"🎣 Экипирована {item_info.emoji} {item_info.name}!",
        equipped_rod=item_type,
        rod_bonus=rod_bonus
    ), new_state


# ============================================================================
# Strategies for Rod Equipping Tests
# ============================================================================

# Strategy for rod types
rod_type_strategy = st.sampled_from(ALL_ROD_TYPES)

# Strategy for generating inventory with rods
def inventory_with_rods_strategy():
    """Generate inventory state with various rods."""
    return st.builds(
        lambda rods: MockInventoryState(items={
            rod_type: MockInventoryItem(
                item_type=rod_type,
                item_name=ROD_MOCK_CATALOG[rod_type].name,
                quantity=qty,
                equipped=equipped
            )
            for rod_type, (qty, equipped) in rods.items()
        }),
        rods=st.fixed_dictionaries({
            rod_type: st.tuples(
                st.integers(min_value=0, max_value=1),  # quantity (0 or 1 for rods)
                st.booleans()  # equipped
            )
            for rod_type in ALL_ROD_TYPES
        })
    )


# ============================================================================
# Property Tests for Rod Equipping
# ============================================================================

class TestRodEquipResultsInSingleEquippedRod:
    """
    Property 5: Rod equip results in single equipped rod
    
    *For any* rod equip action, exactly one rod SHALL be equipped after the operation, 
    and it SHALL be the selected rod.
    
    **Validates: Requirements 5.1**
    """

    @given(
        rod_to_equip=rod_type_strategy,
        inventory=inventory_with_rods_strategy()
    )
    @settings(max_examples=100)
    def test_exactly_one_rod_equipped_after_equip(
        self, rod_to_equip: str, inventory: MockInventoryState
    ):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        For any rod equip action, exactly one rod should be equipped after.
        """
        # Ensure user has the rod to equip
        if rod_to_equip not in inventory.items:
            inventory.items[rod_to_equip] = MockInventoryItem(
                item_type=rod_to_equip,
                item_name=ROD_MOCK_CATALOG[rod_to_equip].name,
                quantity=1,
                equipped=False
            )
        else:
            inventory.items[rod_to_equip].quantity = max(1, inventory.items[rod_to_equip].quantity)
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success, f"Equip should succeed, got: {result.message}"
        
        # Count equipped rods
        equipped_count = new_state.count_equipped_rods()
        assert equipped_count == 1, \
            f"Exactly one rod should be equipped after equip, got {equipped_count}"

    @given(
        rod_to_equip=rod_type_strategy,
        inventory=inventory_with_rods_strategy()
    )
    @settings(max_examples=100)
    def test_selected_rod_is_equipped(
        self, rod_to_equip: str, inventory: MockInventoryState
    ):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        For any rod equip action, the selected rod should be the one equipped.
        """
        # Ensure user has the rod to equip
        if rod_to_equip not in inventory.items:
            inventory.items[rod_to_equip] = MockInventoryItem(
                item_type=rod_to_equip,
                item_name=ROD_MOCK_CATALOG[rod_to_equip].name,
                quantity=1,
                equipped=False
            )
        else:
            inventory.items[rod_to_equip].quantity = max(1, inventory.items[rod_to_equip].quantity)
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success
        
        # Verify the selected rod is equipped
        equipped_rod = new_state.get_equipped_rod()
        assert equipped_rod == rod_to_equip, \
            f"Selected rod {rod_to_equip} should be equipped, got {equipped_rod}"

    @given(
        rod_to_equip=rod_type_strategy,
        inventory=inventory_with_rods_strategy()
    )
    @settings(max_examples=100)
    def test_previous_rod_unequipped(
        self, rod_to_equip: str, inventory: MockInventoryState
    ):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        For any rod equip action, any previously equipped rod should be unequipped.
        """
        # Ensure user has the rod to equip
        if rod_to_equip not in inventory.items:
            inventory.items[rod_to_equip] = MockInventoryItem(
                item_type=rod_to_equip,
                item_name=ROD_MOCK_CATALOG[rod_to_equip].name,
                quantity=1,
                equipped=False
            )
        else:
            inventory.items[rod_to_equip].quantity = max(1, inventory.items[rod_to_equip].quantity)
        
        # Get previously equipped rod (if any)
        previous_equipped = inventory.get_equipped_rod()
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success
        
        # If there was a different rod equipped before, it should be unequipped now
        if previous_equipped and previous_equipped != rod_to_equip:
            prev_item = new_state.items.get(previous_equipped)
            if prev_item:
                assert not prev_item.equipped, \
                    f"Previous rod {previous_equipped} should be unequipped"

    @given(rod_to_equip=rod_type_strategy)
    @settings(max_examples=100)
    def test_equip_fails_without_rod(self, rod_to_equip: str):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Equipping should fail if user doesn't have the rod.
        """
        # Empty inventory
        inventory = MockInventoryState(items={})
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert not result.success, "Equip should fail without rod"
        assert "нет" in result.message.lower(), "Error should mention missing item"

    @given(rod_to_equip=rod_type_strategy)
    @settings(max_examples=100)
    def test_equip_fails_with_zero_quantity(self, rod_to_equip: str):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Equipping should fail if rod quantity is zero.
        """
        inventory = MockInventoryState(items={
            rod_to_equip: MockInventoryItem(
                item_type=rod_to_equip,
                item_name=ROD_MOCK_CATALOG[rod_to_equip].name,
                quantity=0,  # Zero quantity
                equipped=False
            )
        })
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert not result.success, "Equip should fail with zero quantity"

    @given(non_rod=st.sampled_from(["pp_cream_small", "energy_drink", "lootbox_common"]))
    @settings(max_examples=100)
    def test_non_rod_items_rejected(self, non_rod: str):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Non-rod items should be rejected.
        """
        inventory = MockInventoryState(items={})
        
        result, new_state = equip_rod_logic(
            item_type=non_rod,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert not result.success, f"Non-rod {non_rod} should be rejected"
        assert "не удочка" in result.message.lower() or "неизвестн" in result.message.lower()

    @given(
        rod_to_equip=rod_type_strategy,
        inventory=inventory_with_rods_strategy()
    )
    @settings(max_examples=100)
    def test_result_contains_rod_info(
        self, rod_to_equip: str, inventory: MockInventoryState
    ):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Successful equip result should contain rod info.
        """
        # Ensure user has the rod to equip
        if rod_to_equip not in inventory.items:
            inventory.items[rod_to_equip] = MockInventoryItem(
                item_type=rod_to_equip,
                item_name=ROD_MOCK_CATALOG[rod_to_equip].name,
                quantity=1,
                equipped=False
            )
        else:
            inventory.items[rod_to_equip].quantity = max(1, inventory.items[rod_to_equip].quantity)
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success
        assert result.equipped_rod == rod_to_equip, "Result should contain equipped rod type"
        assert result.rod_bonus is not None, "Result should contain rod bonus"
        
        # Verify rod bonus matches catalog
        expected_bonus = ROD_MOCK_CATALOG[rod_to_equip].effect.get("rod_bonus", 0)
        assert result.rod_bonus == expected_bonus, \
            f"Rod bonus should be {expected_bonus}, got {result.rod_bonus}"

    @given(
        first_rod=rod_type_strategy,
        second_rod=rod_type_strategy
    )
    @settings(max_examples=100)
    def test_equip_different_rod_switches(self, first_rod: str, second_rod: str):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Equipping a different rod should switch to that rod.
        """
        # Start with first rod equipped
        inventory = MockInventoryState(items={
            first_rod: MockInventoryItem(
                item_type=first_rod,
                item_name=ROD_MOCK_CATALOG[first_rod].name,
                quantity=1,
                equipped=True
            ),
            second_rod: MockInventoryItem(
                item_type=second_rod,
                item_name=ROD_MOCK_CATALOG[second_rod].name,
                quantity=1,
                equipped=False
            )
        })
        
        # Equip second rod
        result, new_state = equip_rod_logic(
            item_type=second_rod,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success
        
        # Verify second rod is now equipped
        equipped = new_state.get_equipped_rod()
        assert equipped == second_rod, \
            f"Second rod {second_rod} should be equipped, got {equipped}"
        
        # Verify only one rod is equipped
        assert new_state.count_equipped_rods() == 1

    @given(rod_to_equip=rod_type_strategy)
    @settings(max_examples=100)
    def test_equip_same_rod_keeps_equipped(self, rod_to_equip: str):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Equipping an already equipped rod should keep it equipped.
        """
        # Start with rod already equipped
        inventory = MockInventoryState(items={
            rod_to_equip: MockInventoryItem(
                item_type=rod_to_equip,
                item_name=ROD_MOCK_CATALOG[rod_to_equip].name,
                quantity=1,
                equipped=True
            )
        })
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success
        
        # Verify rod is still equipped
        equipped = new_state.get_equipped_rod()
        assert equipped == rod_to_equip
        assert new_state.count_equipped_rods() == 1

    @given(inventory=inventory_with_rods_strategy())
    @settings(max_examples=100)
    def test_multiple_equipped_rods_normalized(self, inventory: MockInventoryState):
        """
        Feature: unified-inventory, Property 5: Rod equip results in single equipped rod
        **Validates: Requirements 5.1**
        
        Even if inventory starts with multiple equipped rods (invalid state),
        equipping should normalize to exactly one.
        """
        # Force multiple rods to be equipped (invalid state)
        equipped_count = 0
        for item_type, item in inventory.items.items():
            if item_type.endswith("_rod") and item.quantity > 0:
                item.equipped = True
                equipped_count += 1
        
        # Skip if no rods available
        if equipped_count == 0:
            return
        
        # Pick any rod to equip
        rod_to_equip = None
        for item_type, item in inventory.items.items():
            if item_type.endswith("_rod") and item.quantity > 0:
                rod_to_equip = item_type
                break
        
        if rod_to_equip is None:
            return
        
        result, new_state = equip_rod_logic(
            item_type=rod_to_equip,
            inventory_state=inventory,
            item_catalog=ROD_MOCK_CATALOG
        )
        
        assert result.success
        
        # After equip, exactly one rod should be equipped
        assert new_state.count_equipped_rods() == 1, \
            f"Should have exactly 1 equipped rod, got {new_state.count_equipped_rods()}"


# ============================================================================
# Lootbox Opening Functions (for isolated testing)
# ============================================================================

@dataclass
class MockLootboxReward:
    """Mock lootbox reward for testing."""
    name: str
    emoji: str
    coins: int = 0
    item_type: Optional[str] = None


@dataclass
class MockLootboxResult:
    """Mock result of opening a lootbox."""
    success: bool
    message: str
    rewards: List[MockLootboxReward]
    total_coins: int = 0
    items: List[str] = field(default_factory=list)


@dataclass
class MockLootboxOpenResult:
    """Mock result of the open_lootbox function."""
    success: bool
    message: str
    items_received: List[tuple]  # [(item_type, quantity), ...]
    coins_received: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


# Mock lootbox contents for testing
MOCK_LOOTBOX_CONTENTS = {
    "common": [
        MockLootboxReward("Горсть монет", "🪙", coins=20),
        MockLootboxReward("Мелочь", "💵", coins=30),
        MockLootboxReward("Талисман удачи", "🍀", item_type="lucky_charm"),
    ],
    "rare": [
        MockLootboxReward("Монеты", "💰", coins=75),
        MockLootboxReward("Энергетик", "🥤", item_type="energy_drink"),
        MockLootboxReward("Щит", "🛡️", item_type="shield"),
    ],
    "epic": [
        MockLootboxReward("Монеты", "💰", coins=150),
        MockLootboxReward("VIP статус", "👑", item_type="vip_status"),
    ],
    "legendary": [
        MockLootboxReward("Монеты", "💰", coins=300),
        MockLootboxReward("Золотая удочка", "🎣", item_type="fishing_rod_golden"),
    ],
}


# Extended mock catalog with lootbox types
LOOTBOX_MOCK_CATALOG = {
    "lootbox_common": MockItemInfo("lootbox_common", "Обычный лутбокс", "📦", {"lootbox_tier": "common"}),
    "lootbox_rare": MockItemInfo("lootbox_rare", "Редкий лутбокс", "📦", {"lootbox_tier": "rare"}),
    "lootbox_epic": MockItemInfo("lootbox_epic", "Эпический лутбокс", "💜", {"lootbox_tier": "epic"}),
    "lootbox_legendary": MockItemInfo("lootbox_legendary", "Легендарный лутбокс", "🌟", {"lootbox_tier": "legendary"}),
    # Items that can be received from lootboxes
    "lucky_charm": MockItemInfo("lucky_charm", "Талисман удачи", "🍀", {"luck_bonus": 0.1}),
    "energy_drink": MockItemInfo("energy_drink", "Энергетик", "🥤", {"reset_fishing_cooldown": True}),
    "shield": MockItemInfo("shield", "Щит", "🛡️", {"loss_protection": True}),
    "vip_status": MockItemInfo("vip_status", "VIP статус", "👑", {"win_bonus": 0.2}),
    "fishing_rod_golden": MockItemInfo("fishing_rod_golden", "Золотая удочка", "🎣", {"rod_bonus": 0.25}),
}


def is_lootbox(item_type: str) -> bool:
    """Check if item is a lootbox."""
    return item_type.startswith("lootbox_")


class MockLootboxInventoryState:
    """Mock inventory state for lootbox testing."""
    
    def __init__(self, items: Dict[str, MockInventoryItem] = None, coins: int = 0):
        self.items = items or {}
        self.coins = coins
    
    def has_item(self, item_type: str) -> bool:
        """Check if user has item with positive quantity."""
        item = self.items.get(item_type)
        return item is not None and item.quantity > 0
    
    def remove_item(self, item_type: str, quantity: int = 1) -> bool:
        """Remove item from inventory."""
        item = self.items.get(item_type)
        if item is None or item.quantity < quantity:
            return False
        item.quantity -= quantity
        return True
    
    def add_item(self, item_type: str, quantity: int = 1) -> bool:
        """Add item to inventory."""
        if item_type in self.items:
            self.items[item_type].quantity += quantity
        else:
            item_info = LOOTBOX_MOCK_CATALOG.get(item_type)
            name = item_info.name if item_info else item_type
            self.items[item_type] = MockInventoryItem(
                item_type=item_type,
                item_name=name,
                quantity=quantity,
                equipped=False
            )
        return True
    
    def add_coins(self, amount: int):
        """Add coins to balance."""
        self.coins += amount
    
    def get_item_quantity(self, item_type: str) -> int:
        """Get quantity of an item."""
        item = self.items.get(item_type)
        return item.quantity if item else 0
    
    def copy(self) -> 'MockLootboxInventoryState':
        """Create a copy of the inventory state."""
        new_items = {}
        for item_type, item in self.items.items():
            new_items[item_type] = MockInventoryItem(
                item_type=item.item_type,
                item_name=item.item_name,
                quantity=item.quantity,
                equipped=item.equipped
            )
        return MockLootboxInventoryState(items=new_items, coins=self.coins)


def mock_lootbox_engine_open(lootbox_tier: str, reward_index: int = 0) -> MockLootboxResult:
    """
    Mock lootbox engine that returns deterministic rewards for testing.
    
    Args:
        lootbox_tier: Tier of lootbox (common, rare, epic, legendary)
        reward_index: Index of reward to return (for deterministic testing)
        
    Returns:
        MockLootboxResult with rewards
    """
    if lootbox_tier not in MOCK_LOOTBOX_CONTENTS:
        return MockLootboxResult(
            success=False,
            message="Неизвестный тип лутбокса",
            rewards=[]
        )
    
    rewards_list = MOCK_LOOTBOX_CONTENTS[lootbox_tier]
    # Use modulo to handle index out of range
    reward = rewards_list[reward_index % len(rewards_list)]
    
    items = [reward.item_type] if reward.item_type else []
    
    return MockLootboxResult(
        success=True,
        message=f"📦 Открываем лутбокс...\n\n{reward.emoji} {reward.name}!",
        rewards=[reward],
        total_coins=reward.coins,
        items=items
    )


def open_lootbox_logic(
    item_type: str,
    inventory_state: MockLootboxInventoryState,
    item_catalog: Dict[str, MockItemInfo],
    lootbox_result: MockLootboxResult
) -> tuple[MockLootboxOpenResult, MockLootboxInventoryState]:
    """
    Pure function implementing lootbox opening logic.
    
    This mirrors the logic from app/handlers/inventory.py open_lootbox()
    but without database dependencies for isolated testing.
    
    Args:
        item_type: Type of lootbox to open
        inventory_state: Current inventory state
        item_catalog: Item catalog for lookups
        lootbox_result: Pre-determined lootbox result (for deterministic testing)
        
    Returns:
        Tuple of (MockLootboxOpenResult, new_inventory_state)
    """
    # Create a copy of inventory state to avoid mutation
    new_state = inventory_state.copy()
    
    # Validate item type is a lootbox
    if not is_lootbox(item_type):
        return MockLootboxOpenResult(
            success=False,
            message="❌ Это не лутбокс!",
            items_received=[]
        ), new_state
    
    # Get item info from catalog
    item_info = item_catalog.get(item_type)
    if not item_info:
        return MockLootboxOpenResult(
            success=False,
            message="❌ Неизвестный предмет",
            items_received=[]
        ), new_state
    
    # Check if user has the lootbox
    if not new_state.has_item(item_type):
        return MockLootboxOpenResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!",
            items_received=[]
        ), new_state
    
    # Remove lootbox from inventory
    if not new_state.remove_item(item_type, 1):
        return MockLootboxOpenResult(
            success=False,
            message="❌ Ошибка при открытии",
            items_received=[]
        ), new_state
    
    # Check if lootbox opening succeeded
    if not lootbox_result.success:
        # Restore lootbox if opening failed
        new_state.add_item(item_type, 1)
        return MockLootboxOpenResult(
            success=False,
            message=f"❌ Ошибка при открытии: {lootbox_result.message}",
            items_received=[]
        ), new_state
    
    # Add coins from lootbox
    coins_received = lootbox_result.total_coins
    if coins_received > 0:
        new_state.add_coins(coins_received)
    
    # Add items to inventory
    items_received = []
    for item_type_received in lootbox_result.items:
        if item_type_received:
            new_state.add_item(item_type_received, 1)
            items_received.append((item_type_received, 1))
    
    return MockLootboxOpenResult(
        success=True,
        message=lootbox_result.message,
        items_received=items_received,
        coins_received=coins_received,
        details={
            "lootbox_type": item_type,
            "rewards": [{"name": r.name, "coins": r.coins, "item_type": r.item_type} 
                       for r in lootbox_result.rewards]
        }
    ), new_state


# ============================================================================
# Strategies for Lootbox Tests
# ============================================================================

# Strategy for lootbox types
lootbox_type_strategy = st.sampled_from([
    "lootbox_common",
    "lootbox_rare",
    "lootbox_epic",
    "lootbox_legendary"
])

# Strategy for lootbox tiers
lootbox_tier_strategy = st.sampled_from(["common", "rare", "epic", "legendary"])

# Strategy for reward index
reward_index_strategy = st.integers(min_value=0, max_value=10)

# Strategy for initial lootbox quantity
lootbox_quantity_strategy = st.integers(min_value=1, max_value=10)


# ============================================================================
# Property Tests for Lootbox Opening
# ============================================================================

class TestLootboxGeneratesItemsAddedToInventory:
    """
    Property 6: Lootbox generates items added to inventory
    
    *For any* lootbox opening, all generated items SHALL be present in 
    user's inventory after the operation.
    
    **Validates: Requirements 6.1, 6.3**
    """

    @given(
        lootbox_type=lootbox_type_strategy,
        initial_quantity=lootbox_quantity_strategy,
        reward_index=reward_index_strategy
    )
    @settings(max_examples=100)
    def test_lootbox_items_added_to_inventory(
        self, 
        lootbox_type: str, 
        initial_quantity: int,
        reward_index: int
    ):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        For any lootbox opening, all generated items should be in inventory after.
        """
        # Setup inventory with lootbox
        inventory = MockLootboxInventoryState(items={
            lootbox_type: MockInventoryItem(
                item_type=lootbox_type,
                item_name=LOOTBOX_MOCK_CATALOG[lootbox_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        # Get lootbox tier
        lootbox_tier = lootbox_type.replace("lootbox_", "")
        
        # Generate lootbox result
        lootbox_result = mock_lootbox_engine_open(lootbox_tier, reward_index)
        
        # Record items before opening
        items_before = {k: v.quantity for k, v in inventory.items.items()}
        
        # Open lootbox
        result, new_state = open_lootbox_logic(
            item_type=lootbox_type,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=lootbox_result
        )
        
        # Should succeed
        assert result.success, f"Lootbox opening should succeed, got: {result.message}"
        
        # All generated items should be in inventory
        for item_type_received, quantity in result.items_received:
            current_qty = new_state.get_item_quantity(item_type_received)
            expected_qty = items_before.get(item_type_received, 0) + quantity
            assert current_qty == expected_qty, \
                f"Item {item_type_received} should have quantity {expected_qty}, got {current_qty}"

    @given(
        lootbox_type=lootbox_type_strategy,
        initial_quantity=lootbox_quantity_strategy,
        reward_index=reward_index_strategy
    )
    @settings(max_examples=100)
    def test_lootbox_consumed_after_opening(
        self, 
        lootbox_type: str, 
        initial_quantity: int,
        reward_index: int
    ):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        After opening, lootbox quantity should decrease by 1.
        """
        # Setup inventory with lootbox
        inventory = MockLootboxInventoryState(items={
            lootbox_type: MockInventoryItem(
                item_type=lootbox_type,
                item_name=LOOTBOX_MOCK_CATALOG[lootbox_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        lootbox_tier = lootbox_type.replace("lootbox_", "")
        lootbox_result = mock_lootbox_engine_open(lootbox_tier, reward_index)
        
        result, new_state = open_lootbox_logic(
            item_type=lootbox_type,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=lootbox_result
        )
        
        assert result.success
        
        # Lootbox quantity should decrease by 1
        expected_qty = initial_quantity - 1
        actual_qty = new_state.get_item_quantity(lootbox_type)
        assert actual_qty == expected_qty, \
            f"Lootbox quantity should be {expected_qty}, got {actual_qty}"

    @given(
        lootbox_type=lootbox_type_strategy,
        reward_index=reward_index_strategy
    )
    @settings(max_examples=100)
    def test_coins_added_to_balance(
        self, 
        lootbox_type: str,
        reward_index: int
    ):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        Coins from lootbox should be added to user's balance.
        """
        initial_coins = 100
        
        inventory = MockLootboxInventoryState(
            items={
                lootbox_type: MockInventoryItem(
                    item_type=lootbox_type,
                    item_name=LOOTBOX_MOCK_CATALOG[lootbox_type].name,
                    quantity=1,
                    equipped=False
                )
            },
            coins=initial_coins
        )
        
        lootbox_tier = lootbox_type.replace("lootbox_", "")
        lootbox_result = mock_lootbox_engine_open(lootbox_tier, reward_index)
        
        result, new_state = open_lootbox_logic(
            item_type=lootbox_type,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=lootbox_result
        )
        
        assert result.success
        
        # Coins should be added
        expected_coins = initial_coins + lootbox_result.total_coins
        assert new_state.coins == expected_coins, \
            f"Coins should be {expected_coins}, got {new_state.coins}"
        assert result.coins_received == lootbox_result.total_coins

    @given(lootbox_type=lootbox_type_strategy)
    @settings(max_examples=100)
    def test_missing_lootbox_rejected(self, lootbox_type: str):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        Opening a lootbox user doesn't have should fail.
        """
        # Empty inventory
        inventory = MockLootboxInventoryState()
        
        lootbox_tier = lootbox_type.replace("lootbox_", "")
        lootbox_result = mock_lootbox_engine_open(lootbox_tier, 0)
        
        result, new_state = open_lootbox_logic(
            item_type=lootbox_type,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=lootbox_result
        )
        
        assert not result.success, "Opening missing lootbox should fail"
        assert "нет" in result.message.lower()

    @given(non_lootbox=st.sampled_from(["basic_rod", "pp_cream_small", "energy_drink"]))
    @settings(max_examples=100)
    def test_non_lootbox_items_rejected(self, non_lootbox: str):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        Non-lootbox items should be rejected.
        """
        inventory = MockLootboxInventoryState(items={
            non_lootbox: MockInventoryItem(
                item_type=non_lootbox,
                item_name="Test Item",
                quantity=1,
                equipped=False
            )
        })
        
        lootbox_result = mock_lootbox_engine_open("common", 0)
        
        result, new_state = open_lootbox_logic(
            item_type=non_lootbox,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=lootbox_result
        )
        
        assert not result.success, "Non-lootbox item should be rejected"
        assert "не лутбокс" in result.message.lower()

    @given(
        lootbox_type=lootbox_type_strategy,
        initial_quantity=lootbox_quantity_strategy
    )
    @settings(max_examples=100)
    def test_failed_engine_restores_lootbox(
        self, 
        lootbox_type: str, 
        initial_quantity: int
    ):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        If lootbox engine fails, lootbox should be restored to inventory.
        """
        inventory = MockLootboxInventoryState(items={
            lootbox_type: MockInventoryItem(
                item_type=lootbox_type,
                item_name=LOOTBOX_MOCK_CATALOG[lootbox_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        # Create a failed lootbox result
        failed_result = MockLootboxResult(
            success=False,
            message="Engine error",
            rewards=[]
        )
        
        result, new_state = open_lootbox_logic(
            item_type=lootbox_type,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=failed_result
        )
        
        assert not result.success
        
        # Lootbox should be restored
        actual_qty = new_state.get_item_quantity(lootbox_type)
        assert actual_qty == initial_quantity, \
            f"Lootbox should be restored to {initial_quantity}, got {actual_qty}"

    @given(
        lootbox_type=lootbox_type_strategy,
        reward_index=reward_index_strategy
    )
    @settings(max_examples=100)
    def test_items_received_matches_engine_output(
        self, 
        lootbox_type: str,
        reward_index: int
    ):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        Items received should match what the lootbox engine generated.
        """
        inventory = MockLootboxInventoryState(items={
            lootbox_type: MockInventoryItem(
                item_type=lootbox_type,
                item_name=LOOTBOX_MOCK_CATALOG[lootbox_type].name,
                quantity=1,
                equipped=False
            )
        })
        
        lootbox_tier = lootbox_type.replace("lootbox_", "")
        lootbox_result = mock_lootbox_engine_open(lootbox_tier, reward_index)
        
        result, new_state = open_lootbox_logic(
            item_type=lootbox_type,
            inventory_state=inventory,
            item_catalog=LOOTBOX_MOCK_CATALOG,
            lootbox_result=lootbox_result
        )
        
        assert result.success
        
        # Items received should match engine output
        expected_items = [(item, 1) for item in lootbox_result.items if item]
        assert result.items_received == expected_items, \
            f"Items received {result.items_received} should match engine output {expected_items}"

    @given(
        lootbox_type=lootbox_type_strategy,
        initial_quantity=lootbox_quantity_strategy,
        num_opens=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=100)
    def test_multiple_opens_accumulate_items(
        self, 
        lootbox_type: str, 
        initial_quantity: int,
        num_opens: int
    ):
        """
        Feature: unified-inventory, Property 6: Lootbox generates items added to inventory
        **Validates: Requirements 6.1, 6.3**
        
        Opening multiple lootboxes should accumulate items correctly.
        """
        # Ensure we have enough lootboxes
        actual_quantity = max(initial_quantity, num_opens)
        
        inventory = MockLootboxInventoryState(items={
            lootbox_type: MockInventoryItem(
                item_type=lootbox_type,
                item_name=LOOTBOX_MOCK_CATALOG[lootbox_type].name,
                quantity=actual_quantity,
                equipped=False
            )
        })
        
        lootbox_tier = lootbox_type.replace("lootbox_", "")
        total_coins = 0
        total_items: Dict[str, int] = {}
        
        current_state = inventory
        
        for i in range(num_opens):
            lootbox_result = mock_lootbox_engine_open(lootbox_tier, i)
            
            result, current_state = open_lootbox_logic(
                item_type=lootbox_type,
                inventory_state=current_state,
                item_catalog=LOOTBOX_MOCK_CATALOG,
                lootbox_result=lootbox_result
            )
            
            assert result.success, f"Open {i+1} should succeed"
            
            total_coins += result.coins_received
            for item, qty in result.items_received:
                total_items[item] = total_items.get(item, 0) + qty
        
        # Verify final state
        assert current_state.coins == total_coins, \
            f"Total coins should be {total_coins}, got {current_state.coins}"
        
        for item_type, expected_qty in total_items.items():
            actual_qty = current_state.get_item_quantity(item_type)
            assert actual_qty == expected_qty, \
                f"Item {item_type} should have quantity {expected_qty}, got {actual_qty}"
        
        # Lootbox quantity should decrease by num_opens
        remaining_lootboxes = current_state.get_item_quantity(lootbox_type)
        assert remaining_lootboxes == actual_quantity - num_opens, \
            f"Should have {actual_quantity - num_opens} lootboxes remaining, got {remaining_lootboxes}"


# ============================================================================
# Consumable Quantity Management Functions (for isolated testing)
# ============================================================================

@dataclass
class MockConsumableInventoryState:
    """Mock inventory state for consumable quantity testing."""
    
    def __init__(self, items: Dict[str, MockInventoryItem] = None):
        self.items = items or {}
    
    def has_item(self, item_type: str) -> bool:
        """Check if user has item with positive quantity."""
        item = self.items.get(item_type)
        return item is not None and item.quantity > 0
    
    def get_item_quantity(self, item_type: str) -> int:
        """Get quantity of an item."""
        item = self.items.get(item_type)
        return item.quantity if item else 0
    
    def remove_item(self, item_type: str, quantity: int = 1) -> tuple[bool, int]:
        """
        Remove item from inventory.
        
        Returns:
            Tuple of (success, remaining_quantity)
            If quantity reaches 0, item is removed from inventory.
        """
        item = self.items.get(item_type)
        if item is None or item.quantity < quantity:
            return False, item.quantity if item else 0
        
        item.quantity -= quantity
        remaining = item.quantity
        
        # Remove item from inventory if quantity reaches 0
        if item.quantity <= 0:
            del self.items[item_type]
        
        return True, remaining
    
    def item_exists(self, item_type: str) -> bool:
        """Check if item exists in inventory (regardless of quantity)."""
        return item_type in self.items
    
    def copy(self) -> 'MockConsumableInventoryState':
        """Create a copy of the inventory state."""
        new_items = {}
        for item_type, item in self.items.items():
            new_items[item_type] = MockInventoryItem(
                item_type=item.item_type,
                item_name=item.item_name,
                quantity=item.quantity,
                equipped=item.equipped
            )
        return MockConsumableInventoryState(items=new_items)


@dataclass
class MockConsumableUseResult:
    """Mock result of using a consumable."""
    success: bool
    message: str
    quantity_before: int
    quantity_after: int
    item_removed: bool  # True if item was removed from inventory (quantity reached 0)


# Consumable item types for testing
CONSUMABLE_TYPES = [
    "pp_cream_small",
    "pp_cream_medium", 
    "pp_cream_large",
    "pp_cream_titan",
    "energy_drink",
    "lucky_charm",
    "shield",
    "vip_status",
    "double_xp",
]

# Mock catalog for consumables
CONSUMABLE_MOCK_CATALOG = {
    "pp_cream_small": MockItemInfo("pp_cream_small", "Мазь 'Подрастай'", "🧴", {"pp_boost_min": 1, "pp_boost_max": 3}),
    "pp_cream_medium": MockItemInfo("pp_cream_medium", "Крем 'Титан'", "🧴", {"pp_boost_min": 2, "pp_boost_max": 5}),
    "pp_cream_large": MockItemInfo("pp_cream_large", "Гель 'Мегамен'", "🧴", {"pp_boost_min": 5, "pp_boost_max": 10}),
    "pp_cream_titan": MockItemInfo("pp_cream_titan", "Эликсир 'Годзилла'", "🧪", {"pp_boost_min": 10, "pp_boost_max": 20}),
    "energy_drink": MockItemInfo("energy_drink", "Энергетик", "🥤", {"reset_fishing_cooldown": True}),
    "lucky_charm": MockItemInfo("lucky_charm", "Талисман удачи", "🍀", {"luck_bonus": 0.1}),
    "shield": MockItemInfo("shield", "Щит", "🛡️", {"loss_protection": True}),
    "vip_status": MockItemInfo("vip_status", "VIP статус", "👑", {"win_bonus": 0.2, "duration_hours": 24}),
    "double_xp": MockItemInfo("double_xp", "Энергетик x2", "⚡", {"xp_bonus": 2.0, "duration_hours": 1}),
}


def use_consumable_logic(
    item_type: str,
    inventory_state: MockConsumableInventoryState,
    item_catalog: Dict[str, MockItemInfo],
    effect_succeeds: bool = True
) -> tuple[MockConsumableUseResult, MockConsumableInventoryState]:
    """
    Pure function implementing consumable usage logic.
    
    This mirrors the logic from app/handlers/inventory.py for consumable usage
    but without database dependencies for isolated testing.
    
    The key behavior being tested:
    - Quantity decreases by 1 on successful use
    - Item is removed from inventory when quantity reaches 0
    
    Args:
        item_type: Type of consumable item
        inventory_state: Current inventory state
        item_catalog: Item catalog for lookups
        effect_succeeds: Whether the item effect succeeds (for testing)
        
    Returns:
        Tuple of (MockConsumableUseResult, new_inventory_state)
    """
    # Create a copy of inventory state to avoid mutation
    new_state = inventory_state.copy()
    
    # Get item info from catalog
    item_info = item_catalog.get(item_type)
    if not item_info:
        return MockConsumableUseResult(
            success=False,
            message="❌ Неизвестный предмет",
            quantity_before=0,
            quantity_after=0,
            item_removed=False
        ), new_state
    
    # Check if user has the item
    quantity_before = new_state.get_item_quantity(item_type)
    if not new_state.has_item(item_type):
        return MockConsumableUseResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!",
            quantity_before=quantity_before,
            quantity_after=quantity_before,
            item_removed=False
        ), new_state
    
    # Simulate effect application
    if not effect_succeeds:
        return MockConsumableUseResult(
            success=False,
            message="❌ Ошибка при применении эффекта",
            quantity_before=quantity_before,
            quantity_after=quantity_before,
            item_removed=False
        ), new_state
    
    # Remove item from inventory (decrease quantity by 1)
    success, quantity_after = new_state.remove_item(item_type, 1)
    
    if not success:
        return MockConsumableUseResult(
            success=False,
            message="❌ Ошибка при использовании",
            quantity_before=quantity_before,
            quantity_after=quantity_before,
            item_removed=False
        ), new_state
    
    # Check if item was removed (quantity reached 0)
    item_removed = not new_state.item_exists(item_type)
    
    return MockConsumableUseResult(
        success=True,
        message=f"✅ Использован {item_info.emoji} {item_info.name}!",
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        item_removed=item_removed
    ), new_state


# ============================================================================
# Strategies for Consumable Quantity Tests
# ============================================================================

# Strategy for consumable types
consumable_type_strategy = st.sampled_from(CONSUMABLE_TYPES)

# Strategy for initial quantity (positive values)
positive_quantity_strategy = st.integers(min_value=1, max_value=99)

# Strategy for quantity that will reach zero after use
quantity_one_strategy = st.just(1)


# ============================================================================
# Property Tests for Consumable Quantity Management
# ============================================================================

class TestConsumableUsageDecreasesQuantity:
    """
    Property 1: Consumable usage decreases quantity and removes at zero
    
    *For any* consumable item with quantity N > 0, using it SHALL result in 
    quantity N-1, and if N-1 = 0, the item SHALL not appear in inventory display.
    
    **Validates: Requirements 1.2, 1.4**
    """

    @given(
        item_type=consumable_type_strategy,
        initial_quantity=positive_quantity_strategy
    )
    @settings(max_examples=100)
    def test_consumable_usage_decreases_quantity_by_one(
        self, 
        item_type: str, 
        initial_quantity: int
    ):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        For any consumable with quantity N > 0, using it should result in quantity N-1.
        """
        # Setup inventory with consumable
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        # Use the consumable
        result, new_state = use_consumable_logic(
            item_type=item_type,
            inventory_state=inventory,
            item_catalog=CONSUMABLE_MOCK_CATALOG,
            effect_succeeds=True
        )
        
        # Should succeed
        assert result.success, f"Consumable usage should succeed, got: {result.message}"
        
        # Quantity should decrease by exactly 1
        assert result.quantity_before == initial_quantity, \
            f"Quantity before should be {initial_quantity}, got {result.quantity_before}"
        assert result.quantity_after == initial_quantity - 1, \
            f"Quantity after should be {initial_quantity - 1}, got {result.quantity_after}"

    @given(item_type=consumable_type_strategy)
    @settings(max_examples=100)
    def test_consumable_removed_when_quantity_reaches_zero(self, item_type: str):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        When quantity reaches 0, item should be removed from inventory.
        """
        # Setup inventory with quantity = 1
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=1,
                equipped=False
            )
        })
        
        # Use the consumable
        result, new_state = use_consumable_logic(
            item_type=item_type,
            inventory_state=inventory,
            item_catalog=CONSUMABLE_MOCK_CATALOG,
            effect_succeeds=True
        )
        
        # Should succeed
        assert result.success
        
        # Quantity should be 0
        assert result.quantity_after == 0, \
            f"Quantity after should be 0, got {result.quantity_after}"
        
        # Item should be removed from inventory
        assert result.item_removed, "Item should be marked as removed"
        assert not new_state.item_exists(item_type), \
            f"Item {item_type} should not exist in inventory after quantity reaches 0"

    @given(
        item_type=consumable_type_strategy,
        initial_quantity=st.integers(min_value=2, max_value=99)
    )
    @settings(max_examples=100)
    def test_consumable_not_removed_when_quantity_above_zero(
        self, 
        item_type: str, 
        initial_quantity: int
    ):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        When quantity is still above 0 after use, item should remain in inventory.
        """
        # Setup inventory with quantity > 1
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        # Use the consumable
        result, new_state = use_consumable_logic(
            item_type=item_type,
            inventory_state=inventory,
            item_catalog=CONSUMABLE_MOCK_CATALOG,
            effect_succeeds=True
        )
        
        # Should succeed
        assert result.success
        
        # Quantity should be > 0
        assert result.quantity_after > 0, \
            f"Quantity after should be > 0, got {result.quantity_after}"
        
        # Item should NOT be removed from inventory
        assert not result.item_removed, "Item should not be marked as removed"
        assert new_state.item_exists(item_type), \
            f"Item {item_type} should still exist in inventory"

    @given(
        item_type=consumable_type_strategy,
        initial_quantity=positive_quantity_strategy,
        num_uses=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_multiple_uses_decrease_quantity_correctly(
        self, 
        item_type: str, 
        initial_quantity: int,
        num_uses: int
    ):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        Multiple uses should decrease quantity by the number of uses.
        """
        # Ensure we have enough items
        actual_quantity = max(initial_quantity, num_uses)
        
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=actual_quantity,
                equipped=False
            )
        })
        
        current_state = inventory
        successful_uses = 0
        
        for i in range(num_uses):
            result, current_state = use_consumable_logic(
                item_type=item_type,
                inventory_state=current_state,
                item_catalog=CONSUMABLE_MOCK_CATALOG,
                effect_succeeds=True
            )
            
            if result.success:
                successful_uses += 1
        
        # All uses should succeed
        assert successful_uses == num_uses, \
            f"All {num_uses} uses should succeed, got {successful_uses}"
        
        # Final quantity should be initial - num_uses
        expected_final = actual_quantity - num_uses
        actual_final = current_state.get_item_quantity(item_type)
        
        if expected_final <= 0:
            assert not current_state.item_exists(item_type), \
                "Item should be removed when quantity reaches 0"
        else:
            assert actual_final == expected_final, \
                f"Final quantity should be {expected_final}, got {actual_final}"

    @given(item_type=consumable_type_strategy)
    @settings(max_examples=100)
    def test_using_missing_item_fails(self, item_type: str):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        Using an item not in inventory should fail without changing state.
        """
        # Empty inventory
        inventory = MockConsumableInventoryState()
        
        result, new_state = use_consumable_logic(
            item_type=item_type,
            inventory_state=inventory,
            item_catalog=CONSUMABLE_MOCK_CATALOG,
            effect_succeeds=True
        )
        
        # Should fail
        assert not result.success, "Using missing item should fail"
        assert "нет" in result.message.lower(), "Error message should mention missing item"
        
        # Quantity should remain 0
        assert result.quantity_before == 0
        assert result.quantity_after == 0
        assert not result.item_removed

    @given(
        item_type=consumable_type_strategy,
        initial_quantity=positive_quantity_strategy
    )
    @settings(max_examples=100)
    def test_failed_effect_does_not_decrease_quantity(
        self, 
        item_type: str, 
        initial_quantity: int
    ):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        If the item effect fails, quantity should not decrease.
        """
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        # Use with effect failure
        result, new_state = use_consumable_logic(
            item_type=item_type,
            inventory_state=inventory,
            item_catalog=CONSUMABLE_MOCK_CATALOG,
            effect_succeeds=False  # Effect fails
        )
        
        # Should fail
        assert not result.success
        
        # Quantity should remain unchanged
        assert result.quantity_before == initial_quantity
        assert result.quantity_after == initial_quantity
        assert not result.item_removed
        
        # Item should still exist with original quantity
        assert new_state.get_item_quantity(item_type) == initial_quantity

    @given(item_type=consumable_type_strategy)
    @settings(max_examples=100)
    def test_zero_quantity_item_cannot_be_used(self, item_type: str):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        An item with quantity 0 should not be usable.
        """
        # Setup inventory with quantity = 0 (edge case - shouldn't normally exist)
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=0,
                equipped=False
            )
        })
        
        result, new_state = use_consumable_logic(
            item_type=item_type,
            inventory_state=inventory,
            item_catalog=CONSUMABLE_MOCK_CATALOG,
            effect_succeeds=True
        )
        
        # Should fail because has_item returns False for quantity <= 0
        assert not result.success, "Item with quantity 0 should not be usable"

    @given(
        item_type=consumable_type_strategy,
        initial_quantity=positive_quantity_strategy
    )
    @settings(max_examples=100)
    def test_quantity_never_goes_negative(
        self, 
        item_type: str, 
        initial_quantity: int
    ):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        Quantity should never become negative.
        """
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        current_state = inventory
        
        # Try to use more times than we have items
        for _ in range(initial_quantity + 5):
            result, current_state = use_consumable_logic(
                item_type=item_type,
                inventory_state=current_state,
                item_catalog=CONSUMABLE_MOCK_CATALOG,
                effect_succeeds=True
            )
            
            # Quantity should never be negative
            assert result.quantity_after >= 0, \
                f"Quantity should never be negative, got {result.quantity_after}"
            
            # If item still exists, quantity should be positive
            if current_state.item_exists(item_type):
                qty = current_state.get_item_quantity(item_type)
                assert qty > 0, f"Existing item should have positive quantity, got {qty}"

    @given(
        item_type=consumable_type_strategy,
        initial_quantity=positive_quantity_strategy
    )
    @settings(max_examples=100)
    def test_inventory_display_excludes_used_up_items(
        self, 
        item_type: str, 
        initial_quantity: int
    ):
        """
        Feature: unified-inventory, Property 1: Consumable usage decreases quantity and removes at zero
        **Validates: Requirements 1.2, 1.4**
        
        After using all items, the item should not appear in inventory display.
        """
        inventory = MockConsumableInventoryState(items={
            item_type: MockInventoryItem(
                item_type=item_type,
                item_name=CONSUMABLE_MOCK_CATALOG[item_type].name,
                quantity=initial_quantity,
                equipped=False
            )
        })
        
        current_state = inventory
        
        # Use all items
        for _ in range(initial_quantity):
            result, current_state = use_consumable_logic(
                item_type=item_type,
                inventory_state=current_state,
                item_catalog=CONSUMABLE_MOCK_CATALOG,
                effect_succeeds=True
            )
        
        # Item should not exist in inventory
        assert not current_state.item_exists(item_type), \
            f"Item {item_type} should not exist after using all {initial_quantity} items"
        
        # Build display from remaining items (should be empty or not contain this item)
        remaining_items = list(current_state.items.values())
        display_text = build_inventory_display(remaining_items)
        
        item_info = CONSUMABLE_MOCK_CATALOG.get(item_type)
        if item_info:
            # The item name should not appear in display
            assert item_info.name not in display_text or display_text == "📭 Пусто!", \
                f"Used up item '{item_info.name}' should not appear in display"
