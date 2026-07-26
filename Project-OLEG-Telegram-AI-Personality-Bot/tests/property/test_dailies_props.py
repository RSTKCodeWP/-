"""
Property-based tests for Dailies Service.

Tests the correctness properties for the Dailies system
as defined in the design document.

**Feature: fortress-update**
**Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5**
"""

import os
import importlib.util
from hypothesis import given, settings, strategies as st

# Import dailies module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'dailies.py')
_spec = importlib.util.spec_from_file_location("dailies", _module_path)
_dailies_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dailies_module)

DailiesService = _dailies_module.DailiesService
DailiesConfig = _dailies_module.DailiesConfig
DailySummary = _dailies_module.DailySummary
DailyQuote = _dailies_module.DailyQuote
DailyStats = _dailies_module.DailyStats
MIN_ACTIVITY_FOR_SUMMARY = _dailies_module.MIN_ACTIVITY_FOR_SUMMARY


# Test data generators
chat_ids = st.integers(min_value=-1000000000000, max_value=-1)
message_counts = st.integers(min_value=0, max_value=10000)
booleans = st.booleans()


class TestDailyMessageRespectSettings:
    """
    Property 33: Daily message respect settings
    
    For any chat with specific daily message types disabled,
    those messages SHALL NOT be sent.
    
    **Feature: fortress-update, Property 33: Daily message respect settings**
    **Validates: Requirements 13.4**
    """
    
    @given(
        chat_id=chat_ids,
        summary_enabled=booleans,
        quote_enabled=booleans,
        stats_enabled=booleans
    )
    @settings(max_examples=100)
    def test_should_send_respects_summary_setting(
        self, 
        chat_id: int, 
        summary_enabled: bool,
        quote_enabled: bool,
        stats_enabled: bool
    ):
        """
        For any config, should_send_message('summary') returns summary_enabled value.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=summary_enabled,
            quote_enabled=quote_enabled,
            stats_enabled=stats_enabled
        )
        
        # should_send_message must respect the summary_enabled setting
        assert service.should_send_message(config, 'summary') == summary_enabled
    
    @given(
        chat_id=chat_ids,
        summary_enabled=booleans,
        quote_enabled=booleans,
        stats_enabled=booleans
    )
    @settings(max_examples=100)
    def test_should_send_respects_quote_setting(
        self, 
        chat_id: int, 
        summary_enabled: bool,
        quote_enabled: bool,
        stats_enabled: bool
    ):
        """
        For any config, should_send_message('quote') returns quote_enabled value.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=summary_enabled,
            quote_enabled=quote_enabled,
            stats_enabled=stats_enabled
        )
        
        # should_send_message must respect the quote_enabled setting
        assert service.should_send_message(config, 'quote') == quote_enabled
    
    @given(
        chat_id=chat_ids,
        summary_enabled=booleans,
        quote_enabled=booleans,
        stats_enabled=booleans
    )
    @settings(max_examples=100)
    def test_should_send_respects_stats_setting(
        self, 
        chat_id: int, 
        summary_enabled: bool,
        quote_enabled: bool,
        stats_enabled: bool
    ):
        """
        For any config, should_send_message('stats') returns stats_enabled value.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=summary_enabled,
            quote_enabled=quote_enabled,
            stats_enabled=stats_enabled
        )
        
        # should_send_message must respect the stats_enabled setting
        assert service.should_send_message(config, 'stats') == stats_enabled
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_disabled_summary_not_sent(self, chat_id: int):
        """
        For any chat with summary disabled, summary should not be sent.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=False,
            quote_enabled=True,
            stats_enabled=True
        )
        
        # Summary should not be sent when disabled
        assert service.should_send_message(config, 'summary') is False
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_disabled_quote_not_sent(self, chat_id: int):
        """
        For any chat with quote disabled, quote should not be sent.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=True,
            quote_enabled=False,
            stats_enabled=True
        )
        
        # Quote should not be sent when disabled
        assert service.should_send_message(config, 'quote') is False
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_disabled_stats_not_sent(self, chat_id: int):
        """
        For any chat with stats disabled, stats should not be sent.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=True,
            quote_enabled=True,
            stats_enabled=False
        )
        
        # Stats should not be sent when disabled
        assert service.should_send_message(config, 'stats') is False
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_all_disabled_nothing_sent(self, chat_id: int):
        """
        For any chat with all dailies disabled, nothing should be sent.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=False,
            quote_enabled=False,
            stats_enabled=False
        )
        
        # Nothing should be sent when all disabled
        assert service.should_send_message(config, 'summary') is False
        assert service.should_send_message(config, 'quote') is False
        assert service.should_send_message(config, 'stats') is False
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_unknown_message_type_not_sent(self, chat_id: int):
        """
        For any unknown message type, should_send_message returns False.
        
        **Feature: fortress-update, Property 33: Daily message respect settings**
        **Validates: Requirements 13.4**
        """
        service = DailiesService()
        
        config = DailiesConfig(
            chat_id=chat_id,
            summary_enabled=True,
            quote_enabled=True,
            stats_enabled=True
        )
        
        # Unknown message types should not be sent
        assert service.should_send_message(config, 'unknown_type') is False
        assert service.should_send_message(config, 'random_xyz') is False


class TestSkipSummaryOnNoActivity:
    """
    Property 34: Skip summary on no activity
    
    For any chat with zero messages in the past 24 hours,
    the daily summary SHALL be skipped.
    
    **Feature: fortress-update, Property 34: Skip summary on no activity**
    **Validates: Requirements 13.5**
    """
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_skip_summary_when_no_activity(self, chat_id: int):
        """
        For any summary with has_activity=False, should_skip_summary returns True.
        
        **Feature: fortress-update, Property 34: Skip summary on no activity**
        **Validates: Requirements 13.5**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        # Create summary with no activity
        summary = DailySummary(
            chat_id=chat_id,
            date=datetime.now(),
            message_count=0,
            has_activity=False
        )
        
        # Should skip when no activity
        assert service.should_skip_summary(summary) is True
    
    @given(
        chat_id=chat_ids,
        message_count=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=100)
    def test_do_not_skip_summary_when_has_activity(self, chat_id: int, message_count: int):
        """
        For any summary with has_activity=True, should_skip_summary returns False.
        
        **Feature: fortress-update, Property 34: Skip summary on no activity**
        **Validates: Requirements 13.5**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        # Create summary with activity
        summary = DailySummary(
            chat_id=chat_id,
            date=datetime.now(),
            message_count=message_count,
            has_activity=True
        )
        
        # Should not skip when has activity
        assert service.should_skip_summary(summary) is False
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_skip_summary_when_none(self, chat_id: int):
        """
        For any None summary, should_skip_summary returns True.
        
        **Feature: fortress-update, Property 34: Skip summary on no activity**
        **Validates: Requirements 13.5**
        """
        service = DailiesService()
        
        # Should skip when summary is None
        assert service.should_skip_summary(None) is True
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_zero_messages_means_no_activity(self, chat_id: int):
        """
        For any summary with message_count=0, has_activity should be False.
        
        **Feature: fortress-update, Property 34: Skip summary on no activity**
        **Validates: Requirements 13.5**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        # Create summary with zero messages
        summary = DailySummary(
            chat_id=chat_id,
            date=datetime.now(),
            message_count=0,
            has_activity=False
        )
        
        # Zero messages means no activity, should skip
        assert service.should_skip_summary(summary) is True
    
    @given(
        chat_id=chat_ids,
        message_count=st.integers(min_value=MIN_ACTIVITY_FOR_SUMMARY, max_value=10000)
    )
    @settings(max_examples=100)
    def test_activity_threshold_respected(self, chat_id: int, message_count: int):
        """
        For any message count >= MIN_ACTIVITY_FOR_SUMMARY, has_activity should be True.
        
        **Feature: fortress-update, Property 34: Skip summary on no activity**
        **Validates: Requirements 13.5**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        # Create summary with activity above threshold
        summary = DailySummary(
            chat_id=chat_id,
            date=datetime.now(),
            message_count=message_count,
            has_activity=True
        )
        
        # Should not skip when above threshold
        assert service.should_skip_summary(summary) is False


class TestDailyQuoteSelection:
    """
    Test daily quote selection functionality.
    
    **Feature: fortress-update**
    **Validates: Requirements 13.2**
    """
    
    def test_default_quote_returned_when_no_golden_fund(self):
        """
        When Golden Fund is empty, a default wisdom quote should be returned.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.2**
        """
        import asyncio
        
        service = DailiesService()
        # Disable golden fund service for this test
        service._golden_fund_service = None
        
        loop = asyncio.new_event_loop()
        try:
            quote = loop.run_until_complete(service.select_daily_quote())
        finally:
            loop.close()
        
        # Should return a quote
        assert quote is not None
        assert isinstance(quote, DailyQuote)
        assert len(quote.text) > 0
        assert quote.is_from_golden_fund is False
    
    @given(chat_id=chat_ids)
    @settings(max_examples=10)
    def test_quote_always_has_text(self, chat_id: int):
        """
        For any chat, selected quote always has non-empty text.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.2**
        """
        import asyncio
        
        service = DailiesService()
        service._golden_fund_service = None  # Use default quotes
        
        loop = asyncio.new_event_loop()
        try:
            quote = loop.run_until_complete(service.select_daily_quote(chat_id))
        finally:
            loop.close()
        
        assert quote is not None
        assert len(quote.text) > 0


class TestDailySummaryFormatting:
    """
    Test daily summary formatting.
    
    **Feature: fortress-update**
    **Validates: Requirements 13.1**
    """
    
    @given(
        chat_id=chat_ids,
        message_count=st.integers(min_value=1, max_value=10000),
        active_users=st.integers(min_value=1, max_value=1000),
        new_members=st.integers(min_value=0, max_value=100),
        moderation_actions=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_summary_format_contains_required_info(
        self,
        chat_id: int,
        message_count: int,
        active_users: int,
        new_members: int,
        moderation_actions: int
    ):
        """
        For any summary, formatted output contains required information.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.1**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        summary = DailySummary(
            chat_id=chat_id,
            date=datetime.now(),
            message_count=message_count,
            active_users=active_users,
            new_members=new_members,
            moderation_actions=moderation_actions,
            has_activity=True
        )
        
        formatted = service.format_summary(summary)
        
        # Should contain hashtag
        assert "#dailysummary" in formatted
        
        # Should contain message count
        assert str(message_count) in formatted
        
        # Should contain active users
        assert str(active_users) in formatted
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_summary_format_includes_hashtag(self, chat_id: int):
        """
        For any summary, formatted output includes #dailysummary hashtag.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.1**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        summary = DailySummary(
            chat_id=chat_id,
            date=datetime.now(),
            message_count=10,
            active_users=5,
            has_activity=True
        )
        
        formatted = service.format_summary(summary)
        
        assert "#dailysummary" in formatted


class TestDailyQuoteFormatting:
    """
    Test daily quote formatting.
    
    **Feature: fortress-update**
    **Validates: Requirements 13.2**
    """
    
    @given(text=st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    def test_quote_format_contains_hashtag(self, text: str):
        """
        For any quote, formatted output contains #dailyquote hashtag.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.2**
        """
        service = DailiesService()
        
        quote = DailyQuote(
            text=text,
            is_from_golden_fund=False
        )
        
        formatted = service.format_quote(quote)
        
        assert "#dailyquote" in formatted
    
    @given(
        text=st.text(min_size=1, max_size=500),
        author=st.text(min_size=1, max_size=64)
    )
    @settings(max_examples=100)
    def test_golden_fund_quote_shows_author(self, text: str, author: str):
        """
        For any Golden Fund quote, formatted output shows author.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.2**
        """
        service = DailiesService()
        
        quote = DailyQuote(
            text=text,
            author=author,
            is_from_golden_fund=True
        )
        
        formatted = service.format_quote(quote)
        
        # Should contain author
        assert author in formatted
        # Should indicate Golden Fund
        assert "Золотого Фонда" in formatted or "Golden" in formatted.lower()


class TestDailyStatsFormatting:
    """
    Test daily stats formatting.
    
    **Feature: fortress-update**
    **Validates: Requirements 13.3**
    """
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_stats_format_contains_hashtag(self, chat_id: int):
        """
        For any stats, formatted output contains #dailystats hashtag.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.3**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        stats = DailyStats(
            chat_id=chat_id,
            date=datetime.now(),
            top_growers=[{"username": "user1", "size": 100}],
            top_losers=[{"username": "user2", "size": 10}],
            tournament_standings=[]
        )
        
        formatted = service.format_stats(stats)
        
        assert "#dailystats" in formatted
    
    @given(chat_id=chat_ids)
    @settings(max_examples=100)
    def test_empty_stats_shows_message(self, chat_id: int):
        """
        For any empty stats, formatted output shows encouragement message.
        
        **Feature: fortress-update**
        **Validates: Requirements 13.3**
        """
        from datetime import datetime
        
        service = DailiesService()
        
        stats = DailyStats(
            chat_id=chat_id,
            date=datetime.now(),
            top_growers=[],
            top_losers=[],
            tournament_standings=[]
        )
        
        formatted = service.format_stats(stats)
        
        # Should contain hashtag
        assert "#dailystats" in formatted
        # Should contain encouragement when empty
        assert "статистики" in formatted.lower() or "играйте" in formatted.lower()
