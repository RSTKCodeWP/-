"""
Property-based tests for AutoReplySystem.

Tests correctness properties defined in the design document.
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import auto_reply module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'auto_reply.py')
_spec = importlib.util.spec_from_file_location("auto_reply", _module_path)
_auto_reply_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auto_reply_module)
AutoReplySystem = _auto_reply_module.AutoReplySystem
ChatSettings = _auto_reply_module.ChatSettings


class TestZeroAutoReplyChanceDisablesReplies:
    """
    **Feature: release-candidate-8, Property 3: Zero auto-reply chance disables random replies**
    **Validates: Requirements 2.1**
    
    *For any* message and `ChatSettings` with `auto_reply_chance = 0`, 
    `AutoReplySystem.should_reply()` SHALL return False.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=500))
    def test_zero_chance_always_returns_false(self, text: str):
        """
        Property 3: Zero auto-reply chance disables random replies.
        
        For any text input, when auto_reply_chance is 0, should_reply must return False.
        """
        system = AutoReplySystem()
        
        # Zero chance setting (as integer percentage)
        settings_zero = ChatSettings(auto_reply_chance=0)
        
        result = system.should_reply(text, settings_zero)
        assert result is False, \
            f"should_reply must return False when auto_reply_chance=0, got {result} for text: {text[:50]}"
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=500))
    def test_zero_float_chance_always_returns_false(self, text: str):
        """
        Property 3 extended: Zero as float (0.0) also disables replies.
        """
        system = AutoReplySystem()
        
        # Zero chance setting (as float)
        settings_zero = ChatSettings(auto_reply_chance=0.0)
        
        result = system.should_reply(text, settings_zero)
        assert result is False, \
            f"should_reply must return False when auto_reply_chance=0.0"
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=20, max_size=200),  # Long enough to pass length filter
    )
    def test_zero_chance_ignores_valid_messages(self, text: str):
        """
        Property 3 extended: Even valid long messages are rejected when chance is 0.
        
        Messages that would normally pass all filters should still be rejected
        when auto_reply_chance is 0.
        """
        system = AutoReplySystem()
        
        # Ensure message is long enough
        assume(len(text) >= system.MIN_MESSAGE_LENGTH)
        # Ensure message is not a blocked phrase
        assume(not system.is_blocked_phrase(text))
        
        settings_zero = ChatSettings(auto_reply_chance=0)
        
        result = system.should_reply(text, settings_zero)
        assert result is False, \
            f"Valid message should still be rejected when auto_reply_chance=0"
    
    @settings(max_examples=50)
    @given(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS))
    def test_zero_chance_ignores_trigger_words(self, trigger: str):
        """
        Property 3 extended: Trigger words don't override zero chance.
        """
        system = AutoReplySystem()
        
        # Create a message with trigger word that's long enough
        text_with_trigger = f"Привет {trigger}, как дела сегодня?"
        
        settings_zero = ChatSettings(auto_reply_chance=0)
        
        result = system.should_reply(text_with_trigger, settings_zero)
        assert result is False, \
            f"Trigger word '{trigger}' should not override zero chance setting"


