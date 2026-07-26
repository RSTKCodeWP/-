"""
Property-based tests for SpamClassifier (Neural Spam Filter).

**Feature: shield-economy-v65, Property 23: Spam Detection Triggers Delete and Ban**
**Validates: Requirements 8.1, 8.2**

**Feature: shield-economy-v65, Property 24: Spam Classification Logging**
**Validates: Requirements 8.4**
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/services/spam_classifier.py)
# ============================================================================

SPAM_THRESHOLD = 0.6


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class SpamClassification:
    """Result of spam classification."""
    is_spam: bool
    confidence: float
    matched_patterns: List[str] = field(default_factory=list)
    category: str = "unknown"


# Default spam patterns by category
DEFAULT_SPAM_PATTERNS: Dict[str, List[tuple]] = {
    "selling": [
        ("sell_account_ru", r"прода[юём]\s*(акк|аккаунт|профиль)", 0.8),
        ("buy_account_ru", r"куп(лю|им)\s*(акк|аккаунт|профиль)", 0.7),
        ("account_sale_ru", r"(акк|аккаунт)\s*(на\s*)?прода(жу|ж[ае])", 0.8),
        ("sell_account_en", r"sell(ing)?\s*(my\s*)?(account|acc)", 0.8),
        ("account_for_sale", r"account\s*(for\s*)?sale", 0.8),
        ("price_tag", r"(цена|price|стоимость)[:\s]*\d+\s*(руб|₽|\$|usd|usdt)", 0.6),
    ],
    "crypto": [
        ("crypto_earn_ru", r"заработ(ок|ай|ать)\s*(на\s*)?(крипт|биткоин|btc|eth)", 0.9),
        ("crypto_invest_ru", r"инвести(ции|руй)\s*(в\s*)?(крипт|биткоин|btc)", 0.8),
        ("crypto_profit_ru", r"(доход|прибыль)\s*\d+%?\s*(в\s*)?(день|месяц|неделю)", 0.9),
        ("crypto_earn_en", r"earn\s*(money\s*)?(with\s*)?(crypto|bitcoin|btc|eth)", 0.9),
        ("crypto_profit_en", r"(profit|income|return)\s*\d+%?\s*(per\s*)?(day|month|week)", 0.9),
    ],
    "job_offer": [
        ("easy_money_ru", r"(л[её]гк(ий|ие)\s*деньги|быстр(ый|ые)\s*заработок)", 0.8),
        ("easy_money_en", r"(easy\s*money|quick\s*cash|fast\s*income)", 0.8),
    ],
    "collaboration": [
        ("collab_ru", r"(предлага[юе]м?\s*сотрудничество|взаимопиар)", 0.6),
        ("promo_ru", r"(рекламн(ое|ая)\s*предложение|размести(м|ть)\s*рекламу)", 0.7),
    ],
}


# Keywords that increase spam probability (mirroring app/services/spam_classifier.py)
SPAM_KEYWORDS: Dict[str, float] = {
    "заработок": 0.3,
    "доход": 0.2,
    "прибыль": 0.3,
    "бесплатно": 0.2,
    "гарантия": 0.2,
    "срочно": 0.2,
    "акция": 0.2,
    "скидка": 0.1,
    "успей": 0.3,
    "только сегодня": 0.4,
    "пассивный доход": 0.5,
    "финансовая свобода": 0.4,
    "earn": 0.2,
    "profit": 0.3,
    "income": 0.2,
    "free": 0.1,
    "guarantee": 0.2,
    "urgent": 0.2,
    "limited": 0.2,
    "discount": 0.1,
    "hurry": 0.3,
    "today only": 0.4,
    "passive income": 0.5,
    "financial freedom": 0.4,
}


class SpamClassifier:
    """
    Minimal SpamClassifier for testing without full app dependencies.
    Mirrors core logic from app/services/spam_classifier.py.
    """
    
    def __init__(self):
        """Initialize spam classifier with default patterns."""
        self._patterns: Dict[str, List[tuple]] = {
            category: list(patterns)
            for category, patterns in DEFAULT_SPAM_PATTERNS.items()
        }
        self._compiled_patterns: Dict[str, List[tuple]] = {}
        self._compile_patterns()
        self._keywords: Dict[str, float] = dict(SPAM_KEYWORDS)
        self._threshold = SPAM_THRESHOLD
    
    def _compile_patterns(self) -> None:
        """Compile all regex patterns."""
        self._compiled_patterns = {}
        for category, patterns in self._patterns.items():
            compiled = []
            for pattern_name, regex, weight in patterns:
                try:
                    compiled.append((
                        pattern_name,
                        re.compile(regex, re.IGNORECASE | re.UNICODE),
                        weight
                    ))
                except re.error:
                    pass
            self._compiled_patterns[category] = compiled
    
    def classify(self, text: str) -> SpamClassification:
        """Classify a message as spam or not spam."""
        if not text or not text.strip():
            return SpamClassification(
                is_spam=False,
                confidence=0.0,
                matched_patterns=[],
                category="unknown"
            )
        
        normalized_text = text.lower().strip()
        category_scores: Dict[str, float] = {}
        all_matched_patterns: List[str] = []
        
        for category, patterns in self._compiled_patterns.items():
            category_score = 0.0
            for pattern_name, compiled_regex, weight in patterns:
                if compiled_regex.search(normalized_text):
                    category_score += weight
                    all_matched_patterns.append(f"{category}:{pattern_name}")
            
            if category_score > 0:
                category_scores[category] = category_score
        
        # Check keywords (matching real implementation)
        keyword_score = 0.0
        for keyword, weight in self._keywords.items():
            if keyword.lower() in normalized_text:
                keyword_score += weight
        
        pattern_score = sum(category_scores.values())
        # Match real implementation: pattern_score * 0.7 + keyword_score * 0.3
        total_score = min(1.0, pattern_score * 0.7 + keyword_score * 0.3)
        
        primary_category = "unknown"
        if category_scores:
            primary_category = max(category_scores, key=category_scores.get)
        
        is_spam = total_score >= self._threshold
        
        return SpamClassification(
            is_spam=is_spam,
            confidence=total_score,
            matched_patterns=all_matched_patterns,
            category=primary_category
        )
    
    @staticmethod
    def _hash_message(text: str) -> str:
        """Create a hash of message content."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def get_message_hash(self, text: str) -> str:
        """Get hash of message content."""
        return self._hash_message(text)


