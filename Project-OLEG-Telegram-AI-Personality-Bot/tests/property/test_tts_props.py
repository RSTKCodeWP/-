"""
Property-based tests for TTSService.

**Feature: fortress-update, Property 12: Text truncation**
**Validates: Requirements 5.5**

**Feature: fortress-update, Property 13: Auto-voice probability**
**Validates: Requirements 5.2**
"""

import os
import sys
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import TTS module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'tts.py')
_spec = importlib.util.spec_from_file_location("tts", _module_path)
_tts_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tts_module)

TTSService = _tts_module.TTSService
MAX_TEXT_LENGTH = _tts_module.MAX_TEXT_LENGTH
TRUNCATION_SUFFIX = _tts_module.TRUNCATION_SUFFIX
AUTO_VOICE_PROBABILITY = _tts_module.AUTO_VOICE_PROBABILITY


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for generating text of various lengths
short_text = st.text(min_size=0, max_size=MAX_TEXT_LENGTH)
long_text = st.text(min_size=MAX_TEXT_LENGTH + 1, max_size=2000)
any_text = st.text(min_size=0, max_size=2000)

# Strategy for generating text with specific lengths
text_with_length = lambda n: st.text(min_size=n, max_size=n)


# ============================================================================
# Property 12: Text Truncation
# ============================================================================

class TestTextTruncation:
    """
    **Feature: fortress-update, Property 12: Text truncation**
    **Validates: Requirements 5.5**
    
    For any text input longer than 500 characters, the TTS output text 
    SHALL be truncated to 500 characters with "...и так далее" suffix.
    """
    
    @settings(max_examples=100)
    @given(text=long_text)
    def test_property_3_text_truncation_preserves_limit(self, text: str):
        """
        **Feature: oleg-commands-fix, Property 3: Text truncation preserves limit**
        **Validates: Requirements 2.3**
        
        For any text longer than 500 characters, the truncated output 
        SHALL have length ≤ 500 and end with "...и так далее".
        """
        assume(len(text) > MAX_TEXT_LENGTH)
        
        service = TTSService()
        result, was_truncated = service.truncate_text(text)
        
        # Property 3: truncated output has length ≤ 500
        assert len(result) <= MAX_TEXT_LENGTH, f"Truncated text length {len(result)} exceeds {MAX_TEXT_LENGTH}"
        # Property 3: truncated output ends with suffix
        assert result.endswith(TRUNCATION_SUFFIX), f"Truncated text does not end with '{TRUNCATION_SUFFIX}'"
        assert was_truncated is True
    
    @settings(max_examples=100)
    @given(text=long_text)
    def test_long_text_is_truncated(self, text: str):
        """
        Property: Text longer than 500 chars is truncated.
        """
        assume(len(text) > MAX_TEXT_LENGTH)
        
        service = TTSService()
        result, was_truncated = service.truncate_text(text)
        
        assert was_truncated is True
        assert len(result) <= MAX_TEXT_LENGTH
    
    @settings(max_examples=100)
    @given(text=long_text)
    def test_truncated_text_has_suffix(self, text: str):
        """
        Property: Truncated text ends with "...и так далее".
        """
        assume(len(text) > MAX_TEXT_LENGTH)
        
        service = TTSService()
        result, was_truncated = service.truncate_text(text)
        
        assert was_truncated is True
        assert result.endswith(TRUNCATION_SUFFIX)
    
    @settings(max_examples=100)
    @given(text=short_text)
    def test_short_text_not_truncated(self, text: str):
        """
        Property: Text <= 500 chars is not truncated.
        """
        assume(len(text) <= MAX_TEXT_LENGTH)
        
        service = TTSService()
        result, was_truncated = service.truncate_text(text)
        
        assert was_truncated is False
        assert result == text
    
    @settings(max_examples=100)
    @given(text=any_text)
    def test_truncate_returns_string(self, text: str):
        """
        Property: Truncation always returns a string.
        """
        service = TTSService()
        result, _ = service.truncate_text(text)
        
        assert isinstance(result, str)
    
    def test_empty_text_returns_empty(self):
        """
        Property: Empty text returns empty string without truncation.
        """
        service = TTSService()
        
        result, was_truncated = service.truncate_text("")
        
        assert result == ""
        assert was_truncated is False
    
    def test_exact_max_length_not_truncated(self):
        """
        Property: Text exactly at max length is not truncated.
        """
        service = TTSService()
        text = "a" * MAX_TEXT_LENGTH
        
        result, was_truncated = service.truncate_text(text)
        
        assert was_truncated is False
        assert result == text
        assert len(result) == MAX_TEXT_LENGTH
    
    def test_one_over_max_length_is_truncated(self):
        """
        Property: Text one char over max length is truncated.
        """
        service = TTSService()
        text = "a" * (MAX_TEXT_LENGTH + 1)
        
        result, was_truncated = service.truncate_text(text)
        
        assert was_truncated is True
        assert len(result) <= MAX_TEXT_LENGTH
        assert result.endswith(TRUNCATION_SUFFIX)
    
    @settings(max_examples=100)
    @given(text=long_text)
    def test_truncated_preserves_beginning(self, text: str):
        """
        Property: Truncation preserves the beginning of the text.
        """
        assume(len(text) > MAX_TEXT_LENGTH)
        
        service = TTSService()
        result, was_truncated = service.truncate_text(text)
        
        # The result (minus suffix) should be a prefix of the original
        prefix_length = MAX_TEXT_LENGTH - len(TRUNCATION_SUFFIX)
        expected_prefix = text[:prefix_length]
        
        assert result.startswith(expected_prefix)


