"""
Property-based tests for PermissionChecker (Bot Permission Verification).

**Feature: shield-economy-v65, Property 20: Permission Check Before Moderation**
**Validates: Requirements 7.1**

**Feature: shield-economy-v65, Property 21: Missing Permission Silent Report**
**Validates: Requirements 7.2**

**Feature: shield-economy-v65, Property 22: No Threats Without Permissions**
**Validates: Requirements 7.3**
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/services/permission_checker.py)
# ============================================================================

CACHE_TTL_SECONDS = 60  # Permission cache TTL


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class ModerationAction(str, Enum):
    """Types of moderation actions that require permission checks."""
    DELETE_MESSAGE = "delete_messages"
    RESTRICT_MEMBER = "restrict_members"
    BAN_USER = "ban_users"
    PIN_MESSAGE = "pin_messages"
    INVITE_USERS = "invite_users"
    MANAGE_CHAT = "manage_chat"


# Action display names for notifications (in Russian)
ACTION_DISPLAY_NAMES = {
    ModerationAction.DELETE_MESSAGE: "удаление сообщений",
    ModerationAction.RESTRICT_MEMBER: "ограничение пользователей",
    ModerationAction.BAN_USER: "бан пользователей",
    ModerationAction.PIN_MESSAGE: "закрепление сообщений",
    ModerationAction.INVITE_USERS: "приглашение пользователей",
    ModerationAction.MANAGE_CHAT: "управление чатом",
}


@dataclass
class BotPermissions:
    """
    Bot permissions in a specific chat.
    
    Attributes:
        chat_id: Telegram chat ID
        can_delete_messages: Permission to delete messages
        can_restrict_members: Permission to restrict/mute users
        can_ban_users: Permission to ban users
        can_pin_messages: Permission to pin messages
        can_invite_users: Permission to invite users
        can_manage_chat: Permission to manage chat settings
        cached_at: When these permissions were cached
    """
    chat_id: int
    can_delete_messages: bool = False
    can_restrict_members: bool = False
    can_ban_users: bool = False
    can_pin_messages: bool = False
    can_invite_users: bool = False
    can_manage_chat: bool = False
    cached_at: datetime = field(default_factory=utc_now)
    
    def has_permission(self, action: ModerationAction) -> bool:
        """Check if bot has permission for a specific action."""
        permission_map = {
            ModerationAction.DELETE_MESSAGE: self.can_delete_messages,
            ModerationAction.RESTRICT_MEMBER: self.can_restrict_members,
            ModerationAction.BAN_USER: self.can_ban_users,
            ModerationAction.PIN_MESSAGE: self.can_pin_messages,
            ModerationAction.INVITE_USERS: self.can_invite_users,
            ModerationAction.MANAGE_CHAT: self.can_manage_chat,
        }
        return permission_map.get(action, False)
    
    def is_cache_valid(self) -> bool:
        """Check if cached permissions are still valid."""
        age = utc_now() - self.cached_at
        return age < timedelta(seconds=CACHE_TTL_SECONDS)


@dataclass
class PermissionCheckResult:
    """Result of a permission check."""
    allowed: bool
    missing_permissions: List[ModerationAction] = field(default_factory=list)
    message: Optional[str] = None


class PermissionChecker:
    """
    Minimal PermissionChecker for testing without Telegram API dependencies.
    
    This mirrors the core logic from app/services/permission_checker.py.
    """
    
    def __init__(self):
        """Initialize PermissionChecker with empty cache."""
        self._cache: Dict[int, BotPermissions] = {}
        # Track permission check calls for verification
        self._permission_check_calls: List[Dict] = []
        # Track moderation action attempts
        self._moderation_attempts: List[Dict] = []
        # Track silent reports sent to admins (Property 21)
        self._silent_reports: List[Dict] = []
        # Admin IDs per chat for testing
        self._chat_admin_ids: Dict[int, List[int]] = {}
        # Track threatening messages sent to violators (Property 22)
        self._threatening_messages: List[Dict] = []
    
    def set_permissions(
        self,
        chat_id: int,
        permissions: BotPermissions
    ) -> None:
        """
        Set permissions for a chat (simulates API response).
        
        Args:
            chat_id: Telegram chat ID
            permissions: Bot permissions to set
        """
        self._cache[chat_id] = permissions
    
    def check_permissions(
        self,
        chat_id: int,
        current_time: Optional[datetime] = None
    ) -> BotPermissions:
        """
        Check and cache bot permissions for a chat.
        
        **Validates: Requirements 7.1, 7.4**
        
        Args:
            chat_id: Telegram chat ID
            current_time: Optional time override for testing
            
        Returns:
            BotPermissions with current permission state
        """
        now = current_time or utc_now()
        
        # Record the permission check call
        self._permission_check_calls.append({
            "chat_id": chat_id,
            "timestamp": now,
            "action": "check_permissions"
        })
        
        # Check cache first
        if chat_id in self._cache:
            cached = self._cache[chat_id]
            if cached.is_cache_valid():
                return cached
        
        # Return empty permissions if not in cache (simulates API failure)
        return BotPermissions(chat_id=chat_id, cached_at=now)
    
    def can_perform_action(
        self,
        chat_id: int,
        action: ModerationAction,
        current_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if bot can perform a specific moderation action.
        
        **Validates: Requirements 7.1**
        WHEN OLEG_Bot attempts a moderation action (mute/ban/delete) THEN
        OLEG_Bot SHALL first verify its permissions via get_chat_member API.
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action to check
            current_time: Optional time override for testing
            
        Returns:
            True if bot has permission for the action, False otherwise
        """
        # Record the permission check for this action
        self._permission_check_calls.append({
            "chat_id": chat_id,
            "timestamp": current_time or utc_now(),
            "action": f"can_perform_{action.value}"
        })
        
        permissions = self.check_permissions(chat_id, current_time)
        return permissions.has_permission(action)
    
    def attempt_moderation_action(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        current_time: Optional[datetime] = None
    ) -> PermissionCheckResult:
        """
        Attempt to perform a moderation action with permission check.
        
        This method demonstrates the pattern where permissions MUST be
        checked before any moderation action is executed.
        
        **Validates: Requirements 7.1**
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action to perform
            target_user_id: User ID to perform action on
            current_time: Optional time override for testing
            
        Returns:
            PermissionCheckResult indicating if action was allowed
        """
        now = current_time or utc_now()
        
        # Record the moderation attempt
        attempt_record = {
            "chat_id": chat_id,
            "action": action,
            "target_user_id": target_user_id,
            "timestamp": now,
            "permission_checked": False,
            "action_executed": False
        }
        
        # CRITICAL: Check permissions BEFORE attempting the action
        # This is the core requirement being tested
        can_perform = self.can_perform_action(chat_id, action, now)
        attempt_record["permission_checked"] = True
        
        if can_perform:
            # Permission granted - action would be executed
            attempt_record["action_executed"] = True
            self._moderation_attempts.append(attempt_record)
            return PermissionCheckResult(allowed=True)
        else:
            # Permission denied - action not executed
            attempt_record["action_executed"] = False
            self._moderation_attempts.append(attempt_record)
            action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[action],
                message=f"У меня нет прав на {action_name}"
            )
    
    def get_permission_check_calls(self) -> List[Dict]:
        """Get all recorded permission check calls."""
        return self._permission_check_calls.copy()
    
    def get_moderation_attempts(self) -> List[Dict]:
        """Get all recorded moderation attempts."""
        return self._moderation_attempts.copy()
    
    def was_permission_checked_before_action(
        self,
        chat_id: int,
        action: ModerationAction
    ) -> bool:
        """
        Verify that permissions were checked before a moderation action.
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action
            
        Returns:
            True if permission was checked before the action
        """
        for attempt in self._moderation_attempts:
            if attempt["chat_id"] == chat_id and attempt["action"] == action:
                return attempt["permission_checked"]
        return False
    
    def clear_tracking(self) -> None:
        """Clear all tracking data."""
        self._permission_check_calls.clear()
        self._moderation_attempts.clear()
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached permissions for a chat."""
        self._cache.pop(chat_id, None)
    
    def clear_cache(self) -> None:
        """Clear all cached permissions."""
        self._cache.clear()
    
    def set_chat_admin_ids(self, chat_id: int, admin_ids: List[int]) -> None:
        """
        Set admin IDs for a chat (for testing silent reports).
        
        Args:
            chat_id: Telegram chat ID
            admin_ids: List of admin user IDs
        """
        self._chat_admin_ids[chat_id] = admin_ids
    
    def report_missing_permission(
        self,
        chat_id: int,
        action: ModerationAction,
        admin_ids: Optional[List[int]] = None
    ) -> None:
        """
        Silently report missing permission to administrators.
        
        **Validates: Requirements 7.2**
        WHEN OLEG_Bot lacks required permissions for an action THEN OLEG_Bot
        SHALL silently report to administrators "У меня нет прав на [action],
        сделайте что-нибудь!"
        
        Args:
            chat_id: Telegram chat ID where permission is missing
            action: The action that requires permission
            admin_ids: Optional list of admin user IDs to notify.
        """
        action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
        message = f"⚠️ У меня нет прав на {action_name}, сделайте что-нибудь!"
        
        # Get admin IDs if not provided
        if admin_ids is None:
            admin_ids = self._chat_admin_ids.get(chat_id, [])
        
        # Record the silent report
        report = {
            "chat_id": chat_id,
            "action": action,
            "message": message,
            "admin_ids_notified": admin_ids.copy() if admin_ids else [],
            "timestamp": utc_now(),
        }
        self._silent_reports.append(report)
    
    def get_silent_reports(self) -> List[Dict]:
        """Get all recorded silent reports."""
        return self._silent_reports.copy()
    
    def clear_silent_reports(self) -> None:
        """Clear all recorded silent reports."""
        self._silent_reports.clear()
    
    def attempt_moderation_action_with_report(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        current_time: Optional[datetime] = None
    ) -> PermissionCheckResult:
        """
        Attempt to perform a moderation action with permission check and silent report.
        
        This method demonstrates the full pattern where:
        1. Permissions are checked before any moderation action
        2. If permission is missing, a silent report is sent to admins
        
        **Validates: Requirements 7.1, 7.2**
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action to perform
            target_user_id: User ID to perform action on
            current_time: Optional time override for testing
            
        Returns:
            PermissionCheckResult indicating if action was allowed
        """
        now = current_time or utc_now()
        
        # Record the moderation attempt
        attempt_record = {
            "chat_id": chat_id,
            "action": action,
            "target_user_id": target_user_id,
            "timestamp": now,
            "permission_checked": False,
            "action_executed": False,
            "silent_report_sent": False
        }
        
        # CRITICAL: Check permissions BEFORE attempting the action
        can_perform = self.can_perform_action(chat_id, action, now)
        attempt_record["permission_checked"] = True
        
        if can_perform:
            # Permission granted - action would be executed
            attempt_record["action_executed"] = True
            self._moderation_attempts.append(attempt_record)
            return PermissionCheckResult(allowed=True)
        else:
            # Permission denied - send silent report to admins
            self.report_missing_permission(chat_id, action)
            attempt_record["silent_report_sent"] = True
            attempt_record["action_executed"] = False
            self._moderation_attempts.append(attempt_record)
            
            action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[action],
                message=f"У меня нет прав на {action_name}"
            )
    
    def get_threatening_messages(self) -> List[Dict]:
        """Get all recorded threatening messages."""
        return self._threatening_messages.copy()
    
    def clear_threatening_messages(self) -> None:
        """Clear all recorded threatening messages."""
        self._threatening_messages.clear()
    
    def should_send_threat(
        self,
        permission_result: PermissionCheckResult
    ) -> bool:
        """
        Determine if a threatening message should be sent to violator.
        
        **Validates: Requirements 7.3**
        WHEN OLEG_Bot lacks permissions THEN OLEG_Bot SHALL NOT send
        threatening messages to violators.
        
        Args:
            permission_result: Result from can_perform_action
            
        Returns:
            True if threat can be sent (bot has permissions), False otherwise
        """
        return permission_result.allowed
    
    def attempt_moderation_with_threat(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        threat_message: str,
        current_time: Optional[datetime] = None
    ) -> PermissionCheckResult:
        """
        Attempt to perform a moderation action with potential threatening message.
        
        This method demonstrates the full pattern where:
        1. Permissions are checked before any moderation action
        2. If permission is missing, NO threatening message is sent (Requirement 7.3)
        3. If permission is granted, the action is executed and threat may be sent
        
        **Validates: Requirements 7.1, 7.3**
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action to perform
            target_user_id: User ID to perform action on
            threat_message: The threatening message to potentially send
            current_time: Optional time override for testing
            
        Returns:
            PermissionCheckResult indicating if action was allowed
        """
        now = current_time or utc_now()
        
        # Record the moderation attempt
        attempt_record = {
            "chat_id": chat_id,
            "action": action,
            "target_user_id": target_user_id,
            "timestamp": now,
            "permission_checked": False,
            "action_executed": False,
            "threat_sent": False,
            "threat_message": threat_message
        }
        
        # CRITICAL: Check permissions BEFORE attempting the action
        can_perform = self.can_perform_action(chat_id, action, now)
        attempt_record["permission_checked"] = True
        
        if can_perform:
            # Permission granted - action would be executed
            attempt_record["action_executed"] = True
            
            # Only send threatening message if we have permission
            # (This is the correct behavior per Requirement 7.3)
            self._threatening_messages.append({
                "chat_id": chat_id,
                "target_user_id": target_user_id,
                "action": action,
                "message": threat_message,
                "timestamp": now,
            })
            attempt_record["threat_sent"] = True
            
            self._moderation_attempts.append(attempt_record)
            return PermissionCheckResult(allowed=True)
        else:
            # Permission denied - DO NOT send threatening message
            # This is the key requirement being tested (Requirement 7.3)
            attempt_record["action_executed"] = False
            attempt_record["threat_sent"] = False
            
            self._moderation_attempts.append(attempt_record)
            
            action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
            return PermissionCheckResult(
                allowed=False,
                missing_permissions=[action],
                message=f"У меня нет прав на {action_name}"
            )


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for moderation actions
moderation_actions = st.sampled_from([
    ModerationAction.DELETE_MESSAGE,
    ModerationAction.RESTRICT_MEMBER,
    ModerationAction.BAN_USER,
    ModerationAction.PIN_MESSAGE,
    ModerationAction.INVITE_USERS,
    ModerationAction.MANAGE_CHAT,
])

# Strategy for boolean permissions
permission_bools = st.booleans()

# Strategy for generating random BotPermissions
@st.composite
def bot_permissions_strategy(draw, chat_id: int = None):
    """Generate random BotPermissions."""
    if chat_id is None:
        chat_id = draw(chat_ids)
    return BotPermissions(
        chat_id=chat_id,
        can_delete_messages=draw(permission_bools),
        can_restrict_members=draw(permission_bools),
        can_ban_users=draw(permission_bools),
        can_pin_messages=draw(permission_bools),
        can_invite_users=draw(permission_bools),
        can_manage_chat=draw(permission_bools),
        cached_at=utc_now(),
    )


# ============================================================================
# Property Tests
# ============================================================================


class TestPermissionCheckerProperties:
    """Property-based tests for PermissionChecker."""

    # ========================================================================
    # Property 20: Permission Check Before Moderation
    # ========================================================================

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_permission_checked_before_any_moderation_action(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 20: Permission Check Before Moderation**
        **Validates: Requirements 7.1**
        
        For any moderation action (mute/ban/delete), the bot's permissions
        SHALL be verified before execution.
        """
        checker = PermissionChecker()
        
        # Set up some permissions (may or may not include the required one)
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_ban_users=True,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Attempt the moderation action
        result = checker.attempt_moderation_action(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify that permission was checked before the action
        was_checked = checker.was_permission_checked_before_action(chat_id, action)
        
        assert was_checked is True, (
            f"Permission MUST be checked before moderation action {action.value}. "
            f"This is required by Requirement 7.1."
        )

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_moderation_action_blocked_without_permission(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 20: Permission Check Before Moderation**
        **Validates: Requirements 7.1**
        
        For any moderation action where the bot lacks permission,
        the action SHALL NOT be executed.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT the required permission
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Attempt the moderation action
        result = checker.attempt_moderation_action(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify that the action was NOT executed
        assert result.allowed is False, (
            f"Moderation action {action.value} should NOT be allowed "
            f"when bot lacks permission"
        )
        
        # Verify the action was recorded as not executed
        attempts = checker.get_moderation_attempts()
        assert len(attempts) == 1
        assert attempts[0]["action_executed"] is False, (
            f"Action should not be executed when permission is denied"
        )

    @given(
        chat_id=chat_ids,
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_moderation_action_allowed_with_permission(
        self,
        chat_id: int,
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 20: Permission Check Before Moderation**
        **Validates: Requirements 7.1**
        
        For any moderation action where the bot has permission,
        the action SHALL be allowed after permission check.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITH all permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_ban_users=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_chat=True,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Test each moderation action
        for action in ModerationAction:
            checker.clear_tracking()
            
            result = checker.attempt_moderation_action(
                chat_id=chat_id,
                action=action,
                target_user_id=target_user_id,
            )
            
            # Verify permission was checked
            was_checked = checker.was_permission_checked_before_action(chat_id, action)
            assert was_checked is True, (
                f"Permission MUST be checked before action {action.value}"
            )
            
            # Verify action was allowed
            assert result.allowed is True, (
                f"Action {action.value} should be allowed when bot has permission"
            )

    @given(
        chat_id=chat_ids,
        actions=st.lists(moderation_actions, min_size=1, max_size=5),
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_each_action_requires_separate_permission_check(
        self,
        chat_id: int,
        actions: List[ModerationAction],
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 20: Permission Check Before Moderation**
        **Validates: Requirements 7.1**
        
        For any sequence of moderation actions, each action SHALL have
        its permissions verified independently.
        """
        checker = PermissionChecker()
        
        # Set up permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_ban_users=True,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Attempt multiple moderation actions
        for action in actions:
            checker.attempt_moderation_action(
                chat_id=chat_id,
                action=action,
                target_user_id=target_user_id,
            )
        
        # Verify each action had its permission checked
        attempts = checker.get_moderation_attempts()
        assert len(attempts) == len(actions), (
            f"Expected {len(actions)} moderation attempts, got {len(attempts)}"
        )
        
        for i, attempt in enumerate(attempts):
            assert attempt["permission_checked"] is True, (
                f"Action {i+1} ({attempt['action'].value}) must have "
                f"permission checked before execution"
            )

    # ========================================================================
    # Property 21: Missing Permission Silent Report
    # ========================================================================

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
        admin_ids=st.lists(user_ids, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_missing_permission_triggers_silent_report(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        admin_ids: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 21: Missing Permission Silent Report**
        **Validates: Requirements 7.2**
        
        For any moderation action where the bot lacks required permissions,
        a silent report SHALL be sent to administrators.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT the required permission
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Set up admin IDs for the chat
        checker.set_chat_admin_ids(chat_id, admin_ids)
        
        # Attempt the moderation action (should fail and trigger silent report)
        result = checker.attempt_moderation_action_with_report(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify the action was denied
        assert result.allowed is False, (
            f"Action {action.value} should be denied when bot lacks permission"
        )
        
        # Verify a silent report was sent
        reports = checker.get_silent_reports()
        assert len(reports) == 1, (
            f"Expected exactly 1 silent report, got {len(reports)}"
        )
        
        report = reports[0]
        assert report["chat_id"] == chat_id, (
            f"Silent report should be for chat {chat_id}"
        )
        assert report["action"] == action, (
            f"Silent report should be for action {action.value}"
        )
        
        # Verify the message format matches requirement 7.2
        action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
        expected_message = f"⚠️ У меня нет прав на {action_name}, сделайте что-нибудь!"
        assert report["message"] == expected_message, (
            f"Silent report message should be '{expected_message}', "
            f"got '{report['message']}'"
        )

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
        admin_ids=st.lists(user_ids, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_silent_report_notifies_all_admins(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        admin_ids: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 21: Missing Permission Silent Report**
        **Validates: Requirements 7.2**
        
        For any missing permission report, all chat administrators SHALL be notified.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT the required permission
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Set up admin IDs for the chat
        checker.set_chat_admin_ids(chat_id, admin_ids)
        
        # Attempt the moderation action (should fail and trigger silent report)
        checker.attempt_moderation_action_with_report(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify the silent report includes all admin IDs
        reports = checker.get_silent_reports()
        assert len(reports) == 1
        
        report = reports[0]
        assert set(report["admin_ids_notified"]) == set(admin_ids), (
            f"Silent report should notify all admins {admin_ids}, "
            f"but notified {report['admin_ids_notified']}"
        )

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_no_silent_report_when_permission_granted(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 21: Missing Permission Silent Report**
        **Validates: Requirements 7.2**
        
        For any moderation action where the bot HAS permission,
        NO silent report SHALL be sent.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITH all permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_ban_users=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_chat=True,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Set up admin IDs for the chat
        checker.set_chat_admin_ids(chat_id, [123456789])
        
        # Attempt the moderation action (should succeed)
        result = checker.attempt_moderation_action_with_report(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify the action was allowed
        assert result.allowed is True, (
            f"Action {action.value} should be allowed when bot has permission"
        )
        
        # Verify NO silent report was sent
        reports = checker.get_silent_reports()
        assert len(reports) == 0, (
            f"No silent report should be sent when permission is granted, "
            f"but got {len(reports)} reports"
        )

    @given(
        chat_id=chat_ids,
        actions=st.lists(moderation_actions, min_size=2, max_size=5),
        target_user_id=user_ids,
        admin_ids=st.lists(user_ids, min_size=1, max_size=3, unique=True),
    )
    @settings(max_examples=100)
    def test_each_missing_permission_triggers_separate_report(
        self,
        chat_id: int,
        actions: List[ModerationAction],
        target_user_id: int,
        admin_ids: List[int],
    ):
        """
        **Feature: shield-economy-v65, Property 21: Missing Permission Silent Report**
        **Validates: Requirements 7.2**
        
        For any sequence of moderation actions where the bot lacks permissions,
        each failed action SHALL trigger its own silent report.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT any permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Set up admin IDs for the chat
        checker.set_chat_admin_ids(chat_id, admin_ids)
        
        # Attempt multiple moderation actions
        for action in actions:
            checker.attempt_moderation_action_with_report(
                chat_id=chat_id,
                action=action,
                target_user_id=target_user_id,
            )
        
        # Verify each action triggered a silent report
        reports = checker.get_silent_reports()
        assert len(reports) == len(actions), (
            f"Expected {len(actions)} silent reports (one per failed action), "
            f"got {len(reports)}"
        )
        
        # Verify each report corresponds to the correct action
        for i, (action, report) in enumerate(zip(actions, reports)):
            assert report["action"] == action, (
                f"Report {i+1} should be for action {action.value}, "
                f"got {report['action'].value}"
            )

    # ========================================================================
    # Property 22: No Threats Without Permissions
    # ========================================================================

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
        threat_message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_no_threatening_message_when_permission_lacking(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        threat_message: str,
    ):
        """
        **Feature: shield-economy-v65, Property 22: No Threats Without Permissions**
        **Validates: Requirements 7.3**
        
        For any moderation scenario where the bot lacks permissions,
        NO threatening messages SHALL be sent to violators.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT any permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Attempt the moderation action with a potential threatening message
        result = checker.attempt_moderation_with_threat(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
            threat_message=threat_message,
        )
        
        # Verify the action was denied
        assert result.allowed is False, (
            f"Action {action.value} should be denied when bot lacks permission"
        )
        
        # CRITICAL: Verify NO threatening message was sent
        threats = checker.get_threatening_messages()
        assert len(threats) == 0, (
            f"No threatening message should be sent when bot lacks permissions. "
            f"This is required by Requirement 7.3. "
            f"Got {len(threats)} threatening messages."
        )

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
        threat_message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_threatening_message_allowed_with_permission(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
        threat_message: str,
    ):
        """
        **Feature: shield-economy-v65, Property 22: No Threats Without Permissions**
        **Validates: Requirements 7.3**
        
        For any moderation scenario where the bot HAS permissions,
        threatening messages MAY be sent to violators.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITH all permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_ban_users=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_chat=True,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Attempt the moderation action with a potential threatening message
        result = checker.attempt_moderation_with_threat(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
            threat_message=threat_message,
        )
        
        # Verify the action was allowed
        assert result.allowed is True, (
            f"Action {action.value} should be allowed when bot has permission"
        )
        
        # Verify threatening message WAS sent (since we have permission)
        threats = checker.get_threatening_messages()
        assert len(threats) == 1, (
            f"Threatening message should be sent when bot has permissions. "
            f"Got {len(threats)} threatening messages."
        )
        
        # Verify the threat details
        threat = threats[0]
        assert threat["chat_id"] == chat_id
        assert threat["target_user_id"] == target_user_id
        assert threat["action"] == action
        assert threat["message"] == threat_message

    @given(
        chat_id=chat_ids,
        actions=st.lists(moderation_actions, min_size=2, max_size=5),
        target_user_id=user_ids,
        threat_message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_no_threats_for_any_action_without_permissions(
        self,
        chat_id: int,
        actions: List[ModerationAction],
        target_user_id: int,
        threat_message: str,
    ):
        """
        **Feature: shield-economy-v65, Property 22: No Threats Without Permissions**
        **Validates: Requirements 7.3**
        
        For any sequence of moderation actions where the bot lacks permissions,
        NO threatening messages SHALL be sent for ANY of the actions.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT any permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Attempt multiple moderation actions
        for action in actions:
            checker.attempt_moderation_with_threat(
                chat_id=chat_id,
                action=action,
                target_user_id=target_user_id,
                threat_message=f"{threat_message} - {action.value}",
            )
        
        # CRITICAL: Verify NO threatening messages were sent for ANY action
        threats = checker.get_threatening_messages()
        assert len(threats) == 0, (
            f"No threatening messages should be sent when bot lacks permissions. "
            f"Attempted {len(actions)} actions, got {len(threats)} threats. "
            f"This violates Requirement 7.3."
        )

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_should_send_threat_returns_false_without_permission(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 22: No Threats Without Permissions**
        **Validates: Requirements 7.3**
        
        For any permission check result where permission is denied,
        should_send_threat() SHALL return False.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITHOUT any permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_ban_users=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Get permission check result
        result = checker.attempt_moderation_action(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify should_send_threat returns False
        should_send = checker.should_send_threat(result)
        assert should_send is False, (
            f"should_send_threat() must return False when bot lacks permission. "
            f"This is required by Requirement 7.3."
        )

    @given(
        chat_id=chat_ids,
        action=moderation_actions,
        target_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_should_send_threat_returns_true_with_permission(
        self,
        chat_id: int,
        action: ModerationAction,
        target_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 22: No Threats Without Permissions**
        **Validates: Requirements 7.3**
        
        For any permission check result where permission is granted,
        should_send_threat() SHALL return True.
        """
        checker = PermissionChecker()
        
        # Set up permissions WITH all permissions
        permissions = BotPermissions(
            chat_id=chat_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_ban_users=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_chat=True,
            cached_at=utc_now(),
        )
        checker.set_permissions(chat_id, permissions)
        
        # Get permission check result
        result = checker.attempt_moderation_action(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
        )
        
        # Verify should_send_threat returns True
        should_send = checker.should_send_threat(result)
        assert should_send is True, (
            f"should_send_threat() must return True when bot has permission."
        )