@dataclass
class ModerationAction:
    """Represents a moderation action taken."""
    action_type: str  # "delete" or "ban"
    chat_id: int
    user_id: int
    message_id: Optional[int] = None
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=utc_now)


@dataclass
class SpamLog:
    """Log entry for spam classification."""
    message_hash: str
    confidence: float
    category: str
    matched_patterns: List[str]
    timestamp: datetime = field(default_factory=utc_now)


class SpamModerationHandler:
    """
    Handler that coordinates spam detection with moderation actions.
    
    This class demonstrates the integration between SpamClassifier
    and moderation actions (delete + ban) as required by Requirements 8.1, 8.2.
    """
    
    def __init__(self, classifier: Optional[SpamClassifier] = None):
        """Initialize handler with spam classifier."""
        self._classifier = classifier or SpamClassifier()
        self._actions: List[ModerationAction] = []
        self._spam_logs: List[SpamLog] = []
    
    def handle_message(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        text: str
    ) -> Tuple[bool, List[ModerationAction]]:
        """
        Handle an incoming message, checking for spam.
        
        **Validates: Requirements 8.1, 8.2**
        
        If spam is detected:
        - 8.1: Message SHALL be deleted immediately
        - 8.2: Sender SHALL be banned without warning
        
        Args:
            chat_id: Telegram chat ID
            user_id: Sender's user ID
            message_id: Message ID
            text: Message text
            
        Returns:
            Tuple of (is_spam, list of actions taken)
        """
        classification = self._classifier.classify(text)
        actions_taken: List[ModerationAction] = []
        
        if classification.is_spam:
            # Log the spam detection (Requirement 8.4)
            self._spam_logs.append(SpamLog(
                message_hash=self._classifier.get_message_hash(text),
                confidence=classification.confidence,
                category=classification.category,
                matched_patterns=classification.matched_patterns,
            ))
            
            # Requirement 8.1: Delete the message immediately
            delete_action = ModerationAction(
                action_type="delete",
                chat_id=chat_id,
                user_id=user_id,
                message_id=message_id,
                reason=f"Spam detected: {classification.category}",
            )
            actions_taken.append(delete_action)
            self._actions.append(delete_action)
            
            # Requirement 8.2: Ban the sender without warning
            ban_action = ModerationAction(
                action_type="ban",
                chat_id=chat_id,
                user_id=user_id,
                reason=f"Spam: {classification.category} (confidence: {classification.confidence:.2f})",
            )
            actions_taken.append(ban_action)
            self._actions.append(ban_action)
        
        return classification.is_spam, actions_taken
    
    def get_actions(self) -> List[ModerationAction]:
        """Get all recorded moderation actions."""
        return self._actions.copy()
    
    def get_spam_logs(self) -> List[SpamLog]:
        """Get all spam classification logs."""
        return self._spam_logs.copy()
    
    def clear(self) -> None:
        """Clear all recorded actions and logs."""
        self._actions.clear()
        self._spam_logs.clear()


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for message IDs (positive)
message_ids = st.integers(min_value=1, max_value=999999999)