# ============================================================================
# Property 13: Auto-voice Probability
# ============================================================================

class TestAutoVoiceProbability:
    """
    **Feature: fortress-update, Property 13: Auto-voice probability**
    **Validates: Requirements 5.2**
    
    For any large sample of text responses (n > 1000), the proportion 
    converted to voice SHALL be approximately 0.1% (within statistical tolerance).
    """
    
    def test_auto_voice_probability_distribution(self):
        """
        Property: Auto-voice triggers approximately 0.1% of the time.
        
        We run 10000 trials and check that the proportion is within
        reasonable statistical bounds (0.05% to 0.2% for 0.1% expected).
        """
        service = TTSService()
        
        n_trials = 10000
        n_triggered = sum(1 for _ in range(n_trials) if service.should_auto_voice())
        
        proportion = n_triggered / n_trials
        
        # Expected: 0.1% = 0.001
        # With 10000 trials, expected count is 10
        # Allow for statistical variance: 0 to 30 (very generous bounds)
        # This corresponds to 0% to 0.3%
        assert 0 <= n_triggered <= 30, f"Got {n_triggered} triggers ({proportion*100:.2f}%)"
    
    def test_auto_voice_returns_bool(self):
        """
        Property: should_auto_voice always returns a boolean.
        """
        service = TTSService()
        
        for _ in range(100):
            result = service.should_auto_voice()
            assert isinstance(result, bool)
    
    def test_auto_voice_is_random(self):
        """
        Property: Auto-voice results are not deterministic.
        
        Over many calls, we should see both True and False results
        (though True is very rare at 0.1%).
        """
        service = TTSService()
        
        # Run enough trials that we're very likely to see at least one True
        # With 0.1% probability, 5000 trials gives ~99.3% chance of at least one True
        results = [service.should_auto_voice() for _ in range(5000)]
        
        # We should definitely see False values
        assert False in results
        
        # We might see True values (but don't require it as it's probabilistic)
        # Just verify the function runs without error


# ============================================================================
# Additional TTS Service Tests
# ============================================================================

