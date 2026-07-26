"""
Модуль для поиска и фильтрации писем
"""

from typing import List, Dict
import re


class MessageSearch:
    """Класс для поиска по письмам"""
    
    @staticmethod
    def search_in_history(messages: List[Dict], query: str) -> List[Dict]:
        """
        Поиск по истории писем
        
        Args:
            messages: Список писем для поиска
            query: Поисковый запрос
        
        Returns:
            Отфильтрованный список писем
        """
        if not query:
            return messages
        
        query_lower = query.lower()
        results = []
        
        for msg in messages:
            # Поиск в теме
            if query_lower in msg.get('subject', '').lower():
                results.append(msg)
                continue
            
            # Поиск в отправителе
            if query_lower in msg.get('from_email', '').lower():
                results.append(msg)
                continue
            
            # Поиск в теле письма
            if query_lower in msg.get('body', '').lower():
                results.append(msg)
                continue
        
        return results
    
    @staticmethod
    def filter_by_sender(messages: List[Dict], sender: str) -> List[Dict]:
        """Фильтрация по отправителю"""
        return [msg for msg in messages if sender.lower() in msg.get('from_email', '').lower()]
    
    @staticmethod
    def filter_favorites(messages: List[Dict]) -> List[Dict]:
        """Фильтрация только избранных"""
        return [msg for msg in messages if msg.get('is_favorite', False)]
    
    @staticmethod
    def search_with_regex(messages: List[Dict], pattern: str) -> List[Dict]:
        """Поиск с использованием регулярных выражений"""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            results = []
            
            for msg in messages:
                text = f"{msg.get('subject', '')} {msg.get('body', '')}"
                if regex.search(text):
                    results.append(msg)
            
            return results
        except re.error:
            return []
