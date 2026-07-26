"""
Property-based tests for SummarizerService.

**Feature: fortress-update, Property 14: Summary sentence limit**
**Validates: Requirements 6.1**

**Feature: fortress-update, Property 15: Short content rejection**
**Validates: Requirements 6.5**

**Feature: fortress-update, Property 16: URL detection**
**Validates: Requirements 6.3**
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume
import pytest

# Import Summarizer module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'summarizer.py')
_spec = importlib.util.spec_from_file_location("summarizer", _module_path)
_summarizer_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_summarizer_module)

SummarizerService = _summarizer_module.SummarizerService
SummaryResult = _summarizer_module.SummaryResult
MIN_CONTENT_LENGTH = _summarizer_module.MIN_CONTENT_LENGTH
MAX_SENTENCES = _summarizer_module.MAX_SENTENCES
URL_PATTERN = _summarizer_module.URL_PATTERN


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for generating short content (< 100 chars)
short_content = st.text(min_size=0, max_size=MIN_CONTENT_LENGTH - 1)

# Strategy for generating long content (>= 100 chars)
long_content = st.text(min_size=MIN_CONTENT_LENGTH, max_size=2000)

# Strategy for generating multi-sentence text
def multi_sentence_text(min_sentences: int = 3, max_sentences: int = 10):
    """Generate text with multiple sentences."""
    sentence = st.text(min_size=5, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'Z'),
        blacklist_characters='.!?'
    ))
    endings = st.sampled_from(['. ', '! ', '? '])
    
    return st.lists(
        st.tuples(sentence, endings),
        min_size=min_sentences,
        max_size=max_sentences
    ).map(lambda pairs: ''.join(s + e for s, e in pairs))

# Strategy for generating valid URLs
valid_urls = st.sampled_from([
    "https://example.com",
    "http://test.org/page",
    "https://www.google.com/search?q=test",
    "http://localhost:8080/api/v1",
    "https://sub.domain.co.uk/path/to/resource",
])

# Strategy for text without URLs
text_without_urls = st.text(
    min_size=0, 
    max_size=500,
    alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'Z'),
        blacklist_characters=':'  # Avoid creating URL-like patterns
    )
)


# ============================================================================
# Property 14: Summary Sentence Limit
# ============================================================================

class TestSummarySentenceLimit:
    """
    **Feature: fortress-update, Property 14: Summary sentence limit**
    **Validates: Requirements 6.1**
    
    For any summarization output, the result SHALL contain at most 2 sentences.
    """
    
    def test_limit_sentences_caps_at_max(self):
        """
        Property: limit_sentences returns at most MAX_SENTENCES sentences.
        
        Uses explicit test cases to avoid hypothesis filtering issues.
        """
        service = SummarizerService()
        
        # Test with various multi-sentence texts
        test_cases = [
            "One. Two. Three. Four. Five.",
            "First sentence! Second sentence? Third sentence. Fourth sentence!",
            "A" * 30 + ". " + "B" * 30 + ". " + "C" * 30 + ". " + "D" * 30 + ".",
            "Hello world. How are you today. I am doing fine. Thanks for asking.",
            "Short. Medium length sentence here. Another one that is longer. And more.",
        ]
        
        for text in test_cases:
            result = service.limit_sentences(text)
            sentence_count = service.count_sentences(result)
            assert sentence_count <= MAX_SENTENCES, f"Failed for: {text[:50]}..."
    
    @settings(max_examples=100)
    @given(text=multi_sentence_text(min_sentences=1, max_sentences=2))
    def test_short_text_preserved(self, text: str):
        """
        Property: Text with <= 2 sentences is preserved.
        """
        service = SummarizerService()
        original_count = service.count_sentences(text)
        
        assume(original_count <= MAX_SENTENCES)
        
        result = service.limit_sentences(text)
        result_count = service.count_sentences(result)
        
        # Result should have same or fewer sentences
        assert result_count <= original_count
    
    @settings(max_examples=100)
    @given(text=st.text(min_size=1, max_size=500))
    def test_limit_sentences_returns_string(self, text: str):
        """
        Property: limit_sentences always returns a string.
        """
        service = SummarizerService()
        result = service.limit_sentences(text)
        
        assert isinstance(result, str)
    
    def test_empty_text_returns_empty(self):
        """
        Property: Empty text returns empty string.
        """
        service = SummarizerService()
        
        result = service.limit_sentences("")
        
        assert result == ""
    
    def test_single_sentence_preserved(self):
        """
        Property: Single sentence is preserved.
        """
        service = SummarizerService()
        text = "This is a single sentence."
        
        result = service.limit_sentences(text)
        
        assert service.count_sentences(result) == 1
    
    def test_two_sentences_preserved(self):
        """
        Property: Two sentences are preserved.
        """
        service = SummarizerService()
        text = "First sentence. Second sentence."
        
        result = service.limit_sentences(text)
        
        assert service.count_sentences(result) == 2
    
    def test_three_sentences_limited_to_two(self):
        """
        Property: Three sentences are limited to two.
        """
        service = SummarizerService()
        text = "First sentence. Second sentence. Third sentence."
        
        result = service.limit_sentences(text)
        
        assert service.count_sentences(result) <= 2
    
    @pytest.mark.asyncio
    async def test_summarize_limits_sentences(self):
        """
        Property: summarize() output has at most 2 sentences.
        
        Uses explicit test cases instead of hypothesis to avoid
        filtering issues with multi-sentence text generation.
        """
        service = SummarizerService()
        
        # Test with various multi-sentence texts that are long enough
        test_cases = [
            "First sentence here. Second sentence here. Third sentence here. Fourth sentence here.",
            "This is one. This is two. This is three. This is four. This is five.",
            "Hello world! How are you? I am fine. Thanks for asking. Have a nice day!",
            "A" * 50 + ". " + "B" * 50 + ". " + "C" * 50 + ". " + "D" * 50 + ".",
        ]
        
        for text in test_cases:
            result = await service.summarize(text)
            assert result.sentence_count <= MAX_SENTENCES, f"Failed for: {text[:50]}..."


# ============================================================================
# Property 15: Short Content Rejection
# ============================================================================

class TestShortContentRejection:
    """
    **Feature: fortress-update, Property 15: Short content rejection**
    **Validates: Requirements 6.5**
    
    For any content with length less than 100 characters, 
    the summarizer SHALL return is_too_short=true.
    """
    
    @settings(max_examples=100)
    @given(text=short_content)
    def test_short_content_detected(self, text: str):
        """
        Property: Content < 100 chars is detected as too short.
        """
        assume(len(text.strip()) < MIN_CONTENT_LENGTH)
        
        service = SummarizerService()
        result = service.is_too_short(text)
        
        assert result is True
    
    @settings(max_examples=100)
    @given(text=long_content)
    def test_long_content_not_rejected(self, text: str):
        """
        Property: Content >= 100 chars is not rejected.
        """
        assume(len(text.strip()) >= MIN_CONTENT_LENGTH)
        
        service = SummarizerService()
        result = service.is_too_short(text)
        
        assert result is False
    
    def test_empty_string_is_too_short(self):
        """
        Property: Empty string is too short.
        """
        service = SummarizerService()
        
        assert service.is_too_short("") is True
        assert service.is_too_short(None) is True
    
    def test_whitespace_only_is_too_short(self):
        """
        Property: Whitespace-only content is too short.
        """
        service = SummarizerService()
        
        assert service.is_too_short("   ") is True
        assert service.is_too_short("\n\t\n") is True
    
    def test_exactly_99_chars_is_too_short(self):
        """
        Property: Content with exactly 99 chars is too short.
        """
        service = SummarizerService()
        text = "a" * 99
        
        assert service.is_too_short(text) is True
    
    def test_exactly_100_chars_is_not_too_short(self):
        """
        Property: Content with exactly 100 chars is not too short.
        """
        service = SummarizerService()
        text = "a" * 100
        
        assert service.is_too_short(text) is False
    
    @pytest.mark.asyncio
    @settings(max_examples=50)
    @given(text=short_content)
    async def test_summarize_returns_too_short_flag(self, text: str):
        """
        Property: summarize() sets is_too_short=True for short content.
        """
        assume(len(text.strip()) < MIN_CONTENT_LENGTH)
        
        service = SummarizerService()
        result = await service.summarize(text)
        
        assert result.is_too_short is True
    
    @pytest.mark.asyncio
    @settings(max_examples=50)
    @given(text=long_content)
    async def test_summarize_not_too_short_for_long_content(self, text: str):
        """
        Property: summarize() sets is_too_short=False for long content.
        """
        assume(len(text.strip()) >= MIN_CONTENT_LENGTH)
        
        service = SummarizerService()
        result = await service.summarize(text)
        
        assert result.is_too_short is False


# ============================================================================
# Property 16: URL Detection
# ============================================================================

class TestURLDetection:
    """
    **Feature: fortress-update, Property 16: URL detection**
    **Validates: Requirements 6.3**
    
    For any message containing a URL pattern, the summarizer 
    SHALL attempt to fetch the article content.
    """
    
    @settings(max_examples=100)
    @given(url=valid_urls)
    def test_url_detected_in_text(self, url: str):
        """
        Property: Valid URLs are detected in text.
        """
        service = SummarizerService()
        text = f"Check out this link: {url} for more info."
        
        assert service.contains_url(text) is True
    
    @settings(max_examples=100)
    @given(url=valid_urls)
    def test_url_extracted_from_text(self, url: str):
        """
        Property: URLs are correctly extracted from text.
        """
        service = SummarizerService()
        text = f"Check out this link: {url} for more info."
        
        urls = service.extract_urls(text)
        
        assert len(urls) >= 1
        assert url in urls
    
    @settings(max_examples=100)
    @given(text=text_without_urls)
    def test_no_url_in_plain_text(self, text: str):
        """
        Property: Plain text without URLs returns False.
        """
        # Filter out any text that accidentally contains URL patterns
        assume('http' not in text.lower())
        assume('://' not in text)
        
        service = SummarizerService()
        
        assert service.contains_url(text) is False
    
    def test_empty_string_no_url(self):
        """
        Property: Empty string has no URLs.
        """
        service = SummarizerService()
        
        assert service.contains_url("") is False
        assert service.contains_url(None) is False
    
    def test_multiple_urls_detected(self):
        """
        Property: Multiple URLs are all detected.
        """
        service = SummarizerService()
        text = "Visit https://example.com and http://test.org for info."
        
        urls = service.extract_urls(text)
        
        assert len(urls) == 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls
    
    def test_https_url_detected(self):
        """
        Property: HTTPS URLs are detected.
        """
        service = SummarizerService()
        
        assert service.contains_url("https://example.com") is True
    
    def test_http_url_detected(self):
        """
        Property: HTTP URLs are detected.
        """
        service = SummarizerService()
        
        assert service.contains_url("http://example.com") is True
    
    def test_url_with_path_detected(self):
        """
        Property: URLs with paths are detected.
        """
        service = SummarizerService()
        
        assert service.contains_url("https://example.com/path/to/page") is True
    
    def test_url_with_query_params_detected(self):
        """
        Property: URLs with query parameters are detected.
        """
        service = SummarizerService()
        
        assert service.contains_url("https://example.com?foo=bar&baz=qux") is True
    
    def test_extract_urls_empty_list_for_no_urls(self):
        """
        Property: extract_urls returns empty list when no URLs.
        """
        service = SummarizerService()
        
        assert service.extract_urls("No URLs here") == []
        assert service.extract_urls("") == []
        assert service.extract_urls(None) == []


# ============================================================================
# Additional Summarizer Service Tests
# ============================================================================

class TestSummarizerServiceBasics:
    """
    Basic tests for SummarizerService functionality.
    """
    
    def test_service_initialization(self):
        """
        Property: SummarizerService initializes correctly.
        """
        service = SummarizerService()
        
        assert service is not None
        assert service.is_available is True
    
    def test_service_availability_toggle(self):
        """
        Property: Service availability can be toggled.
        """
        service = SummarizerService()
        
        assert service.is_available is True
        
        service.set_available(False)
        assert service.is_available is False
        
        service.set_available(True)
        assert service.is_available is True
    
    @settings(max_examples=50)
    @given(text=st.text(min_size=0, max_size=500))
    def test_count_sentences_non_negative(self, text: str):
        """
        Property: Sentence count is always non-negative.
        """
        service = SummarizerService()
        
        count = service.count_sentences(text)
        
        assert count >= 0
    
    def test_count_sentences_examples(self):
        """
        Property: Sentence counting works for known examples.
        """
        service = SummarizerService()
        
        assert service.count_sentences("") == 0
        assert service.count_sentences("Hello") == 1
        assert service.count_sentences("Hello.") == 1
        assert service.count_sentences("Hello. World.") == 2
        assert service.count_sentences("Hello! World?") == 2
        assert service.count_sentences("One. Two. Three.") == 3
    
    @pytest.mark.asyncio
    async def test_summarize_returns_summary_result(self):
        """
        Property: summarize() returns a SummaryResult.
        """
        service = SummarizerService()
        text = "a" * 150  # Long enough content
        
        result = await service.summarize(text)
        
        assert isinstance(result, SummaryResult)
        assert hasattr(result, 'summary')
        assert hasattr(result, 'original_length')
        assert hasattr(result, 'is_too_short')
        assert hasattr(result, 'source_type')
        assert hasattr(result, 'sentence_count')
    
    @pytest.mark.asyncio
    async def test_summarize_preserves_original_length(self):
        """
        Property: summarize() records original content length.
        """
        service = SummarizerService()
        text = "a" * 200
        
        result = await service.summarize(text)
        
        assert result.original_length == 200
