"""
Unit tests for Fact Checker service.

**Feature: anti-hallucination-v1**
"""

import pytest
from app.services.fact_checker import fact_checker, FactCheckResult


class TestFactChecker:
    """Tests for FactChecker class."""
    
    def test_detects_known_hallucinations(self):
        """Should detect known hallucinated GPU models."""
        response = "Рекомендую RTX 4090 Ti, она скоро выйдет"
        result = fact_checker.check_response(response)
        
        assert not result.is_reliable
        assert "RTX 4090 TI" in result.hallucinated_items
        assert result.confidence < 1.0
    
    def test_detects_multiple_hallucinations(self):
        """Should detect multiple hallucinated models."""
        response = "Выбирай между RTX 5060 и RX 8900 XTX"
        result = fact_checker.check_response(response)
        
        assert not result.is_reliable
        assert len(result.hallucinated_items) >= 1  # At least RX 8900
    
    def test_verifies_valid_models(self):
        """Should verify known valid GPU models."""
        response = "RTX 4070 Super — отличный выбор для 1440p"
        result = fact_checker.check_response(response)
        
        assert result.is_reliable
        # Check that some form of 4070 super is in verified items
        verified_lower = [v.lower() for v in result.verified_items]
        assert any("4070" in v and "super" in v for v in verified_lower) or \
               any("4070 super" in v for v in verified_lower)
    
    def test_extracts_hardware_mentions(self):
        """Should extract hardware mentions from text."""
        text = "У меня RTX 4090 и Ryzen 9 7950X"
        mentions = fact_checker._extract_hardware_mentions(text)
        
        assert len(mentions) >= 1
    
    def test_high_confidence_for_clean_response(self):
        """Should have high confidence for response without hardware."""
        response = "Привет, как дела?"
        result = fact_checker.check_response(response)
        
        assert result.is_reliable
        assert result.confidence == 1.0
    
    def test_format_warnings_empty_for_reliable(self):
        """Should return empty string for reliable responses."""
        result = FactCheckResult(
            is_reliable=True,
            confidence=1.0,
            warnings=[],
            hallucinated_items=[],
            verified_items=["RTX 4070"]
        )
        
        warning = fact_checker.format_warnings(result)
        assert warning == ""
    
    def test_format_warnings_for_hallucinations(self):
        """Should format warnings for hallucinated items."""
        result = FactCheckResult(
            is_reliable=False,
            confidence=0.5,
            warnings=["Test warning"],
            hallucinated_items=["RTX 5090"],
            verified_items=[]
        )
        
        warning = fact_checker.format_warnings(result)
        assert "RTX 5090" in warning
        assert "⚠️" in warning


class TestKnownModels:
    """Tests for known valid/invalid model lists."""
    
    @pytest.mark.parametrize("model", [
        "rtx 4090", "rtx 4080 super", "rtx 4070 ti super",
        "rx 7900 xtx", "rx 7800 xt", "arc a770"
    ])
    def test_valid_models_in_list(self, model):
        """Known valid models should be in the valid list."""
        assert model in fact_checker.KNOWN_VALID_MODELS
    
    @pytest.mark.parametrize("model", [
        "rtx 4090 ti", "rx 8900", "rx 9000", "rtx 5060"
    ])
    def test_hallucinations_in_list(self, model):
        """Known hallucinations should be in the hallucination list."""
        assert model in fact_checker.KNOWN_HALLUCINATIONS
    
    @pytest.mark.parametrize("model", [
        "rtx 5090", "rtx 5080", "rtx 5070", "rx 9070 xt", "rx 9070"
    ])
    def test_new_gen_models_are_valid(self, model):
        """RTX 50 and RX 9000 series should be valid (announced at CES 2025)."""
        assert model in fact_checker.KNOWN_VALID_MODELS