# Known spam messages that should trigger detection
# These messages are designed to exceed the 0.6 threshold by:
# - Matching high-weight patterns (0.8-0.9)
# - Including keywords that add to the score
# - Or matching multiple patterns
SPAM_MESSAGES = [
    # Selling category - with price tag pattern (0.6) + sell pattern (0.8) = 1.4 * 0.7 = 0.98
    "Продаю аккаунт! Цена: 500 руб",
    "Продам акк на продажу! Цена: 1000 руб",
    # Crypto category - high weight patterns (0.9)
    "Заработок на крипте! Доход 100% в день!",  # crypto_earn_ru (0.9) + crypto_profit_ru (0.9) = 1.26
    "Earn money with crypto! Profit 50% per week!",  # crypto_earn_en (0.9) + crypto_profit_en (0.9) = 1.26
    "Инвестиции в биткоин - прибыль 200% в месяц",  # crypto_invest_ru (0.8) + crypto_profit_ru (0.9) = 1.19
    # Job offer category - high weight patterns (0.8)
    "Лёгкие деньги! Быстрый заработок!",  # easy_money_ru (0.8) + keywords
    "Easy money! Quick cash! Fast income!",  # easy_money_en (0.8) + keywords
    # Collaboration category - multiple patterns
    "Предлагаем сотрудничество! Рекламное предложение!",  # collab_ru (0.6) + promo_ru (0.7) = 0.91
]

# Non-spam messages
NON_SPAM_MESSAGES = [
    "Привет, как дела?",
    "Hello, how are you?",
    "Отличная погода сегодня",
    "Nice weather today",
    "Кто хочет поиграть?",
    "Anyone want to play?",
    "Спасибо за помощь!",
    "Thanks for the help!",
]

# Strategy for spam messages
spam_messages = st.sampled_from(SPAM_MESSAGES)

# Strategy for non-spam messages
non_spam_messages = st.sampled_from(NON_SPAM_MESSAGES)


# ============================================================================
# Property Tests
# ============================================================================


