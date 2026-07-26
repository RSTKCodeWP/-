"""
Антиспам защита — лимит запросов к боту.

Двойной лимит:
- Burst: 5 запросов в минуту (защита от спама)
- Hourly: 50 запросов в час (общий лимит)
"""

import logging
import time
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class UserUsage:
    """Использование запросов."""
    # Минутный лимит (burst)
    minute_requests: int = 0
    minute_start: float = 0
    # Часовой лимит
    hour_requests: int = 0
    hour_start: float = 0
    # Флаги
    warned: bool = False


class AntiSpamLimiter:
    """
    Антиспам с двойным лимитом:
    - burst_limit: запросов в минуту (защита от спама)
    - hourly_limit: запросов в час (общий лимит)
    """
    
    def __init__(
        self,
        burst_limit: int = 5,  # 5 запросов/минуту
        hourly_limit: int = 50,  # 50 запросов/час
    ):
        self.burst_limit = burst_limit
        self.hourly_limit = hourly_limit
        
        self.users: dict[int, UserUsage] = defaultdict(UserUsage)
        self.whitelist: set[int] = set()
        self.total_blocked = 0
    
    def _reset_if_needed(self, usage: UserUsage):
        """Сбросить счётчики если прошло время."""
        now = time.time()
        
        # Минутный сброс
        if now - usage.minute_start >= 60:
            usage.minute_requests = 0
            usage.minute_start = now
        
        # Часовой сброс
        if now - usage.hour_start >= 3600:
            usage.hour_requests = 0
            usage.hour_start = now
            usage.warned = False
    
    def add_to_whitelist(self, user_id: int):
        """Добавить в whitelist."""
        self.whitelist.add(user_id)
        logger.info(f"User {user_id} added to antispam whitelist")
    
    def check_limit(self, user_id: int) -> tuple[bool, str]:
        """
        Проверить лимиты.
        
        Returns:
            (allowed, message)
        """
        if user_id in self.whitelist:
            return True, ""
        
        usage = self.users[user_id]
        self._reset_if_needed(usage)
        
        # Проверяем burst (минутный)
        if usage.minute_requests >= self.burst_limit:
            self.total_blocked += 1
            wait = int(60 - (time.time() - usage.minute_start))
            logger.warning(f"User {user_id} burst limit: {usage.minute_requests}/{self.burst_limit}")
            return False, f"⏱ Слишком быстро! Подожди {wait} сек."
        
        # Проверяем часовой
        if usage.hour_requests >= self.hourly_limit:
            self.total_blocked += 1
            wait = int((3600 - (time.time() - usage.hour_start)) / 60)
            logger.warning(f"User {user_id} hourly limit: {usage.hour_requests}/{self.hourly_limit}")
            return False, f"⏱ Лимит запросов. Подожди ~{wait} мин."
        
        return True, ""
    
    def get_warning(self, user_id: int) -> Optional[str]:
        """Предупреждение при 80% часового лимита."""
        if user_id in self.whitelist:
            return None
        
        usage = self.users[user_id]
        if usage.warned:
            return None
        
        if usage.hour_requests >= self.hourly_limit * 0.8:
            usage.warned = True
            left = self.hourly_limit - usage.hour_requests
            return f"⚠️ Осталось {left} запросов в этом часе."
        
        return None
    
    def record_request(self, user_id: int):
        """Записать запрос."""
        usage = self.users[user_id]
        self._reset_if_needed(usage)
        
        now = time.time()
        if usage.minute_start == 0:
            usage.minute_start = now
        if usage.hour_start == 0:
            usage.hour_start = now
        
        usage.minute_requests += 1
        usage.hour_requests += 1
        
        logger.debug(
            f"Request: user={user_id}, "
            f"minute={usage.minute_requests}/{self.burst_limit}, "
            f"hour={usage.hour_requests}/{self.hourly_limit}"
        )
    
    def get_user_stats(self, user_id: int) -> dict:
        """Статистика пользователя."""
        usage = self.users[user_id]
        self._reset_if_needed(usage)
        
        minute_reset = max(0, int(60 - (time.time() - usage.minute_start))) if usage.minute_start else 60
        hour_reset = max(0, int((3600 - (time.time() - usage.hour_start)) / 60)) if usage.hour_start else 60
        
        return {
            "minute_requests": usage.minute_requests,
            "burst_limit": self.burst_limit,
            "hour_requests": usage.hour_requests,
            "hourly_limit": self.hourly_limit,
            "minute_reset_secs": minute_reset,
            "hour_reset_mins": hour_reset,
            "is_whitelisted": user_id in self.whitelist,
        }
    
    def set_burst_limit(self, limit: int):
        """Установить burst лимит."""
        self.burst_limit = max(1, limit)
        logger.info(f"Burst limit set to {self.burst_limit}")
    
    def set_hourly_limit(self, limit: int):
        """Установить часовой лимит."""
        self.hourly_limit = max(1, limit)
        logger.info(f"Hourly limit set to {self.hourly_limit}")
    
    def get_stats(self) -> dict:
        """Глобальная статистика антиспама."""
        return {
            "burst_limit": self.burst_limit,
            "hourly_limit": self.hourly_limit,
            "total_users": len(self.users),
            "whitelisted": len(self.whitelist),
            "total_blocked": self.total_blocked,
        }
    
    def reset_user(self, user_id: int):
        """Сбросить счётчики пользователя."""
        if user_id in self.users:
            del self.users[user_id]
            logger.info(f"Reset limits for user {user_id}")


# Глобальный инстанс
token_limiter = AntiSpamLimiter()


def estimate_tokens(text: str) -> int:
    """Заглушка для совместимости."""
    return 0
