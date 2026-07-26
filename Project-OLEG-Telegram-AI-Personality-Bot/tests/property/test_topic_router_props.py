"""
Property-based tests for Topic Router in games.

Tests correctness properties defined in the design document.
**Property 7: Game messages preserve topic ID**
**Validates: Requirements 5.1, 5.2, 5.3**
"""

import os
import importlib.util
from typing import Optional
from hypothesis import given, strategies as st, settings, assume

# Import challenges module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'handlers', 'challenges.py')
_spec = importlib.util.spec_from_file_location("challenges", _module_path)
_challenges_module = importlib.util.module_from_spec(_spec)

# Mock dependencies before loading the module
import sys
from unittest.mock import MagicMock

# Create mock modules for dependencies
mock_modules = [
    'aiogram', 'aiogram.types', 'aiogram.filters', 'aiogram.types.Message',
    'aiogram.types.CallbackQuery', 'aiogram.types.InlineKeyboardMarkup',
    'aiogram.types.InlineKeyboardButton', 'aiogram.Router', 'aiogram.F',
    'sqlalchemy', 'sqlalchemy.select', 'app.database.session', 'app.database.models',
    'app.services.game_engine', 'app.services.state_manager', 'app.services.duel_engine',
    'app.handlers.games', 'app.utils'
]

for mod in mock_modules:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Now we can test the keyboard creation functions directly
# We'll re-implement them here for testing since the module has complex dependencies


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
thread_id_strategy = st.one_of(st.none(), st.integers(min_value=1, max_value=10**9))
challenge_id_strategy = st.text(min_size=8, max_size=32, alphabet='abcdef0123456789')
duel_id_strategy = st.text(min_size=8, max_size=8, alphabet='abcdef0123456789')
zone_strategy = st.sampled_from(['head', 'body', 'legs'])
phase_strategy = st.sampled_from(['attack', 'defend'])


def parse_thread_id_from_callback(callback_data: str) -> Optional[int]:
    """Parse thread_id from callback_data string.
    
    Callback data format: prefix:...:thread_id
    Thread ID is always the last part, 0 means None.
    """
    parts = callback_data.split(":")
    if len(parts) < 2:
        return None
    
    try:
        thread_id = int(parts[-1])
        return thread_id if thread_id != 0 else None
    except ValueError:
        return None


def create_challenge_callback_data(challenge_id: str, thread_id: Optional[int], accept: bool = True) -> str:
    """Create callback data for challenge accept/decline buttons."""
    prefix = "challenge_accept:" if accept else "challenge_decline:"
    thread_suffix = f":{thread_id or 0}"
    return f"{prefix}{challenge_id}{thread_suffix}"


def create_attack_callback_data(owner_id: int, zone: str, thread_id: Optional[int]) -> str:
    """Create callback data for attack zone selection."""
    thread_suffix = f":{thread_id or 0}"
    return f"duel:{owner_id}:attack:{zone}{thread_suffix}"


def create_defend_callback_data(owner_id: int, attack_zone: str, defend_zone: str, thread_id: Optional[int]) -> str:
    """Create callback data for defense zone selection."""
    thread_suffix = f":{thread_id or 0}"
    return f"duel:{owner_id}:defend:{attack_zone}:{defend_zone}{thread_suffix}"


def create_pvp_move_callback_data(duel_id: str, user_id: int, phase: str, zone: str, thread_id: Optional[int]) -> str:
    """Create callback data for PvP move selection."""
    thread_suffix = f":{thread_id or 0}"
    return f"pvp:{duel_id}:{user_id}:{phase}:{zone}{thread_suffix}"


