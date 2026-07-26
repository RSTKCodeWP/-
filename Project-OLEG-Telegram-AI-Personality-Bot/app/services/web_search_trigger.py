"""
Smart Web Search Trigger — умная система определения когда нужен поиск.

Вместо тупых триггеров по словам — категоризация вопросов:
1. НИКОГДА не искать — болтовня, базовые знания, код
2. ВОЗМОЖНО искать — если LLM не уверен (self-assessment)
3. ВСЕГДА искать — цены, релизы, актуальные новости

**Feature: anti-hallucination-v2**
"""

import logging
import re
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SearchPriority(Enum):
    """Приоритет поиска."""
    NEVER = "never"           # Никогда не искать
    LOW = "low"               # Только если LLM не уверен
    MEDIUM = "medium"         # Искать если есть время
    HIGH = "high"             # Всегда искать
    CRITICAL = "critical"     # Критично — без поиска нельзя отвечать


# =============================================================================
# КАТЕГОРИИ ВОПРОСОВ
# =============================================================================

# НИКОГДА не нужен поиск — болтовня, вопросы про бота, базовые знания
NEVER_SEARCH_PATTERNS = [
    # Болтовня
    r"^(привет|здарова|хай|йо|ку|здравствуй)",
    r"^как (дела|жизнь|сам|ты)\??$",
    r"^(спасибо|благодарю|пасиб|спс)",
    r"^(пока|бб|до свидания|удачи)",
    r"^(лол|кек|ахах|хаха|ржу|смешно)",
    r"^(да|нет|ок|окей|понял|ясно|норм)$",
    # Вопросы про бота
    r"(кто ты|что ты|ты кто|ты что)",
    r"(твои характеристики|твоё железо|на чём ты работаешь)",
    r"(расскажи о себе|что умеешь)",
    # Базовые знания (не требуют актуальности)
    r"^что такое (gpu|cpu|ram|ssd|hdd|psu|mobo)\??$",
    r"^(объясни|расскажи) (что такое|как работает)",
    r"^в чём разница между .* и .*\?$",  # Концептуальные вопросы
]

# ВСЕГДА нужен поиск — актуальная информация
ALWAYS_SEARCH_PATTERNS = [
    # Цены (меняются постоянно)
    r"(сколько стоит|цена|ценник|почём|за сколько)",
    r"(где купить|где заказать|где взять)",
    # Релизы и новости
    r"(когда выйдет|когда релиз|дата выхода)",
    r"(вышла ли|вышел ли|уже вышла)",
    r"(последние новости|что нового|новости про)",
    # Актуальные версии
    r"(последняя версия|актуальная версия|свежий драйвер)",
    r"(какой сейчас|на данный момент)",
    # Конкретные вопросы о существовании
    r"(существует ли|есть ли|выпустили ли)",
]

# ВЫСОКИЙ приоритет — технические вопросы о железе
HIGH_PRIORITY_PATTERNS = [
    # Характеристики конкретных моделей
    r"(rtx|gtx|rx|arc)\s*\d{4}",  # RTX 4070, RX 7900
    r"(ryzen|core|i[3579]|xeon)\s*\d",  # Ryzen 7, i5, Core
    r"(сколько|какой|какая)\s*(vram|памяти|ядер|потоков|tdp|частота)",
    # Сравнения конкретных моделей
    r"(rtx|rx|arc)\s*\d+.*(vs|или|против)",
    r"что лучше.*(rtx|rx|ryzen|intel)",
    # Бенчмарки и тесты
    r"(benchmark|бенчмарк|тест|fps в)",
]

# СРЕДНИЙ приоритет — может понадобиться поиск
MEDIUM_PRIORITY_PATTERNS = [
    # Рекомендации по сборкам
    r"(собрать|сборка|конфиг).*(пк|комп|компьютер)",
    r"(что взять|что выбрать|посоветуй)",
    # Совместимость
    r"(совместим|подойдёт|будет работать)",
    # Проблемы (могут быть известные баги)
    r"(не работает|баг|глюк|проблема|ошибка)",
]


# =============================================================================
# ПРИМЕРЫ ДЛЯ LLM (self-assessment)
# =============================================================================

