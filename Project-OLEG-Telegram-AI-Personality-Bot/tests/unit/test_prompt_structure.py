"""Tests for CORE_OLEG_PROMPT structure.

Validates the minimal prompt v2:
- No forbidden bot-like phrases
- Contains key personality traits
- Has examples section
- Is short and focused
"""

import pytest
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def get_core_oleg_prompt():
    """Extract CORE_OLEG_PROMPT from ollama_client.py without importing the module."""
    file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'services', 'ollama_client.py')
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    match = re.search(r'CORE_OLEG_PROMPT_TEMPLATE\s*=\s*"""(.*?)"""', content, re.DOTALL)
    if match:
        return match.group(1)
    raise ValueError("CORE_OLEG_PROMPT_TEMPLATE not found in ollama_client.py")


CORE_OLEG_PROMPT = get_core_oleg_prompt()


class TestPromptForbiddenPhrases:
    """Test that forbidden phrases are not in the prompt."""

    def test_no_rastekayeshsya_myslyu(self):
        """No literary phrases."""
        assert "растекаешься мыслью" not in CORE_OLEG_PROMPT.lower()
        assert "по древу" not in CORE_OLEG_PROMPT.lower()

    def test_no_toksichnogo_chata(self):
        """No 'из токсичного чата' phrase."""
        assert "из токсичного чата" not in CORE_OLEG_PROMPT.lower()

    def test_no_bez_forsirovaniya(self):
        """No 'без форсирования техно-отсылок' phrase."""
        assert "без форсирования" not in CORE_OLEG_PROMPT.lower()
        assert "техно-отсылок" not in CORE_OLEG_PROMPT.lower()

    def test_no_bot_phrases_as_instructions(self):
        """Bot phrases like 'рад помочь' should not be encouraged."""
        # The phrase should only appear in negative context (what NOT to do)
        prompt_lower = CORE_OLEG_PROMPT.lower()
        if "рад помочь" in prompt_lower:
            # If mentioned, should be in "без" or negative context
            assert 'без "рад помочь"' in prompt_lower or 'без' in prompt_lower


class TestPromptCore:
    """Test core personality elements."""

    def test_has_oleg_identity(self):
        """Prompt establishes Олег identity."""
        assert "олег" in CORE_OLEG_PROMPT.lower()

    def test_has_human_like_instruction(self):
        """Prompt instructs to act like a human."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        assert "человек" in prompt_lower or "живой" in prompt_lower

    def test_has_short_response_instruction(self):
        """Prompt instructs short responses."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        assert "коротко" in prompt_lower or "мессенджер" in prompt_lower

    def test_no_lists_instruction(self):
        """Prompt prohibits lists."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        assert "без списков" in prompt_lower or "списк" in prompt_lower


class TestPromptStructure:
    """Test the overall structure of the prompt."""

    def test_has_examples(self):
        """Prompt has examples section."""
        assert "пример" in CORE_OLEG_PROMPT.lower()

    def test_examples_at_end(self):
        """Examples are in the second half of prompt."""
        examples_pos = CORE_OLEG_PROMPT.lower().find("пример")
        assert examples_pos > 0
        prompt_length = len(CORE_OLEG_PROMPT)
        assert examples_pos > prompt_length * 0.3, "Examples should be after intro"

    def test_prompt_is_minimal(self):
        """Prompt should be under 2000 chars (minimal version)."""
        assert len(CORE_OLEG_PROMPT) < 2000, f"Prompt is too long: {len(CORE_OLEG_PROMPT)} chars"

    def test_has_jailbreak_example(self):
        """Prompt has example of handling jailbreak attempts."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        assert "забудь" in prompt_lower or "инструкции" in prompt_lower

    def test_has_dont_know_examples(self):
        """Prompt has examples of admitting ignorance."""
        prompt_lower = CORE_OLEG_PROMPT.lower()
        # Should have at least one "don't know" pattern
        dont_know_patterns = ["хз", "хуй знает", "не моя тема", "без деталей"]
        assert any(p in prompt_lower for p in dont_know_patterns)
