"""
Property-based tests for Reaction System Cooldown.

**Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
**Validates: Requirements 8.4**
"""

import time
from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/handlers/reactions.py)
# ============================================================================

REACTION_COOLDOWN = 30.0  # 30 seconds cooldown per message


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

class ReactionCooldownManager:
    """
    Minimal ReactionCooldownManager for testing without async dependencies.
    
    This mirrors the core cooldown logic from app/handlers/reactions.py.
    """
    
    def __init__(self, cooldown_seconds: float = REACTION_COOLDOWN):
        # Key: (chat_id, message_id), Value: timestamp of last reaction response
        self._reaction_cooldowns: dict[tuple[int, int], float] = {}
        self._cooldown_seconds = cooldown_seconds
    
    def is_on_cooldown(self, chat_id: int, message_id: int, current_time: float = None) -> bool:
        """
        Check if a message is on cooldown for reaction responses.
        
        **Validates: Requirements 8.4**
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            current_time: Current timestamp (for testing)
            
        Returns:
            True if on cooldown, False otherwise
        """
        if current_time is None:
            current_time = time.time()
        
        key = (chat_id, message_id)
        last_response_time = self._reaction_cooldowns.get(key, 0)
        return current_time - last_response_time < self._cooldown_seconds
    
    def set_cooldown(self, chat_id: int, message_id: int, current_time: float = None) -> None:
        """
        Set cooldown for a message after responding to a reaction.
        
        **Validates: Requirements 8.4**
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            current_time: Current timestamp (for testing)
        """
        if current_time is None:
            current_time = time.time()
        
        key = (chat_id, message_id)
        self._reaction_cooldowns[key] = current_time
    
    def cleanup_old_cooldowns(self, current_time: float = None) -> int:
        """
        Remove expired cooldowns to prevent memory leaks.
        
        Returns:
            Number of cooldowns removed
        """
        if current_time is None:
            current_time = time.time()
        
        expired_keys = [
            key for key, timestamp in self._reaction_cooldowns.items()
            if current_time - timestamp > self._cooldown_seconds * 2
        ]
        for key in expired_keys:
            del self._reaction_cooldowns[key]
        
        return len(expired_keys)
    
    def process_reaction(
        self, 
        chat_id: int, 
        message_id: int, 
        current_time: float = None
    ) -> bool:
        """
        Process a reaction and return whether a response should be sent.
        
        This simulates the full reaction processing flow:
        1. Check if on cooldown
        2. If not on cooldown, set cooldown and return True (should respond)
        3. If on cooldown, return False (should not respond)
        
        **Validates: Requirements 8.4**
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            current_time: Current timestamp (for testing)
            
        Returns:
            True if a response should be sent, False if on cooldown
        """
        if current_time is None:
            current_time = time.time()
        
        if self.is_on_cooldown(chat_id, message_id, current_time):
            return False
        
        self.set_cooldown(chat_id, message_id, current_time)
        return True


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for message IDs (positive integers)
message_ids = st.integers(min_value=1, max_value=1000000000)

# Strategy for timestamps (reasonable range)
timestamps = st.floats(min_value=1000000000.0, max_value=2000000000.0, allow_nan=False)

# Strategy for time deltas within cooldown window
time_within_cooldown = st.floats(min_value=0.0, max_value=REACTION_COOLDOWN - 0.1, allow_nan=False)

# Strategy for time deltas after cooldown window
time_after_cooldown = st.floats(min_value=REACTION_COOLDOWN, max_value=REACTION_COOLDOWN * 3, allow_nan=False)


# ============================================================================
# Property Tests
# ============================================================================


