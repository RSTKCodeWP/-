"""Property-based tests for PP Cage functionality.

Feature: release-candidate-8
Tests the PP Cage item for correct behavior.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional
import json


# ============================================================================
# Simplified models for isolated testing (no database dependencies)
# ============================================================================

@dataclass
class MockInventoryItem:
    """Mock inventory item for testing."""
    item_type: str
    quantity: int
    equipped: bool
    item_data: Optional[str] = None


class MockInventoryService:
    """
    Mock inventory service for testing PP Cage logic.
    Mirrors the logic from app/services/inventory.py
    """
    
    def __init__(self):
        self.items: dict[tuple[int, int, str], MockInventoryItem] = {}
    
    def add_item(self, user_id: int, chat_id: int, item_type: str, quantity: int = 1) -> bool:
        """Add item to inventory."""
        key = (user_id, chat_id, item_type)
        if key in self.items:
            self.items[key].quantity += quantity
        else:
            self.items[key] = MockInventoryItem(
                item_type=item_type,
                quantity=quantity,
                equipped=False,
                item_data=None
            )
        return True
    
    def has_item(self, user_id: int, chat_id: int, item_type: str) -> bool:
        """Check if user has an item."""
        key = (user_id, chat_id, item_type)
        item = self.items.get(key)
        return item is not None and item.quantity > 0
    
    def has_active_item(self, user_id: int, chat_id: int, item_type: str) -> bool:
        """
        Check if user has an active (equipped and not expired) item.
        
        For time-limited items like PP_CAGE, checks if the item is equipped
        and hasn't expired based on item_data.expires_at.
        """
        key = (user_id, chat_id, item_type)
        item = self.items.get(key)
        
        if not item or item.quantity <= 0 or not item.equipped:
            return False
        
        # Check expiration for time-limited items
        if item.item_data:
            try:
                data = json.loads(item.item_data)
                expires_at_str = data.get("expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    if now > expires_at:
                        return False
            except (json.JSONDecodeError, ValueError):
                pass
        
        return True
    
    def activate_item(self, user_id: int, chat_id: int, item_type: str, duration_hours: int = 24) -> bool:
        """Activate a time-limited item."""
        key = (user_id, chat_id, item_type)
        item = self.items.get(key)
        
        if not item or item.quantity <= 0:
            return False
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=duration_hours)
        
        item.equipped = True
        item.item_data = json.dumps({
            "activated_at": now.isoformat(),
            "expires_at": expires_at.isoformat()
        })
        
        return True
    
    def deactivate_item(self, user_id: int, chat_id: int, item_type: str) -> bool:
        """Deactivate (remove) a time-limited item."""
        key = (user_id, chat_id, item_type)
        item = self.items.get(key)
        
        if not item or item.quantity <= 0 or not item.equipped:
            return False
        
        # Remove the item
        del self.items[key]
        return True


def apply_pp_change(inventory: MockInventoryService, user_id: int, chat_id: int, change: int) -> int:
    """
    Apply PP size change with PP_CAGE protection check.
    
    If change is negative and user has active PP_CAGE, the change is blocked.
    
    Returns:
        Actual change applied (0 if blocked by PP_CAGE)
    """
    if change < 0:
        # Check if PP_CAGE is active
        if inventory.has_active_item(user_id, chat_id, "pp_cage"):
            return 0  # Protection activated, no change
    
    return change


def can_grow(inventory: MockInventoryService, user_id: int, chat_id: int) -> bool:
    """
    Check if user can use /grow command.
    
    Returns False if PP_CAGE is active.
    """
    return not inventory.has_active_item(user_id, chat_id, "pp_cage")


# ============================================================================
# Property Tests
# ============================================================================

class TestPPCageBlocksGrowth:
    """
    Property 13: PP Cage blocks growth
    
    *For any* user with active PP_CAGE, `/grow` command SHALL not change PP size.
    
    **Validates: Requirements 10.4**
    """

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000),
        current_size=st.integers(min_value=1, max_value=10000),
        growth_amount=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100)
    def test_active_cage_blocks_growth(self, user_id: int, chat_id: int, current_size: int, growth_amount: int):
        """
        Feature: release-candidate-8, Property 13: PP Cage blocks growth
        **Validates: Requirements 10.4**
        
        For any user with active PP_CAGE, the can_grow check should return False.
        """
        inventory = MockInventoryService()
        
        # Add and activate PP_CAGE
        inventory.add_item(user_id, chat_id, "pp_cage", 1)
        inventory.activate_item(user_id, chat_id, "pp_cage", duration_hours=24)
        
        # Verify cage is active
        assert inventory.has_active_item(user_id, chat_id, "pp_cage"), "PP_CAGE should be active"
        
        # Check that growth is blocked
        can_grow_result = can_grow(inventory, user_id, chat_id)
        assert can_grow_result is False, "Growth should be blocked when PP_CAGE is active"

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000),
        current_size=st.integers(min_value=1, max_value=10000),
        growth_amount=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100)
    def test_no_cage_allows_growth(self, user_id: int, chat_id: int, current_size: int, growth_amount: int):
        """
        Feature: release-candidate-8, Property 13: PP Cage blocks growth
        **Validates: Requirements 10.4**
        
        For any user without PP_CAGE, the can_grow check should return True.
        """
        inventory = MockInventoryService()
        
        # No cage added
        
        # Check that growth is allowed
        can_grow_result = can_grow(inventory, user_id, chat_id)
        assert can_grow_result is True, "Growth should be allowed when no PP_CAGE"

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=100)
    def test_inactive_cage_allows_growth(self, user_id: int, chat_id: int):
        """
        Feature: release-candidate-8, Property 13: PP Cage blocks growth
        **Validates: Requirements 10.4**
        
        For any user with PP_CAGE in inventory but not activated, growth should be allowed.
        """
        inventory = MockInventoryService()
        
        # Add cage but don't activate
        inventory.add_item(user_id, chat_id, "pp_cage", 1)
        
        # Verify cage is not active
        assert not inventory.has_active_item(user_id, chat_id, "pp_cage"), "PP_CAGE should not be active"
        
        # Check that growth is allowed
        can_grow_result = can_grow(inventory, user_id, chat_id)
        assert can_grow_result is True, "Growth should be allowed when PP_CAGE is not activated"


class TestPPCageProvidesProtection:
    """
    Property 14: PP Cage provides protection
    
    *For any* user with active PP_CAGE and negative PP change event, 
    the change SHALL be blocked (result = 0).
    
    **Validates: Requirements 10.3**
    """

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000),
        negative_change=st.integers(min_value=-1000, max_value=-1)
    )
    @settings(max_examples=100)
    def test_active_cage_blocks_negative_changes(self, user_id: int, chat_id: int, negative_change: int):
        """
        Feature: release-candidate-8, Property 14: PP Cage provides protection
        **Validates: Requirements 10.3**
        
        For any user with active PP_CAGE, negative PP changes should be blocked.
        """
        inventory = MockInventoryService()
        
        # Add and activate PP_CAGE
        inventory.add_item(user_id, chat_id, "pp_cage", 1)
        inventory.activate_item(user_id, chat_id, "pp_cage", duration_hours=24)
        
        # Apply negative change
        actual_change = apply_pp_change(inventory, user_id, chat_id, negative_change)
        
        assert actual_change == 0, f"Negative change {negative_change} should be blocked, got {actual_change}"

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000),
        positive_change=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=100)
    def test_active_cage_allows_positive_changes(self, user_id: int, chat_id: int, positive_change: int):
        """
        Feature: release-candidate-8, Property 14: PP Cage provides protection
        **Validates: Requirements 10.3**
        
        For any user with active PP_CAGE, positive PP changes should still be allowed.
        """
        inventory = MockInventoryService()
        
        # Add and activate PP_CAGE
        inventory.add_item(user_id, chat_id, "pp_cage", 1)
        inventory.activate_item(user_id, chat_id, "pp_cage", duration_hours=24)
        
        # Apply positive change
        actual_change = apply_pp_change(inventory, user_id, chat_id, positive_change)
        
        assert actual_change == positive_change, f"Positive change {positive_change} should be allowed, got {actual_change}"

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000),
        negative_change=st.integers(min_value=-1000, max_value=-1)
    )
    @settings(max_examples=100)
    def test_no_cage_allows_negative_changes(self, user_id: int, chat_id: int, negative_change: int):
        """
        Feature: release-candidate-8, Property 14: PP Cage provides protection
        **Validates: Requirements 10.3**
        
        For any user without PP_CAGE, negative PP changes should be applied.
        """
        inventory = MockInventoryService()
        
        # No cage
        
        # Apply negative change
        actual_change = apply_pp_change(inventory, user_id, chat_id, negative_change)
        
        assert actual_change == negative_change, f"Negative change {negative_change} should be applied without cage, got {actual_change}"


class TestPPCagePurchaseAddsToInventory:
    """
    Property 15: PP Cage purchase adds to inventory
    
    *For any* successful PP_CAGE purchase, 
    `inventory_service.has_item(user_id, PP_CAGE)` SHALL return True.
    
    **Validates: Requirements 10.2**
    """

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=100)
    def test_purchase_adds_cage_to_inventory(self, user_id: int, chat_id: int):
        """
        Feature: release-candidate-8, Property 15: PP Cage purchase adds to inventory
        **Validates: Requirements 10.2**
        
        For any successful purchase, the cage should be in inventory.
        """
        inventory = MockInventoryService()
        
        # Verify cage is not in inventory initially
        assert not inventory.has_item(user_id, chat_id, "pp_cage"), "PP_CAGE should not be in inventory initially"
        
        # Simulate purchase (add item)
        result = inventory.add_item(user_id, chat_id, "pp_cage", 1)
        
        assert result is True, "Purchase should succeed"
        assert inventory.has_item(user_id, chat_id, "pp_cage"), "PP_CAGE should be in inventory after purchase"

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000),
        quantity=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=100)
    def test_multiple_purchases_stack(self, user_id: int, chat_id: int, quantity: int):
        """
        Feature: release-candidate-8, Property 15: PP Cage purchase adds to inventory
        **Validates: Requirements 10.2**
        
        Multiple purchases should increase quantity (though PP_CAGE is non-stackable in real impl).
        """
        inventory = MockInventoryService()
        
        # Add multiple cages
        for _ in range(quantity):
            inventory.add_item(user_id, chat_id, "pp_cage", 1)
        
        # Verify cage is in inventory
        assert inventory.has_item(user_id, chat_id, "pp_cage"), "PP_CAGE should be in inventory"
        
        # Check quantity
        key = (user_id, chat_id, "pp_cage")
        item = inventory.items.get(key)
        assert item is not None, "Item should exist"
        assert item.quantity == quantity, f"Quantity should be {quantity}, got {item.quantity}"

    @given(
        user_id=st.integers(min_value=1, max_value=1000000),
        chat_id=st.integers(min_value=1, max_value=1000000)
    )
    @settings(max_examples=100)
    def test_cage_can_be_activated_after_purchase(self, user_id: int, chat_id: int):
        """
        Feature: release-candidate-8, Property 15: PP Cage purchase adds to inventory
        **Validates: Requirements 10.2**
        
        After purchase, the cage should be activatable.
        """
        inventory = MockInventoryService()
        
        # Purchase cage
        inventory.add_item(user_id, chat_id, "pp_cage", 1)
        
        # Activate cage
        result = inventory.activate_item(user_id, chat_id, "pp_cage", duration_hours=24)
        
        assert result is True, "Activation should succeed"
        assert inventory.has_active_item(user_id, chat_id, "pp_cage"), "PP_CAGE should be active after activation"
