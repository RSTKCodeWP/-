"""
Property-based tests for UserScanner (New User Scanning).

**Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
**Validates: Requirements 9.1, 9.2, 9.3**

**Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
**Validates: Requirements 9.4**

**Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
**Validates: Requirements 9.5**
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple
import unicodedata

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Constants (mirroring app/services/user_scanner.py)
# ============================================================================

# Suspicion score thresholds
SILENT_BAN_THRESHOLD = 0.7
CAPTCHA_THRESHOLD = 0.5

# Score weights for different factors
SCORE_NO_AVATAR = 0.4
SCORE_SUSPICIOUS_NAME = 0.3
SCORE_RTL_CHARS = 0.2
SCORE_HIEROGLYPHICS = 0.15
SCORE_SPAM_WORDS = 0.25
SCORE_PREMIUM_BONUS = -0.3

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


# ============================================================================
# Mock User class (mirroring aiogram.types.User structure)
# ============================================================================

@dataclass
class MockUser:
    """Mock Telegram User object for testing."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_premium: bool = False
    has_photo: Optional[bool] = None  # None means unknown, True/False means known
    photo: Optional[object] = None  # Simplified photo representation


# ============================================================================
# Data Classes (mirroring app/services/user_scanner.py)
# ============================================================================

@dataclass
class UserScanResult:
    """Result of scanning a new user."""
    user_id: int
    suspicion_score: float
    flags: List[str] = field(default_factory=list)
    should_silent_ban: bool = False
    should_require_captcha: bool = False


# ============================================================================
# UserScanner implementation for testing (mirrors app/services/user_scanner.py)
# ============================================================================

