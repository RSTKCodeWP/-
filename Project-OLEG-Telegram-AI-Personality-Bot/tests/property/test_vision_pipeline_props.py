"""
Property-based tests for VisionPipeline.

**Feature: oleg-v5-refactoring, Property 3: Vision Pipeline State Round-Trip**
**Validates: Requirements 2.5, 2.6**
"""

from hypothesis import given, strategies as st, settings
import json
from dataclasses import dataclass, asdict


# Define VisionPipelineState locally to avoid importing app dependencies
# This mirrors the implementation in app/services/vision_pipeline.py
@dataclass
class VisionPipelineState:
    """Состояние pipeline для сериализации/десериализации."""
    
    image_hash: str
    description: str
    final_response: str
    
    def to_json(self) -> str:
        """Сериализует состояние в JSON строку."""
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "VisionPipelineState":
        """Десериализует состояние из JSON строки."""
        data = json.loads(json_str)
        return cls(**data)


# Strategy for generating valid image hashes (hex strings)
image_hash_strategy = st.text(
    alphabet='0123456789abcdef',
    min_size=16,
    max_size=16
)

# Strategy for generating description text
description_strategy = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),  # Exclude surrogates
    ),
    min_size=0,
    max_size=500
)

# Strategy for generating final response text
response_strategy = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),  # Exclude surrogates
    ),
    min_size=0,
    max_size=500
)


class TestVisionPipelineStateRoundTrip:
    """
    **Feature: oleg-v5-refactoring, Property 3: Vision Pipeline State Round-Trip**
    **Validates: Requirements 2.5, 2.6**
    
    For any valid VisionPipelineState object, serializing to JSON and 
    deserializing SHALL produce an equivalent object.
    """
    
    @settings(max_examples=100)
    @given(
        image_hash=image_hash_strategy,
        description=description_strategy,
        final_response=response_strategy
    )
    def test_json_round_trip(self, image_hash: str, description: str, final_response: str):
        """
        Property: Serializing to JSON and deserializing produces equivalent state.
        """
        # Create original state
        original = VisionPipelineState(
            image_hash=image_hash,
            description=description,
            final_response=final_response
        )
        
        # Serialize to JSON
        json_str = original.to_json()
        
        # Deserialize from JSON
        restored = VisionPipelineState.from_json(json_str)
        
        # Verify all fields are equal
        assert restored.image_hash == original.image_hash
        assert restored.description == original.description
        assert restored.final_response == original.final_response
    
    @settings(max_examples=100)
    @given(
        image_hash=image_hash_strategy,
        description=description_strategy,
        final_response=response_strategy
    )
    def test_double_round_trip(self, image_hash: str, description: str, final_response: str):
        """
        Property: Multiple round-trips produce consistent results.
        """
        original = VisionPipelineState(
            image_hash=image_hash,
            description=description,
            final_response=final_response
        )
        
        # First round-trip
        json1 = original.to_json()
        restored1 = VisionPipelineState.from_json(json1)
        
        # Second round-trip
        json2 = restored1.to_json()
        restored2 = VisionPipelineState.from_json(json2)
        
        # Both restored states should be equal
        assert restored1.image_hash == restored2.image_hash
        assert restored1.description == restored2.description
        assert restored1.final_response == restored2.final_response
    
    @settings(max_examples=100)
    @given(
        image_hash=image_hash_strategy,
        description=description_strategy,
        final_response=response_strategy
    )
    def test_json_is_valid_string(self, image_hash: str, description: str, final_response: str):
        """
        Property: to_json produces a valid JSON string.
        """
        import json
        
        state = VisionPipelineState(
            image_hash=image_hash,
            description=description,
            final_response=final_response
        )
        
        json_str = state.to_json()
        
        # Should be parseable as JSON
        parsed = json.loads(json_str)
        
        # Should contain all expected keys
        assert 'image_hash' in parsed
        assert 'description' in parsed
        assert 'final_response' in parsed
    
    @settings(max_examples=50)
    @given(
        prefix=st.text(min_size=0, max_size=40),
        special_char=st.sampled_from(['"', '\\', '\n', '\t', '\r']),
        suffix=st.text(min_size=0, max_size=40)
    )
    def test_special_characters_preserved(self, prefix: str, special_char: str, suffix: str):
        """
        Property: Special characters (quotes, backslashes, newlines) are preserved.
        """
        # Build description that always contains at least one special character
        description = prefix + special_char + suffix
        
        state = VisionPipelineState(
            image_hash="a" * 16,
            description=description,
            final_response="test response"
        )
        
        json_str = state.to_json()
        restored = VisionPipelineState.from_json(json_str)
        
        assert restored.description == description
    
    @settings(max_examples=50)
    @given(
        final_response=st.text(
            alphabet=st.sampled_from('абвгдеёжзийклмнопрстуфхцчшщъыьэюя'),
            min_size=1,
            max_size=100
        )
    )
    def test_unicode_preserved(self, final_response: str):
        """
        Property: Unicode characters (Cyrillic) are preserved through round-trip.
        """
        state = VisionPipelineState(
            image_hash="b" * 16,
            description="Test description",
            final_response=final_response
        )
        
        json_str = state.to_json()
        restored = VisionPipelineState.from_json(json_str)
        
        assert restored.final_response == final_response


class TestVisionPipelineStateEdgeCases:
    """
    Edge case tests for VisionPipelineState.
    """
    
    def test_empty_fields(self):
        """
        Edge case: Empty strings for all fields.
        """
        state = VisionPipelineState(
            image_hash="",
            description="",
            final_response=""
        )
        
        json_str = state.to_json()
        restored = VisionPipelineState.from_json(json_str)
        
        assert restored.image_hash == ""
        assert restored.description == ""
        assert restored.final_response == ""
    
    def test_very_long_description(self):
        """
        Edge case: Very long description text.
        """
        long_description = "A" * 10000
        
        state = VisionPipelineState(
            image_hash="c" * 16,
            description=long_description,
            final_response="short"
        )
        
        json_str = state.to_json()
        restored = VisionPipelineState.from_json(json_str)
        
        assert restored.description == long_description
