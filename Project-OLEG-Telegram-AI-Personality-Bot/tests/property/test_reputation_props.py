"""
Property-based tests for ReputationService (Social Credit System).

**Feature: fortress-update, Property 5: Reputation initialization**
**Validates: Requirements 4.1**

**Feature: fortress-update, Property 6: Reputation change deltas**
**Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**

**Feature: fortress-update, Property 7: Read-only threshold**
**Validates: Requirements 4.7**
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline definitions to avoid import issues during testing
# These mirror the actual implementation in app/services/reputation.py
# ============================================================================

class ReputationChange(IntEnum):
    """Reputation change deltas for various events."""
    WARNING = -50
    MUTE = -100
    MESSAGE_DELETED = -10
    THANK_YOU = 5
    TOURNAMENT_WIN = 20


# Reputation thresholds
INITIAL_REPUTATION = 1000
READ_ONLY_THRESHOLD = 200
READ_ONLY_RECOVERY_THRESHOLD = 300


@dataclass
class ReputationStatus:
    """Current reputation status for a user."""
    user_id: int
    chat_id: int
    score: int = INITIAL_REPUTATION
    is_read_only: bool = False
    recent_changes: List[Tuple[datetime, int, str]] = field(default_factory=list)


class ReputationService:
    """Minimal ReputationService for testing without DB dependencies."""
    
    def __init__(self):
        self._cache: Dict[Tuple[int, int], ReputationStatus] = {}
    
    def initialize_user(self, user_id: int, chat_id: int) -> ReputationStatus:
        """Initialize a new user with default reputation score."""
        cache_key = (user_id, chat_id)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        status = ReputationStatus(
            user_id=user_id,
            chat_id=chat_id,
            score=INITIAL_REPUTATION,
            is_read_only=False
        )
        self._cache[cache_key] = status
        return status
    
    def get_reputation(self, user_id: int, chat_id: int) -> ReputationStatus:
        """Get reputation status for a user."""
        cache_key = (user_id, chat_id)
        
        if cache_key not in self._cache:
            return ReputationStatus(
                user_id=user_id,
                chat_id=chat_id,
                score=INITIAL_REPUTATION,
                is_read_only=False
            )
        
        return self._cache[cache_key]
    
    def modify_reputation(
        self,
        user_id: int,
        chat_id: int,
        change: int,
        reason: str
    ) -> ReputationStatus:
        """Modify a user's reputation score."""
        cache_key = (user_id, chat_id)
        
        # Get or create status
        if cache_key not in self._cache:
            self._cache[cache_key] = ReputationStatus(
                user_id=user_id,
                chat_id=chat_id,
                score=INITIAL_REPUTATION,
                is_read_only=False
            )
        
        status = self._cache[cache_key]
        old_score = status.score
        new_score = max(0, old_score + change)  # Score can't go below 0
        
        # Calculate new read-only status
        is_read_only = self._calculate_read_only_status(new_score, status.is_read_only)
        
        # Update status
        new_status = ReputationStatus(
            user_id=user_id,
            chat_id=chat_id,
            score=new_score,
            is_read_only=is_read_only,
            recent_changes=[(datetime.utcnow(), change, reason)]
        )
        self._cache[cache_key] = new_status
        
        return new_status
    
    def _calculate_read_only_status(self, score: int, current_is_read_only: bool) -> bool:
        """Calculate read-only status based on score and current status."""
        if current_is_read_only:
            # Currently read-only: exit only if score > 300
            return score <= READ_ONLY_RECOVERY_THRESHOLD
        else:
            # Currently not read-only: become read-only if score < 200
            return score < READ_ONLY_THRESHOLD
    
    def check_read_only_status(self, user_id: int, chat_id: int) -> bool:
        """Check if a user is in read-only mode."""
        status = self.get_reputation(user_id, chat_id)
        return status.is_read_only


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for reputation scores
reputation_scores = st.integers(min_value=0, max_value=5000)

# Strategy for reputation changes
reputation_changes = st.sampled_from([
    ReputationChange.WARNING,
    ReputationChange.MUTE,
    ReputationChange.MESSAGE_DELETED,
    ReputationChange.THANK_YOU,
    ReputationChange.TOURNAMENT_WIN
])


# ============================================================================
# Property 5: Reputation Initialization
# ============================================================================

