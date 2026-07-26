"""
Property-based tests for Smart Web Search Trigger.

Tests correctness properties for the new categorization system.
**Feature: anti-hallucination-v2**
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import web_search_trigger module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'web_search_trigger.py')
_spec = importlib.util.spec_from_file_location("web_search_trigger", _module_path)
_trigger_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_trigger_module)

# Import functions
should_trigger_web_search = _trigger_module.should_trigger_web_search_simple
get_search_priority = _trigger_module.get_search_priority
SearchPriority = _trigger_module.SearchPriority

# Keywords that should ALWAYS trigger search (CRITICAL priority)
ALWAYS_SEARCH_KEYWORDS = [
    "сколько стоит", "цена", "ценник", "почём", "где купить",
    "когда выйдет", "когда релиз", "дата выхода",
    "вышла ли", "вышел ли", "уже вышла",
    "последние новости", "что нового",
    "последняя версия", "актуальная версия",
]

# Keywords that should NEVER trigger search (casual chat)
NEVER_SEARCH_KEYWORDS = [
    "привет", "здарова", "хай",
    "спасибо", "пасиб",
    "пока", "бб",
    "лол", "кек", "ахах",
]


class TestSearchPriorityCategories:
    """
    Tests for search priority categorization.
    **Feature: anti-hallucination-v2**
    """
    
    @settings(max_examples=50)
    @given(st.sampled_from(ALWAYS_SEARCH_KEYWORDS))
    def test_critical_keywords_trigger_search(self, keyword: str):
        """
        Property: Critical keywords (prices, releases) should ALWAYS trigger search.
        """
        message = f"Привет, {keyword} что-нибудь интересное?"
        
        priority, _ = get_search_priority(message)
        assert priority == SearchPriority.CRITICAL, \
            f"Keyword '{keyword}' should have CRITICAL priority, got {priority}"
    
    @settings(max_examples=50)
    @given(st.sampled_from(NEVER_SEARCH_KEYWORDS))
    def test_casual_keywords_never_search(self, keyword: str):
        """
        Property: Casual chat keywords should NEVER trigger search.
        """
        # Test standalone keyword
        priority, _ = get_search_priority(keyword)
        assert priority == SearchPriority.NEVER, \
            f"Casual keyword '{keyword}' should have NEVER priority, got {priority}"
    
    def test_critical_overrides_never(self):
        """
        Property: Critical keywords should override casual keywords.
        """
        # Message starts with greeting but asks about price
        message = "привет, сколько стоит RTX 5090?"
        
        priority, _ = get_search_priority(message)
        assert priority == SearchPriority.CRITICAL, \
            "Price question should override greeting"
    
    @settings(max_examples=30)
    @given(st.sampled_from(["RTX 4070", "RX 7900", "Ryzen 9", "i9-14900"]))
    def test_hardware_models_high_priority(self, model: str):
        """
        Property: Questions about specific hardware models should have HIGH priority.
        """
        message = f"сколько VRAM у {model}?"
        
        priority, _ = get_search_priority(message)
        assert priority in (SearchPriority.HIGH, SearchPriority.CRITICAL), \
            f"Hardware question about '{model}' should have HIGH/CRITICAL priority"


class TestSearchTriggerFunction:
    """
    Tests for should_trigger_web_search function.
    """
    
    @settings(max_examples=50)
    @given(st.sampled_from(ALWAYS_SEARCH_KEYWORDS))
    def test_always_keywords_return_true(self, keyword: str):
        """
        Property: ALWAYS keywords should return True from should_trigger_web_search.
        """
        message = f"Вопрос: {keyword}?"
        
        result = should_trigger_web_search(message)
        assert result is True, \
            f"Keyword '{keyword}' should trigger search"
    
    @settings(max_examples=50)
    @given(st.sampled_from(NEVER_SEARCH_KEYWORDS))
    def test_never_keywords_return_false(self, keyword: str):
        """
        Property: NEVER keywords (alone) should return False.
        """
        result = should_trigger_web_search(keyword)
        assert result is False, \
            f"Casual keyword '{keyword}' should not trigger search"
    
    def test_empty_string_no_trigger(self):
        """
        Property: Empty string should not trigger web search.
        """
        result = should_trigger_web_search("")
        assert result is False, "Empty string should not trigger search"
    
    def test_case_insensitive(self):
        """
        Property: Search detection should be case-insensitive.
        """
        result_lower = should_trigger_web_search("сколько стоит rtx 5090?")
        result_upper = should_trigger_web_search("СКОЛЬКО СТОИТ RTX 5090?")
        
        assert result_lower == result_upper, \
            "Case should not affect search trigger"


class TestReleaseKeywords:
    """
    Tests specifically for release/news related keywords.
    """
    
    @settings(max_examples=30)
    @given(st.sampled_from(["когда выйдет", "дата выхода", "вышла ли", "последние новости"]))
    def test_release_keywords_critical(self, keyword: str):
        """
        Release-related keywords should have CRITICAL priority.
        """
        message = f"{keyword} GTA 6?"
        
        priority, _ = get_search_priority(message)
        assert priority == SearchPriority.CRITICAL, \
            f"Release keyword '{keyword}' should be CRITICAL"


class TestPriceKeywords:
    """
    Tests specifically for price-related keywords.
    """
    
    @settings(max_examples=30)
    @given(st.sampled_from(["сколько стоит", "цена", "ценник", "где купить"]))
    def test_price_keywords_critical(self, keyword: str):
        """
        Price-related keywords should have CRITICAL priority.
        """
        message = f"{keyword} RTX 4090?"
        
        priority, _ = get_search_priority(message)
        assert priority == SearchPriority.CRITICAL, \
            f"Price keyword '{keyword}' should be CRITICAL"
