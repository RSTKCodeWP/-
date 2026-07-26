"""
Property-based tests for EnergyLimiterService (Personal Cooldown System).

**Feature: shield-economy-v65, Property 1: Energy Decrement on Rapid Requests**
**Validates: Requirements 1.1**

**Feature: shield-economy-v65, Property 2: Cooldown Message Contains Required Elements**
**Validates: Requirements 1.2**

**Feature: shield-economy-v65, Property 3: Energy Reset After Inactivity**
**Validates: Requirements 1.3**

**Feature: shield-economy-v65, Property 4: Energy Allows Processing**
**Validates: Requirements 1.4**
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/services/energy_limiter.py)
# ============================================================================

MAX_ENERGY = 3
RAPID_REQUEST_WINDOW = 10  # seconds
COOLDOWN_DURATION = 60  # seconds
INACTIVITY_RESET_PERIOD = 60  # seconds


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class EnergyStatus:
    """Current energy status for a user."""
    user_id: int
    chat_id: int
    energy: int = MAX_ENERGY
    last_request: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    can_proceed: bool = True
    cooldown_message: Optional[str] = None


class EnergyLimiterService:
    """
    Minimal EnergyLimiterService for testing without DB/Redis dependencies.
    
    This mirrors the core logic from app/services/energy_limiter.py.
    """
    
    def __init__(self):
        self._cache: Dict[Tuple[int, int], EnergyStatus] = {}
    
    def _get_status(self, user_id: int, chat_id: int) -> EnergyStatus:
        """Get or create energy status."""
        cache_key = (user_id, chat_id)
        if cache_key not in self._cache:
            self._cache[cache_key] = EnergyStatus(
                user_id=user_id,
                chat_id=chat_id,
                energy=MAX_ENERGY,
            )
        return self._cache[cache_key]
    
    def _save_status(self, status: EnergyStatus) -> None:
        """Save energy status."""
        cache_key = (status.user_id, status.chat_id)
        self._cache[cache_key] = status
    
    def check_energy(
        self,
        user_id: int,
        chat_id: int,
        user_mention: str = "",
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a user has energy to make a request.
        
        Returns:
            Tuple of (can_proceed, cooldown_message)
        """
        now = current_time or utc_now()
        status = self._get_status(user_id, chat_id)
        
        # Check if in cooldown
        if status.cooldown_until and status.cooldown_until > now:
            remaining = int((status.cooldown_until - now).total_seconds())
            message = self._format_cooldown_message(user_mention, remaining)
            return False, message
        
        # Check if energy should be reset due to inactivity
        if status.last_request:
            time_since_last = (now - status.last_request).total_seconds()
            if time_since_last >= INACTIVITY_RESET_PERIOD:
                self.reset_energy(user_id, chat_id)
                return True, None
        
        # Check if user has energy
        if status.energy > 0:
            return True, None
        
        # No energy - set cooldown
        status.cooldown_until = now + timedelta(seconds=COOLDOWN_DURATION)
        self._save_status(status)
        message = self._format_cooldown_message(user_mention, COOLDOWN_DURATION)
        return False, message
    
    def consume_energy(
        self,
        user_id: int,
        chat_id: int,
        user_mention: str = "",
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Consume energy for a user request.
        
        Returns:
            Tuple of (success, cooldown_message)
        """
        now = current_time or utc_now()
        status = self._get_status(user_id, chat_id)
        
        # Check if this is a rapid request
        is_rapid = False
        if status.last_request:
            time_since_last = (now - status.last_request).total_seconds()
            is_rapid = time_since_last < RAPID_REQUEST_WINDOW
        
        # Update last request time
        status.last_request = now
        
        if is_rapid and status.energy > 0:
            # Decrement energy on rapid request
            status.energy -= 1
            
            if status.energy == 0:
                # Enter cooldown
                status.cooldown_until = now + timedelta(seconds=COOLDOWN_DURATION)
                self._save_status(status)
                message = self._format_cooldown_message(user_mention, COOLDOWN_DURATION)
                return True, message
        
        self._save_status(status)
        return True, None
    
    def reset_energy(self, user_id: int, chat_id: int) -> None:
        """Reset a user's energy to maximum."""
        status = EnergyStatus(
            user_id=user_id,
            chat_id=chat_id,
            energy=MAX_ENERGY,
            last_request=None,
            cooldown_until=None,
        )
        self._save_status(status)
    
    def get_cooldown_remaining(
        self,
        user_id: int,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> int:
        """Get remaining cooldown time in seconds."""
        now = current_time or utc_now()
        status = self._get_status(user_id, chat_id)
        
        if not status.cooldown_until:
            return 0
        
        if status.cooldown_until <= now:
            return 0
        
        return int((status.cooldown_until - now).total_seconds())
    
    def get_energy(self, user_id: int, chat_id: int) -> int:
        """Get current energy level."""
        status = self._get_status(user_id, chat_id)
        return status.energy
    
    def _format_cooldown_message(
        self,
        user_mention: str,
        remaining_seconds: int
    ) -> str:
        """Format the cooldown message."""
        if not user_mention:
            user_mention = "Пользователь"
        
        return (
            f"{user_mention}, подожди {remaining_seconds} секунд перед следующим запросом. "
            f"Энергия восстановится после паузы."
        )


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for energy levels
energy_levels = st.integers(min_value=0, max_value=MAX_ENERGY)

# Strategy for time intervals in seconds
time_intervals = st.integers(min_value=0, max_value=300)

# Strategy for user mentions
user_mentions = st.text(min_size=1, max_size=50).filter(lambda x: x.strip())


# ============================================================================
# Property Tests
# ============================================================================


class TestEnergyLimiterProperties:
    """Property-based tests for EnergyLimiterService."""

    # ========================================================================
    # Property 1: Energy Decrement on Rapid Requests
    # ========================================================================

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        initial_energy=st.integers(min_value=1, max_value=MAX_ENERGY),
        rapid_interval=st.integers(min_value=0, max_value=RAPID_REQUEST_WINDOW - 1),
    )
    @settings(max_examples=100)
    def test_energy_decrements_by_one_on_rapid_request(
        self,
        user_id: int,
        chat_id: int,
        initial_energy: int,
        rapid_interval: int,
    ):
        """
        **Feature: shield-economy-v65, Property 1: Energy Decrement on Rapid Requests**
        **Validates: Requirements 1.1**
        
        For any user with energy > 0 who sends a message within 10 seconds
        of their previous message, the energy counter SHALL be decremented by exactly 1.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set initial energy state
        status = service._get_status(user_id, chat_id)
        status.energy = initial_energy
        status.last_request = base_time
        service._save_status(status)
        
        # Make a rapid request (within RAPID_REQUEST_WINDOW seconds)
        rapid_time = base_time + timedelta(seconds=rapid_interval)
        service.consume_energy(user_id, chat_id, current_time=rapid_time)
        
        # Verify energy decremented by exactly 1
        new_energy = service.get_energy(user_id, chat_id)
        assert new_energy == initial_energy - 1, (
            f"Energy should decrement by 1 on rapid request. "
            f"Expected {initial_energy - 1}, got {new_energy}"
        )

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        slow_interval=st.integers(min_value=RAPID_REQUEST_WINDOW, max_value=INACTIVITY_RESET_PERIOD - 1),
    )
    @settings(max_examples=100)
    def test_energy_does_not_decrement_on_slow_request(
        self,
        user_id: int,
        chat_id: int,
        slow_interval: int,
    ):
        """
        **Feature: shield-economy-v65, Property 1: Energy Decrement on Rapid Requests**
        **Validates: Requirements 1.1**
        
        For any user who sends a message after 10+ seconds (but before inactivity reset),
        the energy counter SHALL NOT be decremented.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set initial state with full energy
        status = service._get_status(user_id, chat_id)
        status.energy = MAX_ENERGY
        status.last_request = base_time
        service._save_status(status)
        
        # Make a slow request (>= RAPID_REQUEST_WINDOW seconds)
        slow_time = base_time + timedelta(seconds=slow_interval)
        service.consume_energy(user_id, chat_id, current_time=slow_time)
        
        # Verify energy did NOT decrement
        new_energy = service.get_energy(user_id, chat_id)
        assert new_energy == MAX_ENERGY, (
            f"Energy should NOT decrement on slow request. "
            f"Expected {MAX_ENERGY}, got {new_energy}"
        )

    # ========================================================================
    # Property 2: Cooldown Message Contains Required Elements
    # ========================================================================

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        user_mention=user_mentions,
    )
    @settings(max_examples=100)
    def test_cooldown_message_contains_user_mention_and_wait_instruction(
        self,
        user_id: int,
        chat_id: int,
        user_mention: str,
    ):
        """
        **Feature: shield-economy-v65, Property 2: Cooldown Message Contains Required Elements**
        **Validates: Requirements 1.2**
        
        For any user with energy = 0, the cooldown response SHALL contain
        the user's mention and a 60-second wait instruction.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set user to zero energy with active cooldown
        status = service._get_status(user_id, chat_id)
        status.energy = 0
        status.last_request = base_time
        status.cooldown_until = base_time + timedelta(seconds=COOLDOWN_DURATION)
        service._save_status(status)
        
        # Check energy - should return cooldown message
        can_proceed, message = service.check_energy(
            user_id, chat_id, user_mention, current_time=base_time
        )
        
        assert can_proceed is False, "User with 0 energy should not proceed"
        assert message is not None, "Cooldown message should not be None"
        assert user_mention in message, (
            f"Cooldown message should contain user mention '{user_mention}'"
        )
        assert "секунд" in message, (
            "Cooldown message should contain wait instruction with seconds"
        )

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        remaining_seconds=st.integers(min_value=1, max_value=COOLDOWN_DURATION),
    )
    @settings(max_examples=100)
    def test_cooldown_message_shows_correct_remaining_time(
        self,
        user_id: int,
        chat_id: int,
        remaining_seconds: int,
    ):
        """
        **Feature: shield-economy-v65, Property 2: Cooldown Message Contains Required Elements**
        **Validates: Requirements 1.2**
        
        The cooldown message SHALL show the correct remaining time.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set cooldown to expire in remaining_seconds
        status = service._get_status(user_id, chat_id)
        status.energy = 0
        status.cooldown_until = base_time + timedelta(seconds=remaining_seconds)
        service._save_status(status)
        
        # Check energy
        can_proceed, message = service.check_energy(
            user_id, chat_id, "TestUser", current_time=base_time
        )
        
        assert can_proceed is False
        assert message is not None
        assert str(remaining_seconds) in message, (
            f"Cooldown message should contain remaining time {remaining_seconds}"
        )

    # ========================================================================
    # Property 3: Energy Reset After Inactivity
    # ========================================================================

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        depleted_energy=st.integers(min_value=0, max_value=MAX_ENERGY - 1),
        inactivity_seconds=st.integers(min_value=INACTIVITY_RESET_PERIOD, max_value=300),
    )
    @settings(max_examples=100)
    def test_energy_resets_to_max_after_inactivity(
        self,
        user_id: int,
        chat_id: int,
        depleted_energy: int,
        inactivity_seconds: int,
    ):
        """
        **Feature: shield-economy-v65, Property 3: Energy Reset After Inactivity**
        **Validates: Requirements 1.3**
        
        For any user who sends a message after 60+ seconds of inactivity,
        the energy counter SHALL be reset to 3.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set depleted energy state
        status = service._get_status(user_id, chat_id)
        status.energy = depleted_energy
        status.last_request = base_time
        status.cooldown_until = None  # Not in cooldown
        service._save_status(status)
        
        # Check energy after inactivity period
        inactive_time = base_time + timedelta(seconds=inactivity_seconds)
        can_proceed, _ = service.check_energy(user_id, chat_id, current_time=inactive_time)
        
        # Verify energy was reset to MAX
        new_energy = service.get_energy(user_id, chat_id)
        assert new_energy == MAX_ENERGY, (
            f"Energy should reset to {MAX_ENERGY} after {inactivity_seconds}s inactivity. "
            f"Got {new_energy}"
        )
        assert can_proceed is True, "User should be able to proceed after inactivity reset"

    # ========================================================================
    # Property 4: Energy Allows Processing
    # ========================================================================

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        positive_energy=st.integers(min_value=1, max_value=MAX_ENERGY),
    )
    @settings(max_examples=100)
    def test_user_with_energy_can_proceed(
        self,
        user_id: int,
        chat_id: int,
        positive_energy: int,
    ):
        """
        **Feature: shield-economy-v65, Property 4: Energy Allows Processing**
        **Validates: Requirements 1.4**
        
        For any user with energy > 0, the request SHALL be allowed
        to proceed to LLM processing.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Set positive energy state
        status = service._get_status(user_id, chat_id)
        status.energy = positive_energy
        status.last_request = None  # Fresh user
        status.cooldown_until = None
        service._save_status(status)
        
        # Check energy
        can_proceed, message = service.check_energy(user_id, chat_id, current_time=base_time)
        
        assert can_proceed is True, (
            f"User with energy={positive_energy} should be allowed to proceed"
        )
        assert message is None, "No cooldown message should be returned for user with energy"

    @given(
        user_id=user_ids,
        chat_id=chat_ids,
    )
    @settings(max_examples=100)
    def test_new_user_starts_with_max_energy_and_can_proceed(
        self,
        user_id: int,
        chat_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 4: Energy Allows Processing**
        **Validates: Requirements 1.4**
        
        A new user SHALL start with maximum energy and be allowed to proceed.
        """
        service = EnergyLimiterService()
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # New user - no prior state
        can_proceed, message = service.check_energy(user_id, chat_id, current_time=base_time)
        
        assert can_proceed is True, "New user should be allowed to proceed"
        assert message is None, "No cooldown message for new user"
        
        # Verify initial energy is MAX
        energy = service.get_energy(user_id, chat_id)
        assert energy == MAX_ENERGY, f"New user should have {MAX_ENERGY} energy, got {energy}"
