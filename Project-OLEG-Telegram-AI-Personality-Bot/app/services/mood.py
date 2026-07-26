"""
Система настроения Олега.

Олег меняет настроение в зависимости от времени суток и рандома.
Это добавляет вариативности в ответы.
"""

import random
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import settings


class MoodService:
    """Сервис настроения Олега."""
    
    # Базовые настроения по времени суток
    TIME_MOODS = {
        "night": {  # 00:00 - 06:00
            "base": "сонный",
            "modifiers": ["философский", "меланхоличный", "задумчивый"],
            "energy": 0.3,
        },
        "morning": {  # 06:00 - 12:00
            "base": "бодрый",
            "modifiers": ["оптимистичный", "деловой", "собранный"],
            "energy": 0.7,
        },
        "day": {  # 12:00 - 18:00
            "base": "нормальный",
            "modifiers": ["расслабленный", "дружелюбный", "ироничный"],
            "energy": 1.0,
        },
        "evening": {  # 18:00 - 00:00
            "base": "расслабленный",
            "modifiers": ["уставший", "ленивый", "саркастичный"],
            "energy": 0.6,
        },
    }
    
    # Рандомные настроения (могут перекрыть базовое)
    RANDOM_MOODS = [
        {"mood": "раздражённый", "chance": 0.05, "trigger": "Олег сегодня не в духе — отвечает резче обычного."},
        {"mood": "весёлый", "chance": 0.08, "trigger": "Олег в хорошем настроении — больше шуток и подколов."},
        {"mood": "задумчивый", "chance": 0.05, "trigger": "Олег философствует — ответы глубже и длиннее."},
        {"mood": "лаконичный", "chance": 0.1, "trigger": "Олег краток — отвечает максимально коротко."},
        {"mood": "экспертный", "chance": 0.07, "trigger": "Олег в режиме эксперта — больше технических деталей."},
        {"mood": "дерзкий", "chance": 0.08, "trigger": "Олег дерзит — больше подколов и сарказма."},
    ]
    
    def __init__(self):
        self._current_mood: Optional[str] = None
        self._mood_trigger: Optional[str] = None
        self._last_mood_check: Optional[datetime] = None
        self._mood_duration_minutes = 30  # Настроение держится 30 минут
    
    def _get_timezone(self) -> ZoneInfo:
        """Получить таймзону из настроек."""
        try:
            return ZoneInfo(settings.timezone)
        except:
            return ZoneInfo("Europe/Moscow")
    
    def _get_time_period(self, hour: int) -> str:
        """Определить период суток по часу."""
        if 0 <= hour < 6:
            return "night"
        elif 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "day"
        else:
            return "evening"
    
    def get_current_mood(self) -> tuple[str, Optional[str]]:
        """
        Получить текущее настроение Олега.
        
        Returns:
            (mood, trigger) — настроение и триггер для промпта (или None)
        """
        now = datetime.now(self._get_timezone())
        
        # Проверяем нужно ли обновить настроение
        if self._last_mood_check:
            minutes_passed = (now - self._last_mood_check).total_seconds() / 60
            if minutes_passed < self._mood_duration_minutes and self._current_mood:
                return self._current_mood, self._mood_trigger
        
        # Определяем базовое настроение по времени
        period = self._get_time_period(now.hour)
        time_mood = self.TIME_MOODS[period]
        base_mood = time_mood["base"]
        
        # Проверяем рандомные настроения
        for random_mood in self.RANDOM_MOODS:
            if random.random() < random_mood["chance"]:
                self._current_mood = random_mood["mood"]
                self._mood_trigger = random_mood["trigger"]
                self._last_mood_check = now
                return self._current_mood, self._mood_trigger
        
        # Иногда добавляем модификатор к базовому настроению
        if random.random() < 0.3 and time_mood["modifiers"]:
            modifier = random.choice(time_mood["modifiers"])
            self._current_mood = f"{base_mood}, {modifier}"
        else:
            self._current_mood = base_mood
        
        self._mood_trigger = None
        self._last_mood_check = now
        
        return self._current_mood, self._mood_trigger
    
    def get_mood_context(self) -> str:
        """
        Получить контекст настроения для промпта.
        
        Returns:
            Строка для добавления в промпт (или пустая)
        """
        mood, trigger = self.get_current_mood()
        
        if trigger:
            return f"\n[НАСТРОЕНИЕ: {mood}. {trigger}]\n"
        
        # Для базовых настроений не добавляем контекст — пусть будет естественно
        return ""
    
    def get_energy_level(self) -> float:
        """
        Получить уровень энергии (влияет на длину ответов).
        
        Returns:
            0.0 - 1.0
        """
        now = datetime.now(self._get_timezone())
        period = self._get_time_period(now.hour)
        return self.TIME_MOODS[period]["energy"]


# Глобальный экземпляр
mood_service = MoodService()