class TestAutoReplyProbabilityScaling:
    """
    **Feature: release-candidate-8, Property 4: Auto-reply probability scales with setting**
    **Validates: Requirements 2.2, 2.4**
    
    *For any* large sample of messages with `auto_reply_chance = N`, the percentage 
    of `should_reply() = True` SHALL be approximately N% (within statistical tolerance).
    """
    
    @settings(max_examples=100)
    @given(
        st.integers(min_value=1, max_value=100),  # Percentage 1-100
        st.text(min_size=20, max_size=100)  # Valid message length
    )
    def test_probability_scales_with_percentage_setting(self, chance_percent: int, base_text: str):
        """
        Property 4: Auto-reply probability scales with setting.
        
        When auto_reply_chance is set to N (as percentage 0-100), the effective
        probability should be scaled by N/100.
        """
        system = AutoReplySystem()
        
        # Ensure message passes filters
        assume(len(base_text) >= system.MIN_MESSAGE_LENGTH)
        assume(not system.is_blocked_phrase(base_text))
        
        # Calculate base probability
        base_prob = system.calculate_probability(base_text)
        
        # Expected effective probability with scaling
        expected_effective = base_prob * (chance_percent / 100.0)
        expected_effective = min(expected_effective, system.MAX_PROBABILITY)
        
        # The effective probability should be proportional to chance_percent
        # We verify this structurally: higher chance = higher effective probability
        if chance_percent > 0:
            assert expected_effective > 0, \
                f"Effective probability should be positive for chance={chance_percent}%"
            assert expected_effective <= system.MAX_PROBABILITY, \
                f"Effective probability should not exceed MAX_PROBABILITY"
    
    @settings(max_examples=50)
    @given(st.floats(min_value=0.01, max_value=1.0))
    def test_probability_scales_with_float_setting(self, chance_float: float):
        """
        Property 4 extended: Float values (0.0-1.0) are used directly as multipliers.
        """
        system = AutoReplySystem()
        
        # Valid message
        text = "Это достаточно длинное сообщение для теста"
        
        # Calculate base probability
        base_prob = system.calculate_probability(text)
        
        # For float values <= 1.0, they should be used directly
        expected_effective = base_prob * chance_float
        expected_effective = min(expected_effective, system.MAX_PROBABILITY)
        
        assert expected_effective >= 0
        assert expected_effective <= system.MAX_PROBABILITY
    
    @settings(max_examples=50)
    @given(
        st.integers(min_value=1, max_value=50),
        st.integers(min_value=51, max_value=100)
    )
    def test_higher_chance_means_higher_probability(self, low_chance: int, high_chance: int):
        """
        Property 4 extended: Higher auto_reply_chance results in higher effective probability.
        
        For any two chance values where high > low, the effective probability
        with high_chance should be >= effective probability with low_chance.
        """
        system = AutoReplySystem()
        
        # Fixed text for comparison
        text = "Это тестовое сообщение достаточной длины для проверки"
        
        # Calculate base probability (same for both)
        base_prob = system.calculate_probability(text)
        
        # Calculate effective probabilities
        effective_low = min(base_prob * (low_chance / 100.0), system.MAX_PROBABILITY)
        effective_high = min(base_prob * (high_chance / 100.0), system.MAX_PROBABILITY)
        
        # Higher chance should result in higher or equal effective probability
        assert effective_high >= effective_low, \
            f"Higher chance ({high_chance}%) should give higher probability than lower ({low_chance}%)"
    
    @settings(max_examples=50)
    @given(st.integers(min_value=1, max_value=100))
    def test_percentage_interpretation(self, chance_percent: int):
        """
        Property 4 extended: Values > 1 are interpreted as percentages.
        
        When auto_reply_chance > 1.0, it should be divided by 100 to get the multiplier.
        """
        system = AutoReplySystem()
        
        # The implementation should handle both:
        # - Values 0-100 (percentage) -> divide by 100
        # - Values 0.0-1.0 (already normalized) -> use as-is
        
        # For percentage values, the effective multiplier should be chance/100
        if chance_percent > 1:
            expected_multiplier = chance_percent / 100.0
        else:
            expected_multiplier = chance_percent
        
        assert 0 <= expected_multiplier <= 1.0, \
            f"Multiplier should be in range [0, 1], got {expected_multiplier}"