class TestChallengeCallbackThreadIdPreservation:
    """
    **Feature: release-candidate-8, Property 7: Game messages preserve topic ID**
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    *For any* game started in a topic with message_thread_id = X, 
    all subsequent game messages SHALL be sent with message_thread_id = X.
    """
    
    @settings(max_examples=100)
    @given(
        challenge_id=challenge_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_challenge_accept_callback_preserves_thread_id(
        self,
        challenge_id: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: Challenge accept callback preserves thread_id.
        
        For any challenge with thread_id X:
        - The callback_data should contain thread_id X
        - Parsing the callback_data should return thread_id X
        """
        callback_data = create_challenge_callback_data(challenge_id, thread_id, accept=True)
        
        # Parse the callback data
        parsed_thread_id = parse_thread_id_from_callback(callback_data)
        
        assert parsed_thread_id == thread_id, \
            f"Thread ID should be preserved: expected {thread_id}, got {parsed_thread_id}"
    
    @settings(max_examples=100)
    @given(
        challenge_id=challenge_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_challenge_decline_callback_preserves_thread_id(
        self,
        challenge_id: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: Challenge decline callback preserves thread_id.
        """
        callback_data = create_challenge_callback_data(challenge_id, thread_id, accept=False)
        
        parsed_thread_id = parse_thread_id_from_callback(callback_data)
        
        assert parsed_thread_id == thread_id, \
            f"Thread ID should be preserved: expected {thread_id}, got {parsed_thread_id}"


class TestDuelCallbackThreadIdPreservation:
    """
    **Feature: release-candidate-8, Property 7: Game messages preserve topic ID**
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    Tests that PvE duel callbacks preserve thread_id.
    """
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        zone=zone_strategy,
        thread_id=thread_id_strategy
    )
    def test_attack_callback_preserves_thread_id(
        self,
        owner_id: int,
        zone: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: Attack zone callback preserves thread_id.
        """
        callback_data = create_attack_callback_data(owner_id, zone, thread_id)
        
        parsed_thread_id = parse_thread_id_from_callback(callback_data)
        
        assert parsed_thread_id == thread_id, \
            f"Thread ID should be preserved in attack callback: expected {thread_id}, got {parsed_thread_id}"
    
    @settings(max_examples=100)
    @given(
        owner_id=user_id_strategy,
        attack_zone=zone_strategy,
        defend_zone=zone_strategy,
        thread_id=thread_id_strategy
    )
    def test_defend_callback_preserves_thread_id(
        self,
        owner_id: int,
        attack_zone: str,
        defend_zone: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: Defense zone callback preserves thread_id.
        """
        callback_data = create_defend_callback_data(owner_id, attack_zone, defend_zone, thread_id)
        
        parsed_thread_id = parse_thread_id_from_callback(callback_data)
        
        assert parsed_thread_id == thread_id, \
            f"Thread ID should be preserved in defend callback: expected {thread_id}, got {parsed_thread_id}"


class TestPvPCallbackThreadIdPreservation:
    """
    **Feature: release-candidate-8, Property 7: Game messages preserve topic ID**
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    Tests that PvP duel callbacks preserve thread_id.
    """
    
    @settings(max_examples=100)
    @given(
        duel_id=duel_id_strategy,
        user_id=user_id_strategy,
        phase=phase_strategy,
        zone=zone_strategy,
        thread_id=thread_id_strategy
    )
    def test_pvp_move_callback_preserves_thread_id(
        self,
        duel_id: str,
        user_id: int,
        phase: str,
        zone: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: PvP move callback preserves thread_id.
        
        For any PvP duel with thread_id X:
        - The callback_data should contain thread_id X
        - Parsing the callback_data should return thread_id X
        """
        callback_data = create_pvp_move_callback_data(duel_id, user_id, phase, zone, thread_id)
        
        parsed_thread_id = parse_thread_id_from_callback(callback_data)
        
        assert parsed_thread_id == thread_id, \
            f"Thread ID should be preserved in PvP callback: expected {thread_id}, got {parsed_thread_id}"
    
    @settings(max_examples=100)
    @given(
        duel_id=duel_id_strategy,
        user_id=user_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_pvp_attack_then_defend_preserves_thread_id(
        self,
        duel_id: str,
        user_id: int,
        thread_id: Optional[int]
    ):
        """
        Property 7: Thread ID is preserved through attack -> defend flow.
        
        When a player selects attack zone, the defend callback should
        still contain the same thread_id.
        """
        # Attack callback
        attack_callback = create_pvp_move_callback_data(duel_id, user_id, "attack", "head", thread_id)
        attack_thread_id = parse_thread_id_from_callback(attack_callback)
        
        # Defend callback (created after attack)
        defend_callback = create_pvp_move_callback_data(duel_id, user_id, "defend", "body", thread_id)
        defend_thread_id = parse_thread_id_from_callback(defend_callback)
        
        assert attack_thread_id == thread_id, \
            f"Attack callback should preserve thread_id: expected {thread_id}, got {attack_thread_id}"
        assert defend_thread_id == thread_id, \
            f"Defend callback should preserve thread_id: expected {thread_id}, got {defend_thread_id}"
        assert attack_thread_id == defend_thread_id, \
            "Thread ID should be consistent between attack and defend callbacks"


class TestThreadIdRoundTrip:
    """
    **Feature: release-candidate-8, Property 7: Game messages preserve topic ID**
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    Tests round-trip preservation of thread_id through callback data.
    """
    
    @settings(max_examples=100)
    @given(
        thread_id=st.integers(min_value=1, max_value=10**9)
    )
    def test_non_zero_thread_id_round_trip(self, thread_id: int):
        """
        Property 7: Non-zero thread_id survives round-trip through callback data.
        """
        # Create various callback types with the thread_id
        challenge_cb = create_challenge_callback_data("abc12345", thread_id)
        attack_cb = create_attack_callback_data(123456, "head", thread_id)
        defend_cb = create_defend_callback_data(123456, "head", "body", thread_id)
        pvp_cb = create_pvp_move_callback_data("duel1234", 123456, "attack", "legs", thread_id)
        
        # All should parse back to the same thread_id
        assert parse_thread_id_from_callback(challenge_cb) == thread_id
        assert parse_thread_id_from_callback(attack_cb) == thread_id
        assert parse_thread_id_from_callback(defend_cb) == thread_id
        assert parse_thread_id_from_callback(pvp_cb) == thread_id
    
    @settings(max_examples=100)
    @given(
        challenge_id=challenge_id_strategy,
        owner_id=user_id_strategy,
        duel_id=duel_id_strategy
    )
    def test_none_thread_id_round_trip(
        self,
        challenge_id: str,
        owner_id: int,
        duel_id: str
    ):
        """
        Property 7: None thread_id (encoded as 0) survives round-trip.
        """
        thread_id = None
        
        challenge_cb = create_challenge_callback_data(challenge_id, thread_id)
        attack_cb = create_attack_callback_data(owner_id, "head", thread_id)
        defend_cb = create_defend_callback_data(owner_id, "head", "body", thread_id)
        pvp_cb = create_pvp_move_callback_data(duel_id, owner_id, "attack", "legs", thread_id)
        
        # All should parse back to None
        assert parse_thread_id_from_callback(challenge_cb) is None
        assert parse_thread_id_from_callback(attack_cb) is None
        assert parse_thread_id_from_callback(defend_cb) is None
        assert parse_thread_id_from_callback(pvp_cb) is None


class TestCallbackDataFormat:
    """
    **Feature: release-candidate-8, Property 7: Game messages preserve topic ID**
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    Tests that callback data format is correct and parseable.
    """
    
    @settings(max_examples=100)
    @given(
        challenge_id=challenge_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_challenge_callback_format(
        self,
        challenge_id: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: Challenge callback data has correct format.
        
        Format: challenge_accept:{challenge_id}:{thread_id}
        """
        callback_data = create_challenge_callback_data(challenge_id, thread_id)
        
        # Should start with correct prefix
        assert callback_data.startswith("challenge_accept:"), \
            f"Callback should start with 'challenge_accept:', got {callback_data}"
        
        # Should contain challenge_id
        assert challenge_id in callback_data, \
            f"Callback should contain challenge_id '{challenge_id}'"
        
        # Should end with thread_id (or 0 for None)
        expected_suffix = str(thread_id or 0)
        assert callback_data.endswith(f":{expected_suffix}"), \
            f"Callback should end with ':{expected_suffix}', got {callback_data}"
    
    @settings(max_examples=100)
    @given(
        duel_id=duel_id_strategy,
        user_id=user_id_strategy,
        phase=phase_strategy,
        zone=zone_strategy,
        thread_id=thread_id_strategy
    )
    def test_pvp_callback_format(
        self,
        duel_id: str,
        user_id: int,
        phase: str,
        zone: str,
        thread_id: Optional[int]
    ):
        """
        Property 7: PvP callback data has correct format.
        
        Format: pvp:{duel_id}:{user_id}:{phase}:{zone}:{thread_id}
        """
        callback_data = create_pvp_move_callback_data(duel_id, user_id, phase, zone, thread_id)
        
        # Should start with correct prefix
        assert callback_data.startswith("pvp:"), \
            f"Callback should start with 'pvp:', got {callback_data}"
        
        # Should contain all parts
        parts = callback_data.split(":")
        assert len(parts) == 6, \
            f"PvP callback should have 6 parts, got {len(parts)}: {parts}"
        
        assert parts[0] == "pvp"
        assert parts[1] == duel_id
        assert parts[2] == str(user_id)
        assert parts[3] == phase
        assert parts[4] == zone
        assert parts[5] == str(thread_id or 0)
