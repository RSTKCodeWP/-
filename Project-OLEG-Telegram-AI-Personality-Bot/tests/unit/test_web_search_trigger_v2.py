"""
Unit tests for Smart Web Search Trigger.

**Feature: anti-hallucination-v2**
"""

import pytest
from app.services.web_search_trigger import (
    get_search_priority,
    should_trigger_web_search,
    should_trigger_web_search_simple,
    parse_self_assessment,
    is_question_about_current_info,
    SearchPriority,
)


class TestSearchPriority:
    """Tests for search priority detection."""
    
    # NEVER search - болтовня
    @pytest.mark.parametrize("text", [
        "привет",
        "как дела?",
        "спасибо",
        "пока",
        "лол",
        "да",
        "ок",
    ])
    def test_never_search_chatter(self, text):
        """Should never search for casual chatter."""
        priority, _ = get_search_priority(text)
        assert priority == SearchPriority.NEVER
    
    # NEVER search - вопросы про бота
    @pytest.mark.parametrize("text", [
        "кто ты?",
        "что ты умеешь?",
        "расскажи о себе",
        "твои характеристики",
    ])
    def test_never_search_bot_questions(self, text):
        """Should never search for questions about the bot."""
        priority, _ = get_search_priority(text)
        assert priority == SearchPriority.NEVER
    
    # CRITICAL - цены
    @pytest.mark.parametrize("text", [
        "сколько стоит RTX 5090?",
        "какая цена на Ryzen 9800X3D?",
        "почём 4070 Super?",
        "где купить RX 9070?",
    ])
    def test_critical_search_prices(self, text):
        """Should always search for prices."""
        priority, _ = get_search_priority(text)
        assert priority == SearchPriority.CRITICAL
    
    # CRITICAL - релизы
    @pytest.mark.parametrize("text", [
        "когда выйдет GTA 6?",
        "вышла ли Windows 12?",
        "дата выхода RTX 5060",
        "последние новости про AMD",
    ])
    def test_critical_search_releases(self, text):
        """Should always search for release info."""
        priority, _ = get_search_priority(text)
        assert priority == SearchPriority.CRITICAL
    
    # HIGH - конкретные модели железа
    @pytest.mark.parametrize("text", [
        "RTX 4070 vs RX 7800 XT",
        "сколько VRAM у RTX 5080?",
        "какой TDP у Ryzen 9 9950X?",
        "что лучше RTX 5070 или RX 9070?",
    ])
    def test_high_search_hardware_specs(self, text):
        """Should search for specific hardware specs."""
        priority, _ = get_search_priority(text)
        assert priority == SearchPriority.HIGH


class TestShouldTriggerWebSearch:
    """Tests for should_trigger_web_search function."""
    
    def test_triggers_on_price_question(self):
        """Should trigger on price questions."""
        result, reason = should_trigger_web_search("сколько стоит RTX 5090?")
        assert result is True
        assert "always_pattern" in reason or "high_pattern" in reason
    
    def test_triggers_on_release_question(self):
        """Should trigger on release questions."""
        result, reason = should_trigger_web_search("когда выйдет GTA 6?")
        assert result is True
    
    def test_not_triggers_on_greeting(self):
        """Should not trigger on greetings."""
        result, _ = should_trigger_web_search("привет")
        assert result is False
    
    def test_not_triggers_on_thanks(self):
        """Should not trigger on thanks."""
        result, _ = should_trigger_web_search("спасибо")
        assert result is False
    
    def test_simple_version_returns_bool(self):
        """Simple version should return bool."""
        result = should_trigger_web_search_simple("сколько стоит видеокарта?")
        assert isinstance(result, bool)


class TestSelfAssessment:
    """Tests for self-assessment parsing."""
    
    def test_parse_confidence_high(self):
        """Should parse high confidence."""
        response = "Ответ на вопрос.<!--CONFIDENCE:high--><!--NEEDS_SEARCH:no-->"
        clean, confidence, needs_search = parse_self_assessment(response)
        
        assert clean == "Ответ на вопрос."
        assert confidence == "high"
        assert needs_search is False
    
    def test_parse_confidence_low_needs_search(self):
        """Should parse low confidence with search needed."""
        response = "Не уверен.<!--CONFIDENCE:low--><!--NEEDS_SEARCH:yes-->"
        clean, confidence, needs_search = parse_self_assessment(response)
        
        assert clean == "Не уверен."
        assert confidence == "low"
        assert needs_search is True
    
    def test_parse_no_metadata(self):
        """Should handle response without metadata."""
        response = "Просто ответ без метаданных."
        clean, confidence, needs_search = parse_self_assessment(response)
        
        assert clean == "Просто ответ без метаданных."
        assert confidence is None
        assert needs_search is None
    
    def test_clean_response_removes_metadata(self):
        """Should remove all metadata from response."""
        response = "Текст<!--CONFIDENCE:medium-->ещё текст<!--NEEDS_SEARCH:no-->"
        clean, _, _ = parse_self_assessment(response)
        
        assert "CONFIDENCE" not in clean
        assert "NEEDS_SEARCH" not in clean
        assert "<!--" not in clean


class TestIsQuestionAboutCurrentInfo:
    """Tests for is_question_about_current_info."""
    
    @pytest.mark.parametrize("text", [
        "сколько стоит RTX 5090?",
        "когда выйдет игра?",
        "последняя версия драйвера",
    ])
    def test_current_info_questions(self, text):
        """Should detect questions about current info."""
        assert is_question_about_current_info(text) is True
    
    @pytest.mark.parametrize("text", [
        "привет",
        "что такое GPU?",
        "помоги с кодом",
    ])
    def test_not_current_info_questions(self, text):
        """Should not detect non-current info questions."""
        assert is_question_about_current_info(text) is False


class TestEdgeCases:
    """Edge case tests."""
    
    def test_empty_string(self):
        """Should handle empty string."""
        priority, _ = get_search_priority("")
        assert priority == SearchPriority.NEVER
    
    def test_case_insensitive(self):
        """Should be case insensitive."""
        result1, _ = should_trigger_web_search("СКОЛЬКО СТОИТ RTX 5090?")
        result2, _ = should_trigger_web_search("сколько стоит rtx 5090?")
        assert result1 == result2
    
    def test_mixed_content(self):
        """Should handle mixed content."""
        # Цена в вопросе должна триггерить поиск
        result, _ = should_trigger_web_search("привет, сколько стоит видеокарта?")
        assert result is True
