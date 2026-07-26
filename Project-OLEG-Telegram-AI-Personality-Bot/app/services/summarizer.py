"""Summarizer service for content summarization.

This module provides summarization functionality including:
- 2-sentence summary generation in Oleg's style
- URL content fetching and summarization
- Short content rejection (< 100 chars)
- Voice option for summaries

**Feature: fortress-update**
**Validates: Requirements 6.1, 6.3, 6.5**
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.services.http_clients import get_web_client

logger = logging.getLogger(__name__)

# Summarizer Configuration
MIN_CONTENT_LENGTH = 100
MAX_SENTENCES = 2
URL_FETCH_TIMEOUT = 10

# URL pattern for detection
URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+',
    re.IGNORECASE
)


@dataclass
class SummaryResult:
    """Result of summarization."""
    summary: str
    original_length: int
    is_too_short: bool
    source_type: str  # message, article, forwarded
    sentence_count: int


class SummarizerService:
    """
    Summarizer service for generating content summaries.
    
    Provides summarization with Oleg's characteristic style,
    URL content fetching, and short content rejection.
    
    **Feature: fortress-update**
    **Validates: Requirements 6.1, 6.3, 6.5**
    """
    
    def __init__(self, ollama_client=None):
        """
        Initialize Summarizer service.
        
        Args:
            ollama_client: Optional Ollama client for LLM summarization
        """
        self._ollama_client = ollama_client
        self._is_available = True
    
    def is_too_short(self, content: str) -> bool:
        """
        Check if content is too short for summarization.
        
        **Property 15: Short content rejection**
        For any content with length less than 100 characters, 
        the summarizer SHALL return is_too_short=true.
        
        Args:
            content: Content to check
            
        Returns:
            True if content is too short (< 100 chars)
        """
        if not content:
            return True
        return len(content.strip()) < MIN_CONTENT_LENGTH
    
    def contains_url(self, text: str) -> bool:
        """
        Check if text contains a URL.
        
        **Property 16: URL detection**
        For any message containing a URL pattern, the summarizer 
        SHALL attempt to fetch the article content.
        
        Args:
            text: Text to check for URLs
            
        Returns:
            True if text contains a URL
        """
        if not text:
            return False
        return bool(URL_PATTERN.search(text))
    
    def extract_urls(self, text: str) -> list[str]:
        """
        Extract all URLs from text.
        
        Args:
            text: Text to extract URLs from
            
        Returns:
            List of URLs found in text
        """
        if not text:
            return []
        return URL_PATTERN.findall(text)
    
    def count_sentences(self, text: str) -> int:
        """
        Count the number of sentences in text.
        
        Uses simple sentence boundary detection based on
        punctuation marks (. ! ?) followed by space or end.
        
        Args:
            text: Text to count sentences in
            
        Returns:
            Number of sentences
        """
        if not text or not text.strip():
            return 0
        
        # Simple sentence boundary detection
        # Match . ! ? followed by space, newline, or end of string
        sentence_endings = re.findall(r'[.!?]+(?:\s|$)', text)
        
        # If no sentence endings found but text exists, count as 1 sentence
        if not sentence_endings and text.strip():
            return 1
        
        return len(sentence_endings)
    
    def limit_sentences(self, text: str, max_sentences: int = MAX_SENTENCES) -> str:
        """
        Limit text to a maximum number of sentences.
        
        **Property 14: Summary sentence limit**
        For any summarization output, the result SHALL contain 
        at most 2 sentences.
        
        Args:
            text: Text to limit
            max_sentences: Maximum number of sentences (default 2)
            
        Returns:
            Text limited to max_sentences
        """
        if not text or not text.strip():
            return ""
        
        # Split by sentence boundaries while keeping the delimiters
        # This regex splits on . ! ? followed by whitespace
        parts = re.split(r'([.!?]+\s*)', text)
        
        sentences = []
        current_sentence = ""
        
        for part in parts:
            if re.match(r'^[.!?]+\s*$', part):
                # This is a sentence ending
                current_sentence += part
                sentences.append(current_sentence.strip())
                current_sentence = ""
            else:
                current_sentence += part
        
        # Add any remaining text as a sentence
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # Take only max_sentences
        limited = sentences[:max_sentences]
        
        # Join back together
        result = " ".join(limited)
        
        # Ensure proper ending punctuation
        if result and not result[-1] in '.!?':
            result += '.'
        
        return result
    
    async def fetch_article(self, url: str) -> Optional[str]:
        """
        Fetch article content from URL.
        
        **Property 16: URL detection**
        For any message containing a URL pattern, the summarizer 
        SHALL attempt to fetch the article content.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Article text content, or None if fetch failed
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid URL format: {url}")
                return None
            
            client = get_web_client()
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                follow_redirects=True,
                timeout=URL_FETCH_TIMEOUT
            )
            response.raise_for_status()
            
            html = response.text
            
            # Simple HTML to text extraction
            # Remove script and style elements
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Decode HTML entities
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&quot;', '"')
            text = text.replace('&#39;', "'")
            
            return text if text else None
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching URL: {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching URL {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
    
    async def summarize(
        self,
        content: str,
        style: str = "oleg",
        source_type: str = "message"
    ) -> SummaryResult:
        """
        Summarize content in Oleg's style.
        
        **Property 14: Summary sentence limit**
        For any summarization output, the result SHALL contain 
        at most 2 sentences.
        
        **Property 15: Short content rejection**
        For any content with length less than 100 characters, 
        the summarizer SHALL return is_too_short=true.
        
        Args:
            content: Content to summarize
            style: Summary style (default "oleg")
            source_type: Source type (message, article, forwarded)
            
        Returns:
            SummaryResult with summary and metadata
        """
        original_length = len(content) if content else 0
        
        # Check if content is too short
        if self.is_too_short(content):
            return SummaryResult(
                summary="Тут и так всё понятно, чё пересказывать?",
                original_length=original_length,
                is_too_short=True,
                source_type=source_type,
                sentence_count=1
            )
        
        # Generate summary using LLM if available
        if self._ollama_client:
            try:
                summary = await self._generate_llm_summary(content, style)
            except Exception as e:
                logger.error(f"LLM summarization failed: {e}")
                summary = self._generate_fallback_summary(content)
        else:
            summary = self._generate_fallback_summary(content)
        
        # Ensure summary is limited to 2 sentences
        summary = self.limit_sentences(summary, MAX_SENTENCES)
        sentence_count = self.count_sentences(summary)
        
        return SummaryResult(
            summary=summary,
            original_length=original_length,
            is_too_short=False,
            source_type=source_type,
            sentence_count=sentence_count
        )
    
    async def _generate_llm_summary(self, content: str, style: str) -> str:
        """
        Generate summary using LLM.
        
        Args:
            content: Content to summarize
            style: Summary style
            
        Returns:
            Generated summary
        """
        # This would call the Ollama client in production
        # For now, use fallback
        return self._generate_fallback_summary(content)
    
    def _generate_fallback_summary(self, content: str) -> str:
        """
        Generate a simple fallback summary without LLM.
        
        Takes the first two sentences of the content.
        
        Args:
            content: Content to summarize
            
        Returns:
            Simple summary (first 2 sentences)
        """
        if not content:
            return ""
        
        # Clean up the content
        content = content.strip()
        
        # Limit to first 2 sentences
        return self.limit_sentences(content, MAX_SENTENCES)
    
    async def summarize_with_voice_option(
        self,
        content: str,
        chat_id: int,
        message_id: int
    ) -> tuple[SummaryResult, Optional[dict]]:
        """
        Summarize content and provide voice option.
        
        Args:
            content: Content to summarize
            chat_id: Chat ID for voice option
            message_id: Message ID for voice option
            
        Returns:
            Tuple of (SummaryResult, voice_button_data or None)
        """
        result = await self.summarize(content)
        
        # If content was too short, no voice option
        if result.is_too_short:
            return result, None
        
        # Provide voice option data
        voice_data = {
            "action": "voice_summary",
            "chat_id": chat_id,
            "message_id": message_id,
            "text": result.summary
        }
        
        return result, voice_data
    
    @property
    def is_available(self) -> bool:
        """Check if summarizer service is currently available."""
        return self._is_available
    
    def set_available(self, available: bool) -> None:
        """Set summarizer service availability status."""
        self._is_available = available


# Global summarizer service instance
summarizer_service = SummarizerService()
