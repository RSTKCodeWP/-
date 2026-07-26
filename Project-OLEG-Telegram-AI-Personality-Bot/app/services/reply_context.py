"""
Reply Context Injector for AI prompts.

This module provides functionality to inject reply context into AI prompts
when a user replies to another message.

**Feature: grand-casino-dictator**
**Validates: Requirements 14.1, 14.2, 14.3**
"""

import logging
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class MessageLike(Protocol):
    """Protocol for message-like objects that may have reply_to_message."""
    
    @property
    def reply_to_message(self) -> Optional["MessageLike"]:
        """The message this message is a reply to."""
        ...
    
    @property
    def text(self) -> Optional[str]:
        """The text content of the message."""
        ...


class ReplyContextInjector:
    """
    Инъекция контекста реплая в промпт.
    
    When a user replies to a message, this class extracts the original
    message text and injects it into the AI prompt for better context.
    
    **Property 19: Reply Context Injection**
    **Validates: Requirements 14.1, 14.2, 14.3**
    """
    
    TEMPLATE = "User replies to: '{original_text}'"
    MAX_CONTEXT_LENGTH = 500  # Limit context to avoid overly long prompts
    
    def extract_reply_text(self, message: MessageLike) -> Optional[str]:
        """
        Извлечь текст сообщения на которое отвечают.
        
        **Validates: Requirements 14.1**
        
        Args:
            message: The message to check for reply context
            
        Returns:
            The text of the original message if this is a reply, None otherwise
        """
        if message is None:
            return None
            
        reply_to = getattr(message, 'reply_to_message', None)
        if reply_to is None:
            return None
            
        original_text = getattr(reply_to, 'text', None)
        if original_text is None:
            # Try caption for media messages
            original_text = getattr(reply_to, 'caption', None)
            
        if original_text is None:
            return None
            
        # Truncate if too long
        if len(original_text) > self.MAX_CONTEXT_LENGTH:
            original_text = original_text[:self.MAX_CONTEXT_LENGTH] + "..."
            
        return original_text
    
    def format_context(self, original_text: str) -> str:
        """
        Format the reply context using the template.
        
        **Validates: Requirements 14.2**
        
        Args:
            original_text: The text of the original message
            
        Returns:
            Formatted context string
        """
        return self.TEMPLATE.format(original_text=original_text)
    
    def inject(self, message: MessageLike, prompt: str) -> str:
        """
        Добавить контекст реплая в промпт если есть.
        
        **Property 19: Reply Context Injection**
        **Validates: Requirements 14.1, 14.2, 14.3**
        
        If the message is a reply to another message, the original message
        text is extracted and prepended to the prompt in the specified format.
        
        Args:
            message: The message to check for reply context
            prompt: The original prompt text
            
        Returns:
            The prompt with reply context injected (if applicable),
            or the original prompt unchanged
        """
        original_text = self.extract_reply_text(message)
        
        if original_text is None:
            logger.debug("No reply context to inject")
            return prompt
            
        context = self.format_context(original_text)
        injected_prompt = f"{context}\n\n{prompt}"
        
        logger.debug(f"Injected reply context: {context[:50]}...")
        return injected_prompt


# Singleton instance for easy import
reply_context_injector = ReplyContextInjector()
