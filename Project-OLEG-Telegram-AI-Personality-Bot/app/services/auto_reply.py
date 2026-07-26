"""
Система автоматических ответов бота.

Реализует логику "вклинивания" бота в разговор с настраиваемой вероятностью.
Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging
import random
import re
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class ChatSettings:
    """Настройки чата для авто-ответов."""
    auto_reply_chance: float = 0.0  # 0.0 = disabled, >0 = enabled with base chance


class AutoReplySystem:
    """
    Система авто-ответов бота.
    
    Определяет, должен ли бот автоматически ответить на сообщение
    на основе вероятности, которая зависит от:
    - Базового шанса (1-5%)
    - Наличия CAPS LOCK (+5%)
    - Наличия триггерных слов (+2% за каждый)
    
    Requirements:
    - 5.1: 1-5% random chance to auto-reply
    - 5.2: Increase probability for CAPS LOCK and trigger words
    - 5.3: Generate contextually relevant response
    - 5.4: Respect enabled/disabled setting from admin dashboard
    - 5.5: Skip auto-reply evaluation when disabled
    """
    
    # Probability bounds - снижены для менее навязчивого поведения (Requirements 2.1, 2.4)
    MIN_PROBABILITY: float = 0.02  # 2% minimum
    MAX_PROBABILITY: float = 0.15  # 15% maximum cap
    
    # Base probability range - снижены для менее частых ответов (Requirements 2.1)
    BASE_PROBABILITY_MIN: float = 0.02  # 2%
    BASE_PROBABILITY_MAX: float = 0.05  # 5%
    
    # Message length filter (Requirements 2.2)
    MIN_MESSAGE_LENGTH: int = 2
    
    # Blocked short phrases - не отвечаем на короткие фразы (Requirements 2.3)
    BLOCKED_SHORT_PHRASES: set = {
        "че", "чё", "ок", "да", "нет", "лол", "кек",
        "ага", "угу", "ну", "хз", "пон", "ясн", "норм",
        "го", "gg", "wp", "лан", "ладно", "окей"
    }
    
    # Boosts (Requirements 5.2)
    CAPS_BOOST: float = 0.10  # +10% for CAPS LOCK
    TRIGGER_BOOST: float = 0.05  # +5% per trigger word
    
    # Default trigger words (can be extended from memory/config)
    DEFAULT_TRIGGERS: List[str] = [
        "олег", "oleg", "бот", "bot",
        "железо", "комп", "проц", "видюха",
        "разгон", "fps", "лаги", "тормозит"
    ]
    
    def __init__(self, triggers: Optional[List[str]] = None):
        """
        Инициализирует систему авто-ответов.
        
        Args:
            triggers: Список триггерных слов (опционально)
        """
        self.triggers = triggers or self.DEFAULT_TRIGGERS.copy()
    
    def is_caps_lock(self, text: str) -> bool:
        """
        Проверяет, написан ли текст в CAPS LOCK.
        
        Считается CAPS LOCK если >70% букв заглавные.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если текст в CAPS LOCK
        """
        if not text:
            return False
        
        # Извлекаем только буквы
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 3:  # Слишком короткий текст
            return False
        
        upper_count = sum(1 for c in letters if c.isupper())
        return upper_count / len(letters) > 0.7
    
    def count_triggers(self, text: str) -> int:
        """
        Подсчитывает количество триггерных слов в тексте.
        
        Args:
            text: Текст для проверки
            
        Returns:
            Количество найденных триггеров
        """
        if not text:
            return 0
        
        text_lower = text.lower()
        count = 0
        for trigger in self.triggers:
            # Используем word boundary для точного совпадения
            pattern = rf'\b{re.escape(trigger)}\b'
            if re.search(pattern, text_lower):
                count += 1
        
        return count
    
    def calculate_probability(self, text: str, triggers: Optional[List[str]] = None) -> float:
        """
        Вычисляет вероятность авто-ответа.
        
        Формула:
        - Базовая вероятность: 1-5% (случайная в этом диапазоне)
        - +5% если CAPS LOCK
        - +2% за каждый триггер
        - Результат ограничен диапазоном [1%, 15%]
        
        Args:
            text: Текст сообщения
            triggers: Дополнительные триггеры (опционально)
            
        Returns:
            Вероятность от 0.01 до 0.15
        """
        # Базовая вероятность в диапазоне 1-5%
        base = random.uniform(self.BASE_PROBABILITY_MIN, self.BASE_PROBABILITY_MAX)
        
        probability = base
        
        # Boost за CAPS LOCK (Requirements 5.2)
        if self.is_caps_lock(text):
            probability += self.CAPS_BOOST
        
        # Boost за триггеры (Requirements 5.2)
        all_triggers = self.triggers.copy()
        if triggers:
            all_triggers.extend(triggers)
        
        trigger_count = self.count_triggers(text)
        probability += trigger_count * self.TRIGGER_BOOST
        
        # Ограничиваем диапазоном (Requirements 5.1)
        probability = max(self.MIN_PROBABILITY, min(self.MAX_PROBABILITY, probability))
        
        return probability
    
    def is_message_too_short(self, text: str) -> bool:
        """
        Проверяет, слишком ли короткое сообщение для авто-ответа.
        
        Requirements 2.2: Сообщения короче MIN_MESSAGE_LENGTH символов отклоняются.
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если сообщение слишком короткое
        """
        if not text:
            return True
        return len(text) < self.MIN_MESSAGE_LENGTH
    
    def is_blocked_phrase(self, text: str) -> bool:
        """
        Проверяет, является ли сообщение заблокированной короткой фразой.
        
        Requirements 2.3: Короткие фразы типа "че", "ок", "да" отклоняются.
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если сообщение в блоклисте
        """
        if not text:
            return False
        return text.lower().strip() in self.BLOCKED_SHORT_PHRASES
    
    def should_reply(self, text: str, chat_settings: ChatSettings) -> bool:
        """
        Определяет, нужно ли отвечать на сообщение.
        
        Args:
            text: Текст сообщения
            chat_settings: Настройки чата (auto_reply_chance может быть 0-100 или 0.0-1.0)
            
        Returns:
            True если бот должен ответить
        """
        # Requirements 2.1: При auto_reply_chance = 0 сразу возвращаем False
        if chat_settings.auto_reply_chance <= 0:
            return False
        
        # Requirements 2.2: Фильтр по длине сообщения
        if self.is_message_too_short(text):
            logger.debug(f"Auto-reply skipped: message too short ({len(text) if text else 0} < {self.MIN_MESSAGE_LENGTH})")
            return False
        
        # Requirements 2.3: Фильтр по блоклисту коротких фраз
        if self.is_blocked_phrase(text):
            logger.debug(f"Auto-reply skipped: blocked phrase '{text}'")
            return False
        
        # Вычисляем вероятность
        probability = self.calculate_probability(text)
        
        # Requirements 2.4: Правильно масштабируем вероятность
        # auto_reply_chance может быть:
        # - 0-100 (процент) - делим на 100
        # - 0.0-1.0 (уже нормализовано) - используем как есть
        chance = chat_settings.auto_reply_chance
        if chance > 1.0:
            # Значение в процентах (0-100), нормализуем
            chance = chance / 100.0
        
        effective_probability = probability * chance
        
        # Ограничиваем максимумом
        effective_probability = min(effective_probability, self.MAX_PROBABILITY)
        
        # Бросаем кости
        roll = random.random()
        should = roll < effective_probability
        
        if should:
            logger.debug(
                f"Auto-reply triggered: roll={roll:.4f} < prob={effective_probability:.4f}"
            )
        
        return should


# Глобальный экземпляр системы авто-ответов
auto_reply_system = AutoReplySystem()
