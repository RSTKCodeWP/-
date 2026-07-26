"""User Scanner Service - New User Screening.

This module provides automatic screening of new users to detect
bot accounts and suspicious profiles.

**Feature: shield-economy-v65**
**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from aiogram import Bot
from aiogram.types import User
from sqlalchemy import select, delete

from app.database.session import get_session
from app.database.models import SilentBan
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Suspicion score thresholds
SILENT_BAN_THRESHOLD = 0.7  # Score above this triggers silent ban
CAPTCHA_THRESHOLD = 0.5  # Score above this requires captcha

# Score weights for different factors
SCORE_NO_AVATAR = 0.4  # No profile photo
SCORE_SUSPICIOUS_NAME = 0.3  # Suspicious username patterns
SCORE_RTL_CHARS = 0.2  # RTL characters in name
SCORE_HIEROGLYPHICS = 0.15  # Hieroglyphic/unusual scripts
SCORE_SPAM_WORDS = 0.25  # Spam words in username
SCORE_PREMIUM_BONUS = -0.3  # Premium status reduces suspicion

# Suspicious username patterns
SPAM_WORDS: Set[str] = {
    # Russian spam words
    "заработок", "доход", "прибыль", "инвестиции", "крипто", "биткоин",
    "казино", "ставки", "бонус", "акция", "скидка", "бесплатно",
    "работа", "вакансия", "удаленно", "реклама", "продвижение",
    "канал", "подписка", "розыгрыш", "приз", "выигрыш",
    # English spam words
    "earn", "profit", "income", "invest", "crypto", "bitcoin",
    "casino", "betting", "bonus", "promo", "discount", "free",
    "job", "vacancy", "remote", "ads", "promotion",
    "channel", "subscribe", "giveaway", "prize", "winner",
    # Common bot patterns
    "bot", "admin", "support", "official", "verify", "verified",
    "manager", "helper", "assistant", "service",
}

# RTL character ranges (Arabic, Hebrew, etc.)
RTL_RANGES = [
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0700, 0x074F),  # Syriac
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
]

# Hieroglyphic/unusual script ranges
HIEROGLYPHIC_RANGES = [
    (0x13000, 0x1342F),  # Egyptian Hieroglyphs
    (0x14400, 0x1467F),  # Anatolian Hieroglyphs
    (0x16800, 0x16A3F),  # Bamum Supplement
    (0x1B000, 0x1B0FF),  # Kana Supplement
    (0x1F300, 0x1F5FF),  # Miscellaneous Symbols and Pictographs (some)
]

# CJK ranges (Chinese, Japanese, Korean) - not suspicious by themselves
CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xAC00, 0xD7AF),   # Hangul Syllables
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class UserScanResult:
    """
    Result of scanning a new user.
    
    Attributes:
        user_id: Telegram user ID
        suspicion_score: Score from 0.0 to 1.0 (higher = more suspicious)
        flags: List of detected suspicious indicators
        should_silent_ban: Whether to apply silent ban
        should_require_captcha: Whether to require captcha verification
    """
    user_id: int
    suspicion_score: float
    flags: List[str] = field(default_factory=list)
    should_silent_ban: bool = False
    should_require_captcha: bool = False


# ============================================================================
# User Scanner Service
# ============================================================================

class UserScanner:
    """
    Scanner for detecting suspicious new users.
    
    Checks multiple factors:
    - Presence of profile photo (avatar)
    - Username patterns (RTL characters, hieroglyphics, spam words)
    - Premium status (trust signal)
    
    Calculates a suspicion score and determines appropriate action.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    """
    
    def __init__(self):
        """Initialize UserScanner with default settings."""
        self._spam_words = set(SPAM_WORDS)
        self._silent_ban_threshold = SILENT_BAN_THRESHOLD
        self._captcha_threshold = CAPTCHA_THRESHOLD
    
    # =========================================================================
    # Main Scanning Methods
    # =========================================================================
    
    async def scan_user(self, user: User) -> UserScanResult:
        """
        Scan a user for suspicious indicators.
        
        Checks:
        1. Presence of profile photo (Requirement 9.1)
        2. Username patterns - RTL, hieroglyphics, spam words (Requirement 9.2)
        3. Premium status as trust signal (Requirement 9.3)
        
        Args:
            user: Telegram User object
            
        Returns:
            UserScanResult with suspicion score and flags
            
        **Validates: Requirements 9.1, 9.2, 9.3**
        """
        flags: List[str] = []
        
        # Check avatar (Requirement 9.1)
        has_avatar = self.check_avatar(user)
        if not has_avatar:
            flags.append("no_avatar")
        
        # Check name patterns (Requirement 9.2)
        name_to_check = self._get_display_name(user)
        is_suspicious_name, name_flags = self.check_name(name_to_check)
        if is_suspicious_name:
            flags.extend(name_flags)
        
        # Also check username if present
        if user.username:
            _, username_flags = self.check_name(user.username)
            for flag in username_flags:
                if flag not in flags:
                    flags.append(flag)
        
        # Check premium status (Requirement 9.3)
        is_premium = self.check_premium(user)
        if is_premium:
            flags.append("premium_user")
        
        # Calculate suspicion score
        score = self.calculate_score(flags)
        
        # Determine actions based on score
        should_silent_ban = score >= self._silent_ban_threshold
        should_require_captcha = score >= self._captcha_threshold and not should_silent_ban
        
        result = UserScanResult(
            user_id=user.id,
            suspicion_score=score,
            flags=flags,
            should_silent_ban=should_silent_ban,
            should_require_captcha=should_require_captcha
        )
        
        if should_silent_ban:
            logger.warning(
                f"User {user.id} flagged for silent ban: "
                f"score={score:.2f}, flags={flags}"
            )
        elif should_require_captcha:
            logger.info(
                f"User {user.id} requires captcha: "
                f"score={score:.2f}, flags={flags}"
            )
        
        return result
    
    def check_avatar(self, user: User) -> bool:
        """
        Check if user has a profile photo.
        
        Args:
            user: Telegram User object
            
        Returns:
            True if user has an avatar
            
        **Validates: Requirements 9.1**
        """
        # In aiogram, we can't directly check for avatar from User object
        # The has_photo attribute is not available in basic User
        # We check if the user object has photo-related attributes
        # For full check, we'd need to call get_user_profile_photos API
        
        # Check if user has any indication of having a photo
        # This is a heuristic - full check requires API call
        return getattr(user, 'has_photo', None) is not None or \
               getattr(user, 'photo', None) is not None
    
    async def check_avatar_full(self, user_id: int, bot: Bot) -> bool:
        """
        Full check for user profile photo using Telegram API.
        
        Args:
            user_id: Telegram user ID
            bot: Bot instance for API calls
            
        Returns:
            True if user has at least one profile photo
            
        **Validates: Requirements 9.1**
        """
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            return photos.total_count > 0
        except Exception as e:
            logger.warning(f"Failed to check avatar for user {user_id}: {e}")
            # Assume no avatar on error (fail-safe)
            return False
    
    def check_name(self, name: str) -> Tuple[bool, List[str]]:
        """
        Analyze a name for suspicious patterns.
        
        Checks for:
        - RTL characters (Arabic, Hebrew, etc.)
        - Hieroglyphic/unusual scripts
        - Spam words
        
        Args:
            name: Name string to analyze
            
        Returns:
            Tuple of (is_suspicious, list of flags)
            
        **Validates: Requirements 9.2**
        """
        if not name:
            return False, []
        
        flags: List[str] = []
        name_lower = name.lower()
        
        # Check for RTL characters
        if self._has_rtl_chars(name):
            flags.append("rtl_chars")
        
        # Check for hieroglyphics/unusual scripts
        if self._has_hieroglyphics(name):
            flags.append("hieroglyphics")
        
        # Check for spam words
        if self._has_spam_words(name_lower):
            flags.append("spam_words")
        
        # Check for excessive special characters
        if self._has_excessive_special_chars(name):
            flags.append("special_chars")
        
        # Check for number-heavy names (like "user123456")
        if self._is_number_heavy(name):
            flags.append("number_heavy")
        
        is_suspicious = len(flags) > 0
        return is_suspicious, flags
    
    def check_premium(self, user: User) -> bool:
        """
        Check if user has Telegram Premium.
        
        Premium status is a trust signal that reduces suspicion.
        
        Args:
            user: Telegram User object
            
        Returns:
            True if user has Premium
            
        **Validates: Requirements 9.3**
        """
        return getattr(user, 'is_premium', False) or False
    
    def calculate_score(self, flags: List[str]) -> float:
        """
        Calculate suspicion score from flags.
        
        Score ranges from 0.0 (not suspicious) to 1.0 (very suspicious).
        
        Args:
            flags: List of detected flags
            
        Returns:
            Suspicion score (0.0 - 1.0)
            
        **Validates: Requirements 9.4**
        """
        score = 0.0
        
        # Add scores for each flag
        if "no_avatar" in flags:
            score += SCORE_NO_AVATAR
        
        if "rtl_chars" in flags:
            score += SCORE_RTL_CHARS
        
        if "hieroglyphics" in flags:
            score += SCORE_HIEROGLYPHICS
        
        if "spam_words" in flags:
            score += SCORE_SPAM_WORDS
        
        if "special_chars" in flags:
            score += 0.1
        
        if "number_heavy" in flags:
            score += 0.1
        
        # Premium reduces suspicion
        if "premium_user" in flags:
            score += SCORE_PREMIUM_BONUS
        
        # Clamp to 0.0 - 1.0
        return max(0.0, min(1.0, score))
    
    # =========================================================================
    # Silent Ban Methods
    # =========================================================================
    
    async def apply_silent_ban(
        self,
        user_id: int,
        chat_id: int,
        reason: str = "suspicious_profile",
        captcha_answer: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Apply silent ban to a user.
        
        Creates a SilentBan record in the database.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            reason: Reason for the ban
            captcha_answer: Optional captcha answer for unban
            expires_at: Optional expiration time
            
        Returns:
            True if ban was applied successfully
            
        **Validates: Requirements 9.4**
        """
        try:
            async with get_session()() as session:
                # Check if already banned
                stmt = select(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing ban
                    existing.reason = reason
                    if captcha_answer:
                        existing.captcha_answer = captcha_answer
                    if expires_at:
                        existing.expires_at = expires_at
                else:
                    # Create new ban
                    silent_ban = SilentBan(
                        user_id=user_id,
                        chat_id=chat_id,
                        reason=reason,
                        captcha_answer=captcha_answer,
                        expires_at=expires_at
                    )
                    session.add(silent_ban)
                
                await session.commit()
                
                logger.info(
                    f"Applied silent ban to user {user_id} in chat {chat_id}: {reason}"
                )
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply silent ban: {e}")
            return False
    
    async def remove_silent_ban(
        self,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Remove silent ban from a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if ban was removed successfully
        """
        try:
            async with get_session()() as session:
                stmt = delete(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(
                        f"Removed silent ban from user {user_id} in chat {chat_id}"
                    )
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove silent ban: {e}")
            return False
    
    async def is_silent_banned(
        self,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Check if a user is under silent ban.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if user is silent banned
            
        **Validates: Requirements 9.5**
        """
        try:
            async with get_session()() as session:
                stmt = select(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                silent_ban = result.scalar_one_or_none()
                
                if silent_ban is None:
                    return False
                
                # Check if ban has expired
                if silent_ban.expires_at and silent_ban.expires_at <= utc_now():
                    # Ban expired, remove it
                    await session.delete(silent_ban)
                    await session.commit()
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to check silent ban status: {e}")
            return False
    
    async def get_silent_ban(
        self,
        user_id: int,
        chat_id: int
    ) -> Optional[SilentBan]:
        """
        Get silent ban record for a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            SilentBan record or None
        """
        try:
            async with get_session()() as session:
                stmt = select(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error(f"Failed to get silent ban: {e}")
            return None
    
    async def should_delete_message(
        self,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Check if a message from this user should be silently deleted.
        
        Messages from silent-banned users are deleted without notification.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if message should be deleted
            
        **Validates: Requirements 9.5**
        """
        return await self.is_silent_banned(user_id, chat_id)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _get_display_name(self, user: User) -> str:
        """Get the display name for a user."""
        parts = []
        if user.first_name:
            parts.append(user.first_name)
        if user.last_name:
            parts.append(user.last_name)
        return " ".join(parts) if parts else ""
    
    def _has_rtl_chars(self, text: str) -> bool:
        """Check if text contains RTL characters."""
        for char in text:
            code_point = ord(char)
            for start, end in RTL_RANGES:
                if start <= code_point <= end:
                    return True
        return False
    
    def _has_hieroglyphics(self, text: str) -> bool:
        """Check if text contains hieroglyphic/unusual script characters."""
        for char in text:
            code_point = ord(char)
            for start, end in HIEROGLYPHIC_RANGES:
                if start <= code_point <= end:
                    return True
        return False
    
    def _has_spam_words(self, text_lower: str) -> bool:
        """Check if text contains spam words."""
        # Check each spam word
        for word in self._spam_words:
            if word in text_lower:
                return True
        return False
    
    def _has_excessive_special_chars(self, text: str) -> bool:
        """Check if text has excessive special characters."""
        if not text:
            return False
        
        special_count = 0
        for char in text:
            category = unicodedata.category(char)
            # Count symbols and punctuation
            if category.startswith('S') or category.startswith('P'):
                special_count += 1
        
        # More than 30% special characters is suspicious
        return special_count / len(text) > 0.3 if text else False
    
    def _is_number_heavy(self, text: str) -> bool:
        """Check if text is number-heavy (like bot-generated names)."""
        if not text:
            return False
        
        digit_count = sum(1 for c in text if c.isdigit())
        
        # More than 40% digits is suspicious
        return digit_count / len(text) > 0.4 if text else False
    
    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    def add_spam_word(self, word: str) -> None:
        """Add a word to the spam words list."""
        self._spam_words.add(word.lower())
    
    def remove_spam_word(self, word: str) -> bool:
        """Remove a word from the spam words list."""
        word_lower = word.lower()
        if word_lower in self._spam_words:
            self._spam_words.discard(word_lower)
            return True
        return False
    
    def set_silent_ban_threshold(self, threshold: float) -> None:
        """Set the threshold for silent ban."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._silent_ban_threshold = threshold
    
    def set_captcha_threshold(self, threshold: float) -> None:
        """Set the threshold for captcha requirement."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._captcha_threshold = threshold
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current thresholds."""
        return {
            "silent_ban": self._silent_ban_threshold,
            "captcha": self._captcha_threshold
        }


# Global user scanner instance
user_scanner = UserScanner()