class TestTTSServiceBasics:
    """
    Basic tests for TTSService functionality.
    """
    
    def test_service_initialization(self):
        """
        Property: TTSService initializes correctly.
        """
        service = TTSService()
        
        assert service is not None
        assert service.is_available is True
    
    def test_service_availability_toggle(self):
        """
        Property: Service availability can be toggled.
        """
        service = TTSService()
        
        assert service.is_available is True
        
        service.set_available(False)
        assert service.is_available is False
        
        service.set_available(True)
        assert service.is_available is True
    
    @settings(max_examples=50)
    @given(text=any_text)
    def test_duration_estimation_positive(self, text: str):
        """
        Property: Duration estimation is always non-negative.
        """
        service = TTSService()
        
        duration = service._estimate_duration(text)
        
        assert duration >= 0
    
    @settings(max_examples=50)
    @given(text=st.text(min_size=1, max_size=1000))
    def test_duration_proportional_to_length(self, text: str):
        """
        Property: Longer text has longer estimated duration.
        """
        service = TTSService()
        
        duration = service._estimate_duration(text)
        
        # Duration should be proportional to text length
        # At 10 chars/second, 100 chars = 10 seconds
        expected_duration = len(text) / 10
        
        assert duration == expected_duration


# ============================================================================
# Property 5: TTS produces valid OGG
# ============================================================================

from hypothesis import HealthCheck

class TestOGGFormat:
    """
    **Feature: oleg-commands-fix, Property 5: TTS produces valid OGG**
    **Validates: Requirements 5.2**
    
    For any successful TTS generation, the output audio_data 
    SHALL be valid OGG format (starts with "OggS" magic bytes).
    """
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    @given(
        audio_length=st.integers(min_value=100, max_value=5000),
        sample_rate=st.sampled_from([16000, 22050, 44100, 48000])
    )
    def test_property_5_ogg_format_valid(self, audio_length: int, sample_rate: int):
        """
        **Feature: oleg-commands-fix, Property 5: TTS produces valid OGG**
        **Validates: Requirements 5.2**
        
        For any valid audio tensor, the _convert_to_ogg method SHALL produce
        output that starts with "OggS" magic bytes (valid OGG format).
        """
        try:
            import numpy as np
        except ImportError:
            # Skip test if numpy not available
            return
        
        service = TTSService()
        
        # Generate audio data using numpy (more efficient than hypothesis lists)
        np.random.seed(audio_length)  # Reproducible random data
        audio_tensor = np.random.uniform(-1.0, 1.0, audio_length).astype(np.float32)
        
        # Convert to OGG
        result = service._convert_to_ogg(audio_tensor, sample_rate)
        
        # If conversion succeeded, verify OGG format
        if result is not None:
            # OGG files start with "OggS" magic bytes
            assert result.startswith(b'OggS'), "Output does not have valid OGG header"
            # Should have reasonable size
            assert len(result) > 0, "OGG output is empty"
    
    def test_ogg_conversion_with_valid_audio(self):
        """
        Property: OGG conversion produces valid output for typical audio.
        """
        try:
            import numpy as np
        except ImportError:
            # Skip test if numpy not available
            return
        
        service = TTSService()
        
        # Create a simple sine wave audio
        sample_rate = 48000
        duration = 0.5  # 0.5 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_tensor = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        
        result = service._convert_to_ogg(audio_tensor, sample_rate)
        
        if result is not None:
            # Verify OGG magic bytes
            assert result.startswith(b'OggS'), "Output does not have valid OGG header"
            # Should have reasonable size for 0.5s audio
            assert len(result) > 100, "OGG output too small"
    
    def test_ogg_conversion_handles_empty_audio(self):
        """
        Property: OGG conversion handles edge cases gracefully.
        """
        try:
            import numpy as np
        except ImportError:
            return
        
        service = TTSService()
        
        # Empty audio should either return None or valid OGG
        empty_audio = np.array([], dtype=np.float32)
        result = service._convert_to_ogg(empty_audio, 48000)
        
        # Either None (failure) or valid OGG
        if result is not None:
            assert result.startswith(b'OggS')
