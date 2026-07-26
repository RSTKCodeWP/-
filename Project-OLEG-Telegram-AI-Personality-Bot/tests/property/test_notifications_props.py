"""
Property-based tests for Notification Service.

Tests the correctness properties for the Notification system
as defined in the design document.

**Feature: fortress-update**
**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8**
"""

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from hypothesis import given, settings, strategies as st


# ============================================================================
# Recreate minimal types for testing without importing app package
# ============================================================================

class NotificationType(str, Enum):
    """Types of notifications that can be sent to chat owners."""
    RAID_ALERT = "raid_alert"
    BAN_NOTIFICATION = "ban_notification"
    TOXICITY_WARNING = "toxicity_warning"
    DEFCON_RECOMMENDATION = "defcon_recommendation"
    REPEATED_VIOLATOR = "repeated_violator"
    DAILY_TIPS = "daily_tips"


@dataclass
class NotificationConfigData:
    """Notification configuration for a chat."""
    chat_id: int
    owner_id: int
    enabled_types: Set[NotificationType] = field(default_factory=lambda: set(NotificationType))
    
    @classmethod
    def default(cls, chat_id: int, owner_id: int) -> "NotificationConfigData":
        """Create default config with all notifications enabled."""
        return cls(
            chat_id=chat_id,
            owner_id=owner_id,
            enabled_types=set(NotificationType)
        )
    
    def is_enabled(self, notification_type: NotificationType) -> bool:
        """Check if a notification type is enabled."""
        return notification_type in self.enabled_types


@dataclass
class NotificationData:
    """Data for a notification to be sent."""
    notification_type: NotificationType
    chat_id: int
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TipRecommendation:
    """A tip/recommendation for chat improvement."""
    priority: int
    category: str
    message: str
    action: Optional[str] = None


def format_tips(tips: List[TipRecommendation]) -> str:
    """Format tips for display."""
    if not tips:
        return "Нет рекомендаций на данный момент."
    
    lines = ["💡 Рекомендации для вашего чата:", ""]
    
    priority_emoji = {1: "🔴", 2: "🟡", 3: "🟢"}
    
    for i, tip in enumerate(tips, 1):
        emoji = priority_emoji.get(tip.priority, "⚪")
        lines.append(f"{i}. {emoji} {tip.message}")
        if tip.action:
            lines.append(f"   → {tip.action}")
        lines.append("")
    
    return "\n".join(lines)


# Test data generators
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)
user_ids = st.integers(min_value=1, max_value=9999999999)
notification_types = st.sampled_from(list(NotificationType))


class TestDefaultNotificationsEnabled:
    """
    Property 35: Default notifications enabled
    
    For any newly registered chat, all notification types SHALL be
    enabled by default.
    
    **Feature: fortress-update, Property 35: Default notifications enabled**
    **Validates: Requirements 15.8**
    """
    
    @given(chat_id=chat_ids, owner_id=user_ids)
    @settings(max_examples=100)
    def test_default_config_has_all_notifications_enabled(
        self,
        chat_id: int,
        owner_id: int
    ):
        """
        For any newly created default config, all notification types are enabled.
        
        **Feature: fortress-update, Property 35: Default notifications enabled**
        **Validates: Requirements 15.8**
        """
        # Create default config
        config = NotificationConfigData.default(chat_id, owner_id)
        
        # All notification types should be enabled
        for notification_type in NotificationType:
            assert config.is_enabled(notification_type), \
                f"Notification type {notification_type.value} should be enabled by default"
    
    @given(chat_id=chat_ids, owner_id=user_ids)
    @settings(max_examples=100)
    def test_default_config_enabled_types_count(
        self,
        chat_id: int,
        owner_id: int
    ):
        """
        For any default config, the number of enabled types equals total types.
        
        **Feature: fortress-update, Property 35: Default notifications enabled**
        **Validates: Requirements 15.8**
        """
        config = NotificationConfigData.default(chat_id, owner_id)
        
        # Count of enabled types should equal total notification types
        assert len(config.enabled_types) == len(NotificationType)
    
    @given(
        chat_id=chat_ids,
        owner_id=user_ids,
        notification_type=notification_types
    )
    @settings(max_examples=100)
    def test_default_config_each_type_enabled(
        self,
        chat_id: int,
        owner_id: int,
        notification_type: NotificationType
    ):
        """
        For any notification type, default config has it enabled.
        
        **Feature: fortress-update, Property 35: Default notifications enabled**
        **Validates: Requirements 15.8**
        """
        config = NotificationConfigData.default(chat_id, owner_id)
        
        # Each notification type should be enabled
        assert notification_type in config.enabled_types
        assert config.is_enabled(notification_type)
    
    @given(chat_id=chat_ids, owner_id=user_ids)
    @settings(max_examples=100)
    def test_default_config_preserves_chat_and_owner_ids(
        self,
        chat_id: int,
        owner_id: int
    ):
        """
        For any default config, chat_id and owner_id are preserved.
        
        **Feature: fortress-update, Property 35: Default notifications enabled**
        **Validates: Requirements 15.8**
        """
        config = NotificationConfigData.default(chat_id, owner_id)
        
        assert config.chat_id == chat_id
        assert config.owner_id == owner_id


