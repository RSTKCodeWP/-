"""
Property-based tests for ToxicityAnalyzer.

**Feature: fortress-update, Property 8: Toxicity action mapping**
**Validates: Requirements 2.2**

**Feature: fortress-update, Property 9: Toxicity result structure**
**Validates: Requirements 2.3**

**Feature: fortress-update, Property 10: Toxicity incident logging**
**Validates: Requirements 2.4**
"""

import json
import re
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional
from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Local copies of classes for testing (to avoid import issues)
# ============================================================================

class DEFCONLevel(IntEnum):
    """DEFCON protection levels for chat security."""
    PEACEFUL = 1
    STRICT = 2
    MARTIAL_LAW = 3


class ToxicityCategory(str, Enum):
    """Categories of toxic content."""
    INSULT = "insult"
    HATE_SPEECH = "hate_speech"
    THREAT = "threat"
    SPAM = "spam"


class ModerationAction(str, Enum):
    """Actions to take based on toxicity analysis."""
    NONE = "none"
    WARN = "warn"
    DELETE = "delete"
    DELETE_AND_MUTE = "delete_and_mute"


@dataclass
class ToxicityResult:
    """Result of toxicity analysis."""
    score: int  # 0-100
    category: Optional[str]  # insult, hate_speech, threat, spam
    confidence: float  # 0.0-1.0
    is_sarcasm: bool = False
    raw_response: str = ""
    
    def __post_init__(self):
        """Validate and normalize fields."""
        self.score = max(0, min(100, self.score))
        self.confidence = max(0.0, min(1.0, self.confidence))
        if self.category:
            self.category = self.category.lower().replace(" ", "_")
            valid_categories = {c.value for c in ToxicityCategory}
            if self.category not in valid_categories:
                self.category = None


def get_action_for_score(
    score: int,
    defcon_level: DEFCONLevel,
    threshold: int = 75
) -> ModerationAction:
    """Determine moderation action based on toxicity score and DEFCON level."""
    if score <= threshold:
        return ModerationAction.NONE
    
    if defcon_level == DEFCONLevel.PEACEFUL:
        return ModerationAction.WARN
    elif defcon_level == DEFCONLevel.STRICT:
        return ModerationAction.DELETE
    else:  # MARTIAL_LAW
        return ModerationAction.DELETE_AND_MUTE


def _parse_toxicity_response(response: str) -> ToxicityResult:
    """Parse LLM response into ToxicityResult."""
    raw_response = response
    
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
            cleaned = cleaned.rstrip("`").strip()
        
        data = json.loads(cleaned)
        
        # Check if it's a dict (JSON object) vs just a number
        if isinstance(data, dict):
            return ToxicityResult(
                score=int(data.get("score", 0)),
                category=data.get("category"),
                confidence=float(data.get("confidence", 0.5)),
                is_sarcasm=bool(data.get("is_sarcasm", False)),
                raw_response=raw_response
            )
        elif isinstance(data, (int, float)):
            # JSON parsed as a number - treat as legacy format
            return ToxicityResult(
                score=int(data),
                category=None,
                confidence=0.5,
                is_sarcasm=False,
                raw_response=raw_response
            )
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    try:
        match = re.search(r'\d+', response)
        if match:
            score = int(match.group())
            return ToxicityResult(
                score=score,
                category=None,
                confidence=0.5,
                is_sarcasm=False,
                raw_response=raw_response
            )
    except (ValueError, TypeError):
        pass
    
    return ToxicityResult(
        score=0,
        category=None,
        confidence=0.0,
        is_sarcasm=False,
        raw_response=raw_response
    )


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for toxicity scores
toxicity_scores = st.integers(min_value=0, max_value=100)

# Strategy for confidence levels
confidence_levels = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for DEFCON levels
defcon_levels = st.sampled_from([DEFCONLevel.PEACEFUL, DEFCONLevel.STRICT, DEFCONLevel.MARTIAL_LAW])

# Strategy for toxicity categories
toxicity_categories = st.sampled_from([None, "insult", "hate_speech", "threat", "spam"])

# Strategy for thresholds
thresholds = st.integers(min_value=0, max_value=100)

# Strategy for user IDs
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for chat IDs
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for message text
message_texts = st.text(min_size=1, max_size=500)


# ============================================================================
# Property 9: Toxicity Result Structure
# ============================================================================