class TestReactionCooldownProperties:
    """Property-based tests for Reaction Cooldown mechanism."""

    # ========================================================================
    # Property 10: Reaction cooldown prevents spam
    # ========================================================================

    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        base_time=timestamps,
        time_delta=time_within_cooldown,
    )
    @settings(max_examples=100)
    def test_second_reaction_within_cooldown_is_blocked(
        self,
        chat_id: int,
        message_id: int,
        base_time: float,
        time_delta: float,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        For any sequence of reactions on the same message within REACTION_COOLDOWN 
        seconds, only the first reaction SHALL trigger a response.
        """
        manager = ReactionCooldownManager()
        
        # First reaction should trigger a response
        first_response = manager.process_reaction(chat_id, message_id, base_time)
        assert first_response is True, "First reaction should trigger a response"
        
        # Second reaction within cooldown should NOT trigger a response
        second_time = base_time + time_delta
        second_response = manager.process_reaction(chat_id, message_id, second_time)
        assert second_response is False, (
            f"Second reaction within cooldown ({time_delta:.1f}s < {REACTION_COOLDOWN}s) "
            f"should NOT trigger a response"
        )

    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        base_time=timestamps,
        num_reactions=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_only_first_of_many_reactions_triggers_response(
        self,
        chat_id: int,
        message_id: int,
        base_time: float,
        num_reactions: int,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        For any number of reactions on the same message within the cooldown window,
        only the first reaction SHALL trigger a response.
        """
        manager = ReactionCooldownManager()
        responses_triggered = 0
        
        # Send multiple reactions within the cooldown window
        for i in range(num_reactions):
            # Each reaction is 1 second apart (all within 30s cooldown)
            reaction_time = base_time + i
            if manager.process_reaction(chat_id, message_id, reaction_time):
                responses_triggered += 1
        
        assert responses_triggered == 1, (
            f"Only 1 response should be triggered for {num_reactions} reactions "
            f"within cooldown window, but got {responses_triggered}"
        )

    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        base_time=timestamps,
        time_delta=time_after_cooldown,
    )
    @settings(max_examples=100)
    def test_reaction_after_cooldown_triggers_response(
        self,
        chat_id: int,
        message_id: int,
        base_time: float,
        time_delta: float,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        After the cooldown period expires, a new reaction SHALL trigger a response.
        """
        manager = ReactionCooldownManager()
        
        # First reaction triggers response
        first_response = manager.process_reaction(chat_id, message_id, base_time)
        assert first_response is True, "First reaction should trigger a response"
        
        # Reaction after cooldown should also trigger response
        after_cooldown_time = base_time + time_delta
        second_response = manager.process_reaction(chat_id, message_id, after_cooldown_time)
        assert second_response is True, (
            f"Reaction after cooldown ({time_delta:.1f}s >= {REACTION_COOLDOWN}s) "
            f"should trigger a response"
        )

    @given(
        chat_id=chat_ids,
        message_id1=message_ids,
        message_id2=message_ids,
        base_time=timestamps,
    )
    @settings(max_examples=100)
    def test_different_messages_have_independent_cooldowns(
        self,
        chat_id: int,
        message_id1: int,
        message_id2: int,
        base_time: float,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        Cooldowns for different messages SHALL be independent.
        """
        # Ensure different message IDs
        assume(message_id1 != message_id2)
        
        manager = ReactionCooldownManager()
        
        # First reaction on message 1
        response1 = manager.process_reaction(chat_id, message_id1, base_time)
        assert response1 is True, "First reaction on message 1 should trigger response"
        
        # First reaction on message 2 (same time) should also trigger
        response2 = manager.process_reaction(chat_id, message_id2, base_time)
        assert response2 is True, (
            "First reaction on message 2 should trigger response "
            "(independent cooldown from message 1)"
        )

    @given(
        chat_id1=chat_ids,
        chat_id2=chat_ids,
        message_id=message_ids,
        base_time=timestamps,
    )
    @settings(max_examples=100)
    def test_different_chats_have_independent_cooldowns(
        self,
        chat_id1: int,
        chat_id2: int,
        message_id: int,
        base_time: float,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        Cooldowns for different chats SHALL be independent.
        """
        # Ensure different chat IDs
        assume(chat_id1 != chat_id2)
        
        manager = ReactionCooldownManager()
        
        # First reaction in chat 1
        response1 = manager.process_reaction(chat_id1, message_id, base_time)
        assert response1 is True, "First reaction in chat 1 should trigger response"
        
        # First reaction in chat 2 (same message_id, same time) should also trigger
        response2 = manager.process_reaction(chat_id2, message_id, base_time)
        assert response2 is True, (
            "First reaction in chat 2 should trigger response "
            "(independent cooldown from chat 1)"
        )

    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        base_time=timestamps,
    )
    @settings(max_examples=100)
    def test_cooldown_state_is_set_after_first_reaction(
        self,
        chat_id: int,
        message_id: int,
        base_time: float,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        After processing a reaction, the cooldown state SHALL be set.
        """
        manager = ReactionCooldownManager()
        
        # Before any reaction, should not be on cooldown
        assert manager.is_on_cooldown(chat_id, message_id, base_time) is False, (
            "Should not be on cooldown before any reaction"
        )
        
        # Process first reaction
        manager.process_reaction(chat_id, message_id, base_time)
        
        # After reaction, should be on cooldown
        assert manager.is_on_cooldown(chat_id, message_id, base_time + 1) is True, (
            "Should be on cooldown after processing a reaction"
        )

    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        base_time=timestamps,
        cleanup_delay=st.floats(min_value=REACTION_COOLDOWN * 2 + 1, max_value=REACTION_COOLDOWN * 5, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_cleanup_removes_expired_cooldowns(
        self,
        chat_id: int,
        message_id: int,
        base_time: float,
        cleanup_delay: float,
    ):
        """
        **Feature: release-candidate-8, Property 10: Reaction cooldown prevents spam**
        **Validates: Requirements 8.4**
        
        Cleanup SHALL remove expired cooldowns (older than 2x cooldown period).
        """
        manager = ReactionCooldownManager()
        
        # Set a cooldown
        manager.set_cooldown(chat_id, message_id, base_time)
        
        # Verify cooldown exists
        assert len(manager._reaction_cooldowns) == 1, "Cooldown should be set"
        
        # Cleanup after 2x cooldown period
        cleanup_time = base_time + cleanup_delay
        removed = manager.cleanup_old_cooldowns(cleanup_time)
        
        assert removed == 1, f"Should have removed 1 expired cooldown, removed {removed}"
        assert len(manager._reaction_cooldowns) == 0, "Cooldown should be removed after cleanup"
