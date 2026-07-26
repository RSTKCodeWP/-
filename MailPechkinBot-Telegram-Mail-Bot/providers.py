"""
Модуль с провайдерами временной почты
Поддерживает несколько сервисов с автоматическим переключением
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import aiohttp
import random
import string
import logging

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Абстрактный базовый класс для провайдеров временной почты"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.name: str = "Unknown"
        self._is_available: bool = True
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def generate_email(self) -> str:
        """Генерирует новый временный email-адрес"""
        pass
    
    @abstractmethod
    async def get_messages(self, email: str) -> List[Dict]:
        """Получает список сообщений для email"""
        pass
    
    @abstractmethod
    async def read_message(self, email: str, message_id: str) -> Optional[Dict]:
        """Читает конкретное сообщение"""
        pass
    
    @abstractmethod
    async def get_domains(self) -> List[str]:
        """Получает список доступных доменов"""
        pass
    
    def generate_username(self, length: int = 10) -> str:
        """Генерирует случайное имя пользователя"""
        characters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    @property
    def is_available(self) -> bool:
        """Проверяет доступность провайдера"""
        return self._is_available
    
    def mark_unavailable(self):
        """Помечает провайдер как недоступный"""
        self._is_available = False
        logger.warning(f"Провайдер {self.name} помечен как недоступный")
    
    def mark_available(self):
        """Помечает провайдер как доступный"""
        self._is_available = True
        logger.info(f"Провайдер {self.name} снова доступен")


class OneSecMailProvider(EmailProvider):
    """Провайдер для 1secmail.com"""
    
    BASE_URL = "https://www.1secmail.com/api/v1/"
    DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
    
    def __init__(self):
        super().__init__()
        self.name = "1SecMail"
    
    async def generate_email(self) -> str:
        """Генерирует email на 1secmail"""
        try:
            domains = await self.get_domains()
            username = self.generate_username()
            domain = random.choice(domains)
            email = f"{username}@{domain}"
            logger.info(f"[{self.name}] Создан email: {email}")
            return email
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка генерации email: {e}")
            raise
    
    async def get_messages(self, email: str) -> List[Dict]:
        """Получает список сообщений"""
        try:
            username, domain = email.split("@")
            params = {
                "action": "getMessages",
                "login": username,
                "domain": domain
            }
            
            async with self.session.get(self.BASE_URL, params=params, timeout=10) as response:
                if response.status == 200:
                    messages = await response.json()
                    logger.info(f"[{self.name}] Получено {len(messages)} сообщений")
                    return messages if messages else []
                else:
                    logger.error(f"[{self.name}] Ошибка получения сообщений: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при получении сообщений: {e}")
            return []
    
    async def read_message(self, email: str, message_id: str) -> Optional[Dict]:
        """Читает конкретное сообщение"""
        try:
            username, domain = email.split("@")
            params = {
                "action": "readMessage",
                "login": username,
                "domain": domain,
                "id": message_id
            }
            
            async with self.session.get(self.BASE_URL, params=params, timeout=10) as response:
                if response.status == 200:
                    message = await response.json()
                    logger.info(f"[{self.name}] Прочитано сообщение {message_id}")
                    return message
                return None
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при чтении письма: {e}")
            return None
    
    async def get_domains(self) -> List[str]:
        """Получает список доменов"""
        try:
            params = {"action": "getDomainList"}
            async with self.session.get(self.BASE_URL, params=params, timeout=5) as response:
                if response.status == 200:
                    domains = await response.json()
                    return domains if domains else self.DOMAINS
                return self.DOMAINS
        except Exception as e:
            logger.warning(f"[{self.name}] Не удалось получить домены: {e}")
            return self.DOMAINS


class MailTmProvider(EmailProvider):
    """Провайдер для mail.tm (более надежный)"""
    
    BASE_URL = "https://api.mail.tm"
    
    def __init__(self):
        super().__init__()
        self.name = "Mail.tm"
        self._token: Optional[str] = None
        self._account_id: Optional[str] = None
        self._current_email: Optional[str] = None
        self._current_password: Optional[str] = None
    
    async def generate_email(self) -> tuple[str, str, str]:
        """Создает новый аккаунт на mail.tm
        
        Returns:
            Кортеж (email, token, password)
        """
        try:
            # Получаем доступные домены
            domains = await self.get_domains()
            if not domains:
                raise Exception("Не удалось получить домены")
            
            # Генерируем email и пароль
            username = self.generate_username()
            domain = random.choice(domains)
            email = f"{username}@{domain}"
            password = self.generate_username(16)  # Более длинный пароль
            
            # Создаем аккаунт
            account_data = {
                "address": email,
                "password": password
            }
            
            async with self.session.post(
                f"{self.BASE_URL}/accounts",
                json=account_data,
                timeout=10
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    self._account_id = result.get("id")
                    self._current_email = email
                    self._current_password = password
                    
                    # Получаем токен авторизации
                    await self._get_token(email, password)
                    
                    logger.info(f"[{self.name}] Создан email: {email}")
                    return email, self._token, password
                else:
                    error_text = await response.text()
                    raise Exception(f"Ошибка создания аккаунта: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка генерации email: {e}")
            raise
    
    async def _get_token(self, email: str, password: str) -> str:
        """Получает JWT токен для авторизации"""
        try:
            auth_data = {
                "address": email,
                "password": password
            }
            
            async with self.session.post(
                f"{self.BASE_URL}/token",
                json=auth_data,
                timeout=10
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self._token = result.get("token")
                    logger.info(f"[{self.name}] Получен токен авторизации")
                    return self._token
                else:
                    raise Exception(f"Ошибка получения токена: {response.status}")
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка получения токена: {e}")
            raise
    
    def set_auth(self, token: str, password: str):
        """Устанавливает данные авторизации из базы данных"""
        self._token = token
        self._current_password = password
        logger.info(f"[{self.name}] Восстановлена авторизация из БД")
    
    async def get_messages(self, email: str) -> List[Dict]:
        """Получает список сообщений"""
        try:
            # Если нет токена, пытаемся получить его через пароль
            if not self._token and self._current_password:
                try:
                    await self._get_token(email, self._current_password)
                except Exception as e:
                    logger.error(f"[{self.name}] Не удалось получить токен: {e}")
                    return []
            
            # Если это новый email или нет токена
            if not self._token:
                logger.warning(f"[{self.name}] Нет активной сессии для {email}")
                return []
            
            headers = {"Authorization": f"Bearer {self._token}"}
            
            async with self.session.get(
                f"{self.BASE_URL}/messages",
                headers=headers,
                timeout=10
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    messages = result.get("hydra:member", [])
                    
                    # Преобразуем формат для совместимости
                    formatted_messages = []
                    for msg in messages:
                        formatted_messages.append({
                            "id": msg.get("id"),
                            "from": msg.get("from", {}).get("address", "Unknown"),
                            "subject": msg.get("subject", "No subject"),
                            "date": msg.get("createdAt", "")
                        })
                    
                    logger.info(f"[{self.name}] Получено {len(formatted_messages)} сообщений")
                    return formatted_messages
                else:
                    logger.error(f"[{self.name}] Ошибка получения сообщений: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при получении сообщений: {e}")
            return []
    
    async def read_message(self, email: str, message_id: str) -> Optional[Dict]:
        """Читает конкретное сообщение"""
        try:
            if not self._token:
                logger.warning(f"[{self.name}] Нет токена авторизации")
                return None
            
            headers = {"Authorization": f"Bearer {self._token}"}
            
            async with self.session.get(
                f"{self.BASE_URL}/messages/{message_id}",
                headers=headers,
                timeout=10
            ) as response:
                if response.status == 200:
                    msg = await response.json()
                    
                    # Преобразуем формат для совместимости
                    formatted_message = {
                        "id": msg.get("id"),
                        "from": msg.get("from", {}).get("address", "Unknown"),
                        "subject": msg.get("subject", "No subject"),
                        "date": msg.get("createdAt", ""),
                        "textBody": msg.get("text", ""),
                        "htmlBody": msg.get("html", "")
                    }
                    
                    logger.info(f"[{self.name}] Прочитано сообщение {message_id}")
                    return formatted_message
                else:
                    logger.error(f"[{self.name}] Ошибка чтения сообщения: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при чтении письма: {e}")
            return None
    
    async def get_domains(self) -> List[str]:
        """Получает список доступных доменов"""
        try:
            async with self.session.get(f"{self.BASE_URL}/domains", timeout=5) as response:
                if response.status == 200:
                    result = await response.json()
                    domains = [d.get("domain") for d in result.get("hydra:member", [])]
                    logger.info(f"[{self.name}] Получено доменов: {len(domains)}")
                    return domains if domains else ["mail.tm"]
                return ["mail.tm"]
        except Exception as e:
            logger.warning(f"[{self.name}] Не удалось получить домены: {e}")
            return ["mail.tm"]


class TempMailLolProvider(EmailProvider):
    """Провайдер для tempmail.lol"""
    
    BASE_URL = "https://api.tempmail.lol"
    
    def __init__(self):
        super().__init__()
        self.name = "TempMail.lol"
        self._current_token: Optional[str] = None
    
    async def generate_email(self) -> tuple[str, str, None]:
        """Генерирует email на tempmail.lol
        
        Returns:
            Кортеж (email, token, None)
        """
        try:
            # Генерируем случайный токен для управления почтой
            token = self.generate_username(32)
            
            async with self.session.post(
                f"{self.BASE_URL}/generate/rush",
                json={"token": token},
                timeout=10
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    email = result.get("address")
                    self._current_token = result.get("token", token)
                    logger.info(f"[{self.name}] Создан email: {email}")
                    return email, self._current_token, None
                else:
                    raise Exception(f"Ошибка создания email: {response.status}")
                    
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка генерации email: {e}")
            raise
    
    def set_auth(self, token: str, password: str = None):
        """Устанавливает токен авторизации из базы данных"""
        self._current_token = token
        logger.info(f"[{self.name}] Восстановлен токен из БД")
    
    async def get_messages(self, email: str) -> List[Dict]:
        """Получает список сообщений"""
        try:
            if not self._current_token:
                logger.warning(f"[{self.name}] Нет токена для {email}")
                return []
            
            async with self.session.get(
                f"{self.BASE_URL}/auth/{self._current_token}",
                timeout=10
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    messages = result.get("email", [])
                    
                    # Преобразуем формат
                    formatted_messages = []
                    for msg in messages:
                        formatted_messages.append({
                            "id": msg.get("id"),
                            "from": msg.get("from", "Unknown"),
                            "subject": msg.get("subject", "No subject"),
                            "date": msg.get("date", "")
                        })
                    
                    logger.info(f"[{self.name}] Получено {len(formatted_messages)} сообщений")
                    return formatted_messages
                else:
                    logger.error(f"[{self.name}] Ошибка получения сообщений: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при получении сообщений: {e}")
            return []
    
    async def read_message(self, email: str, message_id: str) -> Optional[Dict]:
        """Читает конкретное сообщение"""
        try:
            messages = await self.get_messages(email)
            for msg in messages:
                if str(msg.get("id")) == str(message_id):
                    # Получаем полное содержимое
                    if not self._current_token:
                        return None
                    
                    async with self.session.get(
                        f"{self.BASE_URL}/read/{self._current_token}/{message_id}",
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            full_msg = await response.json()
                            formatted_message = {
                                "id": full_msg.get("id"),
                                "from": full_msg.get("from", "Unknown"),
                                "subject": full_msg.get("subject", "No subject"),
                                "date": full_msg.get("date", ""),
                                "textBody": full_msg.get("body", ""),
                                "htmlBody": full_msg.get("html", "")
                            }
                            logger.info(f"[{self.name}] Прочитано сообщение {message_id}")
                            return formatted_message
            return None
                    
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при чтении письма: {e}")
            return None
    
    async def get_domains(self) -> List[str]:
        """Получает список доменов"""
        try:
            async with self.session.get(f"{self.BASE_URL}/domains", timeout=5) as response:
                if response.status == 200:
                    domains = await response.json()
                    return domains if domains else ["tempmail.lol"]
                return ["tempmail.lol"]
        except Exception as e:
            logger.warning(f"[{self.name}] Не удалось получить домены: {e}")
            return ["tempmail.lol"]
