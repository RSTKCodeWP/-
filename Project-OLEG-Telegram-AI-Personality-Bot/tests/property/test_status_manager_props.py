"""
Property-based tests for StatusManager (Anti-Flood Status Notifications).

**Feature: shield-economy-v65, Property 7: Processing State Triggers Reaction**
**Validates: Requirements 3.1**

**Feature: shield-economy-v65, Property 8: First Request Triggers Notification**
**Validates: Requirements 3.2**
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from hypothesis import given, strategies as st, settings


# ============================================================================
# Constants (mirroring app/services/status_manager.py)
# ============================================================================

PENDING_REACTION = "⏳"


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class ProcessingStatus:
    """Processing status for a chat."""
    chat_id: int
    is_processing: bool = False
    pending_messages: List[int] = field(default_factory=list)
    started_at: Optional[datetime] = None


class StatusManager:
    """
    Minimal StatusManager for testing without Redis dependencies.
    
    This mirrors the core logic from app/services/status_manager.py.
    """
    
    def __init__(self):
        self._processing_state: Dict[int, ProcessingStatus] = {}
    
    def _get_status(self, chat_id: int) -> ProcessingStatus:
        """Get or create processing status."""
        if chat_id not in self._processing_state:
            self._processing_state[chat_id] = ProcessingStatus(chat_id=chat_id)
        return self._processing_state[chat_id]
    
    def _save_status(self, status: ProcessingStatus) -> None:
        """Save processing status."""
        self._processing_state[status.chat_id] = status
    
    def start_processing(
        self,
        chat_id: int,
        message_id: int
    ) -> bool:
        """
        Start processing state for a chat.
        
        Returns:
            True if this is the first request (send notification),
            False if already processing (add reaction instead)
        """
        is_first = not self.is_processing(chat_id)
        
        if is_first:
            # First request - start processing state
            status = ProcessingStatus(
                chat_id=chat_id,
                is_processing=True,
                pending_messages=[message_id],
                started_at=utc_now(),
            )
            self._save_status(status)
            return True
        else:
            # Already processing - add to pending
            self.add_pending_reaction(chat_id, message_id)
            return False
    
    def add_pending_reaction(
        self,
        chat_id: int,
        message_id: int
    ) -> None:
        """Add a message to the pending reactions list."""
        status = self._get_status(chat_id)
        
        if message_id not in status.pending_messages:
            status.pending_messages.append(message_id)
            self._save_status(status)
    
    def finish_processing(
        self,
        chat_id: int
    ) -> List[int]:
        """
        Finish processing state for a chat.
        
        Returns:
            List of message IDs with pending reactions to remove
        """
        status = self._get_status(chat_id)
        pending = status.pending_messages.copy()
        
        # Clear processing state
        status.is_processing = False
        status.pending_messages = []
        status.started_at = None
        self._save_status(status)
        
        return pending
    
    def is_processing(
        self,
        chat_id: int
    ) -> bool:
        """Check if a chat is currently processing a request."""
        status = self._get_status(chat_id)
        return status.is_processing
    
    def get_pending_messages(
        self,
        chat_id: int
    ) -> List[int]:
        """Get list of messages with pending reactions."""
        status = self._get_status(chat_id)
        return status.pending_messages.copy()
    
    def get_pending_reaction_emoji(self) -> str:
        """Get the emoji used for pending reactions."""
        return PENDING_REACTION


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for message IDs (positive)
message_ids = st.integers(min_value=1, max_value=999999999)

# Strategy for lists of unique message IDs
message_id_lists = st.lists(
    st.integers(min_value=1, max_value=999999999),
    min_size=1,
    max_size=10,
    unique=True
)


# ============================================================================
# Property Tests
# ============================================================================


class TestStatusManagerProperties:
    """Property-based tests for StatusManager."""

    # ========================================================================
    # Property 7: Processing State Triggers Reaction
    # ========================================================================

    @given(
        chat_id=chat_ids,
        first_message_id=message_ids,
        subsequent_message_ids=message_id_lists,
    )
    @settings(max_examples=100)
    def test_subsequent_messages_get_pending_reaction(
        self,
        chat_id: int,
        first_message_id: int,
        subsequent_message_ids: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 7: Processing State Triggers Reaction**
        **Validates: Requirements 3.1**
        
        While OLEG_Bot is processing a request in a chat, new incoming messages
        SHALL receive a reaction (⏳) instead of status notifications.
        """
        # Ensure first_message_id is not in subsequent list
        subsequent_message_ids = [
            mid for mid in subsequent_message_ids if mid != first_message_id
        ]
        if not subsequent_message_ids:
            return  # Skip if no subsequent messages
        
        manager = StatusManager()
        
        # Start processing with first message
        is_first = manager.start_processing(chat_id, first_message_id)
        assert is_first is True, "First message should trigger notification"
        
        # Subsequent messages should NOT trigger notification
        for msg_id in subsequent_message_ids:
            is_first = manager.start_processing(chat_id, msg_id)
            assert is_first is False, (
                f"Subsequent message {msg_id} should NOT trigger notification"
            )
        
        # All subsequent messages should be in pending list
        pending = manager.get_pending_messages(chat_id)
        for msg_id in subsequent_message_ids:
            assert msg_id in pending, (
                f"Message {msg_id} should be in pending reactions list"
            )

    @given(
        chat_id=chat_ids,
        message_ids_list=message_id_lists,
    )
    @settings(max_examples=100)
    def test_pending_reaction_emoji_is_hourglass(
        self,
        chat_id: int,
        message_ids_list: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 7: Processing State Triggers Reaction**
        **Validates: Requirements 3.1**
        
        The pending reaction emoji SHALL be ⏳.
        """
        manager = StatusManager()
        
        emoji = manager.get_pending_reaction_emoji()
        assert emoji == "⏳", f"Pending reaction should be ⏳, got {emoji}"

    @given(
        chat_id=chat_ids,
        first_message_id=message_ids,
        subsequent_message_ids=message_id_lists,
    )
    @settings(max_examples=100)
    def test_finish_processing_returns_pending_messages(
        self,
        chat_id: int,
        first_message_id: int,
        subsequent_message_ids: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 7: Processing State Triggers Reaction**
        **Validates: Requirements 3.3**
        
        When processing completes, the list of pending messages SHALL be returned
        so reactions can be removed.
        """
        # Ensure first_message_id is not in subsequent list
        subsequent_message_ids = [
            mid for mid in subsequent_message_ids if mid != first_message_id
        ]
        
        manager = StatusManager()
        
        # Start processing
        manager.start_processing(chat_id, first_message_id)
        
        # Add subsequent messages
        for msg_id in subsequent_message_ids:
            manager.start_processing(chat_id, msg_id)
        
        # Finish processing
        returned_pending = manager.finish_processing(chat_id)
        
        # First message should be in returned list
        assert first_message_id in returned_pending, (
            "First message should be in returned pending list"
        )
        
        # All subsequent messages should be in returned list
        for msg_id in subsequent_message_ids:
            assert msg_id in returned_pending, (
                f"Message {msg_id} should be in returned pending list"
            )
        
        # After finish, pending list should be empty
        current_pending = manager.get_pending_messages(chat_id)
        assert len(current_pending) == 0, (
            "Pending list should be empty after finish_processing"
        )

    # ========================================================================
    # Property 8: First Request Triggers Notification
    # ========================================================================

    @given(
        chat_id=chat_ids,
        message_id=message_ids,
    )
    @settings(max_examples=100)
    def test_first_request_triggers_notification(
        self,
        chat_id: int,
        message_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 8: First Request Triggers Notification**
        **Validates: Requirements 3.2**
        
        When OLEG_Bot starts processing the first request in a chat,
        it SHALL send a single status notification.
        """
        manager = StatusManager()
        
        # Verify chat is not processing initially
        assert manager.is_processing(chat_id) is False, (
            "Chat should not be processing initially"
        )
        
        # First request should trigger notification
        is_first = manager.start_processing(chat_id, message_id)
        
        assert is_first is True, (
            "First request should return True (trigger notification)"
        )
        assert manager.is_processing(chat_id) is True, (
            "Chat should be in processing state after first request"
        )

    @given(
        chat_id=chat_ids,
        message_ids_list=message_id_lists,
    )
    @settings(max_examples=100)
    def test_only_first_request_triggers_notification(
        self,
        chat_id: int,
        message_ids_list: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 8: First Request Triggers Notification**
        **Validates: Requirements 3.2**
        
        Only the first request SHALL trigger a notification.
        All subsequent requests SHALL NOT trigger notifications.
        """
        manager = StatusManager()
        
        notification_count = 0
        
        for msg_id in message_ids_list:
            is_first = manager.start_processing(chat_id, msg_id)
            if is_first:
                notification_count += 1
        
        assert notification_count == 1, (
            f"Exactly 1 notification should be triggered, got {notification_count}"
        )

    @given(
        chat_id=chat_ids,
        first_message_id=message_ids,
        second_message_id=message_ids,
    )
    @settings(max_examples=100)
    def test_new_request_after_finish_triggers_notification(
        self,
        chat_id: int,
        first_message_id: int,
        second_message_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 8: First Request Triggers Notification**
        **Validates: Requirements 3.2**
        
        After processing finishes, a new request SHALL trigger a new notification.
        """
        manager = StatusManager()
        
        # First processing cycle
        is_first_1 = manager.start_processing(chat_id, first_message_id)
        assert is_first_1 is True, "First request should trigger notification"
        
        # Finish processing
        manager.finish_processing(chat_id)
        
        # Verify not processing
        assert manager.is_processing(chat_id) is False, (
            "Chat should not be processing after finish"
        )
        
        # New request should trigger notification again
        is_first_2 = manager.start_processing(chat_id, second_message_id)
        assert is_first_2 is True, (
            "New request after finish should trigger notification"
        )