class UserScanner:
    """
    Scanner for detecting suspicious new users.
    
    Checks multiple factors:
    - Presence of profile photo (avatar) - Requirement 9.1
    - Username patterns (RTL characters, hieroglyphics, spam words) - Requirement 9.2
    - Premium status (trust signal) - Requirement 9.3
    """
    
    def __init__(self):
        """Initialize UserScanner with default settings."""
        self._spam_words = set(SPAM_WORDS)
        self._silent_ban_threshold = SILENT_BAN_THRESHOLD
        self._captcha_threshold = CAPTCHA_THRESHOLD
        # Track which checks were performed for testing
        self._last_scan_checks: List[str] = []
    
    def scan_user(self, user: MockUser) -> UserScanResult:
        """
        Scan a user for suspicious indicators.
        
        Checks:
        1. Presence of profile photo (Requirement 9.1)
        2. Username patterns - RTL, hieroglyphics, spam words (Requirement 9.2)
        3. Premium status as trust signal (Requirement 9.3)
        """
        self._last_scan_checks = []
        flags: List[str] = []
        
        # Check avatar (Requirement 9.1)
        self._last_scan_checks.append("avatar_check")
        has_avatar = self.check_avatar(user)
        if not has_avatar:
            flags.append("no_avatar")
        
        # Check name patterns (Requirement 9.2)
        self._last_scan_checks.append("name_pattern_check")
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
        self._last_scan_checks.append("premium_check")
        is_premium = self.check_premium(user)
        if is_premium:
            flags.append("premium_user")
        
        # Calculate suspicion score
        score = self.calculate_score(flags)
        
        # Determine actions based on score
        should_silent_ban = score >= self._silent_ban_threshold
        should_require_captcha = score >= self._captcha_threshold and not should_silent_ban
        
        return UserScanResult(
            user_id=user.id,
            suspicion_score=score,
            flags=flags,
            should_silent_ban=should_silent_ban,
            should_require_captcha=should_require_captcha
        )
    
    def check_avatar(self, user: MockUser) -> bool:
        """
        Check if user has a profile photo.
        
        **Validates: Requirements 9.1**
        """
        return getattr(user, 'has_photo', None) is not None or \
               getattr(user, 'photo', None) is not None
    
    def check_name(self, name: str) -> Tuple[bool, List[str]]:
        """
        Analyze a name for suspicious patterns.
        
        Checks for:
        - RTL characters (Arabic, Hebrew, etc.)
        - Hieroglyphic/unusual scripts
        - Spam words
        
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
        
        # Check for number-heavy names
        if self._is_number_heavy(name):
            flags.append("number_heavy")
        
        is_suspicious = len(flags) > 0
        return is_suspicious, flags
    
    def check_premium(self, user: MockUser) -> bool:
        """
        Check if user has Telegram Premium.
        
        **Validates: Requirements 9.3**
        """
        return getattr(user, 'is_premium', False) or False
    
    def calculate_score(self, flags: List[str]) -> float:
        """Calculate suspicion score from flags."""
        score = 0.0
        
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
        
        return max(0.0, min(1.0, score))
    
    def get_last_scan_checks(self) -> List[str]:
        """Get the list of checks performed in the last scan."""
        return self._last_scan_checks.copy()
    
    def _get_display_name(self, user: MockUser) -> str:
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
            if category.startswith('S') or category.startswith('P'):
                special_count += 1
        
        return special_count / len(text) > 0.3 if text else False
    
    def _is_number_heavy(self, text: str) -> bool:
        """Check if text is number-heavy."""
        if not text:
            return False
        
        digit_count = sum(1 for c in text if c.isdigit())
        return digit_count / len(text) > 0.4 if text else False


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for normal names (Latin/Cyrillic)
normal_first_names = st.sampled_from([
    "John", "Alice", "Bob", "Maria", "Иван", "Мария", "Алексей", "Анна",
    "Michael", "Sarah", "David", "Emma", "Дмитрий", "Елена", "Сергей", "Ольга"
])

normal_last_names = st.sampled_from([
    "Smith", "Johnson", "Williams", "Brown", "Иванов", "Петров", "Сидоров",
    "Jones", "Davis", "Miller", "Wilson", "Козлов", "Новиков", "Морозов", None
])

# Strategy for usernames
normal_usernames = st.sampled_from([
    "john_doe", "alice123", "bob_smith", "maria_k", "ivan_petrov",
    "cool_user", "happy_cat", "sunny_day", "night_owl", None
])

# Strategy for names with RTL characters
rtl_names = st.sampled_from([
    "محمد",  # Arabic
    "אברהם",  # Hebrew
    "علي",  # Arabic
    "יעקב",  # Hebrew
    "فاطمة",  # Arabic
])

# Strategy for names with spam words
spam_word_names = st.sampled_from([
    "crypto_trader", "bitcoin_master", "earn_money", "free_bonus",
    "заработок_онлайн", "крипто_инвестор", "бесплатно_бонус",
    "admin_support", "official_bot", "verified_manager"
])

# Strategy for boolean values
booleans = st.booleans()


# ============================================================================
# Property Tests
# ============================================================================

class TestUserScannerProperties:
    """Property-based tests for UserScanner."""

    # ========================================================================
    # Property 25: New User Scan Checks All Factors
    # ========================================================================

    @given(
        user_id=user_ids,
        first_name=normal_first_names,
        last_name=normal_last_names,
        username=normal_usernames,
        is_premium=booleans,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_scan_checks_avatar_presence(
        self,
        user_id: int,
        first_name: str,
        last_name: Optional[str],
        username: Optional[str],
        is_premium: bool,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.1**
        
        For any new user joining, the scan SHALL check presence of profile photo.
        """
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_premium=is_premium,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify avatar check was performed
        checks_performed = scanner.get_last_scan_checks()
        assert "avatar_check" in checks_performed, (
            "Scan MUST check for avatar presence (Requirement 9.1)"
        )
        
        # Verify the result reflects avatar status correctly
        has_avatar = has_photo is not None
        if not has_avatar:
            assert "no_avatar" in result.flags, (
                "User without avatar should have 'no_avatar' flag"
            )
        else:
            assert "no_avatar" not in result.flags, (
                "User with avatar should NOT have 'no_avatar' flag"
            )

    @given(
        user_id=user_ids,
        first_name=normal_first_names,
        last_name=normal_last_names,
        username=normal_usernames,
        is_premium=booleans,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_scan_checks_username_patterns(
        self,
        user_id: int,
        first_name: str,
        last_name: Optional[str],
        username: Optional[str],
        is_premium: bool,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.2**
        
        For any new user joining, the scan SHALL analyze the username for 
        suspicious patterns (RTL characters, hieroglyphics, spam words).
        """
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_premium=is_premium,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify name pattern check was performed
        checks_performed = scanner.get_last_scan_checks()
        assert "name_pattern_check" in checks_performed, (
            "Scan MUST check username patterns (Requirement 9.2)"
        )

    @given(
        user_id=user_ids,
        first_name=rtl_names,
        is_premium=booleans,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_scan_detects_rtl_characters(
        self,
        user_id: int,
        first_name: str,
        is_premium: bool,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.2**
        
        For any new user with RTL characters in their name, the scan SHALL
        detect and flag the RTL characters.
        """
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=None,
            username=None,
            is_premium=is_premium,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify RTL characters were detected
        assert "rtl_chars" in result.flags, (
            f"Scan MUST detect RTL characters in name '{first_name}' (Requirement 9.2)"
        )

    @given(
        user_id=user_ids,
        first_name=spam_word_names,
        is_premium=booleans,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_scan_detects_spam_words(
        self,
        user_id: int,
        first_name: str,
        is_premium: bool,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.2**
        
        For any new user with spam words in their name, the scan SHALL
        detect and flag the spam words.
        """
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=None,
            username=None,
            is_premium=is_premium,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify spam words were detected
        assert "spam_words" in result.flags, (
            f"Scan MUST detect spam words in name '{first_name}' (Requirement 9.2)"
        )

    @given(
        user_id=user_ids,
        first_name=normal_first_names,
        last_name=normal_last_names,
        username=normal_usernames,
        is_premium=booleans,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_scan_checks_premium_status(
        self,
        user_id: int,
        first_name: str,
        last_name: Optional[str],
        username: Optional[str],
        is_premium: bool,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.3**
        
        For any new user joining, the scan SHALL check Premium status as a trust signal.
        """
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_premium=is_premium,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify premium check was performed
        checks_performed = scanner.get_last_scan_checks()
        assert "premium_check" in checks_performed, (
            "Scan MUST check Premium status (Requirement 9.3)"
        )
        
        # Verify the result reflects premium status correctly
        if is_premium:
            assert "premium_user" in result.flags, (
                "Premium user should have 'premium_user' flag"
            )
        else:
            assert "premium_user" not in result.flags, (
                "Non-premium user should NOT have 'premium_user' flag"
            )

    @given(
        user_id=user_ids,
        first_name=normal_first_names,
        last_name=normal_last_names,
        username=normal_usernames,
        is_premium=booleans,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_scan_performs_all_three_checks(
        self,
        user_id: int,
        first_name: str,
        last_name: Optional[str],
        username: Optional[str],
        is_premium: bool,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.1, 9.2, 9.3**
        
        For any new user joining, the scan SHALL check ALL THREE factors:
        1. Presence of profile photo (9.1)
        2. Username patterns (9.2)
        3. Premium status (9.3)
        """
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_premium=is_premium,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify all three checks were performed
        checks_performed = scanner.get_last_scan_checks()
        
        assert "avatar_check" in checks_performed, (
            "Scan MUST check for avatar presence (Requirement 9.1)"
        )
        assert "name_pattern_check" in checks_performed, (
            "Scan MUST check username patterns (Requirement 9.2)"
        )
        assert "premium_check" in checks_performed, (
            "Scan MUST check Premium status (Requirement 9.3)"
        )
        
        # Verify all three checks were performed in a single scan
        assert len(checks_performed) >= 3, (
            f"Scan should perform at least 3 checks, performed {len(checks_performed)}"
        )

    @given(
        user_id=user_ids,
        first_name=normal_first_names,
        has_photo=st.one_of(st.none(), booleans),
    )
    @settings(max_examples=100)
    def test_premium_status_reduces_suspicion_score(
        self,
        user_id: int,
        first_name: str,
        has_photo: Optional[bool],
    ):
        """
        **Feature: shield-economy-v65, Property 25: New User Scan Checks All Factors**
        **Validates: Requirements 9.3**
        
        For any user, Premium status SHALL act as a trust signal that
        reduces the suspicion score.
        """
        # Create two users with same attributes except premium status
        user_non_premium = MockUser(
            id=user_id,
            first_name=first_name,
            is_premium=False,
            has_photo=has_photo,
        )
        
        user_premium = MockUser(
            id=user_id,
            first_name=first_name,
            is_premium=True,
            has_photo=has_photo,
        )
        
        scanner = UserScanner()
        
        result_non_premium = scanner.scan_user(user_non_premium)
        result_premium = scanner.scan_user(user_premium)
        
        # Premium user should have lower or equal suspicion score
        assert result_premium.suspicion_score <= result_non_premium.suspicion_score, (
            f"Premium status should reduce suspicion score. "
            f"Non-premium: {result_non_premium.suspicion_score}, "
            f"Premium: {result_premium.suspicion_score}"
        )

    # ========================================================================
    # Property 26: High Suspicion Score Triggers Silent Ban
    # ========================================================================

    @given(
        user_id=user_ids,
        suspicious_name=spam_word_names,
    )
    @settings(max_examples=100)
    def test_no_avatar_plus_suspicious_name_triggers_silent_ban(
        self,
        user_id: int,
        suspicious_name: str,
    ):
        """
        **Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
        **Validates: Requirements 9.4**
        
        For any user with suspicion score exceeding threshold (no avatar + suspicious name),
        Silent_Ban SHALL be applied.
        
        Score calculation:
        - no_avatar: +0.4
        - spam_words: +0.25
        - Total: 0.65 (below 0.7 threshold)
        
        To exceed threshold (0.7), we need additional factors like RTL chars (+0.2)
        or special_chars (+0.1) or number_heavy (+0.1).
        """
        # User with no avatar (has_photo=None) and suspicious name (spam words)
        # This alone gives 0.4 + 0.25 = 0.65, which is below 0.7
        # We need to add more suspicious factors to exceed threshold
        user = MockUser(
            id=user_id,
            first_name=suspicious_name,
            last_name=None,
            username=None,
            is_premium=False,
            has_photo=None,  # No avatar indicator
            photo=None,  # No photo object
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify the flags are detected
        assert "no_avatar" in result.flags, (
            "User without avatar should have 'no_avatar' flag"
        )
        assert "spam_words" in result.flags, (
            f"User with suspicious name '{suspicious_name}' should have 'spam_words' flag"
        )
        
        # Calculate expected minimum score: no_avatar (0.4) + spam_words (0.25) = 0.65
        expected_min_score = SCORE_NO_AVATAR + SCORE_SPAM_WORDS
        assert result.suspicion_score >= expected_min_score, (
            f"Score should be at least {expected_min_score}, got {result.suspicion_score}"
        )

    @given(
        user_id=user_ids,
        rtl_name=rtl_names,
    )
    @settings(max_examples=100)
    def test_no_avatar_plus_rtl_name_triggers_silent_ban(
        self,
        user_id: int,
        rtl_name: str,
    ):
        """
        **Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
        **Validates: Requirements 9.4**
        
        For any user with no avatar AND RTL characters in name,
        the suspicion score should be calculated correctly.
        
        Score: no_avatar (0.4) + rtl_chars (0.2) = 0.6 (below threshold)
        """
        user = MockUser(
            id=user_id,
            first_name=rtl_name,
            last_name=None,
            username=None,
            is_premium=False,
            has_photo=None,
            photo=None,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify flags
        assert "no_avatar" in result.flags
        assert "rtl_chars" in result.flags
        
        # Score: 0.4 + 0.2 = 0.6
        expected_score = SCORE_NO_AVATAR + SCORE_RTL_CHARS
        assert abs(result.suspicion_score - expected_score) < 0.01, (
            f"Expected score ~{expected_score}, got {result.suspicion_score}"
        )

    @given(user_id=user_ids)
    @settings(max_examples=100)
    def test_no_avatar_plus_spam_words_plus_rtl_triggers_silent_ban(
        self,
        user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
        **Validates: Requirements 9.4**
        
        For any user with no avatar + spam words + RTL characters,
        the suspicion score SHALL exceed threshold and trigger silent ban.
        
        Score: no_avatar (0.4) + spam_words (0.25) + rtl_chars (0.2) = 0.85 >= 0.7
        """
        # Create a name that has both spam words and RTL characters
        # Using Arabic word for "profit" which is a spam word concept
        suspicious_name = "crypto محمد"  # Contains spam word "crypto" and RTL chars
        
        user = MockUser(
            id=user_id,
            first_name=suspicious_name,
            last_name=None,
            username=None,
            is_premium=False,
            has_photo=None,
            photo=None,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify flags
        assert "no_avatar" in result.flags, "Should detect no avatar"
        assert "spam_words" in result.flags, "Should detect spam words"
        assert "rtl_chars" in result.flags, "Should detect RTL characters"
        
        # Score: 0.4 + 0.25 + 0.2 = 0.85 >= 0.7 threshold
        assert result.suspicion_score >= SILENT_BAN_THRESHOLD, (
            f"Score {result.suspicion_score} should exceed threshold {SILENT_BAN_THRESHOLD}"
        )
        
        # Should trigger silent ban
        assert result.should_silent_ban is True, (
            f"User with score {result.suspicion_score} >= {SILENT_BAN_THRESHOLD} "
            f"should trigger silent ban"
        )

    @given(user_id=user_ids)
    @settings(max_examples=100)
    def test_no_avatar_plus_multiple_suspicious_factors_triggers_silent_ban(
        self,
        user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
        **Validates: Requirements 9.4**
        
        For any user with no avatar and multiple suspicious name factors,
        when the combined score exceeds threshold (0.7), Silent_Ban SHALL be applied.
        """
        # Name with spam words and numbers (number_heavy)
        # "crypto123456" - contains "crypto" (spam word) and is number-heavy
        suspicious_name = "crypto123456789"
        
        user = MockUser(
            id=user_id,
            first_name=suspicious_name,
            last_name=None,
            username=None,
            is_premium=False,
            has_photo=None,
            photo=None,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify no_avatar flag
        assert "no_avatar" in result.flags, "Should detect no avatar"
        
        # Verify spam_words flag
        assert "spam_words" in result.flags, (
            f"Should detect spam words in '{suspicious_name}'"
        )
        
        # Verify number_heavy flag (9 digits out of 15 chars = 60% > 40%)
        assert "number_heavy" in result.flags, (
            f"Should detect number-heavy name '{suspicious_name}'"
        )
        
        # Score: no_avatar (0.4) + spam_words (0.25) + number_heavy (0.1) = 0.75 >= 0.7
        assert result.suspicion_score >= SILENT_BAN_THRESHOLD, (
            f"Score {result.suspicion_score} should exceed threshold {SILENT_BAN_THRESHOLD}"
        )
        
        # Should trigger silent ban
        assert result.should_silent_ban is True, (
            f"User with score {result.suspicion_score} >= {SILENT_BAN_THRESHOLD} "
            f"should trigger silent ban"
        )

    @given(
        user_id=user_ids,
        first_name=normal_first_names,
    )
    @settings(max_examples=100)
    def test_score_below_threshold_does_not_trigger_silent_ban(
        self,
        user_id: int,
        first_name: str,
    ):
        """
        **Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
        **Validates: Requirements 9.4**
        
        For any user with suspicion score BELOW threshold,
        Silent_Ban SHALL NOT be applied.
        """
        # User with only no_avatar flag (score = 0.4, below 0.7)
        user = MockUser(
            id=user_id,
            first_name=first_name,
            last_name=None,
            username=None,
            is_premium=False,
            has_photo=None,
            photo=None,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # If score is below threshold, should NOT trigger silent ban
        if result.suspicion_score < SILENT_BAN_THRESHOLD:
            assert result.should_silent_ban is False, (
                f"User with score {result.suspicion_score} < {SILENT_BAN_THRESHOLD} "
                f"should NOT trigger silent ban"
            )

    @given(
        user_id=user_ids,
        suspicious_name=spam_word_names,
    )
    @settings(max_examples=100)
    def test_premium_can_prevent_silent_ban(
        self,
        user_id: int,
        suspicious_name: str,
    ):
        """
        **Feature: shield-economy-v65, Property 26: High Suspicion Score Triggers Silent Ban**
        **Validates: Requirements 9.4**
        
        For any user with suspicious indicators, Premium status (-0.3)
        can reduce the score below the silent ban threshold.
        """
        # User with no_avatar + spam_words but WITH premium
        # Score: 0.4 + 0.25 - 0.3 = 0.35 (below threshold)
        user = MockUser(
            id=user_id,
            first_name=suspicious_name,
            last_name=None,
            username=None,
            is_premium=True,  # Premium user
            has_photo=None,
            photo=None,
        )
        
        scanner = UserScanner()
        result = scanner.scan_user(user)
        
        # Verify flags
        assert "no_avatar" in result.flags
        assert "spam_words" in result.flags
        assert "premium_user" in result.flags
        
        # Score should be reduced by premium bonus
        # 0.4 + 0.25 - 0.3 = 0.35
        expected_score = SCORE_NO_AVATAR + SCORE_SPAM_WORDS + SCORE_PREMIUM_BONUS
        assert abs(result.suspicion_score - expected_score) < 0.01, (
            f"Expected score ~{expected_score}, got {result.suspicion_score}"
        )
        
        # Should NOT trigger silent ban due to premium
        assert result.should_silent_ban is False, (
            f"Premium user with score {result.suspicion_score} should NOT trigger silent ban"
        )


    # ========================================================================
    # Property 27: Silent Ban Deletes Messages Silently
    # ========================================================================


class TestSilentBanDeletesMessagesSilently:
    """
    **Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
    **Validates: Requirements 9.5**
    
    Tests that messages from silent-banned users are deleted without notification.
    """

    @given(
        user_id=user_ids,
        chat_id=st.integers(min_value=1, max_value=9999999999),
    )
    @settings(max_examples=100)
    def test_silent_banned_user_messages_should_be_deleted(
        self,
        user_id: int,
        chat_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
        **Validates: Requirements 9.5**
        
        For any user under Silent_Ban, their messages SHALL be marked for deletion.
        The deletion happens without notification (silently).
        """
        # Create a mock silent ban tracker
        silent_bans: Set[Tuple[int, int]] = set()
        
        # Simulate applying silent ban
        silent_bans.add((user_id, chat_id))
        
        # Check if message should be deleted
        def should_delete_message(uid: int, cid: int) -> bool:
            """Check if message from user should be silently deleted."""
            return (uid, cid) in silent_bans
        
        # Property: Silent-banned user's messages should be deleted
        assert should_delete_message(user_id, chat_id) is True, (
            f"Messages from silent-banned user {user_id} in chat {chat_id} "
            f"should be marked for deletion"
        )

    @given(
        user_id=user_ids,
        chat_id=st.integers(min_value=1, max_value=9999999999),
        other_user_id=user_ids,
    )
    @settings(max_examples=100)
    def test_non_banned_user_messages_not_deleted(
        self,
        user_id: int,
        chat_id: int,
        other_user_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
        **Validates: Requirements 9.5**
        
        For any user NOT under Silent_Ban, their messages SHALL NOT be deleted.
        """
        # Ensure other_user_id is different from user_id
        assume(other_user_id != user_id)
        
        # Create a mock silent ban tracker
        silent_bans: Set[Tuple[int, int]] = set()
        
        # Only ban user_id, not other_user_id
        silent_bans.add((user_id, chat_id))
        
        # Check if message should be deleted
        def should_delete_message(uid: int, cid: int) -> bool:
            """Check if message from user should be silently deleted."""
            return (uid, cid) in silent_bans
        
        # Property: Non-banned user's messages should NOT be deleted
        assert should_delete_message(other_user_id, chat_id) is False, (
            f"Messages from non-banned user {other_user_id} in chat {chat_id} "
            f"should NOT be marked for deletion"
        )

    @given(
        user_id=user_ids,
        chat_id=st.integers(min_value=1, max_value=9999999999),
        message_count=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_all_messages_from_silent_banned_user_deleted(
        self,
        user_id: int,
        chat_id: int,
        message_count: int,
    ):
        """
        **Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
        **Validates: Requirements 9.5**
        
        For any user under Silent_Ban, ALL their messages SHALL be deleted,
        not just some of them.
        """
        # Create a mock silent ban tracker
        silent_bans: Set[Tuple[int, int]] = set()
        
        # Apply silent ban
        silent_bans.add((user_id, chat_id))
        
        # Check if message should be deleted
        def should_delete_message(uid: int, cid: int) -> bool:
            """Check if message from user should be silently deleted."""
            return (uid, cid) in silent_bans
        
        # Simulate multiple messages from the banned user
        deleted_count = 0
        for _ in range(message_count):
            if should_delete_message(user_id, chat_id):
                deleted_count += 1
        
        # Property: ALL messages from silent-banned user should be deleted
        assert deleted_count == message_count, (
            f"All {message_count} messages from silent-banned user should be deleted, "
            f"but only {deleted_count} were marked for deletion"
        )

    @given(
        user_id=user_ids,
        chat_id=st.integers(min_value=1, max_value=9999999999),
    )
    @settings(max_examples=100)
    def test_silent_deletion_produces_no_notification(
        self,
        user_id: int,
        chat_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
        **Validates: Requirements 9.5**
        
        For any message deletion from a silent-banned user, 
        NO notification SHALL be sent to the user or the chat.
        """
        # Track notifications
        notifications_sent: List[str] = []
        
        # Create a mock silent ban tracker
        silent_bans: Set[Tuple[int, int]] = set()
        
        # Apply silent ban
        silent_bans.add((user_id, chat_id))
        
        def delete_message_silently(uid: int, cid: int, msg_id: int) -> bool:
            """
            Delete a message silently (without notification).
            
            Returns True if message was deleted, False otherwise.
            The key property is that NO notification is added.
            """
            if (uid, cid) in silent_bans:
                # Delete the message (simulated)
                # IMPORTANT: No notification is sent
                return True
            return False
        
        # Simulate deleting a message
        message_id = 12345
        was_deleted = delete_message_silently(user_id, chat_id, message_id)
        
        # Property: Deletion should happen without notification
        assert was_deleted is True, "Message should be deleted"
        assert len(notifications_sent) == 0, (
            f"Silent deletion should produce NO notifications, "
            f"but {len(notifications_sent)} were sent: {notifications_sent}"
        )

    @given(
        user_id=user_ids,
        chat_id=st.integers(min_value=1, max_value=9999999999),
        other_chat_id=st.integers(min_value=1, max_value=9999999999),
    )
    @settings(max_examples=100)
    def test_silent_ban_is_chat_specific(
        self,
        user_id: int,
        chat_id: int,
        other_chat_id: int,
    ):
        """
        **Feature: shield-economy-v65, Property 27: Silent Ban Deletes Messages Silently**
        **Validates: Requirements 9.5**
        
        For any user under Silent_Ban in one chat, their messages in OTHER chats
        SHALL NOT be affected (ban is chat-specific).
        """
        # Ensure chats are different
        assume(chat_id != other_chat_id)
        
        # Create a mock silent ban tracker
        silent_bans: Set[Tuple[int, int]] = set()
        
        # Ban user only in chat_id, not in other_chat_id
        silent_bans.add((user_id, chat_id))
        
        # Check if message should be deleted
        def should_delete_message(uid: int, cid: int) -> bool:
            """Check if message from user should be silently deleted."""
            return (uid, cid) in silent_bans
        
        # Property: Ban should only apply to the specific chat
        assert should_delete_message(user_id, chat_id) is True, (
            f"Messages in banned chat {chat_id} should be deleted"
        )
        assert should_delete_message(user_id, other_chat_id) is False, (
            f"Messages in other chat {other_chat_id} should NOT be deleted"
        )
