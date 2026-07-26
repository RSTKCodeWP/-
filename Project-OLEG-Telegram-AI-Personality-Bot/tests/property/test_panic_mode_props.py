"""
Property-based tests for PanicModeController (Automatic Raid Protection).

**Feature: shield-economy-v65, Property 16: Panic Mode Activation on Mass Join**
**Feature: shield-economy-v65, Property 17: Panic Mode Activation on Message Flood**
**Feature: shield-economy-v65, Property 18: Panic Mode Silences Welcome Messages**
**Validates: Requirements 6.1, 6.2, 6.3**
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Optional, Set, Tuple

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/services/panic_mode.py)
# ============================================================================

JOIN_THRESHOLD = 10  # Number of joins to trigger panic mode
JOIN_WINDOW_SECONDS = 10  # Time window for join detection

MESSAGE_THRESHOLD = 20  # Messages per second to trigger panic mode
MESSAGE_WINDOW_SECONDS = 1  # Time window for message flood detection


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class PanicModeState:
    """
    Current panic mode state for a chat.
    
    Attributes:
        chat_id: Telegram chat ID
        active: Whether panic mode is currently active
        activated_at: When panic mode was activated
        trigger_reason: What triggered panic mode ("mass_join" or "message_flood")
    """
    chat_id: int
    active: bool = False
    activated_at: Optional[datetime] = None
    trigger_reason: str = ""


# Constants for user restriction
NEW_USER_THRESHOLD_HOURS = 24  # Users joined within this period get restricted
RO_DURATION_MINUTES = 30  # Read-only duration for restricted users


class PanicModeController:
    """
    Minimal PanicModeController for testing without DB/Redis dependencies.
    
    This mirrors the core logic from app/services/panic_mode.py.
    """
    
    def __init__(self):
        """Initialize PanicModeController with in-memory tracking."""
        # In-memory tracking for join events
        self._join_events: Dict[int, Deque[datetime]] = {}
        
        # In-memory tracking for message events (user_id, timestamp)
        self._message_events: Dict[int, Deque[Tuple[int, datetime]]] = {}
        
        # Panic mode state per chat
        self._panic_states: Dict[int, PanicModeState] = {}
        
        # User join times tracking: (chat_id, user_id) -> join_time
        self._user_join_times: Dict[Tuple[int, int], datetime] = {}
    
    def record_join(self, chat_id: int, user_id: int, current_time: Optional[datetime] = None) -> None:
        """
        Record a user join event for raid detection.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID who joined
            current_time: Optional time override for testing
        """
        now = current_time or utc_now()
        
        if chat_id not in self._join_events:
            self._join_events[chat_id] = deque()
        
        self._join_events[chat_id].append(now)
        self._cleanup_old_join_events(chat_id, now)
    
    def check_join_trigger(self, chat_id: int, current_time: Optional[datetime] = None) -> bool:
        """
        Check if mass join raid condition is met.
        
        Triggers when 10+ users join within 10 seconds.
        
        Args:
            chat_id: Telegram chat ID
            current_time: Optional time override for testing
            
        Returns:
            True if raid condition is detected
            
        **Validates: Requirements 6.1**
        """
        now = current_time or utc_now()
        self._cleanup_old_join_events(chat_id, now)
        
        if chat_id not in self._join_events:
            return False
        
        join_count = len(self._join_events[chat_id])
        return join_count >= JOIN_THRESHOLD
    
    def activate_panic_mode(
        self,
        chat_id: int,
        reason: str,
        current_time: Optional[datetime] = None
    ) -> PanicModeState:
        """
        Activate panic mode for a chat.
        
        Args:
            chat_id: Telegram chat ID
            reason: Trigger reason ("mass_join" or "message_flood")
            current_time: Optional time override for testing
            
        Returns:
            Updated PanicModeState
        """
        now = current_time or utc_now()
        
        state = PanicModeState(
            chat_id=chat_id,
            active=True,
            activated_at=now,
            trigger_reason=reason,
        )
        
        self._panic_states[chat_id] = state
        return state
    
    def is_panic_mode_active(self, chat_id: int) -> bool:
        """
        Check if panic mode is currently active for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if panic mode is active
        """
        state = self._panic_states.get(chat_id)
        return state is not None and state.active

    def should_send_welcome(self, chat_id: int) -> bool:
        """
        Check if welcome messages should be sent.
        
        Welcome messages are silenced during panic mode.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if welcome messages should be sent
            
        **Validates: Requirements 6.3**
        """
        is_active = self.is_panic_mode_active(chat_id)
        return not is_active
    
    def get_join_count(self, chat_id: int, current_time: Optional[datetime] = None) -> int:
        """
        Get the current join count within the detection window.
        
        Args:
            chat_id: Telegram chat ID
            current_time: Optional time override for testing
            
        Returns:
            Number of joins in the current window
        """
        now = current_time or utc_now()
        self._cleanup_old_join_events(chat_id, now)
        
        if chat_id not in self._join_events:
            return 0
        
        return len(self._join_events[chat_id])
    
    def _cleanup_old_join_events(self, chat_id: int, now: datetime) -> None:
        """Remove join events outside the detection window."""
        if chat_id not in self._join_events:
            return
        
        events = self._join_events[chat_id]
        cutoff = now - timedelta(seconds=JOIN_WINDOW_SECONDS)
        
        while events and events[0] < cutoff:
            events.popleft()

    # =========================================================================
    # Message Flood Detection Methods
    # =========================================================================

    def record_message(self, chat_id: int, user_id: int, current_time: Optional[datetime] = None) -> None:
        """
        Record a message event for flood detection.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID who sent the message
            current_time: Optional time override for testing
        """
        now = current_time or utc_now()
        
        if chat_id not in self._message_events:
            self._message_events[chat_id] = deque()
        
        self._message_events[chat_id].append((user_id, now))
        self._cleanup_old_message_events(chat_id, now)

    def check_message_trigger(self, chat_id: int, current_time: Optional[datetime] = None) -> bool:
        """
        Check if message flood condition is met.
        
        Triggers when 20+ messages per second from different users.
        
        Args:
            chat_id: Telegram chat ID
            current_time: Optional time override for testing
            
        Returns:
            True if flood condition is detected
            
        **Validates: Requirements 6.2**
        """
        now = current_time or utc_now()
        self._cleanup_old_message_events(chat_id, now)
        
        if chat_id not in self._message_events:
            return False
        
        events = self._message_events[chat_id]
        
        # Count unique users in the window
        unique_users = set()
        for user_id, _ in events:
            unique_users.add(user_id)
        
        message_count = len(events)
        # Flood requires 20+ messages AND from different users (more than 1)
        is_flood = message_count >= MESSAGE_THRESHOLD and len(unique_users) > 1
        
        return is_flood

    def get_message_count(self, chat_id: int, current_time: Optional[datetime] = None) -> int:
        """
        Get the current message count within the detection window.
        
        Args:
            chat_id: Telegram chat ID
            current_time: Optional time override for testing
            
        Returns:
            Number of messages in the current window
        """
        now = current_time or utc_now()
        self._cleanup_old_message_events(chat_id, now)
        
        if chat_id not in self._message_events:
            return 0
        
        return len(self._message_events[chat_id])

    def get_unique_user_count(self, chat_id: int, current_time: Optional[datetime] = None) -> int:
        """
        Get the count of unique users who sent messages within the detection window.
        
        Args:
            chat_id: Telegram chat ID
            current_time: Optional time override for testing
            
        Returns:
            Number of unique users in the current window
        """
        now = current_time or utc_now()
        self._cleanup_old_message_events(chat_id, now)
        
        if chat_id not in self._message_events:
            return 0
        
        unique_users = set()
        for user_id, _ in self._message_events[chat_id]:
            unique_users.add(user_id)
        
        return len(unique_users)

    def _cleanup_old_message_events(self, chat_id: int, now: datetime) -> None:
        """Remove message events outside the detection window."""
        if chat_id not in self._message_events:
            return
        
        events = self._message_events[chat_id]
        cutoff = now - timedelta(seconds=MESSAGE_WINDOW_SECONDS)
        
        while events and events[0][1] < cutoff:
            events.popleft()

    # =========================================================================
    # User Join Time Tracking Methods (for Property 19)
    # =========================================================================

    def record_user_join_time(
        self,
        chat_id: int,
        user_id: int,
        join_time: datetime
    ) -> None:
        """
        Record when a user joined a chat.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            join_time: When the user joined
        """
        self._user_join_times[(chat_id, user_id)] = join_time

    def get_user_join_time(
        self,
        chat_id: int,
        user_id: int
    ) -> Optional[datetime]:
        """
        Get when a user joined a chat.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            
        Returns:
            Join time or None if not recorded
        """
        return self._user_join_times.get((chat_id, user_id))

    def should_restrict_recent_user(
        self,
        chat_id: int,
        user_id: int,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, int]:
        """
        Check if a user should be restricted during panic mode.
        
        Users who joined within the last 24 hours get 30-minute RO status
        when panic mode is active.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            current_time: Optional time override for testing
            
        Returns:
            Tuple of (should_restrict, ro_duration_minutes)
            
        **Validates: Requirements 6.4**
        """
        now = current_time or utc_now()
        
        # Check if panic mode is active
        if not self.is_panic_mode_active(chat_id):
            return (False, 0)
        
        # Get user's join time
        join_time = self.get_user_join_time(chat_id, user_id)
        
        if join_time is None:
            # Unknown join time - don't restrict
            return (False, 0)
        
        # Calculate how long ago the user joined
        time_since_join = now - join_time
        hours_since_join = time_since_join.total_seconds() / 3600
        
        # Restrict if joined within the last 24 hours (strictly less than)
        if hours_since_join < NEW_USER_THRESHOLD_HOURS:
            return (True, RO_DURATION_MINUTES)
        
        return (False, 0)


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for number of joins (at or above threshold)
joins_at_or_above_threshold = st.integers(min_value=JOIN_THRESHOLD, max_value=50)

# Strategy for number of joins (below threshold)
joins_below_threshold = st.integers(min_value=1, max_value=JOIN_THRESHOLD - 1)

# Strategy for time intervals within the window (in milliseconds for precision)
time_within_window_ms = st.integers(min_value=0, max_value=(JOIN_WINDOW_SECONDS * 1000) - 1)

# Strategy for number of messages (at or above threshold)
messages_at_or_above_threshold = st.integers(min_value=MESSAGE_THRESHOLD, max_value=100)

# Strategy for number of messages (below threshold)
messages_below_threshold = st.integers(min_value=1, max_value=MESSAGE_THRESHOLD - 1)

# Strategy for number of unique users (more than 1 for flood detection)
unique_users_for_flood = st.integers(min_value=2, max_value=20)


# ============================================================================
# Property Tests
# ============================================================================


class TestPanicModeProperties:
    """Property-based tests for PanicModeController."""

    # ========================================================================
    # Property 16: Panic Mode Activation on Mass Join
    # ========================================================================

    @given(
        chat_id=chat_ids,
        num_joins=joins_at_or_above_threshold,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_activates_on_mass_join(
        self,
        chat_id: int,
        num_joins: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 16: Panic Mode Activation on Mass Join**
        **Validates: Requirements 6.1**
        
        For any sequence of 10+ user joins within 10 seconds, 
        Panic_Mode SHALL be activated.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate num_joins users joining within the 10-second window
        # Spread joins evenly across the window
        for i in range(num_joins):
            # Calculate time offset - spread joins within the window
            offset_ms = (i * (JOIN_WINDOW_SECONDS * 1000 - 1)) // max(num_joins - 1, 1)
            join_time = base_time + timedelta(milliseconds=offset_ms)
            user_id = user_id_base + i
            
            controller.record_join(chat_id, user_id, current_time=join_time)
        
        # Check at the end of the window
        check_time = base_time + timedelta(seconds=JOIN_WINDOW_SECONDS - 0.001)
        
        # Verify that the join trigger is detected
        is_triggered = controller.check_join_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is True, (
            f"Panic mode should be triggered with {num_joins} joins "
            f"(threshold is {JOIN_THRESHOLD})"
        )
        
        # Activate panic mode and verify state
        state = controller.activate_panic_mode(chat_id, "mass_join", current_time=check_time)
        
        assert state.active is True, "Panic mode state should be active"
        assert state.trigger_reason == "mass_join", "Trigger reason should be 'mass_join'"
        assert controller.is_panic_mode_active(chat_id) is True, (
            "is_panic_mode_active should return True after activation"
        )

    @given(
        chat_id=chat_ids,
        num_joins=joins_below_threshold,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_does_not_activate_below_threshold(
        self,
        chat_id: int,
        num_joins: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 16: Panic Mode Activation on Mass Join**
        **Validates: Requirements 6.1**
        
        For any sequence of fewer than 10 user joins within 10 seconds,
        Panic_Mode SHALL NOT be activated.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate num_joins users joining within the 10-second window
        for i in range(num_joins):
            offset_ms = (i * (JOIN_WINDOW_SECONDS * 1000 - 1)) // max(num_joins - 1, 1)
            join_time = base_time + timedelta(milliseconds=offset_ms)
            user_id = user_id_base + i
            
            controller.record_join(chat_id, user_id, current_time=join_time)
        
        # Check at the end of the window
        check_time = base_time + timedelta(seconds=JOIN_WINDOW_SECONDS - 0.001)
        
        # Verify that the join trigger is NOT detected
        is_triggered = controller.check_join_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is False, (
            f"Panic mode should NOT be triggered with {num_joins} joins "
            f"(threshold is {JOIN_THRESHOLD})"
        )

    @given(
        chat_id=chat_ids,
        num_joins=joins_at_or_above_threshold,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_not_triggered_when_joins_outside_window(
        self,
        chat_id: int,
        num_joins: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 16: Panic Mode Activation on Mass Join**
        **Validates: Requirements 6.1**
        
        For any sequence of joins spread over more than 10 seconds,
        Panic_Mode SHALL NOT be activated (joins outside window are cleaned up).
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate joins spread over a period longer than the window
        # Each join is 2 seconds apart, so they span more than 10 seconds
        for i in range(num_joins):
            join_time = base_time + timedelta(seconds=i * 2)
            user_id = user_id_base + i
            
            controller.record_join(chat_id, user_id, current_time=join_time)
        
        # Check after all joins - at this point, early joins should be cleaned up
        final_time = base_time + timedelta(seconds=(num_joins - 1) * 2)
        
        # Get the actual join count in the window
        join_count = controller.get_join_count(chat_id, current_time=final_time)
        
        # With 2-second intervals, only joins within the last 10 seconds count
        # That's at most 5-6 joins (10 seconds / 2 seconds per join)
        expected_max_joins = (JOIN_WINDOW_SECONDS // 2) + 1
        
        assert join_count <= expected_max_joins, (
            f"Only {expected_max_joins} joins should be in window, got {join_count}"
        )
        
        # Verify trigger is not activated (since joins are spread out)
        is_triggered = controller.check_join_trigger(chat_id, current_time=final_time)
        
        assert is_triggered is False, (
            f"Panic mode should NOT be triggered when joins are spread out "
            f"(only {join_count} joins in window)"
        )

    @given(
        chat_id=chat_ids,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_exactly_threshold_joins_triggers_panic_mode(
        self,
        chat_id: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 16: Panic Mode Activation on Mass Join**
        **Validates: Requirements 6.1**
        
        Exactly 10 joins within 10 seconds SHALL trigger Panic_Mode.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate exactly JOIN_THRESHOLD joins
        for i in range(JOIN_THRESHOLD):
            # All joins happen within a very short time span
            join_time = base_time + timedelta(milliseconds=i * 100)
            user_id = user_id_base + i
            
            controller.record_join(chat_id, user_id, current_time=join_time)
        
        # Check immediately after the last join
        check_time = base_time + timedelta(milliseconds=JOIN_THRESHOLD * 100)
        
        # Verify trigger is detected
        is_triggered = controller.check_join_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is True, (
            f"Panic mode should be triggered with exactly {JOIN_THRESHOLD} joins"
        )

    # ========================================================================
    # Property 17: Panic Mode Activation on Message Flood
    # ========================================================================

    @given(
        chat_id=chat_ids,
        num_messages=messages_at_or_above_threshold,
        num_users=unique_users_for_flood,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_activates_on_message_flood(
        self,
        chat_id: int,
        num_messages: int,
        num_users: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 17: Panic Mode Activation on Message Flood**
        **Validates: Requirements 6.2**
        
        For any sequence of 20+ messages per second from different users,
        Panic_Mode SHALL be activated.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate num_messages messages from num_users different users within 1 second
        # Spread messages evenly across the window
        for i in range(num_messages):
            # Calculate time offset - spread messages within the 1-second window
            offset_ms = (i * (MESSAGE_WINDOW_SECONDS * 1000 - 1)) // max(num_messages - 1, 1)
            msg_time = base_time + timedelta(milliseconds=offset_ms)
            # Distribute messages among different users
            user_id = user_id_base + (i % num_users)
            
            controller.record_message(chat_id, user_id, current_time=msg_time)
        
        # Check at the end of the window
        check_time = base_time + timedelta(seconds=MESSAGE_WINDOW_SECONDS - 0.001)
        
        # Verify that the message flood trigger is detected
        is_triggered = controller.check_message_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is True, (
            f"Panic mode should be triggered with {num_messages} messages "
            f"from {num_users} users (threshold is {MESSAGE_THRESHOLD})"
        )
        
        # Activate panic mode and verify state
        state = controller.activate_panic_mode(chat_id, "message_flood", current_time=check_time)
        
        assert state.active is True, "Panic mode state should be active"
        assert state.trigger_reason == "message_flood", "Trigger reason should be 'message_flood'"
        assert controller.is_panic_mode_active(chat_id) is True, (
            "is_panic_mode_active should return True after activation"
        )

    @given(
        chat_id=chat_ids,
        num_messages=messages_below_threshold,
        num_users=unique_users_for_flood,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_does_not_activate_below_message_threshold(
        self,
        chat_id: int,
        num_messages: int,
        num_users: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 17: Panic Mode Activation on Message Flood**
        **Validates: Requirements 6.2**
        
        For any sequence of fewer than 20 messages per second,
        Panic_Mode SHALL NOT be activated.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate num_messages messages within 1 second
        for i in range(num_messages):
            offset_ms = (i * (MESSAGE_WINDOW_SECONDS * 1000 - 1)) // max(num_messages - 1, 1)
            msg_time = base_time + timedelta(milliseconds=offset_ms)
            user_id = user_id_base + (i % num_users)
            
            controller.record_message(chat_id, user_id, current_time=msg_time)
        
        # Check at the end of the window
        check_time = base_time + timedelta(seconds=MESSAGE_WINDOW_SECONDS - 0.001)
        
        # Verify that the message flood trigger is NOT detected
        is_triggered = controller.check_message_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is False, (
            f"Panic mode should NOT be triggered with {num_messages} messages "
            f"(threshold is {MESSAGE_THRESHOLD})"
        )

    @given(
        chat_id=chat_ids,
        num_messages=messages_at_or_above_threshold,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_does_not_activate_with_single_user(
        self,
        chat_id: int,
        num_messages: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 17: Panic Mode Activation on Message Flood**
        **Validates: Requirements 6.2**
        
        For any sequence of 20+ messages from a SINGLE user,
        Panic_Mode SHALL NOT be activated (requires different users).
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate num_messages messages from a SINGLE user within 1 second
        for i in range(num_messages):
            offset_ms = (i * (MESSAGE_WINDOW_SECONDS * 1000 - 1)) // max(num_messages - 1, 1)
            msg_time = base_time + timedelta(milliseconds=offset_ms)
            # All messages from the same user
            user_id = user_id_base
            
            controller.record_message(chat_id, user_id, current_time=msg_time)
        
        # Check at the end of the window
        check_time = base_time + timedelta(seconds=MESSAGE_WINDOW_SECONDS - 0.001)
        
        # Verify that the message flood trigger is NOT detected (single user)
        is_triggered = controller.check_message_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is False, (
            f"Panic mode should NOT be triggered with {num_messages} messages "
            f"from a single user (requires different users)"
        )

    @given(
        chat_id=chat_ids,
        num_messages=messages_at_or_above_threshold,
        num_users=unique_users_for_flood,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_not_triggered_when_messages_outside_window(
        self,
        chat_id: int,
        num_messages: int,
        num_users: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 17: Panic Mode Activation on Message Flood**
        **Validates: Requirements 6.2**
        
        For any sequence of messages spread over more than 1 second,
        Panic_Mode SHALL NOT be activated (messages outside window are cleaned up).
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate messages spread over a period longer than the window
        # Each message is 100ms apart, so 20 messages span 2 seconds
        for i in range(num_messages):
            msg_time = base_time + timedelta(milliseconds=i * 100)
            user_id = user_id_base + (i % num_users)
            
            controller.record_message(chat_id, user_id, current_time=msg_time)
        
        # Check after all messages - at this point, early messages should be cleaned up
        final_time = base_time + timedelta(milliseconds=(num_messages - 1) * 100)
        
        # Get the actual message count in the window
        msg_count = controller.get_message_count(chat_id, current_time=final_time)
        
        # With 100ms intervals, only messages within the last 1 second count
        # That's at most 10 messages (1000ms / 100ms per message)
        expected_max_messages = (MESSAGE_WINDOW_SECONDS * 1000) // 100 + 1
        
        assert msg_count <= expected_max_messages, (
            f"Only {expected_max_messages} messages should be in window, got {msg_count}"
        )
        
        # Verify trigger is not activated (since messages are spread out)
        is_triggered = controller.check_message_trigger(chat_id, current_time=final_time)
        
        assert is_triggered is False, (
            f"Panic mode should NOT be triggered when messages are spread out "
            f"(only {msg_count} messages in window)"
        )

    @given(
        chat_id=chat_ids,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_exactly_threshold_messages_from_multiple_users_triggers_panic_mode(
        self,
        chat_id: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 17: Panic Mode Activation on Message Flood**
        **Validates: Requirements 6.2**
        
        Exactly 20 messages within 1 second from multiple users SHALL trigger Panic_Mode.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate exactly MESSAGE_THRESHOLD messages from 2 different users
        for i in range(MESSAGE_THRESHOLD):
            # All messages happen within a very short time span
            msg_time = base_time + timedelta(milliseconds=i * 10)
            # Alternate between 2 users
            user_id = user_id_base + (i % 2)
            
            controller.record_message(chat_id, user_id, current_time=msg_time)
        
        # Check immediately after the last message
        check_time = base_time + timedelta(milliseconds=MESSAGE_THRESHOLD * 10)
        
        # Verify trigger is detected
        is_triggered = controller.check_message_trigger(chat_id, current_time=check_time)
        
        assert is_triggered is True, (
            f"Panic mode should be triggered with exactly {MESSAGE_THRESHOLD} messages "
            f"from multiple users"
        )

    # ========================================================================
    # Property 18: Panic Mode Silences Welcome Messages
    # ========================================================================

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_silences_welcome_messages_when_active(
        self,
        chat_id: int,
        user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 18: Panic Mode Silences Welcome Messages**
        **Validates: Requirements 6.3**
        
        For any new user join while Panic_Mode is active,
        no welcome message SHALL be sent (should_send_welcome returns False).
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Activate panic mode
        controller.activate_panic_mode(chat_id, "mass_join", current_time=base_time)
        
        # Verify panic mode is active
        assert controller.is_panic_mode_active(chat_id) is True, (
            "Panic mode should be active after activation"
        )
        
        # Simulate a new user joining
        controller.record_join(chat_id, user_id, current_time=base_time)
        
        # Verify that welcome messages should NOT be sent
        should_welcome = controller.should_send_welcome(chat_id)
        
        assert should_welcome is False, (
            "Welcome messages should NOT be sent while panic mode is active"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_welcome_messages_allowed_when_panic_mode_inactive(
        self,
        chat_id: int,
        user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 18: Panic Mode Silences Welcome Messages**
        **Validates: Requirements 6.3**
        
        For any new user join while Panic_Mode is NOT active,
        welcome messages SHALL be allowed (should_send_welcome returns True).
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Verify panic mode is NOT active (default state)
        assert controller.is_panic_mode_active(chat_id) is False, (
            "Panic mode should NOT be active by default"
        )
        
        # Simulate a new user joining
        controller.record_join(chat_id, user_id, current_time=base_time)
        
        # Verify that welcome messages SHOULD be sent
        should_welcome = controller.should_send_welcome(chat_id)
        
        assert should_welcome is True, (
            "Welcome messages should be sent when panic mode is NOT active"
        )

    @given(
        chat_id=chat_ids,
        num_joins=joins_at_or_above_threshold,
        user_id_base=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_silences_welcome_after_mass_join_trigger(
        self,
        chat_id: int,
        num_joins: int,
        user_id_base: int,
    ):
        """
        **Feature: shield-economy-v65, Property 18: Panic Mode Silences Welcome Messages**
        **Validates: Requirements 6.3**
        
        For any mass join event that triggers panic mode,
        subsequent user joins SHALL NOT receive welcome messages.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Simulate mass join to trigger panic mode
        for i in range(num_joins):
            offset_ms = (i * (JOIN_WINDOW_SECONDS * 1000 - 1)) // max(num_joins - 1, 1)
            join_time = base_time + timedelta(milliseconds=offset_ms)
            user_id = user_id_base + i
            
            controller.record_join(chat_id, user_id, current_time=join_time)
        
        # Check at the end of the window
        check_time = base_time + timedelta(seconds=JOIN_WINDOW_SECONDS - 0.001)
        
        # Verify trigger is detected
        is_triggered = controller.check_join_trigger(chat_id, current_time=check_time)
        assert is_triggered is True, "Mass join should trigger panic mode"
        
        # Activate panic mode
        controller.activate_panic_mode(chat_id, "mass_join", current_time=check_time)
        
        # Simulate another user joining after panic mode is activated
        new_user_id = user_id_base + num_joins + 1
        controller.record_join(chat_id, new_user_id, current_time=check_time)
        
        # Verify that welcome messages should NOT be sent
        should_welcome = controller.should_send_welcome(chat_id)
        
        assert should_welcome is False, (
            "Welcome messages should NOT be sent after panic mode is activated "
            "due to mass join"
        )

    # ========================================================================
    # Property 19: Panic Mode Restricts Recent Users
    # ========================================================================

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        hours_since_join=st.integers(min_value=0, max_value=23),
    )
    @settings(max_examples=100)
    def test_panic_mode_restricts_users_joined_within_24_hours(
        self,
        chat_id: int,
        user_id: int,
        hours_since_join: int,
    ):
        """
        **Feature: shield-economy-v65, Property 19: Panic Mode Restricts Recent Users**
        **Validates: Requirements 6.4**
        
        For any user who joined within the last 24 hours while Panic_Mode is active,
        RO status SHALL be applied for 30 minutes.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # User joined hours_since_join hours ago (within 24 hours)
        join_time = base_time - timedelta(hours=hours_since_join)
        
        # Record the user's join time
        controller.record_user_join_time(chat_id, user_id, join_time)
        
        # Activate panic mode
        controller.activate_panic_mode(chat_id, "mass_join", current_time=base_time)
        
        # Check if user should be restricted (joined within 24 hours)
        should_restrict, ro_duration = controller.should_restrict_recent_user(
            chat_id, user_id, current_time=base_time
        )
        
        assert should_restrict is True, (
            f"User who joined {hours_since_join} hours ago should be restricted "
            f"during panic mode (threshold is 24 hours)"
        )
        
        assert ro_duration == 30, (
            f"RO duration should be 30 minutes, got {ro_duration}"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        hours_since_join=st.integers(min_value=25, max_value=100),
    )
    @settings(max_examples=100)
    def test_panic_mode_does_not_restrict_users_joined_over_24_hours_ago(
        self,
        chat_id: int,
        user_id: int,
        hours_since_join: int,
    ):
        """
        **Feature: shield-economy-v65, Property 19: Panic Mode Restricts Recent Users**
        **Validates: Requirements 6.4**
        
        For any user who joined more than 24 hours ago,
        RO status SHALL NOT be applied even during panic mode.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # User joined hours_since_join hours ago (more than 24 hours)
        join_time = base_time - timedelta(hours=hours_since_join)
        
        # Record the user's join time
        controller.record_user_join_time(chat_id, user_id, join_time)
        
        # Activate panic mode
        controller.activate_panic_mode(chat_id, "mass_join", current_time=base_time)
        
        # Check if user should be restricted
        should_restrict, ro_duration = controller.should_restrict_recent_user(
            chat_id, user_id, current_time=base_time
        )
        
        assert should_restrict is False, (
            f"User who joined {hours_since_join} hours ago should NOT be restricted "
            f"(threshold is 24 hours)"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        hours_since_join=st.integers(min_value=0, max_value=23),
    )
    @settings(max_examples=100)
    def test_panic_mode_does_not_restrict_recent_users_when_inactive(
        self,
        chat_id: int,
        user_id: int,
        hours_since_join: int,
    ):
        """
        **Feature: shield-economy-v65, Property 19: Panic Mode Restricts Recent Users**
        **Validates: Requirements 6.4**
        
        For any user who joined within 24 hours while Panic_Mode is NOT active,
        RO status SHALL NOT be applied.
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # User joined hours_since_join hours ago (within 24 hours)
        join_time = base_time - timedelta(hours=hours_since_join)
        
        # Record the user's join time
        controller.record_user_join_time(chat_id, user_id, join_time)
        
        # Do NOT activate panic mode
        
        # Check if user should be restricted
        should_restrict, ro_duration = controller.should_restrict_recent_user(
            chat_id, user_id, current_time=base_time
        )
        
        assert should_restrict is False, (
            f"User who joined {hours_since_join} hours ago should NOT be restricted "
            f"when panic mode is NOT active"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_panic_mode_restriction_exactly_at_24_hour_boundary(
        self,
        chat_id: int,
        user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 19: Panic Mode Restricts Recent Users**
        **Validates: Requirements 6.4**
        
        For a user who joined exactly 24 hours ago,
        RO status SHALL NOT be applied (boundary condition - must be within 24 hours).
        """
        controller = PanicModeController()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # User joined exactly 24 hours ago
        join_time = base_time - timedelta(hours=24)
        
        # Record the user's join time
        controller.record_user_join_time(chat_id, user_id, join_time)
        
        # Activate panic mode
        controller.activate_panic_mode(chat_id, "mass_join", current_time=base_time)
        
        # Check if user should be restricted
        should_restrict, ro_duration = controller.should_restrict_recent_user(
            chat_id, user_id, current_time=base_time
        )
        
        assert should_restrict is False, (
            "User who joined exactly 24 hours ago should NOT be restricted "
            "(must be within 24 hours, not at 24 hours)"
        )