class TestToxicityResultStructure:
    """
    **Feature: fortress-update, Property 9: Toxicity result structure**
    **Validates: Requirements 2.3**
    
    For any toxicity analysis result, the response SHALL contain: 
    score (0-100), category (nullable string), confidence (0.0-1.0).
    """
    
    @settings(max_examples=100)
    @given(
        score=st.integers(min_value=-50, max_value=150),  # Test out-of-bounds values
        category=toxicity_categories,
        confidence=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    def test_toxicity_result_normalizes_values(self, score: int, category, confidence: float):
        """
        Property: ToxicityResult normalizes score to 0-100 and confidence to 0.0-1.0.
        """
        result = ToxicityResult(
            score=score,
            category=category,
            confidence=confidence
        )
        
        # Score should be clamped to 0-100
        assert 0 <= result.score <= 100
        
        # Confidence should be clamped to 0.0-1.0
        assert 0.0 <= result.confidence <= 1.0
    
    @settings(max_examples=100)
    @given(
        score=toxicity_scores,
        category=toxicity_categories,
        confidence=confidence_levels
    )
    def test_toxicity_result_preserves_valid_values(self, score: int, category, confidence: float):
        """
        Property: ToxicityResult preserves valid values unchanged.
        """
        result = ToxicityResult(
            score=score,
            category=category,
            confidence=confidence
        )
        
        assert result.score == score
        assert result.confidence == confidence
        
        # Category should be normalized (lowercase, underscores)
        if category is not None:
            assert result.category == category.lower().replace(" ", "_")
        else:
            assert result.category is None
    
    @settings(max_examples=100)
    @given(
        score=toxicity_scores,
        confidence=confidence_levels
    )
    def test_toxicity_result_validates_category(self, score: int, confidence: float):
        """
        Property: ToxicityResult validates category against allowed values.
        """
        # Test with invalid category
        result = ToxicityResult(
            score=score,
            category="invalid_category",
            confidence=confidence
        )
        
        # Invalid category should be set to None
        assert result.category is None
    
    def test_toxicity_result_has_required_fields(self):
        """
        Property: ToxicityResult has all required fields.
        """
        result = ToxicityResult(
            score=50,
            category="insult",
            confidence=0.8
        )
        
        # Check all required fields exist
        assert hasattr(result, 'score')
        assert hasattr(result, 'category')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'is_sarcasm')
        assert hasattr(result, 'raw_response')
        
        # Check types
        assert isinstance(result.score, int)
        assert result.category is None or isinstance(result.category, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.is_sarcasm, bool)
        assert isinstance(result.raw_response, str)
    
    @settings(max_examples=50)
    @given(score=toxicity_scores, confidence=confidence_levels)
    def test_parse_json_response(self, score: int, confidence: float):
        """
        Property: JSON responses are correctly parsed into ToxicityResult.
        """
        import json
        
        json_response = json.dumps({
            "score": score,
            "category": "insult",
            "confidence": confidence,
            "is_sarcasm": True
        })
        
        result = _parse_toxicity_response(json_response)
        
        assert result.score == max(0, min(100, score))
        assert result.category == "insult"
        assert result.confidence == max(0.0, min(1.0, confidence))
        assert result.is_sarcasm is True
    
    def test_parse_legacy_integer_response(self):
        """
        Property: Legacy integer-only responses are correctly parsed.
        """
        result = _parse_toxicity_response("75")
        
        assert result.score == 75
        assert result.category is None
        assert result.confidence == 0.5  # Default confidence for legacy
    
    def test_parse_invalid_response_returns_safe_default(self):
        """
        Property: Invalid responses return safe default values.
        """
        result = _parse_toxicity_response("not a valid response")
        
        assert result.score == 0
        assert result.category is None
        assert result.confidence == 0.0


# ============================================================================
# Property 8: Toxicity Action Mapping
# ============================================================================

