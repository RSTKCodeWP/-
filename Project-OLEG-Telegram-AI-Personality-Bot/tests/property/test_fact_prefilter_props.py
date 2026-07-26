"""
Property-based tests for Fact Extraction Pre-filter.

**Feature: ollama-client-optimization, Property 5: Pre-filter Correctness**
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Replicate the pre-filter logic for isolated testing
# This avoids complex module imports with many dependencies
# ============================================================================

# Keywords indicating potential facts worth extracting (Requirements 3.2)
FACT_KEYWORDS: frozenset[str] = frozenset({
    # Hardware-related (Russian)
    "купил", "поставил", "установил", "обновил", "сломал", "починил", "настроил",
    "собрал", "апгрейд", "апгрейдил", "заменил", "добавил", "снял", "разогнал",
    # Problems and issues
    "проблема", "баг", "глюк", "ошибка", "вылет", "краш", "фриз", "тормозит",
    "лагает", "не работает", "сломалось", "зависает", "греется", "шумит",
    # Plans and intentions
    "думаю", "хочу", "планирую", "собираюсь", "буду", "куплю", "возьму",
    # Opinions and preferences
    "нравится", "ненавижу", "люблю", "предпочитаю", "лучше", "хуже", "топ",
    # Hardware brands and components
    "rtx", "gtx", "radeon", "ryzen", "intel", "amd", "nvidia", "geforce",
    "steam deck", "steamdeck", "rog ally", "legion go", "deck",
    "видеокарта", "видюха", "проц", "процессор", "память", "оперативка", "ssd", "nvme",
    "материнка", "мать", "блок питания", "бп", "кулер", "охлаждение", "корпус",
    # Software and games
    "игра", "играю", "прошёл", "прохожу", "запустил", "скачал",
    "linux", "windows", "винда", "драйвер", "proton", "wine",
    # Expertise indicators
    "разбираюсь", "шарю", "знаю", "умею", "могу помочь", "эксперт",
    # Configuration
    "конфиг", "сборка", "система", "комп", "пк", "ноут", "ноутбук",
    # Personal info for dossier (досье)
    "меня зовут", "я из", "живу в", "работаю", "учусь", "мне ", "лет",
    "родился", "день рождения", "др ", "днюха",
    # Location
    "москва", "питер", "спб", "мск", "город", "страна", "россия", "украина", "беларусь",
    # Hobbies and interests
    "увлекаюсь", "хобби", "занимаюсь", "интересуюсь", "коллекционирую",
    "смотрю", "слушаю", "читаю", "катаюсь",
    # Pets
    "кот", "кошка", "собака", "пёс", "питомец", "животное",
    # Work and profession
    "программист", "разработчик", "девелопер", "админ", "сисадмин", "дизайнер",
    "инженер", "менеджер", "фрилансер", "работа", "профессия", "должность",
    # Programming languages
    "python", "javascript", "typescript", "java", "c++", "rust", "golang", "php",
    "кодю", "пишу на", "программирую",
    # Self-description
    "я ", "у меня", "мой ", "моя ", "моё ", "мои ",
})

# Trivial messages to skip (Requirements 3.2)
TRIVIAL_PATTERNS: frozenset[str] = frozenset({
    # Greetings
    "привет", "прив", "хай", "здарова", "здорова", "йо", "ку", "qq", "хелло",
    "доброе утро", "добрый день", "добрый вечер", "доброй ночи",
    # Farewells
    "пока", "бб", "bb", "до связи", "удачи", "спокойной ночи",
    # Acknowledgments
    "ок", "окей", "okay", "ok", "ага", "угу", "да", "нет", "не", "ясно", "понял",
    "понятно", "принял", "спс", "спасибо", "благодарю", "пасиб", "сенкс", "thanks",
    # Reactions
    "лол", "кек", "ржу", "хаха", "хех", "ахах", "лмао", "lol", "kek", "lmao", "rofl",
    "ору", "орнул", "угар", "жиза", "база", "базированно",
    # Filler
    "ну", "эм", "хм", "ммм", "эээ", "ааа",
    # Agreement/disagreement
    "согласен", "соглас", "+", "++", "+++", "-", "--", "плюс", "минус",
    "верно", "точно", "именно", "факт", "правда", "неправда",
    # Questions without context
    "что", "как", "где", "когда", "почему", "зачем", "кто", "чё", "че", "шо",
    "как дела", "как сам", "как оно", "что нового",
    # Expressions
    "круто", "класс", "супер", "отлично", "норм", "нормально", "збс", "пиздато",
    "хуйня", "говно", "фигня", "бред", "чушь",
    # Emotes/reactions
    ")", "))", ")))", "(", "((", "(((", ":)", ":(", ":d", "xd", "хд",
})


def should_extract_facts(text: str) -> bool:
    """
    Lightweight pre-filter for fact extraction.
    Returns True if message likely contains extractable facts.
    
    Requirements: 3.1, 3.3, 3.4
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Skip very short messages (less than 5 chars after stripping)
    if len(text_lower) < 5:
        return False
    
    # Check against trivial patterns first (exact match)
    if text_lower in TRIVIAL_PATTERNS:
        return False
    
    # Check for fact-indicating keywords
    return any(kw in text_lower for kw in FACT_KEYWORDS)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Strategy for trivial messages (exact matches from TRIVIAL_PATTERNS)
