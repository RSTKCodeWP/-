"""
Property-based tests for ThinkTagFilter.

**Feature: oleg-v5-refactoring, Property 1: Think Tag Removal Completeness**
**Validates: Requirements 1.1, 1.2**

**Feature: oleg-v5-refactoring, Property 2: Think Tag Filter Preserves External Content**
**Validates: Requirements 1.3**
"""

from hypothesis import given, strategies as st, settings, assume
import re
import sys
import os
import importlib.util

# Import think_filter module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'think_filter.py')
_spec = importlib.util.spec_from_file_location("think_filter", _module_path)
_think_filter_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_think_filter_module)
ThinkTagFilter = _think_filter_module.ThinkTagFilter


# Strategy for generating text that doesn't contain think tags or markdown
text_without_think_tags = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),  # Exclude surrogates
        blacklist_characters='<>*_`#[]'  # Exclude angle brackets and markdown chars
    ),
    min_size=0,
    max_size=200
)

# Strategy for generating content inside think tags
think_content = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),
        blacklist_characters='<>'  # No nested tags
    ),
    min_size=0,
    max_size=100
)


class TestThinkTagRemovalCompleteness:
    """
    **Feature: oleg-v5-refactoring, Property 1: Think Tag Removal Completeness**
    **Validates: Requirements 1.1, 1.2**
    
    For any string containing <think>...</think> tags, after filtering,
    the result SHALL NOT contain any think tags or their content.
    """
    
    @settings(max_examples=100)
    @given(
        before=text_without_think_tags,
        inside=think_content,
        after=text_without_think_tags
    )
    def test_think_tags_removed_completely(self, before: str, inside: str, after: str):
        """
        Property: After filtering, no <think> or </think> tags remain.
        """
        # Construct text with think tags
        text = f"{before}<think>{inside}</think>{after}"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # Result should not contain any think tags
        assert '<think>' not in result.lower()
        assert '</think>' not in result.lower()
    
    @settings(max_examples=100)
    @given(
        before=text_without_think_tags,
        inside1=think_content,
        middle=text_without_think_tags,
        inside2=think_content,
        after=text_without_think_tags
    )
    def test_multiple_think_tags_removed(
        self, before: str, inside1: str, middle: str, inside2: str, after: str
    ):
        """
        Property: Multiple think tags are all removed.
        """
        # Construct text with multiple think tags
        text = f"{before}<think>{inside1}</think>{middle}<think>{inside2}</think>{after}"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # Result should not contain any think tags
        assert '<think>' not in result.lower()
        assert '</think>' not in result.lower()
    
    @settings(max_examples=100)
    @given(
        before=text_without_think_tags,
        inside=think_content
    )
    def test_unclosed_think_tag_removed(self, before: str, inside: str):
        """
        Property: Malformed (unclosed) think tags are also removed.
        """
        # Construct text with unclosed think tag
        text = f"{before}<think>{inside}"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # Result should not contain any think tags
        assert '<think>' not in result.lower()
    
    @settings(max_examples=100)
    @given(
        inside=think_content,
        after=text_without_think_tags
    )
    def test_unopened_think_tag_removed(self, inside: str, after: str):
        """
        Property: Malformed (unopened) think tags are also removed.
        """
        # Construct text with unopened think tag (starts with </think>)
        text = f"{inside}</think>{after}"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # Result should not contain any think tags
        assert '</think>' not in result.lower()
    
    @settings(max_examples=100)
    @given(
        before=text_without_think_tags,
        inside=think_content,
        after=text_without_think_tags
    )
    def test_case_insensitive_removal(self, before: str, inside: str, after: str):
        """
        Property: Think tags are removed regardless of case.
        """
        # Test various case combinations
        cases = [
            f"{before}<THINK>{inside}</THINK>{after}",
            f"{before}<Think>{inside}</Think>{after}",
            f"{before}<tHiNk>{inside}</tHiNk>{after}",
        ]
        
        filter_instance = ThinkTagFilter()
        
        for text in cases:
            result = filter_instance.filter(text)
            assert '<think>' not in result.lower()
            assert '</think>' not in result.lower()


class TestThinkTagFilterPreservesExternalContent:
    """
    **Feature: oleg-v5-refactoring, Property 2: Think Tag Filter Preserves External Content**
    **Validates: Requirements 1.3**
    
    For any string with think tags, all text outside the tags
    SHALL be preserved exactly after filtering.
    """
    
    @settings(max_examples=100)
    @given(
        before=text_without_think_tags,
        inside=think_content,
        after=text_without_think_tags
    )
    def test_external_content_preserved(self, before: str, inside: str, after: str):
        """
        Property: Text outside think tags is preserved.
        """
        # Skip if both before and after are empty/whitespace (would trigger fallback)
        assume(before.strip() or after.strip())
        
        text = f"{before}<think>{inside}</think>{after}"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # The result should contain the before and after text
        # (accounting for whitespace normalization - multiple spaces become single)
        # Normalize the expected strings the same way the filter does
        def normalize_whitespace(s: str) -> str:
            s = s.strip()
            s = re.sub(r' {2,}', ' ', s)
            return s
        
        before_normalized = normalize_whitespace(before)
        after_normalized = normalize_whitespace(after)
        
        if before_normalized:
            assert before_normalized in result
        if after_normalized:
            assert after_normalized in result
    
    @settings(max_examples=100)
    @given(text=text_without_think_tags)
    def test_text_without_tags_unchanged(self, text: str):
        """
        Property: Text without think tags passes through unchanged (except whitespace).
        """
        # Skip empty strings (would trigger fallback)
        assume(text.strip())
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # Result should be the same as input (with normalized whitespace)
        assert result.strip() == text.strip() or text.strip() in result
    
    @settings(max_examples=100)
    @given(
        before=text_without_think_tags,
        inside1=think_content,
        middle=text_without_think_tags,
        inside2=think_content,
        after=text_without_think_tags
    )
    def test_multiple_external_segments_preserved(
        self, before: str, inside1: str, middle: str, inside2: str, after: str
    ):
        """
        Property: All external segments between multiple think tags are preserved.
        """
        # Skip if all external parts are empty
        assume(before.strip() or middle.strip() or after.strip())
        
        text = f"{before}<think>{inside1}</think>{middle}<think>{inside2}</think>{after}"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # All non-empty external segments should be in result
        for segment in [before.strip(), middle.strip(), after.strip()]:
            if segment:
                assert segment in result


class TestFallbackBehavior:
    """
    Tests for fallback behavior when result is empty.
    **Validates: Requirements 1.4**
    """
    
    @settings(max_examples=100)
    @given(inside=think_content)
    def test_fallback_on_only_think_content(self, inside: str):
        """
        Property: If text contains only think tags, fallback is returned.
        """
        text = f"<think>{inside}</think>"
        
        filter_instance = ThinkTagFilter()
        result = filter_instance.filter(text)
        
        # Should return fallback message
        assert result == filter_instance.fallback_message
    
    def test_fallback_on_empty_input(self):
        """
        Property: Empty input returns fallback.
        """
        filter_instance = ThinkTagFilter()
        
        assert filter_instance.filter("") == filter_instance.fallback_message
        assert filter_instance.filter(None) == filter_instance.fallback_message
    
    def test_custom_fallback_message(self):
        """
        Property: Custom fallback message is used when provided.
        """
        custom_fallback = "Custom fallback message"
        filter_instance = ThinkTagFilter(fallback_message=custom_fallback)
        
        result = filter_instance.filter("<think>only thinking</think>")
        assert result == custom_fallback
