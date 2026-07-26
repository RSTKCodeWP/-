"""
Менеджер провайдеров временной почты с автоматическим переключением
"""

import logging
from typing import List, Dict, Optional
from providers import (
    EmailProvider,
    OneSecMailProvider,
    MailTmProvider,
    TempMailLolProvider
)

logger = logging.getLogger(__name__)


class ProviderManager:
    """Менеджер для работы с несколькими провайдерами временной почты"""
    
    # Приоритет провайдеров (более надежные первые)
    PROVIDER_PRIORITY = ["Mail.tm", "TempMail.lol", "1SecMail"]
    
    def __init__(self):
        self._providers: Dict[str, EmailProvider] = {}
        self._current_provider: Optional[EmailProvider] = None
        self._email_to_provider: Dict[str, str] = {}  # Связь email -> имя провайдера
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Инициализирует все доступные провайдеры"""
        self._providers = {
            "1SecMail": OneSecMailProvider(),
            "Mail.tm": MailTmProvider(),
            "TempMail.lol": TempMailLolProvider()
        }
        logger.info(f"Инициализировано провайдеров: {len(self._providers)}")
    
    async def __aenter__(self):
        """Открывает сессии для всех провайдеров"""
        for provider in self._providers.values():
            await provider.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрывает сессии для всех провайдеров"""
        for provider in self._providers.values():
            await provider.__aexit__(exc_type, exc_val, exc_tb)
    
    def _get_available_providers(self) -> List[EmailProvider]:
        """Возвращает список доступных провайдеров в порядке приоритета"""
        available = []
        for name in self.PROVIDER_PRIORITY:
            provider = self._providers.get(name)
            if provider and provider.is_available:
                available.append(provider)
        
        # Добавляем остальные доступные провайдеры
        for name, provider in self._providers.items():
            if provider.is_available and provider not in available:
                available.append(provider)
        
        return available
    
    def get_provider_by_name(self, name: str) -> Optional[EmailProvider]:
        """Получает провайдер по имени"""
        return self._providers.get(name)
    
    def get_provider_for_email(self, email: str, provider_name_from_db: str = None) -> Optional[EmailProvider]:
        """Получает провайдер, который создал указанный email
        
        Args:
            email: Email-адрес
            provider_name_from_db: Имя провайдера из базы данных (приоритетный)
        """
        # Приоритет 1: Имя провайдера из базы данных
        if provider_name_from_db:
            provider = self._providers.get(provider_name_from_db)
            if provider:
                logger.info(f"Провайдер определен из БД: {provider_name_from_db}")
                return provider
        
        # Приоритет 2: Сохраненная связь в памяти
        provider_name = self._email_to_provider.get(email)
        if provider_name:
            return self._providers.get(provider_name)
        
        # Приоритет 3: Пытаемся определить по домену
        if "@" in email:
            domain = email.split("@")[1]
            
            if domain in ["1secmail.com", "1secmail.org", "1secmail.net"]:
                return self._providers.get("1SecMail")
            elif "tempmail.lol" in domain:
                return self._providers.get("TempMail.lol")
            # Для Mail.tm - любой другой домен, не подходящий под другие критерии
            # (так как Mail.tm использует множество доменов)
            else:
                # По умолчанию пробуем Mail.tm
                logger.info(f"Неизвестный домен {domain}, пробуем Mail.tm")
                return self._providers.get("Mail.tm")
        
        return None
    
    async def generate_email(self, preferred_provider: Optional[str] = None) -> tuple[str, str, str, str]:
        """
        Генерирует новый email, пытаясь использовать разные провайдеры
        
        Args:
            preferred_provider: Предпочитаемый провайдер (опционально)
        
        Returns:
            Кортеж (email, provider_name, auth_token, auth_password)
        """
        providers_to_try = []
        
        # Если указан предпочитаемый провайдер, пробуем его первым
        if preferred_provider and preferred_provider in self._providers:
            provider = self._providers[preferred_provider]
            if provider.is_available:
                providers_to_try.append(provider)
        
        # Добавляем остальные провайдеры по приоритету
        for provider in self._get_available_providers():
            if provider not in providers_to_try:
                providers_to_try.append(provider)
        
        if not providers_to_try:
            raise Exception("Нет доступных провайдеров временной почты")
        
        # Пытаемся создать email, перебирая провайдеры
        last_error = None
        for provider in providers_to_try:
            try:
                logger.info(f"Пытаемся создать email через {provider.name}...")
                result = await provider.generate_email()
                
                # Распаковываем результат в зависимости от провайдера
                if provider.name == "1SecMail":
                    email = result
                    auth_token = None
                    auth_password = None
                else:
                    email, auth_token, auth_password = result
                
                # Сохраняем связь email -> провайдер
                self._email_to_provider[email] = provider.name
                self._current_provider = provider
                
                logger.info(f"✅ Email успешно создан через {provider.name}: {email}")
                return email, provider.name, auth_token, auth_password
                
            except Exception as e:
                logger.warning(f"❌ Провайдер {provider.name} не смог создать email: {e}")
                provider.mark_unavailable()
                last_error = e
                continue
        
        # Если все провайдеры не сработали
        raise Exception(f"Не удалось создать email ни через один провайдер. Последняя ошибка: {last_error}")
    
    async def get_messages(self, email: str, auth_token: str = None, auth_password: str = None, provider_name: str = None) -> List[Dict]:
        """
        Получает список сообщений для email
        
        Args:
            email: Email-адрес
            auth_token: Токен авторизации (если есть)
            auth_password: Пароль (если есть)
            provider_name: Имя провайдера из БД (если есть)
        
        Returns:
            Список сообщений
        """
        provider = self.get_provider_for_email(email, provider_name)
        
        if not provider:
            logger.error(f"Не найден провайдер для email: {email}")
            return []
        
        if not provider.is_available:
            logger.warning(f"Провайдер {provider.name} помечен как недоступный")
            # Пытаемся восстановить доступность
            provider.mark_available()
        
        # Устанавливаем токены авторизации, если они есть
        if auth_token and hasattr(provider, 'set_auth'):
            provider.set_auth(auth_token, auth_password)
            logger.info(f"Установлены токены авторизации для {provider.name}")
        
        try:
            messages = await provider.get_messages(email)
            return messages
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений через {provider.name}: {e}")
            return []
    
    async def read_message(self, email: str, message_id: str, auth_token: str = None, auth_password: str = None, provider_name: str = None) -> Optional[Dict]:
        """
        Читает конкретное сообщение
        
        Args:
            email: Email-адрес
            message_id: ID сообщения
            auth_token: Токен авторизации (если есть)
            auth_password: Пароль (если есть)
            provider_name: Имя провайдера из БД (если есть)
        
        Returns:
            Данные сообщения или None
        """
        provider = self.get_provider_for_email(email, provider_name)
        
        if not provider:
            logger.error(f"Не найден провайдер для email: {email}")
            return None
        
        # Устанавливаем токены авторизации, если они есть
        if auth_token and hasattr(provider, 'set_auth'):
            provider.set_auth(auth_token, auth_password)
        
        try:
            message = await provider.read_message(email, message_id)
            return message
        except Exception as e:
            logger.error(f"Ошибка при чтении сообщения через {provider.name}: {e}")
            return None
    
    async def get_domains(self, provider_name: Optional[str] = None) -> List[str]:
        """
        Получает список доступных доменов
        
        Args:
            provider_name: Имя конкретного провайдера (опционально)
        
        Returns:
            Список доменов
        """
        if provider_name:
            provider = self._providers.get(provider_name)
            if provider:
                return await provider.get_domains()
            return []
        
        # Собираем домены со всех провайдеров
        all_domains = []
        for provider in self._providers.values():
            try:
                domains = await provider.get_domains()
                all_domains.extend(domains)
            except Exception as e:
                logger.warning(f"Не удалось получить домены от {provider.name}: {e}")
        
        return list(set(all_domains))  # Убираем дубликаты
    
    def get_available_provider_names(self) -> List[str]:
        """Возвращает список имен доступных провайдеров"""
        return [p.name for p in self._get_available_providers()]
    
    def get_all_provider_names(self) -> List[str]:
        """Возвращает список имен всех провайдеров"""
        return list(self._providers.keys())
    
    def get_provider_status(self) -> Dict[str, bool]:
        """Возвращает статус всех провайдеров"""
        return {name: provider.is_available for name, provider in self._providers.items()}
    
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