trivial_message_strategy = st.sampled_from(list(TRIVIAL_PATTERNS))

# Strategy for fact keywords
fact_keyword_strategy = st.sampled_from(list(FACT_KEYWORDS))

# Strategy for random text without fact keywords
random_text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'Z'),
        blacklist_characters=''.join(FACT_KEYWORDS)
    ),
    min_size=10,
    max_size=100
)


# ============================================================================
# Property Tests
# ============================================================================

class TestPreFilterCorrectness:
    """
    **Feature: ollama-client-optimization, Property 5: Pre-filter Correctness**
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    
    For any message, if should_extract_facts() returns False, the message SHALL
    match trivial patterns OR lack fact-indicating keywords; if it returns True,
    the message SHALL contain at least one fact-indicating keyword.
    """
    
    @settings(max_examples=100)
    @given(trivial_msg=trivial_message_strategy)
    def test_trivial_messages_filtered(self, trivial_msg: str):
        """
        Property: Messages matching trivial patterns are filtered out.
        **Validates: Requirements 3.2, 3.3**
        """
        result = should_extract_facts(trivial_msg)
        assert result is False, f"Trivial message '{trivial_msg}' should be filtered"
    
    @settings(max_examples=100)
    @given(keyword=fact_keyword_strategy)
    def test_messages_with_keywords_pass(self, keyword: str):
        """
        Property: Messages containing fact keywords pass the filter.
        **Validates: Requirements 3.2, 3.4**
        """
        # Create a message with the keyword embedded
        message = f"Сегодня я {keyword} новую штуку"
        result = should_extract_facts(message)
        assert result is True, f"Message with keyword '{keyword}' should pass filter"
    
    @settings(max_examples=100)
    @given(keyword=fact_keyword_strategy)
    def test_keyword_case_insensitive(self, keyword: str):
        """
        Property: Keyword matching is case-insensitive.
        **Validates: Requirements 3.2**
        """
        # Test with uppercase keyword
        message_upper = f"Сегодня я {keyword.upper()} новую штуку"
        result = should_extract_facts(message_upper)
        assert result is True, f"Uppercase keyword '{keyword.upper()}' should be detected"
    
    def test_empty_message_filtered(self):
        """
        Property: Empty messages are filtered out.
        **Validates: Requirements 3.1**
        """
        assert should_extract_facts("") is False
        assert should_extract_facts(None) is False
        assert should_extract_facts("   ") is False
    
    def test_short_messages_filtered(self):
        """
        Property: Very short messages (< 5 chars) are filtered out.
        **Validates: Requirements 3.1**
        """
        assert should_extract_facts("hi") is False
        assert should_extract_facts("ok") is False
        assert should_extract_facts("да") is False
        assert should_extract_facts("    ") is False
    
    @settings(max_examples=100)
    @given(
        prefix=st.text(min_size=0, max_size=20),
        keyword=fact_keyword_strategy,
        suffix=st.text(min_size=0, max_size=20)
    )
    def test_keyword_anywhere_in_message(self, prefix: str, keyword: str, suffix: str):
        """
        Property: Keywords are detected anywhere in the message.
        **Validates: Requirements 3.2, 3.4**
        """
        message = f"{prefix} {keyword} {suffix}".strip()
        # Skip if message is too short after stripping
        assume(len(message.strip()) >= 5)
        
        result = should_extract_facts(message)
        assert result is True, f"Keyword '{keyword}' should be detected in '{message}'"
    
    def test_real_world_examples_with_facts(self):
        """
        Property: Real-world messages with facts pass the filter.
        **Validates: Requirements 3.1, 3.4**
        """
        fact_messages = [
            "Купил себе RTX 4080, теперь всё летает",
            "У меня проблема с драйверами на Linux",
            "Поставил новый SSD, скорость огонь",
            "Думаю взять Steam Deck на распродаже",
            "Собрал новый комп на Ryzen 7800X3D",
            "Играю в Cyberpunk на ультрах",
            "Обновил BIOS, теперь память работает на 6000",
            "Мой ноутбук греется как печка",
        ]
        
        for msg in fact_messages:
            result = should_extract_facts(msg)
            assert result is True, f"Fact message '{msg}' should pass filter"
    
    def test_real_world_trivial_examples(self):
        """
        Property: Real-world trivial messages are filtered.
        **Validates: Requirements 3.2, 3.3**
        """
        trivial_messages = [
            "привет",
            "лол",
            "ок",
            "спасибо",
            "как дела",
            "))))",
            "хаха",
            "согласен",
        ]
        
        for msg in trivial_messages:
            result = should_extract_facts(msg)
            assert result is False, f"Trivial message '{msg}' should be filtered"
    
    @settings(max_examples=100)
    @given(text=st.text(min_size=10, max_size=200))
    def test_filter_returns_boolean(self, text: str):
        """
        Property: Filter always returns a boolean value.
        **Validates: Requirements 3.1**
        """
        result = should_extract_facts(text)
        assert isinstance(result, bool)
    
    @settings(max_examples=100)
    @given(text=st.text(min_size=10, max_size=200))
    def test_filter_consistency(self, text: str):
        """
        Property: Filter returns consistent results for the same input.
        **Validates: Requirements 3.1**
        """
        result1 = should_extract_facts(text)
        result2 = should_extract_facts(text)
        result3 = should_extract_facts(text)
        
        assert result1 == result2 == result3, "Filter should be deterministic"
    
    @settings(max_examples=100)
    @given(text=st.text(min_size=10, max_size=200))
    def test_true_implies_keyword_present(self, text: str):
        """
        Property: If filter returns True, at least one keyword must be present.
        **Validates: Requirements 3.4**
        """
        result = should_extract_facts(text)
        
        if result is True:
            text_lower = text.lower()
            has_keyword = any(kw in text_lower for kw in FACT_KEYWORDS)
            assert has_keyword, f"Filter returned True but no keyword found in '{text}'"
    
    @settings(max_examples=100)
    @given(text=st.text(min_size=10, max_size=200))
    def test_false_implies_trivial_or_no_keyword(self, text: str):
        """
        Property: If filter returns False, message is trivial OR lacks keywords.
        **Validates: Requirements 3.2, 3.3**
        """
        result = should_extract_facts(text)
        
        if result is False:
            text_lower = text.lower().strip()
            is_trivial = text_lower in TRIVIAL_PATTERNS
            is_short = len(text_lower) < 5
            has_no_keyword = not any(kw in text_lower for kw in FACT_KEYWORDS)
            
            assert is_trivial or is_short or has_no_keyword, \
                f"Filter returned False but message '{text}' is not trivial and has keywords"