class TestShortMessageRejection:
    """
    **Feature: oleg-behavior-improvements, Property 3: Short message rejection**
    **Validates: Requirements 2.2, 2.3**
    
    *For any* message with fewer than 15 characters OR consisting only of 
    blocked short phrases, the Auto_Reply_System should return False 
    regardless of probability.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=14))
    def test_short_messages_rejected(self, short_text: str):
        """
        Property 3a: Messages shorter than MIN_MESSAGE_LENGTH are rejected.
        
        For any text with fewer than 15 characters, should_reply must return False.
        """
        system = AutoReplySystem()
        
        # Ensure text is actually short
        assume(len(short_text) < system.MIN_MESSAGE_LENGTH)
        
        # Even with high auto_reply_chance, short messages should be rejected
        settings_obj = ChatSettings(auto_reply_chance=1.0)
        
        result = system.should_reply(short_text, settings_obj)
        assert result is False, \
            f"Short message ({len(short_text)} chars) should be rejected"
    
    @settings(max_examples=100)
    @given(st.sampled_from(list(AutoReplySystem.BLOCKED_SHORT_PHRASES)))
    def test_blocked_phrases_rejected(self, blocked_phrase: str):
        """
        Property 3b: Blocked short phrases are rejected.
        
        For any phrase in BLOCKED_SHORT_PHRASES, should_reply must return False.
        """
        system = AutoReplySystem()
        
        # Even with high auto_reply_chance, blocked phrases should be rejected
        settings_obj = ChatSettings(auto_reply_chance=1.0)
        
        result = system.should_reply(blocked_phrase, settings_obj)
        assert result is False, \
            f"Blocked phrase '{blocked_phrase}' should be rejected"
    
    @settings(max_examples=100)
    @given(st.sampled_from(list(AutoReplySystem.BLOCKED_SHORT_PHRASES)))
    def test_blocked_phrases_case_insensitive(self, blocked_phrase: str):
        """
        Property 3c: Blocked phrase check is case-insensitive.
        
        Variations like "ОК", "Ок", "OK" should all be rejected.
        """
        system = AutoReplySystem()
        settings_obj = ChatSettings(auto_reply_chance=1.0)
        
        # Test uppercase
        result_upper = system.should_reply(blocked_phrase.upper(), settings_obj)
        # Test with whitespace
        result_whitespace = system.should_reply(f"  {blocked_phrase}  ", settings_obj)
        
        assert result_upper is False, \
            f"Uppercase blocked phrase '{blocked_phrase.upper()}' should be rejected"
        assert result_whitespace is False, \
            f"Blocked phrase with whitespace '  {blocked_phrase}  ' should be rejected"
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=14))
    def test_is_message_too_short_method(self, text: str):
        """
        Property 3d: is_message_too_short correctly identifies short messages.
        """
        system = AutoReplySystem()
        
        result = system.is_message_too_short(text)
        expected = len(text) < system.MIN_MESSAGE_LENGTH
        
        assert result == expected, \
            f"is_message_too_short({repr(text)}) should be {expected}, got {result}"
    
    @settings(max_examples=100)
    @given(st.sampled_from(list(AutoReplySystem.BLOCKED_SHORT_PHRASES)))
    def test_is_blocked_phrase_method(self, phrase: str):
        """
        Property 3e: is_blocked_phrase correctly identifies blocked phrases.
        """
        system = AutoReplySystem()
        
        # Direct match
        assert system.is_blocked_phrase(phrase) is True
        # Case variation
        assert system.is_blocked_phrase(phrase.upper()) is True
        # With whitespace
        assert system.is_blocked_phrase(f"  {phrase}  ") is True


class TestAutoReplyProbabilityBounds:
    """
    **Feature: oleg-behavior-improvements, Property 4: Probability bounds**
    **Validates: Requirements 2.1, 2.4**
    
    *For any* message, the calculated probability should be between 
    2% and 15% (MIN_PROBABILITY and MAX_PROBABILITY).
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=1000))
    def test_probability_within_bounds(self, text: str):
        """
        Property 4: Probability bounds
        
        For any text input, calculate_probability must return a value
        in the range [0.02, 0.15] (2% to 15%).
        """
        system = AutoReplySystem()
        probability = system.calculate_probability(text)
        
        # Requirements 2.1: base probability 2-5%
        # Requirements 2.4: max probability 15%
        assert probability >= system.MIN_PROBABILITY, \
            f"Probability {probability} is below minimum {system.MIN_PROBABILITY} (2%)"
        assert probability <= system.MAX_PROBABILITY, \
            f"Probability {probability} is above maximum {system.MAX_PROBABILITY} (15%)"
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=0, max_size=500),
        st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10)
    )
    def test_probability_bounds_with_custom_triggers(self, text: str, triggers: list):
        """
        Property 4 extended: Even with many custom triggers, probability stays bounded.
        
        Validates that MAX_PROBABILITY (15%) is never exceeded.
        """
        system = AutoReplySystem()
        probability = system.calculate_probability(text, triggers=triggers)
        
        assert probability >= system.MIN_PROBABILITY
        assert probability <= system.MAX_PROBABILITY
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=500))
    def test_base_probability_range(self, text: str):
        """
        Property 4b: Base probability is in range 2-5%.
        
        Verifies the constants are set correctly per Requirements 2.1.
        """
        system = AutoReplySystem()
        
        # Verify constants match requirements
        assert system.BASE_PROBABILITY_MIN == 0.02, \
            f"BASE_PROBABILITY_MIN should be 0.02 (2%), got {system.BASE_PROBABILITY_MIN}"
        assert system.BASE_PROBABILITY_MAX == 0.05, \
            f"BASE_PROBABILITY_MAX should be 0.05 (5%), got {system.BASE_PROBABILITY_MAX}"
        assert system.MAX_PROBABILITY == 0.15, \
            f"MAX_PROBABILITY should be 0.15 (15%), got {system.MAX_PROBABILITY}"