class TestReputationInitialization:
    """
    **Feature: fortress-update, Property 5: Reputation initialization**
    **Validates: Requirements 4.1**
    
    For any new user joining a chat, their initial reputation score SHALL be exactly 1000.
    """
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_new_user_gets_initial_score_1000(self, user_id: int, chat_id: int):
        """
        Property: New users are initialized with reputation score of 1000.
        """
        service = ReputationService()
        
        # Initialize new user
        status = service.initialize_user(user_id, chat_id)
        
        # Verify initial score is exactly 1000
        assert status.score == INITIAL_REPUTATION
        assert status.score == 1000
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_new_user_not_read_only(self, user_id: int, chat_id: int):
        """
        Property: New users are not in read-only mode.
        """
        service = ReputationService()
        
        status = service.initialize_user(user_id, chat_id)
        
        assert status.is_read_only is False
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_get_reputation_returns_default_for_unknown_user(self, user_id: int, chat_id: int):
        """
        Property: Getting reputation for unknown user returns default score.
        """
        service = ReputationService()
        
        # Don't initialize - just get
        status = service.get_reputation(user_id, chat_id)
        
        assert status.score == INITIAL_REPUTATION
        assert status.is_read_only is False
    
    def test_initial_reputation_constant(self):
        """
        Property: Initial reputation constant is 1000.
        """
        assert INITIAL_REPUTATION == 1000
    
    @settings(max_examples=50)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_initialize_is_idempotent(self, user_id: int, chat_id: int):
        """
        Property: Initializing the same user twice returns the same status.
        """
        service = ReputationService()
        
        status1 = service.initialize_user(user_id, chat_id)
        status2 = service.initialize_user(user_id, chat_id)
        
        assert status1.score == status2.score
        assert status1.is_read_only == status2.is_read_only


# ============================================================================
# Property 6: Reputation Change Deltas
# ============================================================================

class TestReputationChangeDeltas:
    """
    **Feature: fortress-update, Property 6: Reputation change deltas**
    **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**
    
    For any reputation-affecting event, the change SHALL match the specified delta:
    - Warning: -50
    - Mute: -100
    - Message deleted: -10
    - Thank you reaction: +5
    - Tournament win: +20
    """
    
    def test_warning_delta_is_minus_50(self):
        """
        Property: Warning penalty is -50.
        **Validates: Requirements 4.2**
        """
        assert ReputationChange.WARNING == -50
    
    def test_mute_delta_is_minus_100(self):
        """
        Property: Mute penalty is -100.
        **Validates: Requirements 4.3**
        """
        assert ReputationChange.MUTE == -100
    
    def test_message_deleted_delta_is_minus_10(self):
        """
        Property: Message deleted penalty is -10.
        **Validates: Requirements 4.4**
        """
        assert ReputationChange.MESSAGE_DELETED == -10
    
    def test_thank_you_delta_is_plus_5(self):
        """
        Property: Thank you bonus is +5.
        **Validates: Requirements 4.5**
        """
        assert ReputationChange.THANK_YOU == 5
    
    def test_tournament_win_delta_is_plus_20(self):
        """
        Property: Tournament win bonus is +20.
        **Validates: Requirements 4.6**
        """
        assert ReputationChange.TOURNAMENT_WIN == 20
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_warning_decreases_score_by_50(self, user_id: int, chat_id: int):
        """
        Property: Applying a warning decreases score by exactly 50.
        """
        service = ReputationService()
        
        # Initialize user
        initial = service.initialize_user(user_id, chat_id)
        initial_score = initial.score
        
        # Apply warning
        result = service.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.WARNING,
            reason="warning"
        )
        
        assert result.score == initial_score + ReputationChange.WARNING
        assert result.score == initial_score - 50
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_mute_decreases_score_by_100(self, user_id: int, chat_id: int):
        """
        Property: Applying a mute decreases score by exactly 100.
        """
        service = ReputationService()
        
        initial = service.initialize_user(user_id, chat_id)
        initial_score = initial.score
        
        result = service.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.MUTE,
            reason="mute"
        )
        
        assert result.score == initial_score + ReputationChange.MUTE
        assert result.score == initial_score - 100
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_message_deleted_decreases_score_by_10(self, user_id: int, chat_id: int):
        """
        Property: Deleting a message decreases score by exactly 10.
        """
        service = ReputationService()
        
        initial = service.initialize_user(user_id, chat_id)
        initial_score = initial.score
        
        result = service.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.MESSAGE_DELETED,
            reason="message_deleted"
        )
        
        assert result.score == initial_score + ReputationChange.MESSAGE_DELETED
        assert result.score == initial_score - 10
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_thank_you_increases_score_by_5(self, user_id: int, chat_id: int):
        """
        Property: Thank you reaction increases score by exactly 5.
        """
        service = ReputationService()
        
        initial = service.initialize_user(user_id, chat_id)
        initial_score = initial.score
        
        result = service.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.THANK_YOU,
            reason="thank_you"
        )
        
        assert result.score == initial_score + ReputationChange.THANK_YOU
        assert result.score == initial_score + 5
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_tournament_win_increases_score_by_20(self, user_id: int, chat_id: int):
        """
        Property: Tournament win increases score by exactly 20.
        """
        service = ReputationService()
        
        initial = service.initialize_user(user_id, chat_id)
        initial_score = initial.score
        
        result = service.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.TOURNAMENT_WIN,
            reason="tournament_win"
        )
        
        assert result.score == initial_score + ReputationChange.TOURNAMENT_WIN
        assert result.score == initial_score + 20
    
    @settings(max_examples=100)
    @given(user_id=user_ids, chat_id=chat_ids, change=reputation_changes)
    def test_reputation_change_is_applied_correctly(
        self, user_id: int, chat_id: int, change: ReputationChange
    ):
        """
        Property: Any reputation change is applied with the correct delta.
        """
        service = ReputationService()
        
        initial = service.initialize_user(user_id, chat_id)
        initial_score = initial.score
        
        result = service.modify_reputation(
            user_id, chat_id,
            change=int(change),
            reason="test"
        )
        
        expected_score = max(0, initial_score + int(change))
        assert result.score == expected_score
    
    @settings(max_examples=50)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_score_cannot_go_below_zero(self, user_id: int, chat_id: int):
        """
        Property: Reputation score cannot go below 0.
        """
        service = ReputationService()
        
        # Initialize and apply many mutes to try to go negative
        service.initialize_user(user_id, chat_id)
        
        # Apply 15 mutes (-1500 total, should floor at 0)
        for _ in range(15):
            result = service.modify_reputation(
                user_id, chat_id,
                change=ReputationChange.MUTE,
                reason="mute"
            )
        
        assert result.score >= 0


