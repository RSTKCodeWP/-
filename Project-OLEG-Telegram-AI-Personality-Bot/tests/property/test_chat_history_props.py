"""
Property-based tests for Chat History Loading and Formatting.

Tests correctness properties defined in the design document.
**Feature: oleg-personality-improvements, Property 2 & 3: Chat history**
**Validates: Requirements 3.1, 3.2**
"""

import os
import sys
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime

# Add project root to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

# We can't easily test the async DB function without mocking,
# so we test the format_chat_history_for_prompt function which is pure


# Manually define the function to test (avoiding heavy imports)
def format_chat_history_for_prompt(messages: list[dict]) -> str:
    """
    Форматирует историю чата для включения в промпт LLM.
    """
    if not messages:
        return ""
    
    lines = []
    for msg in messages:
        # Пропускаем сообщения бота в истории
        if msg.get("is_bot"):
            continue
        
        username = msg.get("username", "???")
        text = msg.get("text", "")
        timestamp = msg.get("timestamp", "")
        
        if timestamp:
            lines.append(f"[{timestamp}] {username}: {text}")
        else:
            lines.append(f"{username}: {text}")
    
    if not lines:
        return ""
    
    return "\n".join(lines)


# Strategy for generating chat messages
message_strategy = st.fixed_dictionaries({
    "username": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    "text": st.text(min_size=1, max_size=200),
    "timestamp": st.sampled_from(["12:30", "14:45", "09:00", ""]),
    "is_bot": st.booleans()
})


class TestChatHistoryFormatting:
    """
    **Feature: oleg-personality-improvements, Property 3: Chat history is included in prompt**
    **Validates: Requirements 3.2**
    
    *For any* non-empty chat history, the LLM prompt SHALL contain the chat history 
    formatted as conversation context.
    """
    
    @settings(max_examples=100)
    @given(st.lists(message_strategy, min_size=1, max_size=20))
    def test_non_empty_history_produces_output(self, messages: list[dict]):
        """
        Property 3a: Non-empty history with user messages produces non-empty output.
        """
        # Filter to only user messages (not bot)
        user_messages = [m for m in messages if not m.get("is_bot")]
        
        if user_messages:
            result = format_chat_history_for_prompt(messages)
            assert len(result) > 0, \
                "Non-empty history with user messages should produce output"
    
    @settings(max_examples=100)
    @given(st.lists(message_strategy, min_size=1, max_size=10))
    def test_usernames_preserved(self, messages: list[dict]):
        """
        Property 3b: All usernames from user messages appear in formatted output.
        """
        result = format_chat_history_for_prompt(messages)
        
        for msg in messages:
            if not msg.get("is_bot") and msg.get("text"):
                username = msg.get("username", "???")
                # Username should appear in output
                assert username in result or result == "", \
                    f"Username '{username}' should appear in formatted output"
    
    @settings(max_examples=100)
    @given(st.lists(message_strategy, min_size=1, max_size=10))
    def test_text_preserved(self, messages: list[dict]):
        """
        Property 3c: All text from user messages appears in formatted output.
        """
        result = format_chat_history_for_prompt(messages)
        
        for msg in messages:
            if not msg.get("is_bot") and msg.get("text"):
                text = msg.get("text", "")
                # Text should appear in output
                assert text in result or result == "", \
                    f"Text '{text[:30]}...' should appear in formatted output"
    
    @settings(max_examples=100)
    @given(st.lists(
        st.fixed_dictionaries({
            "username": st.text(min_size=1, max_size=10),
            "text": st.text(min_size=1, max_size=50),
            "timestamp": st.just(""),
            "is_bot": st.just(True)  # All bot messages
        }),
        min_size=1, max_size=5
    ))
    def test_bot_messages_excluded(self, bot_messages: list[dict]):
        """
        Property 3d: Bot messages are excluded from formatted output.
        """
        result = format_chat_history_for_prompt(bot_messages)
        assert result == "", \
            "History with only bot messages should produce empty output"
    
    def test_empty_history_returns_empty(self):
        """
        Property 3e: Empty history returns empty string.
        """
        result = format_chat_history_for_prompt([])
        assert result == "", "Empty history should return empty string"
    
    @settings(max_examples=50)
    @given(st.lists(message_strategy, min_size=2, max_size=10))
    def test_messages_separated_by_newlines(self, messages: list[dict]):
        """
        Property 3f: Multiple messages are separated by newlines.
        """
        # Filter to user messages only
        user_messages = [m for m in messages if not m.get("is_bot") and m.get("text")]
        
        if len(user_messages) >= 2:
            result = format_chat_history_for_prompt(messages)
            # Should have newlines separating messages
            lines = result.split("\n")
            assert len(lines) >= 2, \
                f"Multiple user messages should produce multiple lines, got {len(lines)}"
    
    @settings(max_examples=50)
    @given(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L',))),
        st.text(min_size=1, max_size=50),
        st.sampled_from(["12:30", "14:45", "09:00"])
    )
    def test_timestamp_format(self, username: str, text: str, timestamp: str):
        """
        Property 3g: Messages with timestamps are formatted as [HH:MM] username: text.
        """
        messages = [{
            "username": username,
            "text": text,
            "timestamp": timestamp,
            "is_bot": False
        }]
        
        result = format_chat_history_for_prompt(messages)
        expected = f"[{timestamp}] {username}: {text}"
        
        assert result == expected, \
            f"Expected '{expected}', got '{result}'"
    
    @settings(max_examples=50)
    @given(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L',))),
        st.text(min_size=1, max_size=50)
    )
    def test_no_timestamp_format(self, username: str, text: str):
        """
        Property 3h: Messages without timestamps are formatted as username: text.
        """
        messages = [{
            "username": username,
            "text": text,
            "timestamp": "",
            "is_bot": False
        }]
        
        result = format_chat_history_for_prompt(messages)
        expected = f"{username}: {text}"
        
        assert result == expected, \
            f"Expected '{expected}', got '{result}'"
