"""
Модуль для автоматического извлечения кодов подтверждения из писем
"""

import re
from typing import Optional, List


class CodeExtractor:
    """Класс для извлечения кодов подтверждения из текста"""
    
    # Паттерны для поиска кодов
    PATTERNS = [
        # 6-значные цифровые коды
        r'\b(\d{6})\b',
        # 4-8 значные цифровые коды с возможными разделителями
        r'\b(\d{4}[-\s]?\d{2,4})\b',
        # Буквенно-цифровые коды (8-12 символов)
        r'\b([A-Z0-9]{8,12})\b',
        # Коды с префиксами
        r'(?:code|код|confirmation|подтверждение|verification|верификация)[:\s]+([A-Z0-9]{4,12})',
        # Коды в кавычках или скобках
        r'["\']([A-Z0-9]{4,12})["\']',
        r'\(([A-Z0-9]{4,12})\)',
    ]
    
    # Ключевые слова для контекста
    KEYWORDS = [
        'verification', 'код', 'code', 'confirm', 'подтверждение',
        'authentication', 'аутентификация', 'otp', 'pin', 'пин'
    ]
    
    @classmethod
    def extract_codes(cls, text: str) -> List[str]:
        """
        Извлекает все возможные коды из текста
        
        Args:
            text: Текст для анализа
        
        Returns:
            Список найденных кодов
        """
        if not text:
            return []
        
        codes = []
        text_lower = text.lower()
        
        # Проверяем наличие ключевых слов
        has_keywords = any(keyword in text_lower for keyword in cls.KEYWORDS)
        
        for pattern in cls.PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                code = match.group(1).strip()
                
                # Фильтрация: пропускаем слишком длинные последовательности
                if len(code.replace('-', '').replace(' ', '')) > 12:
                    continue
                
                # Если есть ключевые слова, добавляем код
                if has_keywords:
                    codes.append(code)
                # Если ключевых слов нет, добавляем только 6-значные коды
                elif len(code) == 6 and code.isdigit():
                    codes.append(code)
        
        # Удаляем дубликаты, сохраняя порядок
        seen = set()
        unique_codes = []
        for code in codes:
            normalized = code.replace('-', '').replace(' ', '').upper()
            if normalized not in seen:
                seen.add(normalized)
                unique_codes.append(code)
        
        return unique_codes
    
    @classmethod
    def find_best_code(cls, text: str) -> Optional[str]:
        """
        Находит наиболее вероятный код подтверждения
        
        Args:
            text: Текст для анализа
        
        Returns:
            Наиболее вероятный код или None
        """
        codes = cls.extract_codes(text)
        
        if not codes:
            return None
        
        # Приоритет: 6-значные цифровые коды
        for code in codes:
            if len(code) == 6 and code.isdigit():
                return code
        
        # Затем 4-значные коды
        for code in codes:
            clean_code = code.replace('-', '').replace(' ', '')
            if len(clean_code) == 4 and clean_code.isdigit():
                return code
        
        # Иначе возвращаем первый найденный
        return codes[0]
    
    @classmethod
    def format_code_message(cls, code: str) -> str:
        """
        Форматирует сообщение с кодом для отображения
        
        Args:
            code: Код подтверждения
        
        Returns:
            Отформатированное сообщение
        """
        return f"🔐 <b>Код подтверждения:</b> <code>{code}</code>"
    
    @classmethod
    def highlight_code_in_text(cls, text: str, code: str) -> str:
        """
        Выделяет код в тексте
        
        Args:
            text: Исходный текст
            code: Код для выделения
        
        Returns:
            Текст с выделенным кодом
        """
        # Экранируем специальные символы для регулярного выражения
        escaped_code = re.escape(code)
        # Заменяем код на выделенную версию
        highlighted = re.sub(
            f'({escaped_code})',
            r'<b>\1</b>',
            text,
            flags=re.IGNORECASE
        )
        return highlighted
