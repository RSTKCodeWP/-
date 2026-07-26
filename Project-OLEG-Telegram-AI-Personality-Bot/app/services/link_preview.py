"""
Link Preview Service - извлечение информации из ссылок.

Поддерживает:
- YouTube (название, описание, канал)
- Обычные веб-страницы (title, description, og:tags)
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

import httpx

from app.services.http_clients import get_web_client

logger = logging.getLogger(__name__)

# Таймаут для запросов
REQUEST_TIMEOUT = 10.0

# User-Agent для запросов
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class LinkPreview:
    """Результат парсинга ссылки."""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    site_name: Optional[str] = None
    author: Optional[str] = None
    duration: Optional[str] = None  # Для видео
    error: Optional[str] = None
    
    def to_context(self) -> str:
        """Форматирует превью для контекста LLM."""
        if self.error:
            return f"[Ссылка: {self.url}] Ошибка: {self.error}"
        
        parts = []
        if self.site_name:
            parts.append(f"Сайт: {self.site_name}")
        if self.title:
            parts.append(f"Название: {self.title}")
        if self.author:
            parts.append(f"Автор: {self.author}")
        if self.duration:
            parts.append(f"Длительность: {self.duration}")
        if self.description:
            # Обрезаем описание если слишком длинное
            desc = self.description[:500] + "..." if len(self.description) > 500 else self.description
            parts.append(f"Описание: {desc}")
        
        if not parts:
            return f"[Ссылка: {self.url}] Не удалось получить информацию"
        
        return f"[Ссылка: {self.url}]\n" + "\n".join(parts)


class LinkPreviewService:
    """Сервис для извлечения информации из ссылок."""
    
    # Паттерн для поиска URL в тексте
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )
    
    # YouTube паттерны
    YOUTUBE_PATTERNS = [
        re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'),
        re.compile(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})'),
    ]
    
    def extract_urls(self, text: str) -> List[str]:
        """
        Извлекает все URL из текста.
        
        Args:
            text: Текст для поиска
            
        Returns:
            Список найденных URL
        """
        if not text:
            return []
        
        urls = self.URL_PATTERN.findall(text)
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_urls = []
        for url in urls:
            # Очищаем URL от trailing punctuation
            url = url.rstrip('.,;:!?)')
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Извлекает YouTube video ID из URL."""
        for pattern in self.YOUTUBE_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        
        # Пробуем через parse_qs
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc:
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return qs['v'][0]
        
        return None
    
    async def _fetch_youtube_info(self, video_id: str) -> LinkPreview:
        """
        Получает информацию о YouTube видео через oEmbed API.
        
        Args:
            video_id: ID видео
            
        Returns:
            LinkPreview с информацией о видео
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        
        try:
            client = get_web_client()
            response = await client.get(
                oembed_url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 401:
                return LinkPreview(
                    url=url,
                    site_name="YouTube",
                    error="Видео приватное или удалено"
                )
            
            if response.status_code == 404:
                return LinkPreview(
                    url=url,
                    site_name="YouTube",
                    error="Видео не найдено"
                )
            
            if response.status_code != 200:
                return LinkPreview(
                    url=url,
                    site_name="YouTube",
                    error=f"HTTP {response.status_code}"
                )
            
            data = response.json()
            
            return LinkPreview(
                url=url,
                title=data.get("title"),
                author=data.get("author_name"),
                site_name="YouTube"
            )
                
        except httpx.TimeoutException:
            return LinkPreview(url=url, site_name="YouTube", error="Таймаут запроса")
        except Exception as e:
            logger.error(f"Error fetching YouTube info for {video_id}: {e}")
            return LinkPreview(url=url, site_name="YouTube", error=str(e))
    
    async def _fetch_webpage_info(self, url: str) -> LinkPreview:
        """
        Получает информацию о веб-странице через HTML meta tags.
        
        Args:
            url: URL страницы
            
        Returns:
            LinkPreview с информацией о странице
        """
        try:
            client = get_web_client()
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                return LinkPreview(url=url, error=f"HTTP {response.status_code}")
            
            html = response.text
            
            # Парсим meta tags
            title = self._extract_meta(html, "og:title") or self._extract_title(html)
            description = self._extract_meta(html, "og:description") or self._extract_meta(html, "description")
            site_name = self._extract_meta(html, "og:site_name")
            author = self._extract_meta(html, "author")
            
            # Определяем site_name из домена если не найден
            if not site_name:
                parsed = urlparse(url)
                site_name = parsed.netloc.replace("www.", "")
            
            return LinkPreview(
                url=url,
                title=title,
                description=description,
                site_name=site_name,
                author=author
            )
                
        except httpx.TimeoutException:
            return LinkPreview(url=url, error="Таймаут запроса")
        except Exception as e:
            logger.error(f"Error fetching webpage info for {url}: {e}")
            return LinkPreview(url=url, error=str(e))
    
    def _extract_meta(self, html: str, name: str) -> Optional[str]:
        """Извлекает значение meta тега."""
        # og:* tags
        pattern = rf'<meta[^>]+(?:property|name)=["\']?{re.escape(name)}["\']?[^>]+content=["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return self._decode_html_entities(match.group(1))
        
        # Альтернативный порядок атрибутов
        pattern = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']?{re.escape(name)}["\']?'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return self._decode_html_entities(match.group(1))
        
        return None
    
    def _extract_title(self, html: str) -> Optional[str]:
        """Извлекает title из HTML."""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if match:
            return self._decode_html_entities(match.group(1).strip())
        return None
    
    def _decode_html_entities(self, text: str) -> str:
        """Декодирует HTML entities."""
        import html
        return html.unescape(text)
    
    async def get_preview(self, url: str) -> LinkPreview:
        """
        Получает превью для URL.
        
        Args:
            url: URL для парсинга
            
        Returns:
            LinkPreview с информацией
        """
        # Проверяем YouTube
        youtube_id = self._extract_youtube_id(url)
        if youtube_id:
            return await self._fetch_youtube_info(youtube_id)
        
        # Обычная веб-страница
        return await self._fetch_webpage_info(url)
    
    async def get_previews(self, text: str, max_links: int = 3) -> List[LinkPreview]:
        """
        Извлекает и парсит все ссылки из текста.
        
        Args:
            text: Текст с ссылками
            max_links: Максимальное количество ссылок для обработки
            
        Returns:
            Список LinkPreview
        """
        urls = self.extract_urls(text)[:max_links]
        
        if not urls:
            return []
        
        previews = []
        for url in urls:
            preview = await self.get_preview(url)
            previews.append(preview)
        
        return previews
    
    def format_for_context(self, previews: List[LinkPreview]) -> str:
        """
        Форматирует превью для добавления в контекст LLM.
        
        Args:
            previews: Список превью
            
        Returns:
            Отформатированная строка
        """
        if not previews:
            return ""
        
        parts = ["ИНФОРМАЦИЯ О ССЫЛКАХ В СООБЩЕНИИ:"]
        for preview in previews:
            parts.append(preview.to_context())
        
        return "\n\n".join(parts)


# Глобальный экземпляр сервиса
link_preview_service = LinkPreviewService()