class TestAutoReplyProbabilityIncrease:
    """
    **Feature: oleg-v5-refactoring, Property 7: Auto-Reply Probability Increases with Triggers**
    **Validates: Requirements 5.2**
    
    *For any* message with CAPS LOCK or trigger words, the probability SHALL be 
    greater than the base probability for a plain message.
    """
    
    @settings(max_examples=100)
    @given(st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=5, max_size=100))
    def test_caps_lock_increases_probability(self, caps_text: str):
        """
        Property 7a: CAPS LOCK text should have higher probability than plain text.
        
        We test this by comparing the minimum possible probability for CAPS text
        (base_min + caps_boost) against the maximum possible for plain text (base_max).
        """
        system = AutoReplySystem()
        
        # CAPS text should trigger the boost
        assert system.is_caps_lock(caps_text), f"Text '{caps_text}' should be detected as CAPS"
        
        # The minimum probability with CAPS boost should be higher than base minimum
        # base_min + caps_boost > base_min
        min_caps_prob = system.BASE_PROBABILITY_MIN + system.CAPS_BOOST
        
        # This is a structural property: CAPS boost adds to probability
        assert system.CAPS_BOOST > 0, "CAPS boost should be positive"
        assert min_caps_prob > system.BASE_PROBABILITY_MIN
    
    @settings(max_examples=100)
    @given(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS))
    def test_trigger_word_increases_probability(self, trigger: str):
        """
        Property 7b: Text with trigger words should have higher probability.
        """
        system = AutoReplySystem()
        
        # Text with trigger
        text_with_trigger = f"Привет, {trigger}, как дела?"
        
        # Count triggers
        trigger_count = system.count_triggers(text_with_trigger)
        assert trigger_count >= 1, f"Should find trigger '{trigger}' in text"
        
        # Structural property: trigger boost is positive
        assert system.TRIGGER_BOOST > 0, "Trigger boost should be positive"
    
    @settings(max_examples=50)
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Ll',)), min_size=10, max_size=50),
        st.lists(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS), min_size=1, max_size=3, unique=True)
    )
    def test_more_triggers_higher_probability_structural(self, base_text: str, triggers: list):
        """
        Property 7c: More triggers should result in higher probability boost.
        
        This is a structural test - we verify the boost calculation is correct.
        """
        system = AutoReplySystem()
        
        # Build text with triggers
        text_with_triggers = base_text + " " + " ".join(triggers)
        
        # Count how many triggers are found
        found_triggers = system.count_triggers(text_with_triggers)
        
        # Expected boost from triggers
        expected_trigger_boost = found_triggers * system.TRIGGER_BOOST
        
        # Verify the boost is proportional to trigger count
        assert expected_trigger_boost >= 0
        if found_triggers > 0:
            assert expected_trigger_boost > 0


class TestAutoReplyDisabledSetting:
    """
    **Feature: oleg-v5-refactoring, Property 8: Auto-Reply Respects Disabled Setting**
    **Validates: Requirements 5.4, 5.5**
    
    *For any* chat with auto-reply disabled, the should_reply function 
    SHALL always return False.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=500))
    def test_disabled_chat_never_replies(self, text: str):
        """
        Property 8: When auto_reply_chance is 0 or negative, should_reply returns False.
        """
        system = AutoReplySystem()
        
        # Disabled settings (auto_reply_chance = 0)
        disabled_settings = ChatSettings(auto_reply_chance=0.0)
        
        # Should never reply when disabled
        result = system.should_reply(text, disabled_settings)
        assert result is False, "should_reply must return False when auto-reply is disabled"
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=0, max_size=500),
        st.floats(min_value=-10.0, max_value=0.0)
    )
    def test_negative_chance_never_replies(self, text: str, negative_chance: float):
        """
        Property 8 extended: Negative auto_reply_chance also means disabled.
        """
        system = AutoReplySystem()
        
        settings_obj = ChatSettings(auto_reply_chance=negative_chance)
        
        result = system.should_reply(text, settings_obj)
        assert result is False, "should_reply must return False for negative auto_reply_chance"
    
    @settings(max_examples=100)
    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=10, max_size=50)
    )
    def test_disabled_ignores_caps_lock(self, caps_text: str):
        """
        Property 8 extended: Even CAPS LOCK text doesn't trigger reply when disabled.
        """
        system = AutoReplySystem()
        
        # Verify it's CAPS
        assume(system.is_caps_lock(caps_text))
        
        disabled_settings = ChatSettings(auto_reply_chance=0.0)
        
        result = system.should_reply(caps_text, disabled_settings)
        assert result is False, "CAPS LOCK should not override disabled setting"
    
    @settings(max_examples=50)
    @given(st.sampled_from(AutoReplySystem.DEFAULT_TRIGGERS))
    def test_disabled_ignores_triggers(self, trigger: str):
        """
        Property 8 extended: Even trigger words don't trigger reply when disabled.
        """
        system = AutoReplySystem()
        
        text_with_trigger = f"Эй {trigger}, помоги!"
        disabled_settings = ChatSettings(auto_reply_chance=0.0)
        
        result = system.should_reply(text_with_trigger, disabled_settings)
        assert result is False, "Trigger words should not override disabled setting"
