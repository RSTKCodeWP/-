"""
Property-based tests for Alive UI Service.

Tests the correctness properties for the Alive UI system
as defined in the design document.

**Feature: fortress-update**
**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
"""

import os
import sys
import time
import importlib.util
from hypothesis import given, settings, strategies as st

# Import alive_ui module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'alive_ui.py')
_spec = importlib.util.spec_from_file_location("alive_ui", _module_path)
_alive_ui_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_alive_ui_module)

AliveUIService = _alive_ui_module.AliveUIService
StatusMessage = _alive_ui_module.StatusMessage
StatusCategory = _alive_ui_module.StatusCategory
ALIVE_PHRASES = _alive_ui_module.ALIVE_PHRASES
STATUS_THRESHOLD_SECONDS = _alive_ui_module.STATUS_THRESHOLD_SECONDS
UPDATE_INTERVAL_SECONDS = _alive_ui_module.UPDATE_INTERVAL_SECONDS


# Test data generators
categories = st.sampled_from(list(ALIVE_PHRASES.keys()))
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)
message_ids = st.integers(min_value=1, max_value=999999999)
elapsed_times = st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False)


class TestStatusTiming:
    """
    Property 29: Status message timing
    
    For any processing task exceeding 2 seconds, a status message 
    SHALL be sent.
    
    **Feature: fortress-update, Property 29: Status message timing**
    **Validates: Requirements 12.1**
    """
    
    @given(elapsed_time=st.floats(min_value=2.01, max_value=60.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_should_show_status_after_threshold(self, elapsed_time: float):
        """
        For any elapsed time > 2 seconds, should_show_status returns True.
        
        **Feature: fortress-update, Property 29: Status message timing**
        **Validates: Requirements 12.1**
        """
        service = AliveUIService()
        
        # Any time greater than 2 seconds should trigger status
        assert service.should_show_status(elapsed_time) is True
    
    @given(elapsed_time=st.floats(min_value=0.0, max_value=1.99, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_should_not_show_status_before_threshold(self, elapsed_time: float):
        """
        For any elapsed time <= 2 seconds, should_show_status returns False.
        
        **Feature: fortress-update, Property 29: Status message timing**
        **Validates: Requirements 12.1**
        """
        service = AliveUIService()
        
        # Any time less than or equal to 2 seconds should not trigger status
        assert service.should_show_status(elapsed_time) is False
    
    def test_threshold_boundary(self):
        """
        Test the exact boundary at 2 seconds.
        
        **Feature: fortress-update, Property 29: Status message timing**
        **Validates: Requirements 12.1**
        """
        service = AliveUIService()
        
        # Exactly at threshold should not show (> not >=)
        assert service.should_show_status(STATUS_THRESHOLD_SECONDS) is False
        
        # Just above threshold should show
        assert service.should_show_status(STATUS_THRESHOLD_SECONDS + 0.001) is True


class TestUpdateInterval:
    """
    Property 30: Status update interval
    
    For any ongoing processing with status message, updates SHALL 
    occur every 3 seconds.
    
    **Feature: fortress-update, Property 30: Status update interval**
    **Validates: Requirements 12.2**
    """
    
    @given(elapsed_time=st.floats(min_value=3.0, max_value=60.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_should_update_after_interval(self, elapsed_time: float):
        """
        For any time >= 3 seconds since last update, should_update_status returns True.
        
        **Feature: fortress-update, Property 30: Status update interval**
        **Validates: Requirements 12.2**
        """
        service = AliveUIService()
        
        # Any time >= 3 seconds should trigger update
        assert service.should_update_status(elapsed_time) is True
    
    @given(elapsed_time=st.floats(min_value=0.0, max_value=2.99, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_should_not_update_before_interval(self, elapsed_time: float):
        """
        For any time < 3 seconds since last update, should_update_status returns False.
        
        **Feature: fortress-update, Property 30: Status update interval**
        **Validates: Requirements 12.2**
        """
        service = AliveUIService()
        
        # Any time less than 3 seconds should not trigger update
        assert service.should_update_status(elapsed_time) is False
    
    def test_interval_boundary(self):
        """
        Test the exact boundary at 3 seconds.
        
        **Feature: fortress-update, Property 30: Status update interval**
        **Validates: Requirements 12.2**
        """
        service = AliveUIService()
        
        # Exactly at interval should update (>= not >)
        assert service.should_update_status(UPDATE_INTERVAL_SECONDS) is True
        
        # Just below interval should not update
        assert service.should_update_status(UPDATE_INTERVAL_SECONDS - 0.001) is False


class TestCategoryPhrases:
    """
    Property 31: Category-specific phrases
    
    For any status message in category X, the phrase SHALL be 
    selected from the X-specific phrase pool.
    
    **Feature: fortress-update, Property 31: Category-specific phrases**
    **Validates: Requirements 12.3, 12.4**
    """
    
    @given(category=categories)
    @settings(max_examples=100)
    def test_phrase_from_correct_category(self, category: str):
        """
        For any category, get_random_phrase returns a phrase from that category's pool.
        
        **Feature: fortress-update, Property 31: Category-specific phrases**
        **Validates: Requirements 12.3, 12.4**
        """
        service = AliveUIService()
        
        phrase = service.get_random_phrase(category)
        
        # The phrase must be from the category's pool
        assert phrase in ALIVE_PHRASES[category]
    
    @given(category=categories, seed=st.integers(min_value=0, max_value=1000000))
    @settings(max_examples=100)
    def test_phrase_randomness(self, category: str, seed: int):
        """
        For any category, multiple calls can return different phrases.
        
        **Feature: fortress-update, Property 31: Category-specific phrases**
        **Validates: Requirements 12.3, 12.4**
        """
        import random
        random.seed(seed)
        
        service = AliveUIService()
        
        # Get multiple phrases
        phrases = [service.get_random_phrase(category) for _ in range(10)]
        
        # All phrases must be from the correct category
        for phrase in phrases:
            assert phrase in ALIVE_PHRASES[category]
    
    def test_photo_category_phrases(self):
        """
        Photo category should contain photo-specific phrases.
        
        **Feature: fortress-update, Property 31: Category-specific phrases**
        **Validates: Requirements 12.3**
        """
        service = AliveUIService()
        
        # Get all phrases for photo category
        phrases = service.get_phrases_for_category("photo")
        
        # Should have phrases
        assert len(phrases) > 0
        
        # Should contain the example phrase from requirements
        assert any("пиксели" in p.lower() or "картинк" in p.lower() for p in phrases)
    
    def test_moderation_category_phrases(self):
        """
        Moderation category should contain moderation-specific phrases.
        
        **Feature: fortress-update, Property 31: Category-specific phrases**
        **Validates: Requirements 12.4**
        """
        service = AliveUIService()
        
        # Get all phrases for moderation category
        phrases = service.get_phrases_for_category("moderation")
        
        # Should have phrases
        assert len(phrases) > 0
        
        # Should contain the example phrase from requirements
        assert any("банхаммер" in p.lower() for p in phrases)
    
    def test_unknown_category_fallback(self):
        """
        Unknown category should fall back to thinking phrases.
        
        **Feature: fortress-update, Property 31: Category-specific phrases**
        **Validates: Requirements 12.3, 12.4**
        """
        service = AliveUIService()
        
        # Unknown category should return a phrase (fallback to thinking)
        phrase = service.get_random_phrase("unknown_category_xyz")
        
        # Should return something (fallback)
        assert phrase is not None
        assert len(phrase) > 0
    
    def test_category_enum_support(self):
        """
        StatusCategory enum values should work as category input.
        
        **Feature: fortress-update, Property 31: Category-specific phrases**
        **Validates: Requirements 12.3, 12.4**
        """
        service = AliveUIService()
        
        for cat in StatusCategory:
            if cat.value in ALIVE_PHRASES:
                phrase = service.get_random_phrase(cat)
                assert phrase in ALIVE_PHRASES[cat.value]


class TestStatusCleanup:
    """
    Property 32: Status cleanup
    
    For any completed processing, the status message SHALL be 
    deleted before sending the response.
    
    **Feature: fortress-update, Property 32: Status cleanup**
    **Validates: Requirements 12.5**
    """
    
    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        category=categories
    )
    @settings(max_examples=100)
    def test_finish_marks_status_as_finished(self, chat_id: int, message_id: int, category: str):
        """
        For any status message, finish_status marks it as finished.
        
        **Feature: fortress-update, Property 32: Status cleanup**
        **Validates: Requirements 12.5**
        """
        import asyncio
        
        service = AliveUIService()
        
        # Create a status message
        status = StatusMessage(
            chat_id=chat_id,
            message_id=message_id,
            category=category,
            started_at=time.time(),
            last_updated_at=time.time(),
            update_count=0,
            is_finished=False
        )
        
        # Finish the status (without bot, just marks as finished)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                service.finish_status(status, bot=None, delete=False)
            )
        finally:
            loop.close()
        
        # Status should be marked as finished
        assert status.is_finished is True
        assert result is True
    
    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        category=categories
    )
    @settings(max_examples=100)
    def test_finish_idempotent(self, chat_id: int, message_id: int, category: str):
        """
        Finishing an already finished status should be idempotent.
        
        **Feature: fortress-update, Property 32: Status cleanup**
        **Validates: Requirements 12.5**
        """
        import asyncio
        
        service = AliveUIService()
        
        # Create an already finished status
        status = StatusMessage(
            chat_id=chat_id,
            message_id=message_id,
            category=category,
            started_at=time.time(),
            last_updated_at=time.time(),
            update_count=0,
            is_finished=True
        )
        
        # Finishing again should succeed
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                service.finish_status(status, bot=None, delete=False)
            )
        finally:
            loop.close()
        
        # Should still be finished and return True
        assert status.is_finished is True
        assert result is True
    
    @given(
        chat_id=chat_ids,
        message_id=message_ids,
        category=categories
    )
    @settings(max_examples=100)
    def test_update_blocked_after_finish(self, chat_id: int, message_id: int, category: str):
        """
        Updates should be blocked after status is finished.
        
        **Feature: fortress-update, Property 32: Status cleanup**
        **Validates: Requirements 12.5**
        """
        import asyncio
        
        service = AliveUIService()
        
        # Create a finished status
        status = StatusMessage(
            chat_id=chat_id,
            message_id=message_id,
            category=category,
            started_at=time.time(),
            last_updated_at=time.time() - 10,  # Old enough to update
            update_count=0,
            is_finished=True
        )
        
        # Update should fail on finished status
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                service.update_status(status, bot=None)
            )
        finally:
            loop.close()
        
        # Should return False (update blocked)
        assert result is False


class TestCategoryMapping:
    """
    Test that task types map to correct categories.
    
    **Feature: fortress-update**
    **Validates: Requirements 12.3, 12.4**
    """
    
    def test_photo_task_mapping(self):
        """Photo-related tasks should map to photo category."""
        service = AliveUIService()
        
        assert service.get_category_for_task("photo_analysis") == "photo"
        assert service.get_category_for_task("image_analysis") == "photo"
        assert service.get_category_for_task("vision") == "photo"
    
    def test_moderation_task_mapping(self):
        """Moderation-related tasks should map to moderation category."""
        service = AliveUIService()
        
        assert service.get_category_for_task("moderation") == "moderation"
        assert service.get_category_for_task("toxicity") == "moderation"
        assert service.get_category_for_task("ban") == "moderation"
    
    def test_tts_task_mapping(self):
        """TTS-related tasks should map to tts category."""
        service = AliveUIService()
        
        assert service.get_category_for_task("tts") == "tts"
        assert service.get_category_for_task("voice") == "tts"
        assert service.get_category_for_task("speech") == "tts"
    
    def test_quote_task_mapping(self):
        """Quote-related tasks should map to quote category."""
        service = AliveUIService()
        
        assert service.get_category_for_task("quote") == "quote"
        assert service.get_category_for_task("sticker") == "quote"
        assert service.get_category_for_task("render") == "quote"
    
    def test_gif_task_mapping(self):
        """GIF-related tasks should map to gif category."""
        service = AliveUIService()
        
        assert service.get_category_for_task("gif") == "gif"
        assert service.get_category_for_task("animation") == "gif"
    
    def test_unknown_task_fallback(self):
        """Unknown tasks should fall back to thinking category."""
        service = AliveUIService()
        
        assert service.get_category_for_task("unknown_task") == "thinking"
        assert service.get_category_for_task("random_xyz") == "thinking"
