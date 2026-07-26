"""
Модуль для работы с API 1secmail.com
Позволяет генерировать временные email-адреса и получать письма
"""

import aiohttp
import random
import string
from typing import List, Dict, Optional


class TempMail:
    """Класс для работы с временной почтой через 1secmail API"""
    
    BASE_URL = "https://www.1secmail.com/api/v1/"
    DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def generate_username(self, length: int = 10) -> str:
        """Генерирует случайное имя пользователя для email"""
        characters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    def generate_email(self) -> str:
        """Генерирует полный временный email-адрес"""
        username = self.generate_username()
        domain = random.choice(self.DOMAINS)
        return f"{username}@{domain}"
    
    async def get_domains(self) -> List[str]:
        """Получает список доступных доменов"""
        try:
            params = {"action": "getDomainList"}
            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    return await response.json()
                return self.DOMAINS
        except Exception as e:
            print(f"Ошибка при получении доменов: {e}")
            return self.DOMAINS
    
    async def get_messages(self, email: str) -> List[Dict]:
        """
        Получает список сообщений для указанного email
        
        Args:
            email: Email-адрес в формате "username@domain"
        
        Returns:
            Список словарей с информацией о письмах
        """
        try:
            username, domain = email.split("@")
            params = {
                "action": "getMessages",
                "login": username,
                "domain": domain
            }
            
            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    messages = await response.json()
                    return messages if messages else []
                return []
        except Exception as e:
            print(f"Ошибка при получении сообщений: {e}")
            return []
    
    async def read_message(self, email: str, message_id: int) -> Optional[Dict]:
        """
        Получает полное содержимое письма
        
        Args:
            email: Email-адрес в формате "username@domain"
            message_id: ID письма
        
        Returns:
            Словарь с полной информацией о письме
        """
        try:
            username, domain = email.split("@")
            params = {
                "action": "readMessage",
                "login": username,
                "domain": domain,
                "id": message_id
            }
            
            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            print(f"Ошибка при чтении письма: {e}")
            return None
    
    @staticmethod
    def format_message_preview(message: Dict) -> str:
        """Форматирует краткую информацию о письме"""
        subject = message.get("subject", "Без темы")
        from_email = message.get("from", "Неизвестный отправитель")
        date = message.get("date", "")
        
        return f"📩 <b>{subject}</b>\n👤 От: {from_email}\n📅 {date}"
    
    @staticmethod
    def format_message_full(message: Dict) -> str:
        """Форматирует полное содержимое письма"""
        subject = message.get("subject", "Без темы")
        from_email = message.get("from", "Неизвестный отправитель")
        date = message.get("date", "")
        body = message.get("textBody", message.get("htmlBody", "Пустое письмо"))
        
        # Ограничиваем длину тела письма для Telegram
        max_length = 3000
        if len(body) > max_length:
            body = body[:max_length] + "\n\n... (письмо обрезано)"
        
        text = f"📧 <b>Тема:</b> {subject}\n"
        text += f"👤 <b>От:</b> {from_email}\n"
        text += f"📅 <b>Дата:</b> {date}\n"
        text += f"\n{'='*30}\n\n"
        text += body
        
        return text