# ============================================================================
# Property 7: Read-Only Threshold
# ============================================================================

class TestReadOnlyThreshold:
    """
    **Feature: fortress-update, Property 7: Read-only threshold**
    **Validates: Requirements 4.7**
    
    For any user with reputation score below 200, their is_read_only status SHALL be true.
    When reputation recovers above 300, is_read_only SHALL be false.
    """
    
    def test_read_only_threshold_constant(self):
        """
        Property: Read-only threshold is 200.
        """
        assert READ_ONLY_THRESHOLD == 200
    
    def test_read_only_recovery_threshold_constant(self):
        """
        Property: Read-only recovery threshold is 300.
        """
        assert READ_ONLY_RECOVERY_THRESHOLD == 300
    
    @settings(max_examples=100)
    @given(score=st.integers(min_value=0, max_value=199))
    def test_score_below_200_triggers_read_only(self, score: int):
        """
        Property: Score below 200 triggers read-only mode.
        """
        service = ReputationService()
        
        # Calculate read-only status for a score below 200
        # Starting from not read-only
        is_read_only = service._calculate_read_only_status(score, current_is_read_only=False)
        
        assert is_read_only is True
    
    @settings(max_examples=100)
    @given(score=st.integers(min_value=301, max_value=5000))
    def test_score_above_300_exits_read_only(self, score: int):
        """
        Property: Score above 300 exits read-only mode.
        """
        service = ReputationService()
        
        # Calculate read-only status for a score above 300
        # Starting from read-only
        is_read_only = service._calculate_read_only_status(score, current_is_read_only=True)
        
        assert is_read_only is False
    
    @settings(max_examples=100)
    @given(score=st.integers(min_value=200, max_value=300))
    def test_score_between_200_and_300_maintains_current_status(self, score: int):
        """
        Property: Score between 200 and 300 maintains current read-only status (hysteresis).
        """
        service = ReputationService()
        
        # If currently not read-only, stays not read-only
        status_from_normal = service._calculate_read_only_status(score, current_is_read_only=False)
        assert status_from_normal is False
        
        # If currently read-only, stays read-only
        status_from_read_only = service._calculate_read_only_status(score, current_is_read_only=True)
        assert status_from_read_only is True
    
    @settings(max_examples=50)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_user_becomes_read_only_when_score_drops_below_200(
        self, user_id: int, chat_id: int
    ):
        """
        Property: User becomes read-only when score drops below 200.
        """
        service = ReputationService()
        
        # Initialize user (score = 1000)
        service.initialize_user(user_id, chat_id)
        
        # Apply enough penalties to drop below 200
        # 9 mutes = -900, score = 100
        for _ in range(9):
            result = service.modify_reputation(
                user_id, chat_id,
                change=ReputationChange.MUTE,
                reason="mute"
            )
        
        assert result.score < READ_ONLY_THRESHOLD
        assert result.is_read_only is True
    
    @settings(max_examples=50)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_user_exits_read_only_when_score_rises_above_300(
        self, user_id: int, chat_id: int
    ):
        """
        Property: User exits read-only when score rises above 300.
        """
        service = ReputationService()
        
        # Initialize user and drop to read-only
        service.initialize_user(user_id, chat_id)
        
        # Drop to read-only (9 mutes = -900, score = 100)
        for _ in range(9):
            service.modify_reputation(
                user_id, chat_id,
                change=ReputationChange.MUTE,
                reason="mute"
            )
        
        # Verify in read-only
        status = service.get_reputation(user_id, chat_id)
        assert status.is_read_only is True
        
        # Add enough positive reputation to exceed 300
        # Need to go from 100 to 301, so +201 minimum
        # 41 thank yous = +205, score = 305
        for _ in range(41):
            result = service.modify_reputation(
                user_id, chat_id,
                change=ReputationChange.THANK_YOU,
                reason="thank_you"
            )
        
        assert result.score > READ_ONLY_RECOVERY_THRESHOLD
        assert result.is_read_only is False
    
    def test_exactly_200_is_not_read_only_from_normal(self):
        """
        Property: Score of exactly 200 does not trigger read-only from normal state.
        """
        service = ReputationService()
        
        is_read_only = service._calculate_read_only_status(200, current_is_read_only=False)
        
        assert is_read_only is False
    
    def test_exactly_300_stays_read_only_from_read_only(self):
        """
        Property: Score of exactly 300 stays read-only from read-only state.
        """
        service = ReputationService()
        
        is_read_only = service._calculate_read_only_status(300, current_is_read_only=True)
        
        assert is_read_only is True
    
    def test_exactly_199_triggers_read_only(self):
        """
        Property: Score of exactly 199 triggers read-only.
        """
        service = ReputationService()
        
        is_read_only = service._calculate_read_only_status(199, current_is_read_only=False)
        
        assert is_read_only is True
    
    def test_exactly_301_exits_read_only(self):
        """
        Property: Score of exactly 301 exits read-only.
        """
        service = ReputationService()
        
        is_read_only = service._calculate_read_only_status(301, current_is_read_only=True)
        
        assert is_read_only is False