SEARCH_DECISION_EXAMPLES = """
ПРИМЕРЫ КОГДА НУЖЕН ПОИСК:
- "сколько стоит RTX 5090?" → НУЖЕН (цены меняются)
- "когда выйдет GTA 6?" → НУЖЕН (актуальная дата)
- "какой последний драйвер NVIDIA?" → НУЖЕН (версии обновляются)
- "вышла ли Windows 12?" → НУЖЕН (факт о релизе)
- "RTX 5070 vs RX 9070 что лучше?" → НУЖЕН (свежие бенчмарки)
- "какая архитектура у RTX 5080?" → НУЖЕН (новое железо)

ПРИМЕРЫ КОГДА НЕ НУЖЕН ПОИСК:
- "привет, как дела?" → НЕ НУЖЕН (болтовня)
- "что такое GPU?" → НЕ НУЖЕН (базовые знания)
- "помоги с кодом на Python" → НЕ НУЖЕН (код)
- "в чём разница между SSD и HDD?" → НЕ НУЖЕН (концепция)
- "RTX 4070 сколько VRAM?" → НЕ НУЖЕН (есть в базе знаний)
- "какой процессор для игр?" → ВОЗМОЖНО (общий совет vs конкретные цены)

ПРАВИЛО: Если не уверен в актуальности информации — лучше поискать.
"""


def get_search_priority(text: str) -> tuple[SearchPriority, str]:
    """
    Определяет приоритет поиска для вопроса.
    
    Returns:
        (приоритет, причина)
    """
    if not text:
        return SearchPriority.NEVER, "empty"
    
    text_lower = text.lower().strip()
    
    # 1. СНАЧАЛА проверяем ALWAYS паттерны — они имеют приоритет!
    for pattern in ALWAYS_SEARCH_PATTERNS:
        if re.search(pattern, text_lower):
            return SearchPriority.CRITICAL, f"always_pattern:{pattern[:20]}"
    
    # 2. Проверяем HIGH паттерны
    for pattern in HIGH_PRIORITY_PATTERNS:
        if re.search(pattern, text_lower):
            return SearchPriority.HIGH, f"high_pattern:{pattern[:20]}"
    
    # 3. Теперь проверяем NEVER паттерны (только если нет важных триггеров)
    for pattern in NEVER_SEARCH_PATTERNS:
        if re.search(pattern, text_lower):
            return SearchPriority.NEVER, f"never_pattern:{pattern[:20]}"
    
    # 4. Проверяем MEDIUM паттерны
    for pattern in MEDIUM_PRIORITY_PATTERNS:
        if re.search(pattern, text_lower):
            return SearchPriority.MEDIUM, f"medium_pattern:{pattern[:20]}"
    
    # 5. По умолчанию — низкий приоритет (LLM сам решит)
    return SearchPriority.LOW, "default"


def should_trigger_web_search(text: str) -> tuple[bool, str]:
    """
    Определяет, нужен ли веб-поиск.
    
    Совместимость со старым API.
    
    Returns:
        (нужен_поиск, причина)
    """
    priority, reason = get_search_priority(text)
    
    # Триггерим поиск для HIGH и CRITICAL
    should_search = priority in (SearchPriority.HIGH, SearchPriority.CRITICAL)
    
    if should_search:
        logger.info(f"[SEARCH TRIGGER] {priority.value}: {reason} | {text[:50]}...")
    
    return should_search, reason


def should_trigger_web_search_simple(text: str) -> bool:
    """Упрощённая версия для обратной совместимости."""
    result, _ = should_trigger_web_search(text)
    return result


def get_self_assessment_prompt() -> str:
    """
    Возвращает промпт для self-assessment.
    
    LLM добавляет в конец ответа оценку уверенности.
    """
    return """
После ответа добавь оценку (НЕ показывай пользователю, это для системы):
<!--CONFIDENCE:high/medium/low-->
<!--NEEDS_SEARCH:yes/no-->

high = уверен на 100%, это базовые знания или есть в контексте
medium = скорее всего правильно, но могу ошибаться
low = не уверен, нужна проверка

NEEDS_SEARCH=yes если:
- Вопрос о ценах, релизах, новостях
- Не уверен в актуальности информации
- Вопрос о новом железе (2024-2025)
"""


def parse_self_assessment(response: str) -> tuple[str, Optional[str], Optional[bool]]:
    """
    Парсит self-assessment из ответа LLM.
    
    Returns:
        (чистый_ответ, confidence, needs_search)
    """
    confidence = None
    needs_search = None
    
    # Извлекаем confidence
    conf_match = re.search(r'<!--CONFIDENCE:(high|medium|low)-->', response)
    if conf_match:
        confidence = conf_match.group(1)
    
    # Извлекаем needs_search
    search_match = re.search(r'<!--NEEDS_SEARCH:(yes|no)-->', response)
    if search_match:
        needs_search = search_match.group(1) == "yes"
    
    # Убираем метаданные из ответа
    clean_response = re.sub(r'<!--(CONFIDENCE|NEEDS_SEARCH):[^>]+-->', '', response)
    clean_response = clean_response.strip()
    
    return clean_response, confidence, needs_search


def is_question_about_current_info(text: str) -> bool:
    """
    Проверяет, требует ли вопрос актуальной информации.
    
    Используется для решения — искать сразу или дать LLM попробовать.
    """
    priority, _ = get_search_priority(text)
    return priority in (SearchPriority.CRITICAL, SearchPriority.HIGH)
