"""
Think Tag Filter - фильтр для удаления thinking-тегов и артефактов из LLM ответов.

Удаляет:
- Теги <think>...</think> из ответов моделей типа DeepSeek
- Сырые tool calls (web_search<｜tool▁sep｜>...)
- Исправляет форматирование списков (добавляет переносы строк)
"""

import re
from typing import Optional


class ThinkTagFilter:
    """Фильтр для удаления thinking-тегов и артефактов из LLM ответов."""
    
    # Regex pattern для удаления <think>...</think> тегов
    # Флаги: DOTALL - точка матчит переносы строк, IGNORECASE - регистронезависимо
    THINK_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
    
    # Паттерн для незакрытых тегов (malformed) - <think> без </think>
    UNCLOSED_THINK_PATTERN = re.compile(r'<think>.*$', re.DOTALL | re.IGNORECASE)
    
    # Паттерн для незакрытых тегов в начале - </think> без <think>
    UNOPENED_THINK_PATTERN = re.compile(r'^.*?</think>', re.DOTALL | re.IGNORECASE)
    
    # Паттерны для очистки сырых tool calls от LLM
    # Формат: tool_name<｜tool▁sep｜>{"args"}<｜tool▁call▁end｜><｜tool▁calls▁end｜>
    # Также захватываем возможный мусор перед tool call (обрезанные слова)
    TOOL_CALL_PATTERN = re.compile(
        r'[а-яёa-z]*\s*\w+<[｜\|]tool[▁_]sep[｜\|]>\s*\{[^}]*\}\s*(?:<[｜\|]tool[▁_]call[▁_]end[｜\|]>)?\s*(?:<[｜\|]tool[▁_]calls[▁_]end[｜\|]>)?',
        re.IGNORECASE
    )
    
    # Альтернативный формат tool calls с обычными символами
    TOOL_CALL_ALT_PATTERN = re.compile(
        r'[а-яёa-z]*\s*\w+<\|tool_sep\|>\s*\{[^}]*\}\s*(?:<\|tool_call_end\|>)?\s*(?:<\|tool_calls_end\|>)?',
        re.IGNORECASE
    )
    
    # Паттерн для нумерованных списков без переносов (1. text2. text → 1. text\n2. text)
    # Ищем цифру с точкой, за которой НЕ следует перенос строки
    NUMBERED_LIST_PATTERN = re.compile(r'(\d+\.)\s*([^\n\d])')
    
    # Паттерны для markdown форматирования
    # **bold** или __bold__ → просто текст
    MARKDOWN_BOLD_PATTERN = re.compile(r'\*\*([^*]+)\*\*|__([^_]+)__')
    # *italic* или _italic_ → просто текст  
    MARKDOWN_ITALIC_PATTERN = re.compile(r'(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)')
    # `code` → просто текст
    MARKDOWN_CODE_PATTERN = re.compile(r'`([^`]+)`')
    # ```code block``` → просто текст
    MARKDOWN_CODEBLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    # [text](url) → text
    MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\([^)]+\)')
    # # Header → Header
    MARKDOWN_HEADER_PATTERN = re.compile(r'^#{1,6}\s+', re.MULTILINE)
    
    DEFAULT_FALLBACK = "Хм, мысль потерял. Повтори вопрос?"
    
    def __init__(self, fallback_message: Optional[str] = None):
        """
        Инициализация фильтра.
        
        Args:
            fallback_message: Сообщение для возврата если результат пустой
        """
        self.fallback_message = fallback_message or self.DEFAULT_FALLBACK
    
    def filter(self, text: str) -> str:
        """
        Удаляет все think-теги и артефакты из текста.
        
        Args:
            text: Исходный текст с возможными think-тегами и артефактами
            
        Returns:
            Очищенный текст или fallback если результат пустой
        """
        if not text:
            return self.fallback_message
        
        # Шаг 1: Удаляем все закрытые <think>...</think> теги
        result = self.THINK_PATTERN.sub('', text)
        
        # Шаг 2: Удаляем незакрытые теги (malformed) - <think> без </think>
        result = self.UNCLOSED_THINK_PATTERN.sub('', result)
        
        # Шаг 3: Удаляем незакрытые теги в начале - </think> без <think>
        result = self.UNOPENED_THINK_PATTERN.sub('', result)
        
        # Шаг 4: Удаляем сырые tool calls (web_search<｜tool▁sep｜>...)
        result = self.TOOL_CALL_PATTERN.sub('', result)
        result = self.TOOL_CALL_ALT_PATTERN.sub('', result)
        
        # Шаг 5: Исправляем форматирование списков
        result = self._fix_list_formatting(result)
        
        # Шаг 6: Убираем markdown форматирование (Telegram не поддерживает его без parse_mode)
        result = self._strip_markdown(result)
        
        # Очищаем лишние пробелы и переносы строк
        result = result.strip()
        
        # Убираем множественные пробелы/переносы, оставшиеся после удаления тегов
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' {2,}', ' ', result)
        
        # Если результат пустой - возвращаем fallback
        if not result:
            return self.fallback_message
        
        return result
    
    def _fix_list_formatting(self, text: str) -> str:
        """
        Исправляет форматирование списков, добавляя переносы строк.
        
        Примеры:
        - "1. item2. item" → "1. item\n2. item"
        - "🏆 Топ-10:1. name: 24" → "🏆 Топ-10:\n1. name: 24"
        
        Args:
            text: Текст для обработки
            
        Returns:
            Текст с исправленным форматированием списков
        """
        if not text:
            return text
        
        # Добавляем перенос перед номерами списка если его нет
        # Паттерн: не-перенос + цифра + точка → добавляем перенос перед цифрой
        result = re.sub(r'([^\n\d])(\d+\.)\s+', r'\1\n\2 ', text)
        
        # Добавляем перенос после заголовков типа "Топ-10:" если за ними сразу идёт цифра
        result = re.sub(r'(Топ-\d+:)(\d)', r'\1\n\2', result, flags=re.IGNORECASE)
        
        # Добавляем перенос после эмодзи-заголовков если за ними сразу идёт цифра
        result = re.sub(r'([\U0001F3C6\U0001F947-\U0001F949]\s*[^:\n]+:)(\d)', r'\1\n\2', result)
        
        # Добавляем перенос перед разделителями (━━━) в конце списков
        result = re.sub(r'(\))(\s*━+)', r'\1\n\2', result)
        
        return result
    
    def _strip_markdown(self, text: str) -> str:
        """
        Убирает markdown форматирование из текста.
        
        Telegram не поддерживает markdown без parse_mode, поэтому
        **bold** и *italic* отображаются как есть — некрасиво.
        
        Примеры:
        - "**Настройки** → Приложения" → "Настройки → Приложения"
        - "`code`" → "code"
        - "[link](url)" → "link"
        
        Args:
            text: Текст с возможным markdown
            
        Returns:
            Текст без markdown форматирования
        """
        if not text:
            return text
        
        result = text
        
        # Убираем code blocks (```...```) — сначала, т.к. они могут содержать другие паттерны
        result = self.MARKDOWN_CODEBLOCK_PATTERN.sub(lambda m: m.group(0).strip('`').strip(), result)
        
        # Убираем inline code (`code`)
        result = self.MARKDOWN_CODE_PATTERN.sub(r'\1', result)
        
        # Убираем bold (**text** или __text__)
        result = self.MARKDOWN_BOLD_PATTERN.sub(lambda m: m.group(1) or m.group(2), result)
        
        # Убираем italic (*text* или _text_) — осторожно, чтобы не сломать смайлики
        result = self.MARKDOWN_ITALIC_PATTERN.sub(lambda m: m.group(1) or m.group(2) or '', result)
        
        # Убираем ссылки [text](url) → text
        result = self.MARKDOWN_LINK_PATTERN.sub(r'\1', result)
        
        # Убираем заголовки (# Header)
        result = self.MARKDOWN_HEADER_PATTERN.sub('', result)
        
        return result
    
    def is_empty_after_filter(self, text: str) -> bool:
        """
        Проверяет, останется ли текст после фильтрации.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если после фильтрации текст будет пустым
        """
        if not text:
            return True
        
        # Применяем те же паттерны что и в filter()
        result = self.THINK_PATTERN.sub('', text)
        result = self.UNCLOSED_THINK_PATTERN.sub('', result)
        result = self.UNOPENED_THINK_PATTERN.sub('', result)
        
        return not result.strip()
    
    def contains_think_tags(self, text: str) -> bool:
        """
        Проверяет, содержит ли текст think-теги.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если текст содержит think-теги
        """
        if not text:
            return False
        
        text_lower = text.lower()
        return '<think>' in text_lower or '</think>' in text_lower


# Глобальный экземпляр фильтра для удобства использования
think_filter = ThinkTagFilter()
