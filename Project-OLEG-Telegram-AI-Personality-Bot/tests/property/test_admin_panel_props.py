"""
Property-based tests for Admin Panel ownership verification.

**Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
**Validates: Requirements 1.1**
"""

from dataclasses import dataclass
from typing import Dict, List, Set
from hypothesis import given, strategies as st, settings


# ============================================================================
# Mock data structures for testing without database/Telegram dependencies
# ============================================================================

@dataclass
class MockChat:
    """Mock Chat object for testing."""
    id: int
    title: str


@dataclass
class MockChatMember:
    """Mock ChatMember object for testing."""
    status: str  # 'creator', 'administrator', 'member', 'restricted', 'left', 'kicked'


# ============================================================================
# Pure functions extracted from admin_panel.py for testing
# ============================================================================

def verify_ownership_pure(user_id: int, chat_id: int, ownership_map: Dict[int, Dict[int, str]]) -> bool:
    """
    Pure function version of verify_ownership for testing.
    
    Args:
        user_id: User ID to verify
        chat_id: Chat ID to check ownership
        ownership_map: Dict mapping chat_id -> {user_id -> status}
        
    Returns:
        True if user is owner/creator, False otherwise
    """
    chat_members = ownership_map.get(chat_id, {})
    status = chat_members.get(user_id, "")
    return status == "creator"


def get_owner_chats_pure(
    user_id: int,
    all_chats: List[MockChat],
    ownership_map: Dict[int, Dict[int, str]]
) -> List[MockChat]:
    """
    Pure function version of get_owner_chats for testing.
    
    Args:
        user_id: User ID to find chats for
        all_chats: List of all chats in the system
        ownership_map: Dict mapping chat_id -> {user_id -> status}
        
    Returns:
        List of Chat objects where user is owner
    """
    owner_chats = []
    for chat in all_chats:
        if verify_ownership_pure(user_id, chat.id, ownership_map):
            owner_chats.append(chat)
    return owner_chats


def build_chat_list_menu_pure(chats: List[MockChat]) -> List[str]:
    """
    Pure function version of build_chat_list_menu for testing.
    Returns list of callback data strings instead of InlineKeyboardMarkup.
    
    Args:
        chats: List of chats where user is owner
        
    Returns:
        List of callback data strings for each chat button
    """
    callback_data_list = []
    for chat in chats:
        callback_data_list.append(f"owner_chat_{chat.id}")
    return callback_data_list


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for user IDs (positive integers)
user_ids = st.integers(min_value=1, max_value=10**9)

# Strategy for chat IDs (can be negative for groups)
chat_ids = st.integers(min_value=-10**12, max_value=-1) | st.integers(min_value=1, max_value=10**9)

# Strategy for chat titles
chat_titles = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=('L', 'N', 'P', 'S'),
    whitelist_characters=' '
)).filter(lambda x: len(x.strip()) > 0)

# Strategy for member status
member_statuses = st.sampled_from(["creator", "administrator", "member", "restricted", "left", "kicked"])


@st.composite
def mock_chats(draw, min_size=0, max_size=10):
    """Generate a list of mock chats with unique IDs."""
    num_chats = draw(st.integers(min_value=min_size, max_value=max_size))
    chats = []
    used_ids = set()
    
    for _ in range(num_chats):
        # Generate unique chat ID
        chat_id = draw(chat_ids.filter(lambda x: x not in used_ids))
        used_ids.add(chat_id)
        title = draw(chat_titles)
        chats.append(MockChat(id=chat_id, title=title))
    
    return chats


@st.composite
def ownership_scenario(draw):
    """
    Generate a complete ownership scenario for testing.
    
    Returns:
        Tuple of (user_id, all_chats, ownership_map, expected_owner_chat_ids)
    """
    user_id = draw(user_ids)
    all_chats = draw(mock_chats(min_size=0, max_size=10))
    
    # Build ownership map
    ownership_map: Dict[int, Dict[int, str]] = {}
    expected_owner_chat_ids: Set[int] = set()
    
    for chat in all_chats:
        # Decide if this user is the owner of this chat
        is_owner = draw(st.booleans())
        
        if is_owner:
            ownership_map[chat.id] = {user_id: "creator"}
            expected_owner_chat_ids.add(chat.id)
        else:
            # User has some other status or is not in the chat
            other_status = draw(st.sampled_from(["administrator", "member", "restricted", "left", "kicked", ""]))
            if other_status:
                ownership_map[chat.id] = {user_id: other_status}
            else:
                ownership_map[chat.id] = {}
    
    return user_id, all_chats, ownership_map, expected_owner_chat_ids


# ============================================================================
# Property 1: Admin panel shows owner chats
# ============================================================================

