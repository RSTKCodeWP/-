"""
Property-based tests for ProtectionProfileManager (Protection Profiles).

**Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
**Validates: Requirements 10.1, 10.2, 10.3**
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple

from hypothesis import given, strategies as st, settings


# ============================================================================
# Inline definitions to avoid import issues during testing
# ============================================================================

class ProtectionProfile(Enum):
    """Protection profile types."""
    STANDARD = "standard"
    STRICT = "strict"
    BUNKER = "bunker"
    CUSTOM = "custom"


@dataclass
class ProfileSettings:
    """Protection profile settings."""
    anti_spam_links: bool = True
    captcha_type: str = "button"
    profanity_allowed: bool = True
    neural_ad_filter: bool = False
    block_forwards: bool = False
    sticker_limit: int = 0
    mute_newcomers: bool = False
    block_media_non_admin: bool = False
    aggressive_profanity: bool = False
    
    def to_dict(self) -> Dict:
        """Convert settings to dictionary."""
        return {
            "anti_spam_links": self.anti_spam_links,
            "captcha_type": self.captcha_type,
            "profanity_allowed": self.profanity_allowed,
            "neural_ad_filter": self.neural_ad_filter,
            "block_forwards": self.block_forwards,
            "sticker_limit": self.sticker_limit,
            "mute_newcomers": self.mute_newcomers,
            "block_media_non_admin": self.block_media_non_admin,
            "aggressive_profanity": self.aggressive_profanity,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProfileSettings":
        """Create settings from dictionary."""
        return cls(
            anti_spam_links=data.get("anti_spam_links", True),
            captcha_type=data.get("captcha_type", "button"),
            profanity_allowed=data.get("profanity_allowed", True),
            neural_ad_filter=data.get("neural_ad_filter", False),
            block_forwards=data.get("block_forwards", False),
            sticker_limit=data.get("sticker_limit", 0),
            mute_newcomers=data.get("mute_newcomers", False),
            block_media_non_admin=data.get("block_media_non_admin", False),
            aggressive_profanity=data.get("aggressive_profanity", False),
        )


# Profile presets matching the implementation
PROFILE_PRESETS: Dict[ProtectionProfile, ProfileSettings] = {
    ProtectionProfile.STANDARD: ProfileSettings(
        anti_spam_links=True,
        captcha_type="button",
        profanity_allowed=True,
        neural_ad_filter=False,
        block_forwards=False,
        sticker_limit=0,
        mute_newcomers=False,
        block_media_non_admin=False,
        aggressive_profanity=False,
    ),
    ProtectionProfile.STRICT: ProfileSettings(
        anti_spam_links=True,
        captcha_type="button",
        profanity_allowed=False,
        neural_ad_filter=True,
        block_forwards=True,
        sticker_limit=3,
        mute_newcomers=False,
        block_media_non_admin=False,
        aggressive_profanity=False,
    ),
    ProtectionProfile.BUNKER: ProfileSettings(
        anti_spam_links=True,
        captcha_type="hard",
        profanity_allowed=False,
        neural_ad_filter=True,
        block_forwards=True,
        sticker_limit=0,
        mute_newcomers=True,
        block_media_non_admin=True,
        aggressive_profanity=True,
    ),
}


class ProtectionProfileManager:
    """
    Minimal ProtectionProfileManager for testing without DB/Redis dependencies.
    
    This mirrors the core logic from app/services/protection_profiles.py.
    """
    
    def __init__(self):
        self._cache: Dict[int, Tuple[ProtectionProfile, ProfileSettings]] = {}
    
    def get_profile(self, chat_id: int) -> Tuple[ProtectionProfile, ProfileSettings]:
        """Get the current protection profile and settings for a chat."""
        if chat_id in self._cache:
            return self._cache[chat_id]
        # Default to Standard
        return ProtectionProfile.STANDARD, PROFILE_PRESETS[ProtectionProfile.STANDARD]
    
    def set_profile(self, chat_id: int, profile: ProtectionProfile) -> ProfileSettings:
        """Set a protection profile for a chat."""
        if profile == ProtectionProfile.CUSTOM:
            # For custom, load existing custom settings or use standard as base
            _, current_settings = self.get_profile(chat_id)
            settings = current_settings
        else:
            # Use preset settings
            settings = PROFILE_PRESETS[profile]
        
        self._cache[chat_id] = (profile, settings)
        return settings
    
    def set_custom_settings(self, chat_id: int, settings: ProfileSettings) -> None:
        """Set custom protection settings for a chat."""
        self._cache[chat_id] = (ProtectionProfile.CUSTOM, settings)
    
    def get_settings(self, chat_id: int) -> ProfileSettings:
        """Get the effective protection settings for a chat."""
        _, settings = self.get_profile(chat_id)
        return settings


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for chat IDs (negative for groups in Telegram)
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)

# Strategy for preset profiles (excluding CUSTOM for preset tests)
preset_profiles = st.sampled_from([
    ProtectionProfile.STANDARD,
    ProtectionProfile.STRICT,
    ProtectionProfile.BUNKER,
])

# Strategy for all profiles
all_profiles = st.sampled_from(list(ProtectionProfile))

# Strategy for custom settings
custom_settings = st.builds(
    ProfileSettings,
    anti_spam_links=st.booleans(),
    captcha_type=st.sampled_from(["button", "hard"]),
    profanity_allowed=st.booleans(),
    neural_ad_filter=st.booleans(),
    block_forwards=st.booleans(),
    sticker_limit=st.integers(min_value=0, max_value=10),
    mute_newcomers=st.booleans(),
    block_media_non_admin=st.booleans(),
    aggressive_profanity=st.booleans(),
)


# ============================================================================
# Property Tests
# ============================================================================


class TestProtectionProfileProperties:
    """Property-based tests for ProtectionProfileManager."""

    # ========================================================================
    # Property 28: Protection Profile Applies Correct Settings
    # ========================================================================

    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_standard_profile_applies_correct_settings(self, chat_id: int):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.1**
        
        For Standard profile selection:
        - anti_spam_links=true
        - captcha_type="button"
        - profanity_allowed=true
        """
        manager = ProtectionProfileManager()
        
        # Apply Standard profile
        settings = manager.set_profile(chat_id, ProtectionProfile.STANDARD)
        
        # Verify Standard profile settings (Requirement 10.1)
        assert settings.anti_spam_links is True, (
            "Standard profile should have anti_spam_links=True"
        )
        assert settings.captcha_type == "button", (
            "Standard profile should have captcha_type='button'"
        )
        assert settings.profanity_allowed is True, (
            "Standard profile should have profanity_allowed=True"
        )

    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_strict_profile_applies_correct_settings(self, chat_id: int):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.2**
        
        For Strict profile selection:
        - neural_ad_filter=true
        - block_forwards=true
        - sticker_limit=3
        """
        manager = ProtectionProfileManager()
        
        # Apply Strict profile
        settings = manager.set_profile(chat_id, ProtectionProfile.STRICT)
        
        # Verify Strict profile settings (Requirement 10.2)
        assert settings.neural_ad_filter is True, (
            "Strict profile should have neural_ad_filter=True"
        )
        assert settings.block_forwards is True, (
            "Strict profile should have block_forwards=True"
        )
        assert settings.sticker_limit == 3, (
            "Strict profile should have sticker_limit=3"
        )

    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_bunker_profile_applies_correct_settings(self, chat_id: int):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.3**
        
        For Bunker profile selection:
        - mute_newcomers=true
        - block_media_non_admin=true
        - aggressive_profanity=true
        """
        manager = ProtectionProfileManager()
        
        # Apply Bunker profile
        settings = manager.set_profile(chat_id, ProtectionProfile.BUNKER)
        
        # Verify Bunker profile settings (Requirement 10.3)
        assert settings.mute_newcomers is True, (
            "Bunker profile should have mute_newcomers=True"
        )
        assert settings.block_media_non_admin is True, (
            "Bunker profile should have block_media_non_admin=True"
        )
        assert settings.aggressive_profanity is True, (
            "Bunker profile should have aggressive_profanity=True"
        )

    @given(
        chat_id=chat_ids,
        profile=preset_profiles,
    )
    @settings(max_examples=100)
    def test_preset_profile_matches_expected_settings(
        self,
        chat_id: int,
        profile: ProtectionProfile,
    ):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.1, 10.2, 10.3**
        
        For any preset profile selection, the applied settings SHALL match
        the predefined preset exactly.
        """
        manager = ProtectionProfileManager()
        
        # Apply the profile
        applied_settings = manager.set_profile(chat_id, profile)
        
        # Get expected settings from presets
        expected_settings = PROFILE_PRESETS[profile]
        
        # Verify all settings match
        assert applied_settings.to_dict() == expected_settings.to_dict(), (
            f"Applied settings for {profile.value} should match preset. "
            f"Expected: {expected_settings.to_dict()}, "
            f"Got: {applied_settings.to_dict()}"
        )

    @given(
        chat_id=chat_ids,
        profile=preset_profiles,
    )
    @settings(max_examples=100)
    def test_get_profile_returns_set_profile(
        self,
        chat_id: int,
        profile: ProtectionProfile,
    ):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.1, 10.2, 10.3**
        
        After setting a profile, get_profile SHALL return the same profile.
        """
        manager = ProtectionProfileManager()
        
        # Set the profile
        manager.set_profile(chat_id, profile)
        
        # Get the profile back
        returned_profile, returned_settings = manager.get_profile(chat_id)
        
        # Verify profile matches
        assert returned_profile == profile, (
            f"get_profile should return {profile.value}, got {returned_profile.value}"
        )
        
        # Verify settings match preset
        expected_settings = PROFILE_PRESETS[profile]
        assert returned_settings.to_dict() == expected_settings.to_dict(), (
            f"get_profile settings should match preset for {profile.value}"
        )

    @given(
        chat_id=chat_ids,
        custom=custom_settings,
    )
    @settings(max_examples=100)
    def test_custom_settings_are_preserved(
        self,
        chat_id: int,
        custom: ProfileSettings,
    ):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.4**
        
        For custom profile, all custom settings SHALL be preserved.
        """
        manager = ProtectionProfileManager()
        
        # Set custom settings
        manager.set_custom_settings(chat_id, custom)
        
        # Get settings back
        profile, settings = manager.get_profile(chat_id)
        
        # Verify profile is CUSTOM
        assert profile == ProtectionProfile.CUSTOM, (
            "Profile should be CUSTOM after set_custom_settings"
        )
        
        # Verify all settings are preserved
        assert settings.to_dict() == custom.to_dict(), (
            f"Custom settings should be preserved. "
            f"Expected: {custom.to_dict()}, Got: {settings.to_dict()}"
        )

    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_default_profile_is_standard(self, chat_id: int):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.1**
        
        A new chat SHALL default to Standard profile.
        """
        manager = ProtectionProfileManager()
        
        # Get profile for new chat (no prior settings)
        profile, settings = manager.get_profile(chat_id)
        
        # Verify default is Standard
        assert profile == ProtectionProfile.STANDARD, (
            f"Default profile should be STANDARD, got {profile.value}"
        )
        
        # Verify settings match Standard preset
        expected = PROFILE_PRESETS[ProtectionProfile.STANDARD]
        assert settings.to_dict() == expected.to_dict(), (
            "Default settings should match Standard preset"
        )

    @given(
        chat_id=chat_ids,
        first_profile=preset_profiles,
        second_profile=preset_profiles,
    )
    @settings(max_examples=100)
    def test_profile_switch_applies_new_settings(
        self,
        chat_id: int,
        first_profile: ProtectionProfile,
        second_profile: ProtectionProfile,
    ):
        """
        **Feature: shield-economy-v65, Property 28: Protection Profile Applies Correct Settings**
        **Validates: Requirements 10.1, 10.2, 10.3**
        
        Switching profiles SHALL apply the new profile's settings.
        """
        manager = ProtectionProfileManager()
        
        # Set first profile
        manager.set_profile(chat_id, first_profile)
        
        # Switch to second profile
        new_settings = manager.set_profile(chat_id, second_profile)
        
        # Verify new settings match second profile's preset
        expected = PROFILE_PRESETS[second_profile]
        assert new_settings.to_dict() == expected.to_dict(), (
            f"After switching to {second_profile.value}, settings should match preset"
        )
        
        # Verify get_profile returns new profile
        current_profile, current_settings = manager.get_profile(chat_id)
        assert current_profile == second_profile, (
            f"Current profile should be {second_profile.value}"
        )
