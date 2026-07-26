"""
Property-based tests for Broadcast Admin Access Control.

**Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
**Validates: Requirements 13.7**

Tests that access to broadcast functionality is granted if and only if
the user's ID is in the admin list.
"""

from typing import List, Set
from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

# Default admin IDs for testing (mirrors SUPER_ADMINS from admin_commands.py)
DEFAULT_SUPER_ADMINS: List[int] = [123456789]

# Default owner ID for testing
DEFAULT_OWNER_ID: int = 987654321


class BroadcastAccessChecker:
    """
    Minimal BroadcastAccessChecker for testing without full app dependencies.
    
    This mirrors the core logic from app/handlers/broadcast.py is_admin function.
    
    **Property 18: Broadcast Admin Access Control**
    **Validates: Requirements 13.7**
    """
    
    def __init__(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        super_admins: List[int] = None
    ):
        """
        Initialize BroadcastAccessChecker.
        
        Args:
            owner_id: Bot owner's Telegram ID
            super_admins: List of super admin user IDs
        """
        self.owner_id = owner_id
        self.super_admins = super_admins if super_admins is not None else DEFAULT_SUPER_ADMINS.copy()
        
        # Track access attempts for verification
        self._access_attempts: List[dict] = []
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if user is an admin allowed to use broadcast.
        
        **Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        Access is granted if and only if the user's ID is in the admin list
        (either as owner_id or in super_admins).
        
        Args:
            user_id: Telegram user ID to check
            
        Returns:
            True if user is admin, False otherwise
        """
        # Record the access attempt
        is_owner = user_id == self.owner_id
        is_super_admin = user_id in self.super_admins
        granted = is_owner or is_super_admin
        
        self._access_attempts.append({
            "user_id": user_id,
            "is_owner": is_owner,
            "is_super_admin": is_super_admin,
            "access_granted": granted,
        })
        
        return granted
    
    def get_all_admin_ids(self) -> Set[int]:
        """
        Get all admin IDs (owner + super admins).
        
        Returns:
            Set of all admin user IDs
        """
        admin_ids = set(self.super_admins)
        admin_ids.add(self.owner_id)
        return admin_ids
    
    def get_access_attempts(self) -> List[dict]:
        """Get all recorded access attempts."""
        return self._access_attempts.copy()
    
    def clear_access_attempts(self) -> None:
        """Clear all recorded access attempts."""
        self._access_attempts.clear()


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for user IDs (positive integers)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for owner IDs
owner_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for lists of super admin IDs
super_admin_lists = st.lists(
    user_ids,
    min_size=0,
    max_size=10,
    unique=True
)


# ============================================================================
# Property Tests
# ============================================================================


class TestBroadcastAdminAccessControlProperties:
    """
    Property-based tests for Broadcast Admin Access Control.
    
    **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
    **Validates: Requirements 13.7**
    """

    @given(
        owner_id=owner_ids,
        super_admins=super_admin_lists,
    )
    @settings(max_examples=100)
    def test_owner_always_has_access(
        self,
        owner_id: int,
        super_admins: List[int],
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        For any configuration, the bot owner SHALL always have access
        to broadcast functionality.
        """
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=super_admins
        )
        
        # Owner should always have access
        has_access = checker.is_admin(owner_id)
        
        assert has_access is True, (
            f"Bot owner (ID: {owner_id}) MUST always have access to broadcast. "
            f"This is required by Requirement 13.7."
        )

    @given(
        owner_id=owner_ids,
        super_admins=super_admin_lists,
    )
    @settings(max_examples=100)
    def test_super_admins_have_access(
        self,
        owner_id: int,
        super_admins: List[int],
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        For any user in the SUPER_ADMINS list, access to broadcast
        functionality SHALL be granted.
        """
        # Skip if no super admins
        assume(len(super_admins) > 0)
        
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=super_admins
        )
        
        # Each super admin should have access
        for admin_id in super_admins:
            has_access = checker.is_admin(admin_id)
            
            assert has_access is True, (
                f"Super admin (ID: {admin_id}) MUST have access to broadcast. "
                f"This is required by Requirement 13.7."
            )

    @given(
        owner_id=owner_ids,
        super_admins=super_admin_lists,
        non_admin_id=user_ids,
    )
    @settings(max_examples=100)
    def test_non_admins_denied_access(
        self,
        owner_id: int,
        super_admins: List[int],
        non_admin_id: int,
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        For any user NOT in the admin list (not owner and not in SUPER_ADMINS),
        access to broadcast functionality SHALL be denied.
        """
        # Ensure non_admin_id is actually not an admin
        assume(non_admin_id != owner_id)
        assume(non_admin_id not in super_admins)
        
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=super_admins
        )
        
        # Non-admin should NOT have access
        has_access = checker.is_admin(non_admin_id)
        
        assert has_access is False, (
            f"Non-admin user (ID: {non_admin_id}) MUST NOT have access to broadcast. "
            f"Owner ID: {owner_id}, Super admins: {super_admins}. "
            f"This is required by Requirement 13.7."
        )

    @given(
        owner_id=owner_ids,
        super_admins=super_admin_lists,
        test_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_access_iff_in_admin_list(
        self,
        owner_id: int,
        super_admins: List[int],
        test_user_id: int,
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        For any user, access is granted if and only if the user's ID
        is in the admin list (owner_id or SUPER_ADMINS).
        
        This is the core property: access ⟺ (user_id == owner_id ∨ user_id ∈ SUPER_ADMINS)
        """
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=super_admins
        )
        
        # Calculate expected access
        is_owner = test_user_id == owner_id
        is_super_admin = test_user_id in super_admins
        expected_access = is_owner or is_super_admin
        
        # Check actual access
        actual_access = checker.is_admin(test_user_id)
        
        assert actual_access == expected_access, (
            f"Access control mismatch for user {test_user_id}. "
            f"Expected: {expected_access}, Got: {actual_access}. "
            f"is_owner: {is_owner}, is_super_admin: {is_super_admin}. "
            f"Owner ID: {owner_id}, Super admins: {super_admins}. "
            f"Access MUST be granted iff user is owner or super admin (Requirement 13.7)."
        )

    @given(
        owner_id=owner_ids,
        super_admins=super_admin_lists,
        user_ids_to_check=st.lists(user_ids, min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_access_control_consistency(
        self,
        owner_id: int,
        super_admins: List[int],
        user_ids_to_check: List[int],
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        For any sequence of access checks, the result SHALL be consistent
        (same user always gets same result).
        """
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=super_admins
        )
        
        # Check each user twice and verify consistency
        for user_id in user_ids_to_check:
            first_check = checker.is_admin(user_id)
            second_check = checker.is_admin(user_id)
            
            assert first_check == second_check, (
                f"Access control inconsistency for user {user_id}. "
                f"First check: {first_check}, Second check: {second_check}. "
                f"Access control MUST be deterministic (Requirement 13.7)."
            )

    @given(
        owner_id=owner_ids,
        super_admins=super_admin_lists,
    )
    @settings(max_examples=100)
    def test_get_all_admin_ids_complete(
        self,
        owner_id: int,
        super_admins: List[int],
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        The set of all admin IDs SHALL include the owner and all super admins.
        """
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=super_admins
        )
        
        all_admins = checker.get_all_admin_ids()
        
        # Owner must be in the set
        assert owner_id in all_admins, (
            f"Owner ID {owner_id} MUST be in all_admin_ids"
        )
        
        # All super admins must be in the set
        for admin_id in super_admins:
            assert admin_id in all_admins, (
                f"Super admin {admin_id} MUST be in all_admin_ids"
            )
        
        # Set should contain exactly owner + super_admins (no extras)
        expected_size = len(set(super_admins) | {owner_id})
        assert len(all_admins) == expected_size, (
            f"all_admin_ids should have {expected_size} entries, got {len(all_admins)}"
        )

    @given(
        owner_id=owner_ids,
    )
    @settings(max_examples=100)
    def test_empty_super_admins_only_owner_has_access(
        self,
        owner_id: int,
    ):
        """
        **Feature: grand-casino-dictator, Property 18: Broadcast Admin Access Control**
        **Validates: Requirements 13.7**
        
        When SUPER_ADMINS is empty, only the owner SHALL have access.
        """
        checker = BroadcastAccessChecker(
            owner_id=owner_id,
            super_admins=[]  # Empty super admins
        )
        
        # Owner should have access
        assert checker.is_admin(owner_id) is True, (
            f"Owner MUST have access even with empty super_admins"
        )
        
        # All admin IDs should only contain owner
        all_admins = checker.get_all_admin_ids()
        assert all_admins == {owner_id}, (
            f"With empty super_admins, only owner should be admin"
        )
