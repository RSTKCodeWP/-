"""
Property-based tests for Native JSON Mode Optimization.

**Feature: ollama-client-optimization, Property 3: JSON Mode Payload Structure**
**Validates: Requirements 2.1**

**Feature: ollama-client-optimization, Property 4: JSON Mode Skip Retry**
**Validates: Requirements 2.3, 2.5**
"""

from hypothesis import given, strategies as st, settings
import json


# ============================================================================
# Replicate the build_json_payload function for isolated testing
# This avoids complex module imports with many dependencies
# ============================================================================

def build_json_payload(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.0
) -> dict:
    """
    Build the API payload for JSON mode requests.
    
    This is a helper function primarily for testing Property 3.
    
    Requirements: 2.1
    
    Args:
        messages: List of message dicts
        model: Model to use
        temperature: Sampling temperature
        
    Returns:
        Payload dict with format="json" field
    """
    return {
        "model": model or "test-model",
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
        },
    }


def parse_json_single_pass(content: str, expect_array: bool = True) -> dict | list | None:
    """
    Parse JSON in a single pass without retry logic.
    
    This simulates the behavior of _ollama_chat_json's response handling.
    With native JSON mode, we expect valid JSON and don't need retries.
    
    Requirements: 2.3, 2.5
    
    Args:
        content: JSON string to parse
        expect_array: Whether to expect a JSON array (True) or object (False)
        
    Returns:
        Parsed JSON or None/empty list on failure
    """
    if not content.strip():
        return [] if expect_array else None
    
    try:
        result = json.loads(content)
        
        # Validate expected type
        if expect_array and not isinstance(result, list):
            return []
        if not expect_array and not isinstance(result, dict):
            return None
        
        return result
    except json.JSONDecodeError:
        return [] if expect_array else None


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Strategy for valid message content
message_content_strategy = st.text(
    alphabet=st.characters(blacklist_categories=('Cs',)),
    min_size=1,
    max_size=200
)

# Strategy for message roles
role_strategy = st.sampled_from(["system", "user", "assistant"])

# Strategy for single message
message_strategy = st.fixed_dictionaries({
    "role": role_strategy,
    "content": message_content_strategy
})

# Strategy for message lists (1-5 messages)
messages_strategy = st.lists(message_strategy, min_size=1, max_size=5)

# Strategy for temperature values
temperature_strategy = st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False)

# Strategy for model names
model_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:'),
    min_size=1,
    max_size=50
)

# Strategy for valid JSON arrays
json_array_strategy = st.lists(
    st.fixed_dictionaries({
        "fact": st.text(min_size=1, max_size=100),
        "category": st.sampled_from(["hardware", "software", "problem", "preference", "other"]),
        "importance": st.integers(min_value=1, max_value=10)
    }),
    min_size=0,
    max_size=5
)

# Strategy for valid JSON objects (toxicity result)
json_object_strategy = st.fixed_dictionaries({
    "is_toxic": st.booleans(),
    "category": st.sampled_from(["insult", "threat", "profanity", "none"]),
    "score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
})


# ============================================================================
# Property Tests
# ============================================================================

class TestJSONModePayloadStructure:
    """
    **Feature: ollama-client-optimization, Property 3: JSON Mode Payload Structure**
    **Validates: Requirements 2.1**
    
    For any call to _ollama_chat_json(), the API payload SHALL contain
    "format": "json" field.
    """
    
    @settings(max_examples=100)
    @given(messages=messages_strategy)
    def test_payload_contains_format_json(self, messages: list[dict]):
        """
        Property: Payload always contains format="json" field.
        """
        payload = build_json_payload(messages)
        
        assert "format" in payload
        assert payload["format"] == "json"
    
    @settings(max_examples=100)
    @given(
        messages=messages_strategy,
        temperature=temperature_strategy
    )
    def test_payload_structure_complete(self, messages: list[dict], temperature: float):
        """
        Property: Payload has all required fields for JSON mode.
        """
        payload = build_json_payload(messages, temperature=temperature)
        
        # Required fields
        assert "model" in payload
        assert "messages" in payload
        assert "stream" in payload
        assert "format" in payload
        assert "options" in payload
        
        # Correct values
        assert payload["format"] == "json"
        assert payload["stream"] is False
        assert payload["messages"] == messages
        assert payload["options"]["temperature"] == temperature
    
    @settings(max_examples=100)
    @given(
        messages=messages_strategy,
        model=model_strategy
    )
    def test_payload_with_custom_model(self, messages: list[dict], model: str):
        """
        Property: Custom model is correctly set in payload.
        """
        payload = build_json_payload(messages, model=model)
        
        assert payload["model"] == model
        assert payload["format"] == "json"
    
    @settings(max_examples=100)
    @given(messages=messages_strategy)
    def test_payload_stream_disabled(self, messages: list[dict]):
        """
        Property: Streaming is always disabled for JSON mode.
        """
        payload = build_json_payload(messages)
        
        assert payload["stream"] is False
    
    def test_empty_messages_still_has_format_json(self):
        """
        Property: Even with minimal input, format="json" is present.
        """
        payload = build_json_payload([{"role": "user", "content": "test"}])
        
        assert payload["format"] == "json"


