"""
Property-based tests for Reply Context Injection.

**Feature: grand-casino-dictator, Property 19: Reply Context Injection**
**Validates: Requirements 14.1, 14.2**

Tests that when a user replies to a message, the original message text
is injected into the AI prompt in the specified format.
"""

from typing import Optional
from dataclasses import dataclass
from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Mock message classes for testing without Telegram dependencies
# ============================================================================

@dataclass
class MockMessage:
    """Mock message for testing reply context injection."""
    text: Optional[str] = None
    caption: Optional[str] = None
    reply_to_message: Optional["MockMessage"] = None


# ============================================================================
# Inline ReplyContextInjector for testing without app dependencies
# ============================================================================

class ReplyContextInjector:
    """
    Инъекция контекста реплая в промпт.
    
    **Property 19: Reply Context Injection**
    **Validates: Requirements 14.1, 14.2**
    """
    
    TEMPLATE = "User replies to: '{original_text}'"
    MAX_CONTEXT_LENGTH = 500
    
    def extract_reply_text(self, message: MockMessage) -> Optional[str]:
        """
        Извлечь текст сообщения на которое отвечают.
        
        **Validates: Requirements 14.1**
        """
        if message is None:
            return None
            
        reply_to = getattr(message, 'reply_to_message', None)
        if reply_to is None:
            return None
            
        original_text = getattr(reply_to, 'text', None)
        if original_text is None:
            original_text = getattr(reply_to, 'caption', None)
            
        if original_text is None:
            return None
            
        if len(original_text) > self.MAX_CONTEXT_LENGTH:
            original_text = original_text[:self.MAX_CONTEXT_LENGTH] + "..."
            
        return original_text
    
    def format_context(self, original_text: str) -> str:
        """
        Format the reply context using the template.
        
        **Validates: Requirements 14.2**
        """
        return self.TEMPLATE.format(original_text=original_text)
    
    def inject(self, message: MockMessage, prompt: str) -> str:
        """
        Добавить контекст реплая в промпт если есть.
        
        **Property 19: Reply Context Injection**
        **Validates: Requirements 14.1, 14.2**
        """
        original_text = self.extract_reply_text(message)
        
        if original_text is None:
            return prompt
            
        context = self.format_context(original_text)
        return f"{context}\n\n{prompt}"


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for non-empty text strings
non_empty_text = st.text(min_size=1, max_size=200).filter(lambda x: x.strip())

# Strategy for prompt text
prompt_text = st.text(min_size=1, max_size=500).filter(lambda x: x.strip())

# Strategy for optional text (can be None or non-empty string)
optional_text = st.one_of(st.none(), non_empty_text)


# ============================================================================
# Property Tests
# ============================================================================