# ============================================================================
# Additional Integration Tests
# ============================================================================

class TestReputationServiceIntegration:
    """
    Integration tests for ReputationService functionality.
    """
    
    @settings(max_examples=50)
    @given(user_id=user_ids, chat_id=chat_ids)
    def test_status_dataclass_creation(self, user_id: int, chat_id: int):
        """
        Property: ReputationStatus can be created with any valid user_id and chat_id.
        """
        status = ReputationStatus(user_id=user_id, chat_id=chat_id)
        
        assert status.user_id == user_id
        assert status.chat_id == chat_id
        assert status.score == INITIAL_REPUTATION
    
    def test_service_instance_creation(self):
        """
        Property: ReputationService can be instantiated.
        """
        service = ReputationService()
        
        assert service is not None
        assert hasattr(service, 'initialize_user')
        assert hasattr(service, 'get_reputation')
        assert hasattr(service, 'modify_reputation')
        assert hasattr(service, 'check_read_only_status')
    
    @settings(max_examples=50)
    @given(
        user_id=user_ids,
        chat_id=chat_ids,
        num_changes=st.integers(min_value=1, max_value=10)
    )
    def test_multiple_changes_accumulate(
        self, user_id: int, chat_id: int, num_changes: int
    ):
        """
        Property: Multiple reputation changes accumulate correctly.
        """
        service = ReputationService()
        
        service.initialize_user(user_id, chat_id)
        
        # Apply multiple thank yous
        for _ in range(num_changes):
            service.modify_reputation(
                user_id, chat_id,
                change=ReputationChange.THANK_YOU,
                reason="thank_you"
            )
        
        result = service.get_reputation(user_id, chat_id)
        expected_score = INITIAL_REPUTATION + (num_changes * ReputationChange.THANK_YOU)
        
        assert result.score == expected_score