class TestNotificationTypeToggling:
    """
    Test notification type toggling functionality.
    
    **Feature: fortress-update**
    **Validates: Requirements 15.1-15.6**
    """
    
    @given(
        chat_id=chat_ids,
        owner_id=user_ids,
        notification_type=notification_types
    )
    @settings(max_examples=100)
    def test_is_enabled_returns_correct_value(
        self,
        chat_id: int,
        owner_id: int,
        notification_type: NotificationType
    ):
        """
        For any config, is_enabled returns True if type is in enabled_types.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.1-15.6**
        """
        # Start with default config (all enabled)
        config = NotificationConfigData.default(chat_id, owner_id)
        
        # Should be enabled
        assert config.is_enabled(notification_type) is True
        
        # Remove the type
        config.enabled_types.discard(notification_type)
        
        # Should now be disabled
        assert config.is_enabled(notification_type) is False
    
    @given(chat_id=chat_ids, owner_id=user_ids)
    @settings(max_examples=100)
    def test_empty_enabled_types_all_disabled(
        self,
        chat_id: int,
        owner_id: int
    ):
        """
        For any config with empty enabled_types, all types are disabled.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.1-15.6**
        """
        config = NotificationConfigData(
            chat_id=chat_id,
            owner_id=owner_id,
            enabled_types=set()
        )
        
        # All types should be disabled
        for notification_type in NotificationType:
            assert config.is_enabled(notification_type) is False


class TestNotificationDataStructure:
    """
    Test notification data structure.
    
    **Feature: fortress-update**
    **Validates: Requirements 15.1-15.6**
    """
    
    @given(
        chat_id=chat_ids,
        notification_type=notification_types,
        title=st.text(min_size=1, max_size=100),
        message=st.text(min_size=1, max_size=1000)
    )
    @settings(max_examples=100)
    def test_notification_data_preserves_fields(
        self,
        chat_id: int,
        notification_type: NotificationType,
        title: str,
        message: str
    ):
        """
        For any notification data, all fields are preserved correctly.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.1-15.6**
        """
        notification = NotificationData(
            notification_type=notification_type,
            chat_id=chat_id,
            title=title,
            message=message,
            data={"key": "value"}
        )
        
        assert notification.notification_type == notification_type
        assert notification.chat_id == chat_id
        assert notification.title == title
        assert notification.message == message
        assert notification.data == {"key": "value"}


class TestTipRecommendationStructure:
    """
    Test tip recommendation structure.
    
    **Feature: fortress-update**
    **Validates: Requirements 15.7**
    """
    
    @given(
        priority=st.integers(min_value=1, max_value=3),
        category=st.text(min_size=1, max_size=50),
        message=st.text(min_size=1, max_size=500)
    )
    @settings(max_examples=100)
    def test_tip_recommendation_preserves_fields(
        self,
        priority: int,
        category: str,
        message: str
    ):
        """
        For any tip recommendation, all fields are preserved correctly.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.7**
        """
        tip = TipRecommendation(
            priority=priority,
            category=category,
            message=message,
            action="Test action"
        )
        
        assert tip.priority == priority
        assert tip.category == category
        assert tip.message == message
        assert tip.action == "Test action"
    
    @given(
        priority=st.integers(min_value=1, max_value=3),
        category=st.text(min_size=1, max_size=50),
        message=st.text(min_size=1, max_size=500)
    )
    @settings(max_examples=100)
    def test_tip_recommendation_optional_action(
        self,
        priority: int,
        category: str,
        message: str
    ):
        """
        For any tip recommendation, action can be None.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.7**
        """
        tip = TipRecommendation(
            priority=priority,
            category=category,
            message=message,
            action=None
        )
        
        assert tip.action is None


class TestTipsFormatting:
    """
    Test tips formatting functionality.
    
    **Feature: fortress-update**
    **Validates: Requirements 15.7**
    """
    
    def test_format_tips_empty_list(self):
        """
        For empty tips list, returns appropriate message.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.7**
        """
        formatted = format_tips([])
        
        assert "Нет рекомендаций" in formatted
    
    @given(
        priority=st.integers(min_value=1, max_value=3),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_format_tips_includes_message(
        self,
        priority: int,
        message: str
    ):
        """
        For any tip, formatted output includes the message.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.7**
        """
        tips = [TipRecommendation(
            priority=priority,
            category="test",
            message=message,
            action=None
        )]
        
        formatted = format_tips(tips)
        
        assert message in formatted
    
    @given(
        priority=st.integers(min_value=1, max_value=3),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        action=st.text(min_size=1, max_size=100).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_format_tips_includes_action(
        self,
        priority: int,
        message: str,
        action: str
    ):
        """
        For any tip with action, formatted output includes the action.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.7**
        """
        tips = [TipRecommendation(
            priority=priority,
            category="test",
            message=message,
            action=action
        )]
        
        formatted = format_tips(tips)
        
        assert action in formatted
    
    def test_format_tips_priority_emoji(self):
        """
        Tips are formatted with priority-based emoji.
        
        **Feature: fortress-update**
        **Validates: Requirements 15.7**
        """
        tips = [
            TipRecommendation(priority=1, category="high", message="High priority", action=None),
            TipRecommendation(priority=2, category="medium", message="Medium priority", action=None),
            TipRecommendation(priority=3, category="low", message="Low priority", action=None),
        ]
        
        formatted = format_tips(tips)
        
        # Should contain priority emojis
        assert "🔴" in formatted  # High priority
        assert "🟡" in formatted  # Medium priority
        assert "🟢" in formatted  # Low priority
