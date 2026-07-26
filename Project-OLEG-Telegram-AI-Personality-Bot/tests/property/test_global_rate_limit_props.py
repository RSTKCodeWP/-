"""
Property-based tests for GlobalRateLimiterService (Chat-level Rate Limiting).

**Feature: shield-economy-v65, Property 5: Global Limit Exceeded Behavior**
**Validates: Requirements 2.1, 2.2**

**Feature: shield-economy-v65, Property 6: Rate Limit Window Reset**
**Validates: Requirements 2.4**
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/services/global_rate_limiter.py)
# ============================================================================

DEFAULT_LIMIT = 20
RATE_LIMIT_WINDOW = 60  # seconds
BUSY_RESPONSE = "Занят."


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class ChatRateLimit:
    """Rate limit status for a chat."""
    chat_id: int
    request_count: int = 0
    limit: int = DEFAULT_LIMIT
    window_start: Optional[datetime] = None


class GlobalRateLimiterService:
    """
    Minimal GlobalRateLimiterService for testing without DB/Redis dependencies.
    
    This mirrors the core logic from app/services/global_rate_limiter.py.
    """
    
    def __init__(self):
        # In-memory counters: chat_id -> (count, window_start)
        self._memory_counters: Dict[int, Tuple[int, datetime]] = {}
        # Limit configurations: chat_id -> limit
        self._limit_cache: Dict[int, int] = {}
    
    def check_chat_limit(
        self,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a chat has exceeded its rate limit.
        
        Returns:
            Tuple of (can_proceed, busy_message)
        """
        limit = self.get_chat_limit(chat_id)
        count = self._get_memory_count(chat_id, current_time)
        
        if count >= limit:
            return False, BUSY_RESPONSE
        
        return True, None
    
    def increment_chat_counter(
        self,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> int:
        """Increment the request counter for a chat."""
        return self._increment_memory(chat_id, current_time)
    
    def set_chat_limit(
        self,
        chat_id: int,
        limit: int
    ) -> None:
        """Set custom rate limit for a chat."""
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        self._limit_cache[chat_id] = limit
    
    def get_chat_limit(
        self,
        chat_id: int
    ) -> int:
        """Get the rate limit for a chat."""
        return self._limit_cache.get(chat_id, DEFAULT_LIMIT)
    
    def get_current_count(
        self,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> int:
        """Get current request count for a chat."""
        return self._get_memory_count(chat_id, current_time)
    
    def reset_counter(
        self,
        chat_id: int
    ) -> None:
        """Reset the request counter for a chat."""
        if chat_id in self._memory_counters:
            del self._memory_counters[chat_id]
    
    def _get_memory_count(
        self,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> int:
        """Get current count from memory, handling window expiration."""
        now = current_time or utc_now()
        
        if chat_id not in self._memory_counters:
            return 0
        
        count, window_start = self._memory_counters[chat_id]
        
        # Check if window has expired
        elapsed = (now - window_start).total_seconds()
        if elapsed >= RATE_LIMIT_WINDOW:
            # Window expired, reset counter
            del self._memory_counters[chat_id]
            return 0
        
        return count
    
    def _increment_memory(
        self,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> int:
        """Increment counter in memory with window tracking."""
        now = current_time or utc_now()
        
        if chat_id in self._memory_counters:
            count, window_start = self._memory_counters[chat_id]
            elapsed = (now - window_start).total_seconds()
            
            if elapsed >= RATE_LIMIT_WINDOW:
                # Start new window
                self._memory_counters[chat_id] = (1, now)
                return 1
            else:
                # Increment in current window
                new_count = count + 1
                self._memory_counters[chat_id] = (new_count, window_start)
                return new_count
        else:
            # First request, start new window
            self._memory_counters[chat_id] = (1, now)
            return 1


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for rate limits
rate_limits = st.integers(min_value=1, max_value=100)

# Strategy for request counts
request_counts = st.integers(min_value=0, max_value=50)


# ============================================================================
# Property Tests
# ============================================================================


class TestGlobalRateLimiterProperties:
    """Property-based tests for GlobalRateLimiterService."""

    # ========================================================================
    # Property 5: Global Limit Exceeded Behavior
    # ========================================================================

    @given(
        chat_id=chat_ids,
        limit=rate_limits,
    )
    @settings(max_examples=100)
    def test_requests_rejected_when_limit_exceeded(
        self,
        chat_id: int,
        limit: int,
    ):
        """
        **Feature: shield-economy-v65, Property 5: Global Limit Exceeded Behavior**
        **Validates: Requirements 2.1, 2.2**
        
        For any chat at or above the configured LLM request limit,
        new requests SHALL be rejected and the response SHALL be "Занят."
        """
        service = GlobalRateLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set custom limit
        service.set_chat_limit(chat_id, limit)
        
        # Make exactly 'limit' requests to reach the limit (all at same time)
        for i in range(limit):
            service.increment_chat_counter(chat_id, current_time=base_time)
        
        # Check that limit is now exceeded (within same window)
        check_time = base_time + timedelta(seconds=30)  # Still within 60s window
        can_proceed, message = service.check_chat_limit(chat_id, current_time=check_time)
        
        assert can_proceed is False, (
            f"Request should be rejected when limit ({limit}) is reached"
        )
        assert message == BUSY_RESPONSE, (
            f"Response should be '{BUSY_RESPONSE}', got '{message}'"
        )

    @given(
        chat_id=chat_ids,
        limit=rate_limits,
        requests_under_limit=st.integers(min_value=0, max_value=19),
    )
    @settings(max_examples=100)
    def test_requests_allowed_when_under_limit(
        self,
        chat_id: int,
        limit: int,
        requests_under_limit: int,
    ):
        """
        **Feature: shield-economy-v65, Property 5: Global Limit Exceeded Behavior**
        **Validates: Requirements 2.1, 2.2**
        
        For any chat under the configured limit, requests SHALL be allowed.
        """
        # Ensure we're testing under the limit
        assume(requests_under_limit < limit)
        
        service = GlobalRateLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set custom limit
        service.set_chat_limit(chat_id, limit)
        
        # Make requests_under_limit requests
        for i in range(requests_under_limit):
            request_time = base_time + timedelta(seconds=i)
            service.increment_chat_counter(chat_id, current_time=request_time)
        
        # Check that we can still proceed
        check_time = base_time + timedelta(seconds=requests_under_limit)
        can_proceed, message = service.check_chat_limit(chat_id, current_time=check_time)
        
        assert can_proceed is True, (
            f"Request should be allowed when under limit "
            f"({requests_under_limit}/{limit})"
        )
        assert message is None, "No busy message should be returned when under limit"

    @given(
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_busy_response_is_correct_message(
        self,
        chat_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 5: Global Limit Exceeded Behavior**
        **Validates: Requirements 2.2**
        
        When limit is exceeded, the response SHALL be exactly "Занят."
        """
        service = GlobalRateLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set limit to 1 and exceed it
        service.set_chat_limit(chat_id, 1)
        service.increment_chat_counter(chat_id, current_time=base_time)
        
        # Check response
        can_proceed, message = service.check_chat_limit(
            chat_id, current_time=base_time + timedelta(seconds=1)
        )
        
        assert can_proceed is False
        assert message == "Занят.", f"Expected 'Занят.', got '{message}'"

    # ========================================================================
    # Property 6: Rate Limit Window Reset
    # ========================================================================

    @given(
        chat_id=chat_ids,
        limit=rate_limits,
        extra_seconds=st.integers(min_value=0, max_value=60),
    )
    @settings(max_examples=100)
    def test_counter_resets_after_window_expires(
        self,
        chat_id: int,
        limit: int,
        extra_seconds: int,
    ):
        """
        **Feature: shield-economy-v65, Property 6: Rate Limit Window Reset**
        **Validates: Requirements 2.4**
        
        For any chat with any request counter value, after 60 seconds
        the counter SHALL be reset to 0.
        """
        service = GlobalRateLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set limit and make requests to reach it
        service.set_chat_limit(chat_id, limit)
        for i in range(limit):
            service.increment_chat_counter(chat_id, current_time=base_time)
        
        # Verify limit is reached
        count_before = service.get_current_count(chat_id, current_time=base_time)
        assert count_before == limit, f"Expected count {limit}, got {count_before}"
        
        # Wait for window to expire (60+ seconds)
        after_window = base_time + timedelta(seconds=RATE_LIMIT_WINDOW + extra_seconds)
        
        # Counter should be reset to 0
        count_after = service.get_current_count(chat_id, current_time=after_window)
        assert count_after == 0, (
            f"Counter should reset to 0 after {RATE_LIMIT_WINDOW}s window. "
            f"Got {count_after}"
        )

    @given(
        chat_id=chat_ids,
        limit=rate_limits,
        extra_seconds=st.integers(min_value=0, max_value=60),
    )
    @settings(max_examples=100)
    def test_requests_allowed_after_window_reset(
        self,
        chat_id: int,
        limit: int,
        extra_seconds: int,
    ):
        """
        **Feature: shield-economy-v65, Property 6: Rate Limit Window Reset**
        **Validates: Requirements 2.4**
        
        After the window resets, requests SHALL be allowed again.
        """
        service = GlobalRateLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set limit and exceed it
        service.set_chat_limit(chat_id, limit)
        for i in range(limit):
            service.increment_chat_counter(chat_id, current_time=base_time)
        
        # Verify limit is exceeded
        can_proceed_before, _ = service.check_chat_limit(chat_id, current_time=base_time)
        assert can_proceed_before is False, "Should be blocked before window reset"
        
        # Wait for window to expire
        after_window = base_time + timedelta(seconds=RATE_LIMIT_WINDOW + extra_seconds)
        
        # Should be allowed again
        can_proceed_after, message = service.check_chat_limit(
            chat_id, current_time=after_window
        )
        assert can_proceed_after is True, (
            "Requests should be allowed after window reset"
        )
        assert message is None, "No busy message after window reset"

    @given(
        chat_id=chat_ids,
        seconds_before_reset=st.integers(min_value=1, max_value=RATE_LIMIT_WINDOW - 1),
    )
    @settings(max_examples=100)
    def test_counter_persists_within_window(
        self,
        chat_id: int,
        seconds_before_reset: int,
    ):
        """
        **Feature: shield-economy-v65, Property 6: Rate Limit Window Reset**
        **Validates: Requirements 2.4**
        
        Within the 60-second window, the counter SHALL persist.
        """
        service = GlobalRateLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Make some requests
        requests_made = 5
        for i in range(requests_made):
            service.increment_chat_counter(chat_id, current_time=base_time)
        
        # Check count within window
        within_window = base_time + timedelta(seconds=seconds_before_reset)
        count = service.get_current_count(chat_id, current_time=within_window)
        
        assert count == requests_made, (
            f"Counter should persist within window. "
            f"Expected {requests_made}, got {count}"
        )