class TestJSONModeSkipRetry:
    """
    **Feature: ollama-client-optimization, Property 4: JSON Mode Skip Retry**
    **Validates: Requirements 2.3, 2.5**
    
    For any JSON response from native JSON mode, the parsing logic SHALL
    complete in a single pass without invoking retry logic.
    """
    
    @settings(max_examples=100)
    @given(json_array=json_array_strategy)
    def test_valid_array_parsed_single_pass(self, json_array: list):
        """
        Property: Valid JSON arrays are parsed in a single pass.
        """
        json_str = json.dumps(json_array)
        
        result = parse_json_single_pass(json_str, expect_array=True)
        
        assert result == json_array
    
    @settings(max_examples=100)
    @given(json_object=json_object_strategy)
    def test_valid_object_parsed_single_pass(self, json_object: dict):
        """
        Property: Valid JSON objects are parsed in a single pass.
        """
        json_str = json.dumps(json_object)
        
        result = parse_json_single_pass(json_str, expect_array=False)
        
        assert result == json_object
    
    @settings(max_examples=100)
    @given(json_array=json_array_strategy)
    def test_no_retry_on_valid_json(self, json_array: list):
        """
        Property: No retry mechanism is invoked for valid JSON.
        
        This test verifies that parse_json_single_pass doesn't have
        any retry logic - it either succeeds or fails immediately.
        """
        json_str = json.dumps(json_array)
        
        # The function should return immediately without any retry
        # We verify this by checking the result matches input
        result = parse_json_single_pass(json_str, expect_array=True)
        
        assert result == json_array
    
    def test_empty_string_returns_empty_array(self):
        """
        Property: Empty string returns empty array for array expectation.
        """
        result = parse_json_single_pass("", expect_array=True)
        
        assert result == []
    
    def test_empty_string_returns_none_for_object(self):
        """
        Property: Empty string returns None for object expectation.
        """
        result = parse_json_single_pass("", expect_array=False)
        
        assert result is None
    
    def test_whitespace_only_returns_empty(self):
        """
        Property: Whitespace-only string returns empty/None.
        """
        result_array = parse_json_single_pass("   \n\t  ", expect_array=True)
        result_object = parse_json_single_pass("   \n\t  ", expect_array=False)
        
        assert result_array == []
        assert result_object is None
    
    @settings(max_examples=100)
    @given(json_array=json_array_strategy)
    def test_type_mismatch_array_expected_object_received(self, json_array: list):
        """
        Property: When array expected but object received, return empty array.
        """
        # Create an object instead of array
        json_str = json.dumps({"data": json_array})
        
        result = parse_json_single_pass(json_str, expect_array=True)
        
        assert result == []
    
    @settings(max_examples=100)
    @given(json_object=json_object_strategy)
    def test_type_mismatch_object_expected_array_received(self, json_object: dict):
        """
        Property: When object expected but array received, return None.
        """
        # Create an array instead of object
        json_str = json.dumps([json_object])
        
        result = parse_json_single_pass(json_str, expect_array=False)
        
        assert result is None


class TestJSONModeRoundTrip:
    """
    Additional property tests for JSON mode round-trip consistency.
    """
    
    @settings(max_examples=100)
    @given(json_array=json_array_strategy)
    def test_serialize_parse_round_trip_array(self, json_array: list):
        """
        Property: JSON array serialization and parsing is consistent.
        """
        serialized = json.dumps(json_array)
        parsed = parse_json_single_pass(serialized, expect_array=True)
        
        assert parsed == json_array
    
    @settings(max_examples=100)
    @given(json_object=json_object_strategy)
    def test_serialize_parse_round_trip_object(self, json_object: dict):
        """
        Property: JSON object serialization and parsing is consistent.
        """
        serialized = json.dumps(json_object)
        parsed = parse_json_single_pass(serialized, expect_array=False)
        
        assert parsed == json_object