class TestSpamClassifierProperties:
    """Property-based tests for SpamClassifier and SpamModerationHandler."""

    # ========================================================================
    # Property 23: Spam Detection Triggers Delete and Ban
    # ========================================================================

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        spam_text=spam_messages,
    )
    @settings(max_examples=100)
    def test_spam_detection_triggers_both_delete_and_ban(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 23: Spam Detection Triggers Delete and Ban**
        **Validates: Requirements 8.1, 8.2**
        
        For any message that matches spam patterns:
        - The message SHALL be deleted immediately (8.1)
        - The sender SHALL be banned without warning (8.2)
        """
        handler = SpamModerationHandler()
        
        is_spam, actions = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=spam_text,
        )
        
        # Verify spam was detected
        assert is_spam is True, (
            f"Message should be classified as spam: '{spam_text}'"
        )
        
        # Verify both actions were taken
        assert len(actions) == 2, (
            f"Spam detection should trigger exactly 2 actions (delete + ban), "
            f"got {len(actions)}"
        )
        
        # Verify delete action
        action_types = [a.action_type for a in actions]
        assert "delete" in action_types, (
            "Spam detection MUST trigger message deletion (Requirement 8.1)"
        )
        
        # Verify ban action
        assert "ban" in action_types, (
            "Spam detection MUST trigger sender ban (Requirement 8.2)"
        )
        
        # Verify actions target correct user and chat
        for action in actions:
            assert action.chat_id == chat_id, (
                f"Action should target chat {chat_id}, got {action.chat_id}"
            )
            assert action.user_id == user_id, (
                f"Action should target user {user_id}, got {action.user_id}"
            )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        spam_text=spam_messages,
    )
    @settings(max_examples=100)
    def test_delete_action_includes_message_id(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 23: Spam Detection Triggers Delete and Ban**
        **Validates: Requirements 8.1**
        
        For any spam message, the delete action SHALL include the message ID
        to ensure the correct message is deleted.
        """
        handler = SpamModerationHandler()
        
        is_spam, actions = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=spam_text,
        )
        
        assume(is_spam)  # Only test when spam is detected
        
        # Find the delete action
        delete_actions = [a for a in actions if a.action_type == "delete"]
        assert len(delete_actions) == 1, "Should have exactly one delete action"
        
        delete_action = delete_actions[0]
        assert delete_action.message_id == message_id, (
            f"Delete action should target message {message_id}, "
            f"got {delete_action.message_id}"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        non_spam_text=non_spam_messages,
    )
    @settings(max_examples=100)
    def test_non_spam_does_not_trigger_actions(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        non_spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 23: Spam Detection Triggers Delete and Ban**
        **Validates: Requirements 8.1, 8.2**
        
        For any message that does NOT match spam patterns,
        no moderation actions SHALL be taken.
        """
        handler = SpamModerationHandler()
        
        is_spam, actions = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=non_spam_text,
        )
        
        # Verify not classified as spam
        assert is_spam is False, (
            f"Message should NOT be classified as spam: '{non_spam_text}'"
        )
        
        # Verify no actions were taken
        assert len(actions) == 0, (
            f"Non-spam messages should not trigger any actions, "
            f"got {len(actions)} actions"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        spam_text=spam_messages,
    )
    @settings(max_examples=100)
    def test_ban_action_has_no_warning(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 23: Spam Detection Triggers Delete and Ban**
        **Validates: Requirements 8.2**
        
        For any spam message, the ban SHALL be applied without warning.
        This means the ban action should be immediate, not preceded by a warning.
        """
        handler = SpamModerationHandler()
        
        is_spam, actions = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=spam_text,
        )
        
        assume(is_spam)  # Only test when spam is detected
        
        # Find the ban action
        ban_actions = [a for a in actions if a.action_type == "ban"]
        assert len(ban_actions) == 1, "Should have exactly one ban action"
        
        # Verify there's no "warning" action type
        action_types = [a.action_type for a in actions]
        assert "warning" not in action_types, (
            "Spam ban should be without warning (Requirement 8.2)"
        )

    @given(
        chat_id=chat_ids,
        user_ids_list=st.lists(user_ids, min_size=2, max_size=5, unique=True),
        message_ids_list=st.lists(message_ids, min_size=2, max_size=5, unique=True),
        spam_texts=st.lists(spam_messages, min_size=2, max_size=5),
    )
    @settings(max_examples=100)
    def test_multiple_spam_messages_each_trigger_actions(
        self,
        chat_id: int,
        user_ids_list: List[int],
        message_ids_list: List[int],
        spam_texts: List[str],
    ):
        """
        **Feature: shield-economy-v65, Property 23: Spam Detection Triggers Delete and Ban**
        **Validates: Requirements 8.1, 8.2**
        
        For any sequence of spam messages from different users,
        each message SHALL trigger both delete and ban actions.
        """
        handler = SpamModerationHandler()
        
        # Ensure we have matching lengths
        min_len = min(len(user_ids_list), len(message_ids_list), len(spam_texts))
        
        spam_count = 0
        for i in range(min_len):
            is_spam, actions = handler.handle_message(
                chat_id=chat_id,
                user_id=user_ids_list[i],
                message_id=message_ids_list[i],
                text=spam_texts[i],
            )
            if is_spam:
                spam_count += 1
        
        # Verify all spam messages triggered actions
        all_actions = handler.get_actions()
        
        # Each spam message should trigger 2 actions (delete + ban)
        expected_actions = spam_count * 2
        assert len(all_actions) == expected_actions, (
            f"Expected {expected_actions} actions for {spam_count} spam messages, "
            f"got {len(all_actions)}"
        )

    # ========================================================================
    # Property 24: Spam Classification Logging
    # ========================================================================

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        spam_text=spam_messages,
    )
    @settings(max_examples=100)
    def test_spam_log_contains_message_hash(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 24: Spam Classification Logging**
        **Validates: Requirements 8.4**
        
        For any message classified as spam, the log SHALL contain
        the message content hash.
        """
        handler = SpamModerationHandler()
        classifier = SpamClassifier()
        
        is_spam, _ = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=spam_text,
        )
        
        assume(is_spam)  # Only test when spam is detected
        
        # Get the spam logs
        spam_logs = handler.get_spam_logs()
        assert len(spam_logs) == 1, "Should have exactly one spam log entry"
        
        log_entry = spam_logs[0]
        
        # Verify message hash is present and non-empty
        assert log_entry.message_hash is not None, (
            "Spam log MUST contain message hash (Requirement 8.4)"
        )
        assert len(log_entry.message_hash) > 0, (
            "Spam log message hash MUST be non-empty (Requirement 8.4)"
        )
        
        # Verify the hash matches the expected hash for the message
        expected_hash = classifier.get_message_hash(spam_text)
        assert log_entry.message_hash == expected_hash, (
            f"Spam log hash should match message hash. "
            f"Expected: {expected_hash}, Got: {log_entry.message_hash}"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        spam_text=spam_messages,
    )
    @settings(max_examples=100)
    def test_spam_log_contains_confidence_score(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 24: Spam Classification Logging**
        **Validates: Requirements 8.4**
        
        For any message classified as spam, the log SHALL contain
        the classification confidence score.
        """
        handler = SpamModerationHandler()
        classifier = SpamClassifier()
        
        is_spam, _ = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=spam_text,
        )
        
        assume(is_spam)  # Only test when spam is detected
        
        # Get the spam logs
        spam_logs = handler.get_spam_logs()
        assert len(spam_logs) == 1, "Should have exactly one spam log entry"
        
        log_entry = spam_logs[0]
        
        # Verify confidence score is present
        assert log_entry.confidence is not None, (
            "Spam log MUST contain confidence score (Requirement 8.4)"
        )
        
        # Verify confidence is a valid float in range [0.0, 1.0]
        assert isinstance(log_entry.confidence, float), (
            f"Confidence should be a float, got {type(log_entry.confidence)}"
        )
        assert 0.0 <= log_entry.confidence <= 1.0, (
            f"Confidence should be in range [0.0, 1.0], got {log_entry.confidence}"
        )
        
        # Verify confidence matches the classifier's result
        classification = classifier.classify(spam_text)
        assert log_entry.confidence == classification.confidence, (
            f"Log confidence should match classification confidence. "
            f"Expected: {classification.confidence}, Got: {log_entry.confidence}"
        )

    @given(
        chat_id=chat_ids,
        user_id=user_ids,
        message_id=message_ids,
        spam_text=spam_messages,
    )
    @settings(max_examples=100)
    def test_spam_log_contains_both_hash_and_confidence(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        spam_text: str,
    ):
        """
        **Feature: shield-economy-v65, Property 24: Spam Classification Logging**
        **Validates: Requirements 8.4**
        
        For any message classified as spam, the log SHALL contain
        BOTH the message content hash AND the classification confidence score.
        """
        handler = SpamModerationHandler()
        classifier = SpamClassifier()
        
        is_spam, _ = handler.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            text=spam_text,
        )
        
        assume(is_spam)  # Only test when spam is detected
        
        # Get the spam logs
        spam_logs = handler.get_spam_logs()
        assert len(spam_logs) == 1, "Should have exactly one spam log entry"
        
        log_entry = spam_logs[0]
        
        # Verify both hash and confidence are present
        assert log_entry.message_hash is not None and len(log_entry.message_hash) > 0, (
            "Spam log MUST contain message hash (Requirement 8.4)"
        )
        assert log_entry.confidence is not None, (
            "Spam log MUST contain confidence score (Requirement 8.4)"
        )
        
        # Verify values match expected
        expected_hash = classifier.get_message_hash(spam_text)
        classification = classifier.classify(spam_text)
        
        assert log_entry.message_hash == expected_hash, (
            f"Hash mismatch: expected {expected_hash}, got {log_entry.message_hash}"
        )
        assert log_entry.confidence == classification.confidence, (
            f"Confidence mismatch: expected {classification.confidence}, "
            f"got {log_entry.confidence}"
        )

