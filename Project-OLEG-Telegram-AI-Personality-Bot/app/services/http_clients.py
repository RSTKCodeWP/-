"""
Shared HTTP clients for external services.

Reusing httpx.AsyncClient saves ~50ms per request by avoiding
connection setup overhead. Each client is configured for its use case.

Usage:
    from app.services.http_clients import get_web_client, get_ollama_client

    async with get_web_client() as client:
        response = await client.get(url)
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Global clients (lazy initialized)
_ollama_client: Optional[httpx.AsyncClient] = None
_web_client: Optional[httpx.AsyncClient] = None

# Default User-Agent for web requests
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def get_ollama_client() -> httpx.AsyncClient:
    """
    Get or create global httpx client for Ollama requests.
    
    Configured with:
    - Timeout from settings
    - Connection pooling (20 max, 10 keepalive)
    """
    global _ollama_client
    if _ollama_client is None or _ollama_client.is_closed:
        _ollama_client = httpx.AsyncClient(
            timeout=settings.ollama_timeout,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )
        logger.debug("Created Ollama httpx client")
    return _ollama_client


def get_web_client() -> httpx.AsyncClient:
    """
    Get or create global httpx client for web requests.
    
    Configured with:
    - 15s timeout (reasonable for web pages)
    - Default User-Agent
    - Follow redirects
    - Connection pooling
    """
    global _web_client
    if _web_client is None or _web_client.is_closed:
        _web_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            limits=httpx.Limits(
                max_connections=30,
                max_keepalive_connections=15,
            ),
        )
        logger.debug("Created web httpx client")
    return _web_client


async def close_all_clients():
    """Close all global httpx clients. Call on shutdown."""
    global _ollama_client, _web_client
    
    if _ollama_client and not _ollama_client.is_closed:
        await _ollama_client.aclose()
        _ollama_client = None
        logger.debug("Closed Ollama httpx client")
    
    if _web_client and not _web_client.is_closed:
        await _web_client.aclose()
        _web_client = None
        logger.debug("Closed web httpx client")
    
    logger.info("All httpx clients closed")