class TestReplyContextInjectionProperties:
    """
    Property-based tests for Reply Context Injection.
    
    **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
    **Validates: Requirements 14.1, 14.2**
    """

    @given(
        original_text=non_empty_text,
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_reply_context_injected_when_reply_exists(
        self,
        original_text: str,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.1, 14.2**
        
        For any message that is a reply to another message with text,
        the original message text SHALL be injected into the AI prompt
        in the format: "User replies to: '{text_of_original_message}'"
        """
        injector = ReplyContextInjector()
        
        # Create a message that is a reply to another message
        original_message = MockMessage(text=original_text)
        reply_message = MockMessage(text="user's reply", reply_to_message=original_message)
        
        # Inject context
        result = injector.inject(reply_message, prompt)
        
        # The result should contain the formatted context
        expected_context = f"User replies to: '{original_text}'"
        
        # Handle truncation for long texts
        if len(original_text) > injector.MAX_CONTEXT_LENGTH:
            truncated_text = original_text[:injector.MAX_CONTEXT_LENGTH] + "..."
            expected_context = f"User replies to: '{truncated_text}'"
        
        assert expected_context in result, (
            f"Reply context MUST be injected in format \"User replies to: '{{text}}'\" "
            f"when message is a reply. Expected context: {expected_context[:50]}... "
            f"Result: {result[:100]}... "
            f"This is required by Requirements 14.1, 14.2."
        )
        
        # The original prompt should also be present
        assert prompt in result, (
            f"Original prompt MUST be preserved after context injection. "
            f"Prompt: {prompt[:50]}... not found in result."
        )

    @given(
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_no_injection_when_no_reply(
        self,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.1, 14.2**
        
        For any message that is NOT a reply to another message,
        the prompt SHALL remain unchanged.
        """
        injector = ReplyContextInjector()
        
        # Create a message that is NOT a reply
        message = MockMessage(text="standalone message", reply_to_message=None)
        
        # Inject context (should not change anything)
        result = injector.inject(message, prompt)
        
        assert result == prompt, (
            f"Prompt MUST remain unchanged when message is not a reply. "
            f"Expected: {prompt}, Got: {result}. "
            f"This is required by Requirements 14.1."
        )

    @given(
        original_text=non_empty_text,
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_context_format_matches_template(
        self,
        original_text: str,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.2**
        
        For any reply context injection, the format SHALL be exactly:
        "User replies to: '{text_of_original_message}'"
        """
        injector = ReplyContextInjector()
        
        # Create a reply message
        original_message = MockMessage(text=original_text)
        reply_message = MockMessage(text="reply", reply_to_message=original_message)
        
        # Inject context
        result = injector.inject(reply_message, prompt)
        
        # Check that the result starts with the expected format
        assert result.startswith("User replies to: '"), (
            f"Injected context MUST start with \"User replies to: '\" "
            f"Got: {result[:50]}... "
            f"This is required by Requirement 14.2."
        )

    @given(
        caption=non_empty_text,
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_caption_used_when_no_text(
        self,
        caption: str,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.1, 14.2**
        
        For any reply to a media message with caption but no text,
        the caption SHALL be used as the reply context.
        """
        injector = ReplyContextInjector()
        
        # Create a media message with caption but no text
        original_message = MockMessage(text=None, caption=caption)
        reply_message = MockMessage(text="reply", reply_to_message=original_message)
        
        # Inject context
        result = injector.inject(reply_message, prompt)
        
        # Handle truncation
        expected_caption = caption
        if len(caption) > injector.MAX_CONTEXT_LENGTH:
            expected_caption = caption[:injector.MAX_CONTEXT_LENGTH] + "..."
        
        expected_context = f"User replies to: '{expected_caption}'"
        
        assert expected_context in result, (
            f"Caption MUST be used as reply context when text is None. "
            f"Expected: {expected_context[:50]}... "
            f"Got: {result[:100]}... "
            f"This is required by Requirements 14.1, 14.2."
        )

    @given(
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_no_injection_when_reply_has_no_content(
        self,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.1**
        
        For any reply to a message with no text and no caption,
        the prompt SHALL remain unchanged.
        """
        injector = ReplyContextInjector()
        
        # Create a message with no text or caption
        original_message = MockMessage(text=None, caption=None)
        reply_message = MockMessage(text="reply", reply_to_message=original_message)
        
        # Inject context (should not change anything)
        result = injector.inject(reply_message, prompt)
        
        assert result == prompt, (
            f"Prompt MUST remain unchanged when reply target has no text/caption. "
            f"Expected: {prompt}, Got: {result}. "
            f"This is required by Requirement 14.1."
        )

    @given(
        original_text=st.text(min_size=600, max_size=1000).filter(lambda x: x.strip()),
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_long_context_truncated(
        self,
        original_text: str,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.1, 14.2**
        
        For any reply context exceeding MAX_CONTEXT_LENGTH,
        the context SHALL be truncated with "..." appended.
        """
        injector = ReplyContextInjector()
        
        # Ensure text is longer than max
        assume(len(original_text) > injector.MAX_CONTEXT_LENGTH)
        
        # Create a reply message with long original text
        original_message = MockMessage(text=original_text)
        reply_message = MockMessage(text="reply", reply_to_message=original_message)
        
        # Inject context
        result = injector.inject(reply_message, prompt)
        
        # The truncated text should end with "..."
        truncated_text = original_text[:injector.MAX_CONTEXT_LENGTH] + "..."
        expected_context = f"User replies to: '{truncated_text}'"
        
        assert expected_context in result, (
            f"Long context MUST be truncated with '...' appended. "
            f"Expected truncated context in result. "
            f"Original length: {len(original_text)}, Max: {injector.MAX_CONTEXT_LENGTH}"
        )

    @given(
        original_text=non_empty_text,
        prompt=prompt_text,
    )
    @settings(max_examples=100)
    def test_extract_reply_text_returns_correct_text(
        self,
        original_text: str,
        prompt: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.1**
        
        For any reply message, extract_reply_text SHALL return the
        text of the original message (possibly truncated).
        """
        injector = ReplyContextInjector()
        
        # Create a reply message
        original_message = MockMessage(text=original_text)
        reply_message = MockMessage(text="reply", reply_to_message=original_message)
        
        # Extract reply text
        extracted = injector.extract_reply_text(reply_message)
        
        assert extracted is not None, (
            f"extract_reply_text MUST return text when reply exists. "
            f"Got None for original text: {original_text[:50]}..."
        )
        
        # Handle truncation
        if len(original_text) > injector.MAX_CONTEXT_LENGTH:
            expected = original_text[:injector.MAX_CONTEXT_LENGTH] + "..."
        else:
            expected = original_text
            
        assert extracted == expected, (
            f"extract_reply_text MUST return correct text. "
            f"Expected: {expected[:50]}..., Got: {extracted[:50]}..."
        )

    @given(
        original_text=non_empty_text,
    )
    @settings(max_examples=100)
    def test_format_context_uses_template(
        self,
        original_text: str,
    ):
        """
        **Feature: grand-casino-dictator, Property 19: Reply Context Injection**
        **Validates: Requirements 14.2**
        
        For any text, format_context SHALL return the text formatted
        according to the TEMPLATE: "User replies to: '{original_text}'"
        """
        injector = ReplyContextInjector()
        
        # Format context
        formatted = injector.format_context(original_text)
        
        expected = f"User replies to: '{original_text}'"
        
        assert formatted == expected, (
            f"format_context MUST use template \"User replies to: '{{text}}'\" "
            f"Expected: {expected}, Got: {formatted}. "
            f"This is required by Requirement 14.2."
        )
