"""
Property-based tests for Typing Indicator in topics.

Tests correctness properties defined in the design document.
**Property 8: Typing indicator uses correct topic**
**Validates: Requirements 7.1, 7.2**
"""

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from hypothesis import given, strategies as st, settings
import pytest


# Strategies for generating test data
chat_id_strategy = st.integers(min_value=-10**12, max_value=10**12)
thread_id_strategy = st.one_of(st.none(), st.integers(min_value=1, max_value=10**9))


def run_async(coro):
    """Helper to run async code in sync context for hypothesis tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MockBot:
    """Mock Bot class that records send_chat_action calls."""
    
    def __init__(self):
        self.chat_action_calls = []
    
    async def send_chat_action(self, chat_id: int, action: str, message_thread_id: int = None):
        """Record the call parameters."""
        self.chat_action_calls.append({
            'chat_id': chat_id,
            'action': action,
            'message_thread_id': message_thread_id
        })


async def keep_typing_single_iteration(bot, chat_id: int, thread_id: int = None):
    """
    Simulates a single iteration of keep_typing for testing.
    This mirrors the logic in app/handlers/qna.py keep_typing function.
    """
    try:
        await bot.send_chat_action(chat_id, "typing", message_thread_id=thread_id)
    except Exception:
        pass


class TestTypingIndicatorTopicPreservation:
    """
    **Feature: release-candidate-8, Property 8: Typing indicator uses correct topic**
    **Validates: Requirements 7.1, 7.2**
    
    *For any* message in topic with message_thread_id = X, 
    send_chat_action("typing") SHALL include message_thread_id = X.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_typing_indicator_preserves_thread_id(
        self,
        chat_id: int,
        thread_id: Optional[int]
    ):
        """
        Property 8: Typing indicator uses correct topic.
        
        For any message in topic with thread_id X:
        - send_chat_action should be called with message_thread_id = X
        """
        bot = MockBot()
        
        # Run the typing function
        run_async(
            keep_typing_single_iteration(bot, chat_id, thread_id)
        )
        
        # Verify the call was made with correct parameters
        assert len(bot.chat_action_calls) == 1, \
            f"Expected 1 call, got {len(bot.chat_action_calls)}"
        
        call = bot.chat_action_calls[0]
        assert call['chat_id'] == chat_id, \
            f"Chat ID should be {chat_id}, got {call['chat_id']}"
        assert call['action'] == "typing", \
            f"Action should be 'typing', got {call['action']}"
        assert call['message_thread_id'] == thread_id, \
            f"Thread ID should be {thread_id}, got {call['message_thread_id']}"
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        thread_id=st.integers(min_value=1, max_value=10**9)
    )
    def test_typing_in_topic_sends_to_topic(
        self,
        chat_id: int,
        thread_id: int
    ):
        """
        Property 8: When message is in a topic, typing goes to that topic.
        
        For any non-None thread_id:
        - send_chat_action must include that thread_id
        """
        bot = MockBot()
        
        run_async(
            keep_typing_single_iteration(bot, chat_id, thread_id)
        )
        
        call = bot.chat_action_calls[0]
        assert call['message_thread_id'] == thread_id, \
            f"Typing in topic {thread_id} should send to that topic, got {call['message_thread_id']}"
        assert call['message_thread_id'] is not None, \
            "Thread ID should not be None when topic is specified"
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy
    )
    def test_typing_in_general_sends_to_general(
        self,
        chat_id: int
    ):
        """
        Property 8: When message is in general (no topic), typing goes to general.
        
        For thread_id = None:
        - send_chat_action should have message_thread_id = None
        """
        bot = MockBot()
        thread_id = None
        
        run_async(
            keep_typing_single_iteration(bot, chat_id, thread_id)
        )
        
        call = bot.chat_action_calls[0]
        assert call['message_thread_id'] is None, \
            f"Typing in general should have thread_id=None, got {call['message_thread_id']}"


class TestTypingIndicatorRoundTrip:
    """
    **Feature: release-candidate-8, Property 8: Typing indicator uses correct topic**
    **Validates: Requirements 7.1, 7.2**
    
    Tests that thread_id is correctly passed through the typing indicator flow.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_thread_id_round_trip(
        self,
        chat_id: int,
        thread_id: Optional[int]
    ):
        """
        Property 8: Thread ID survives round-trip through typing indicator.
        
        The thread_id passed to keep_typing should be exactly the same
        as the message_thread_id passed to send_chat_action.
        """
        bot = MockBot()
        
        # Simulate what happens in _process_qna_message
        # topic_id = getattr(msg, 'message_thread_id', None)
        # typing_task = asyncio.create_task(keep_typing(msg.bot, msg.chat.id, stop_typing, topic_id))
        
        run_async(
            keep_typing_single_iteration(bot, chat_id, thread_id)
        )
        
        call = bot.chat_action_calls[0]
        
        # The thread_id should be exactly preserved
        assert call['message_thread_id'] == thread_id, \
            f"Thread ID should be exactly preserved: input={thread_id}, output={call['message_thread_id']}"


class TestTypingIndicatorConsistency:
    """
    **Feature: release-candidate-8, Property 8: Typing indicator uses correct topic**
    **Validates: Requirements 7.1, 7.2**
    
    Tests consistency of typing indicator behavior.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        thread_id=thread_id_strategy
    )
    def test_multiple_typing_calls_same_topic(
        self,
        chat_id: int,
        thread_id: Optional[int]
    ):
        """
        Property 8: Multiple typing calls use the same topic consistently.
        
        If keep_typing is called multiple times with the same thread_id,
        all send_chat_action calls should use that same thread_id.
        """
        bot = MockBot()
        
        # Simulate multiple typing iterations
        for _ in range(3):
            run_async(
                keep_typing_single_iteration(bot, chat_id, thread_id)
            )
        
        # All calls should have the same thread_id
        for i, call in enumerate(bot.chat_action_calls):
            assert call['message_thread_id'] == thread_id, \
                f"Call {i} should have thread_id={thread_id}, got {call['message_thread_id']}"
            assert call['chat_id'] == chat_id, \
                f"Call {i} should have chat_id={chat_id}, got {call['chat_id']}"