class TestAdminPanelOwnership:
    """
    **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
    **Validates: Requirements 1.1**
    
    For any user ID and set of chats, the admin panel SHALL display exactly 
    those chats where the user is the owner.
    """
    
    @settings(max_examples=100)
    @given(scenario=ownership_scenario())
    def test_property_1_owner_chats_exact_match(self, scenario):
        """
        **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
        **Validates: Requirements 1.1**
        
        For any user and set of chats, get_owner_chats SHALL return exactly 
        those chats where the user has 'creator' status.
        """
        user_id, all_chats, ownership_map, expected_owner_chat_ids = scenario
        
        # Get owner chats using the pure function
        owner_chats = get_owner_chats_pure(user_id, all_chats, ownership_map)
        
        # Extract IDs from returned chats
        returned_chat_ids = {chat.id for chat in owner_chats}
        
        # Property: returned chats must exactly match expected owner chats
        assert returned_chat_ids == expected_owner_chat_ids, (
            f"Expected owner chats {expected_owner_chat_ids}, "
            f"but got {returned_chat_ids}"
        )
    
    @settings(max_examples=100)
    @given(scenario=ownership_scenario())
    def test_property_1_no_non_owner_chats(self, scenario):
        """
        **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
        **Validates: Requirements 1.1**
        
        For any user, get_owner_chats SHALL NOT return any chat where 
        the user is not the owner.
        """
        user_id, all_chats, ownership_map, expected_owner_chat_ids = scenario
        
        owner_chats = get_owner_chats_pure(user_id, all_chats, ownership_map)
        
        for chat in owner_chats:
            # Verify each returned chat has the user as creator
            assert verify_ownership_pure(user_id, chat.id, ownership_map), (
                f"Chat {chat.id} returned but user {user_id} is not the owner"
            )
    
    @settings(max_examples=100)
    @given(scenario=ownership_scenario())
    def test_property_1_all_owner_chats_included(self, scenario):
        """
        **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
        **Validates: Requirements 1.1**
        
        For any user, get_owner_chats SHALL include ALL chats where 
        the user is the owner.
        """
        user_id, all_chats, ownership_map, expected_owner_chat_ids = scenario
        
        owner_chats = get_owner_chats_pure(user_id, all_chats, ownership_map)
        returned_chat_ids = {chat.id for chat in owner_chats}
        
        # All expected owner chats must be in the result
        for expected_id in expected_owner_chat_ids:
            assert expected_id in returned_chat_ids, (
                f"Expected chat {expected_id} to be in owner chats but it was missing"
            )
    
    @settings(max_examples=100)
    @given(scenario=ownership_scenario())
    def test_property_1_menu_contains_all_owner_chats(self, scenario):
        """
        **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
        **Validates: Requirements 1.1**
        
        For any set of owner chats, the menu SHALL contain a button for each chat.
        """
        user_id, all_chats, ownership_map, expected_owner_chat_ids = scenario
        
        owner_chats = get_owner_chats_pure(user_id, all_chats, ownership_map)
        menu_callbacks = build_chat_list_menu_pure(owner_chats)
        
        # Menu should have exactly as many buttons as owner chats
        assert len(menu_callbacks) == len(owner_chats), (
            f"Menu has {len(menu_callbacks)} buttons but there are {len(owner_chats)} owner chats"
        )
        
        # Each owner chat should have a corresponding button
        for chat in owner_chats:
            expected_callback = f"owner_chat_{chat.id}"
            assert expected_callback in menu_callbacks, (
                f"Menu missing button for chat {chat.id}"
            )
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_property_1_empty_chats_returns_empty(self, user_id: int):
        """
        **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
        **Validates: Requirements 1.1**
        
        For any user with no chats in the system, get_owner_chats SHALL return empty list.
        """
        owner_chats = get_owner_chats_pure(user_id, [], {})
        
        assert owner_chats == [], "Empty chat list should return empty owner chats"
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chats=mock_chats(min_size=1, max_size=5))
    def test_property_1_non_owner_returns_empty(self, user_id: int, chats: List[MockChat]):
        """
        **Feature: oleg-commands-fix, Property 1: Admin panel shows owner chats**
        **Validates: Requirements 1.1, 1.3**
        
        For any user who is not owner of any chat, get_owner_chats SHALL return empty list.
        """
        # Create ownership map where user is never a creator
        ownership_map = {
            chat.id: {user_id: "member"} for chat in chats
        }
        
        owner_chats = get_owner_chats_pure(user_id, chats, ownership_map)
        
        assert owner_chats == [], (
            f"User {user_id} is not owner of any chat but got {len(owner_chats)} chats"
        )


class TestVerifyOwnership:
    """
    Tests for the verify_ownership function.
    
    **Validates: Requirements 1.1, 1.3**
    """
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_creator_status_returns_true(self, user_id: int, chat_id: int):
        """
        For any user with 'creator' status, verify_ownership SHALL return True.
        """
        ownership_map = {chat_id: {user_id: "creator"}}
        
        result = verify_ownership_pure(user_id, chat_id, ownership_map)
        
        assert result is True, "Creator status should return True"
    
    @settings(max_examples=100)
    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        status=st.sampled_from(["administrator", "member", "restricted", "left", "kicked"])
    )
    def test_non_creator_status_returns_false(self, user_id: int, chat_id: int, status: str):
        """
        For any user without 'creator' status, verify_ownership SHALL return False.
        """
        ownership_map = {chat_id: {user_id: status}}
        
        result = verify_ownership_pure(user_id, chat_id, ownership_map)
        
        assert result is False, f"Status '{status}' should return False"
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_missing_user_returns_false(self, user_id: int, chat_id: int):
        """
        For any user not in the chat, verify_ownership SHALL return False.
        """
        ownership_map = {chat_id: {}}  # Empty members
        
        result = verify_ownership_pure(user_id, chat_id, ownership_map)
        
        assert result is False, "Missing user should return False"
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_missing_chat_returns_false(self, user_id: int, chat_id: int):
        """
        For any chat not in the system, verify_ownership SHALL return False.
        """
        ownership_map = {}  # Empty chats
        
        result = verify_ownership_pure(user_id, chat_id, ownership_map)
        
        assert result is False, "Missing chat should return False"
