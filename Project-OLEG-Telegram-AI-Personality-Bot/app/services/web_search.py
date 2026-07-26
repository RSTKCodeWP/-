"""
Web Search Service — умный веб-поиск с несколькими провайдерами.

Приоритет провайдеров:
1. SearXNG (self-hosted, бесплатно, без лимитов)
2. Brave Search API (2000 запросов/месяц бесплатно)
3. DuckDuckGo HTML (fallback, без API)

**Feature: anti-hallucination-v2**
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.services.http_clients import get_web_client

logger = logging.getLogger(__name__)


# Паттерны для определения запросов о ценах на железо
HARDWARE_PRICE_PATTERNS = [
    r"(rtx\s*\d{4}|gtx\s*\d{4}|rx\s*\d{4}|arc\s*[ab]\d{3})",  # GPU
    r"(ryzen\s*\d|i[3579]-\d{4,5}|core\s*ultra)",  # CPU
    r"(ddr[45]\s*\d{4}|ram\s*\d{2}gb)",  # RAM
    r"(ssd\s*\d+[gt]b|nvme\s*\d+)",  # Storage
]

# Ключевые слова для определения запроса о цене
PRICE_KEYWORDS = [
    "цена", "стоит", "стоимость", "купить", "price", "cost",
    "сколько", "почём", "за сколько", "где купить",
]


def is_hardware_price_query(query: str) -> bool:
    """Проверяет, является ли запрос вопросом о цене на железо."""
    query_lower = query.lower()
    
    # Проверяем наличие ключевых слов о цене
    has_price_keyword = any(kw in query_lower for kw in PRICE_KEYWORDS)
    
    # Проверяем наличие названия железа
    has_hardware = any(
        re.search(pattern, query_lower) 
        for pattern in HARDWARE_PRICE_PATTERNS
    )
    
    return has_price_keyword and has_hardware


@dataclass
class SearchResult:
    """Результат поиска."""
    title: str
    snippet: str
    url: str
    source: str  # searxng, brave, duckduckgo
    freshness: Optional[str] = None


@dataclass
class SearchResponse:
    """Ответ поискового сервиса."""
    results: list[SearchResult]
    query: str
    provider: str
    cached: bool = False
    error: Optional[str] = None


class WebSearchService:
    """
    Сервис веб-поиска с несколькими провайдерами.
    
    Приоритет:
    1. SearXNG (если настроен) — бесплатно, без лимитов
    2. Brave Search API (если есть ключ) — 2000/мес
    3. DuckDuckGo HTML — всегда доступен
    """
    
    # Публичные SearXNG инстансы (fallback если свой не настроен)
    # Обновлено: декабрь 2025
    PUBLIC_SEARXNG_INSTANCES = [
        "https://searx.be",
        "https://search.bus-hit.me",
        "https://searx.tiekoetter.com",
        "https://search.ononoki.org",
        "https://searx.work",
        "https://search.sapti.me",
        "https://searx.namejeff.xyz",
        "https://searx.divided-by-zero.eu",
    ]
    
    # User-Agent ротация для DDG
    DDG_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    def __init__(self):
        self.searxng_url = getattr(settings, 'searxng_url', None) or None
        # Проверяем что API ключ не пустая строка
        brave_key = getattr(settings, 'brave_search_api_key', None)
        self.brave_api_key = brave_key if brave_key and brave_key.strip() else None
        self._cache: dict[str, tuple[SearchResponse, float]] = {}
        self._cache_ttl = 600  # 10 минут для обычных запросов
        self._price_cache_ttl = 3600  # 1 час для цен на железо
        self._working_searxng: Optional[str] = None  # Кэш рабочего инстанса
        
        # Статистика кэша
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def search(
        self, 
        query: str, 
        max_results: int = 8,
        freshness: str = "month"
    ) -> SearchResponse:
        """
        Выполняет веб-поиск с автоматическим выбором провайдера.
        
        Args:
            query: Поисковый запрос
            max_results: Максимум результатов
            freshness: Фильтр по свежести
            
        Returns:
            SearchResponse с результатами
        """
        # Определяем TTL в зависимости от типа запроса
        is_price_query = is_hardware_price_query(query)
        cache_ttl = self._price_cache_ttl if is_price_query else self._cache_ttl
        
        # Проверяем кэш
        cache_key = f"{query}:{max_results}"
        if cache_key in self._cache:
            response, timestamp = self._cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < cache_ttl:
                self._cache_hits += 1
                logger.debug(f"[SEARCH] Cache hit ({cache_ttl}s TTL): {query[:30]}...")
                response.cached = True
                return response
        
        self._cache_misses += 1
        
        # Пробуем провайдеры по приоритету
        response = await self._try_providers(query, max_results, freshness)
        
        if response.results:
            self._cache[cache_key] = (response, datetime.now().timestamp())
        
        return response
    
    async def _try_providers(
        self, 
        query: str, 
        max_results: int,
        freshness: str
    ) -> SearchResponse:
        """Пробует провайдеры по приоритету."""
        
        # 1. SearXNG (свой или публичный)
        response = await self._search_searxng(query, max_results)
        if response.results:
            return response
        
        # 2. Brave (если есть ключ и он не пустой)
        if self.brave_api_key and self.brave_api_key.strip():
            response = await self._search_brave(query, max_results, freshness)
            if response.results:
                return response
        
        # 3. DuckDuckGo (fallback)
        return await self._search_duckduckgo(query, max_results)
    
    async def _search_searxng(
        self, 
        query: str, 
        max_results: int
    ) -> SearchResponse:
        """Поиск через SearXNG (self-hosted или публичный)."""
        
        # Определяем какой инстанс использовать
        instances_to_try = []
        
        if self.searxng_url:
            instances_to_try.append(self.searxng_url)
        
        if self._working_searxng and self._working_searxng not in instances_to_try:
            instances_to_try.insert(0, self._working_searxng)
        
        instances_to_try.extend(self.PUBLIC_SEARXNG_INSTANCES)
        
        for instance_url in instances_to_try[:4]:  # Пробуем максимум 4
            try:
                client = get_web_client()
                request_params = {
                    "q": query,
                    "format": "json",
                    "engines": "google,bing,duckduckgo",
                    "language": "ru-RU",
                }
                
                # Заголовки для обхода bot detection
                # X-Forwarded-For и X-Real-IP нужны для SearXNG
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "X-Forwarded-For": "127.0.0.1",
                    "X-Real-IP": "127.0.0.1",
                }
                
                response = await client.get(
                    f"{instance_url.rstrip('/')}/search",
                    params=request_params,
                    headers=headers,
                    timeout=8.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get("results", [])[:max_results]:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("content", ""),
                        url=item.get("url", ""),
                        source="searxng",
                        freshness=item.get("publishedDate"),
                    ))
                
                if results:
                    self._working_searxng = instance_url
                    logger.info(f"[SEARXNG] {instance_url}: {len(results)} results for: {query[:30]}...")
                    return SearchResponse(
                        results=results,
                        query=query,
                        provider=f"searxng:{instance_url}"
                    )
                        
            except Exception as e:
                logger.warning(f"[SEARXNG] {instance_url} failed: {e}")
                continue
        
        logger.warning(f"[SEARXNG] All instances failed for: {query[:30]}...")
        return SearchResponse(results=[], query=query, provider="searxng", error="All instances failed")
    
    async def _search_brave(
        self, 
        query: str, 
        max_results: int,
        freshness: str
    ) -> SearchResponse:
        """Поиск через Brave Search API."""
        try:
            # Проверяем наличие API ключа
            if not self.brave_api_key:
                return SearchResponse(results=[], query=query, provider="brave", error="No API key")
            
            client = get_web_client()
            # httpx автоматически кодирует параметры в UTF-8
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={
                    "q": query,  # httpx сам закодирует кириллицу
                    "count": max_results,
                    "freshness": freshness,
                    "text_decorations": "false",
                },
                headers={
                    "X-Subscription-Token": self.brave_api_key,
                    "Accept": "application/json",
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                    url=item.get("url", ""),
                    source="brave",
                    freshness=item.get("age"),
                ))
            
            logger.info(f"[BRAVE] Found {len(results)} results for: {query[:30]}...")
            return SearchResponse(results=results, query=query, provider="brave")
                
        except Exception as e:
            logger.warning(f"[BRAVE] Search error: {e}")
            return SearchResponse(results=[], query=query, provider="brave", error=str(e))
    
    async def _search_duckduckgo(
        self, 
        query: str, 
        max_results: int
    ) -> SearchResponse:
        """Поиск через DuckDuckGo HTML с ротацией User-Agent."""
        import random
        
        # Пробуем несколько раз с разными User-Agent
        for attempt in range(3):
            try:
                user_agent = random.choice(self.DDG_USER_AGENTS)
                
                # DDG требует отдельный клиент без follow_redirects
                async with httpx.AsyncClient(
                    timeout=15,
                    follow_redirects=False  # Не следовать редиректам — это признак блокировки
                ) as client:
                    response = await client.post(
                        "https://html.duckduckgo.com/html/",
                        data={"q": query},
                        headers={
                            "User-Agent": user_agent,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Referer": "https://duckduckgo.com/",
                        }
                    )
                    
                    # Если редирект — DDG заблокировал
                    if response.status_code in (301, 302, 303, 307, 308):
                        logger.debug(f"[DDG] Redirect detected (attempt {attempt + 1}), trying again...")
                        await asyncio.sleep(1)  # Небольшая задержка перед повтором
                        continue
                    
                    response.raise_for_status()
                    
                    html = response.text
                    results = []
                    
                    snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
                    titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', html)
                    urls = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
                    
                    for i, (title, snippet) in enumerate(zip(titles[:max_results], snippets[:max_results])):
                        title = title.replace("&amp;", "&").replace("&quot;", '"').strip()
                        snippet = snippet.replace("&amp;", "&").replace("&quot;", '"').strip()
                        url = urls[i] if i < len(urls) else ""
                        
                        if title and snippet:
                            results.append(SearchResult(
                                title=title, snippet=snippet, url=url, source="duckduckgo"
                            ))
                    
                    if results:
                        logger.info(f"[DDG] Found {len(results)} results for: {query[:30]}...")
                        return SearchResponse(results=results, query=query, provider="duckduckgo")
                    
            except Exception as e:
                logger.debug(f"[DDG] Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.5)
                continue
        
        logger.warning(f"[DDG] All attempts failed for: {query[:30]}...")
        return SearchResponse(results=[], query=query, provider="duckduckgo", error="DDG blocked or unavailable")
    
    def format_for_prompt(self, response: SearchResponse, max_chars: int = 2000) -> str:
        """Форматирует результаты для промпта LLM."""
        if not response.results:
            return ""
        
        lines = [f"[Результаты поиска: {response.query}]"]
        total_chars = len(lines[0])
        
        for i, result in enumerate(response.results, 1):
            line = f"{i}. {result.title}: {result.snippet}"
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)
        
        return "\n".join(lines)


    def get_cache_stats(self) -> dict:
        """Возвращает статистику кэша."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "cached_queries": len(self._cache),
        }
    
    def clear_cache(self):
        """Очищает кэш поиска."""
        self._cache.clear()
        logger.info("[SEARCH] Cache cleared")


# Глобальный экземпляр
web_search = WebSearchService()