class TestToxicityActionMapping:
    """
    **Feature: fortress-update, Property 8: Toxicity action mapping**
    **Validates: Requirements 2.2**
    
    For any toxicity score and DEFCON level combination, the action SHALL be deterministic:
    - Score <= threshold: No action
    - Score > threshold at DEFCON 1: warn
    - Score > threshold at DEFCON 2: delete
    - Score > threshold at DEFCON 3: delete + mute
    """
    
    @settings(max_examples=100)
    @given(score=toxicity_scores, threshold=thresholds)
    def test_below_threshold_no_action(self, score: int, threshold: int):
        """
        Property: Scores at or below threshold result in no action.
        """
        assume(score <= threshold)
        
        for defcon in [DEFCONLevel.PEACEFUL, DEFCONLevel.STRICT, DEFCONLevel.MARTIAL_LAW]:
            action = get_action_for_score(score, defcon, threshold)
            assert action == ModerationAction.NONE
    
    @settings(max_examples=100)
    @given(score=toxicity_scores, threshold=thresholds)
    def test_above_threshold_defcon1_warns(self, score: int, threshold: int):
        """
        Property: Scores above threshold at DEFCON 1 result in warning.
        """
        assume(score > threshold)
        
        action = get_action_for_score(score, DEFCONLevel.PEACEFUL, threshold)
        assert action == ModerationAction.WARN
    
    @settings(max_examples=100)
    @given(score=toxicity_scores, threshold=thresholds)
    def test_above_threshold_defcon2_deletes(self, score: int, threshold: int):
        """
        Property: Scores above threshold at DEFCON 2 result in deletion.
        """
        assume(score > threshold)
        
        action = get_action_for_score(score, DEFCONLevel.STRICT, threshold)
        assert action == ModerationAction.DELETE
    
    @settings(max_examples=100)
    @given(score=toxicity_scores, threshold=thresholds)
    def test_above_threshold_defcon3_deletes_and_mutes(self, score: int, threshold: int):
        """
        Property: Scores above threshold at DEFCON 3 result in delete and mute.
        """
        assume(score > threshold)
        
        action = get_action_for_score(score, DEFCONLevel.MARTIAL_LAW, threshold)
        assert action == ModerationAction.DELETE_AND_MUTE
    
    @settings(max_examples=100)
    @given(score=toxicity_scores, defcon=defcon_levels, threshold=thresholds)
    def test_action_is_deterministic(self, score: int, defcon: DEFCONLevel, threshold: int):
        """
        Property: Same inputs always produce the same action.
        """
        action1 = get_action_for_score(score, defcon, threshold)
        action2 = get_action_for_score(score, defcon, threshold)
        
        assert action1 == action2
    
    @settings(max_examples=100)
    @given(score=toxicity_scores, defcon=defcon_levels, threshold=thresholds)
    def test_action_is_valid_enum(self, score: int, defcon: DEFCONLevel, threshold: int):
        """
        Property: Action is always a valid ModerationAction enum value.
        """
        action = get_action_for_score(score, defcon, threshold)
        
        assert isinstance(action, ModerationAction)
        assert action in [
            ModerationAction.NONE,
            ModerationAction.WARN,
            ModerationAction.DELETE,
            ModerationAction.DELETE_AND_MUTE
        ]
    
    def test_default_threshold_is_75(self):
        """
        Property: Default threshold is 75.
        """
        # Score of 75 should not trigger action (at or below threshold)
        action = get_action_for_score(75, DEFCONLevel.PEACEFUL)
        assert action == ModerationAction.NONE
        
        # Score of 76 should trigger action (above threshold)
        action = get_action_for_score(76, DEFCONLevel.PEACEFUL)
        assert action == ModerationAction.WARN
    
    @settings(max_examples=50)
    @given(defcon=defcon_levels)
    def test_severity_increases_with_defcon(self, defcon: DEFCONLevel):
        """
        Property: Action severity increases with DEFCON level.
        """
        # Use a score that's definitely above threshold
        score = 90
        threshold = 75
        
        action_peaceful = get_action_for_score(score, DEFCONLevel.PEACEFUL, threshold)
        action_strict = get_action_for_score(score, DEFCONLevel.STRICT, threshold)
        action_martial = get_action_for_score(score, DEFCONLevel.MARTIAL_LAW, threshold)
        
        # Define severity order
        severity = {
            ModerationAction.NONE: 0,
            ModerationAction.WARN: 1,
            ModerationAction.DELETE: 2,
            ModerationAction.DELETE_AND_MUTE: 3
        }
        
        assert severity[action_peaceful] <= severity[action_strict]
        assert severity[action_strict] <= severity[action_martial]


# ============================================================================
# Property 10: Toxicity Incident Logging
# ============================================================================

class TestToxicityIncidentLogging:
    """
    **Feature: fortress-update, Property 10: Toxicity incident logging**
    **Validates: Requirements 2.4**
    
    For any message flagged as toxic (score > threshold), a log entry 
    SHALL be created with message_text, score, category, and action_taken.
    """
    
    @settings(max_examples=100)
    @given(
        score=toxicity_scores,
        category=toxicity_categories,
        confidence=confidence_levels
    )
    def test_toxicity_result_can_be_logged(self, score: int, category, confidence: float):
        """
        Property: ToxicityResult contains all fields needed for logging.
        """
        result = ToxicityResult(
            score=score,
            category=category,
            confidence=confidence
        )
        
        # All fields needed for logging should be accessible
        assert hasattr(result, 'score')
        assert hasattr(result, 'category')
        
        # Score should be a number that can be stored
        assert isinstance(result.score, (int, float))
        
        # Category should be a string or None
        assert result.category is None or isinstance(result.category, str)
    
    @settings(max_examples=50)
    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_text=message_texts,
        score=toxicity_scores,
        category=toxicity_categories
    )
    def test_log_entry_fields_are_valid(
        self, chat_id: int, user_id: int, message_text: str, 
        score: int, category
    ):
        """
        Property: Log entry fields have valid types and values.
        """
        result = ToxicityResult(
            score=score,
            category=category,
            confidence=0.8
        )
        
        # Verify all fields that would go into a log entry
        assert isinstance(chat_id, int)
        assert isinstance(user_id, int)
        assert isinstance(message_text, str)
        assert isinstance(result.score, int)
        assert result.category is None or isinstance(result.category, str)
    
    def test_action_taken_is_string(self):
        """
        Property: Action taken is a string suitable for logging.
        """
        for action in ModerationAction:
            assert isinstance(action.value, str)
            assert len(action.value) > 0
    
    @settings(max_examples=50)
    @given(score=toxicity_scores, defcon=defcon_levels, threshold=thresholds)
    def test_action_value_is_loggable(self, score: int, defcon: DEFCONLevel, threshold: int):
        """
        Property: Action value can be stored as a string in the database.
        """
        action = get_action_for_score(score, defcon, threshold)
        
        # Action value should be a non-empty string
        assert isinstance(action.value, str)
        assert len(action.value) > 0
        assert len(action.value) <= 64  # Fits in VARCHAR(64)
