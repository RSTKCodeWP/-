"""Health check handler for /ping command."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings

logger = logging.getLogger(__name__)

router = Router()


@dataclass
class ComponentStatus:
    """Status of a single component."""
    name: str
    is_healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    
    @property
    def indicator(self) -> str:
        """Return status indicator emoji."""
        return "🟢" if self.is_healthy else "🔴"
    
    @property
    def status_text(self) -> str:
        """Return human-readable status text."""
        if self.is_healthy:
            if self.latency_ms is not None:
                return f"Жив ({self.latency_ms:.0f}ms)"
            return "OK"
        return self.error or "Ошибка"


@dataclass
class HealthStatus:
    """Overall health status of all components."""
    telegram: ComponentStatus
    ollama: ComponentStatus
    vision: ComponentStatus
    rag: ComponentStatus
    
    @property
    def all_healthy(self) -> bool:
        """Check if all components are healthy."""
        return all([
            self.telegram.is_healthy,
            self.ollama.is_healthy,
            self.vision.is_healthy,
            self.rag.is_healthy,
        ])


class HealthChecker:
    """Health checker for all bot subsystems."""
    
    async def check_telegram(self, message: Message) -> ComponentStatus:
        """
        Check Telegram API latency by measuring round-trip time.
        
        Args:
            message: The incoming message to measure latency from
            
        Returns:
            ComponentStatus with Telegram health info
        """
        try:
            start = time.perf_counter()
            # Use getMe as a simple health check
            await message.bot.get_me()
            latency_ms = (time.perf_counter() - start) * 1000
            
            return ComponentStatus(
                name="Telegram",
                is_healthy=True,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error(f"Telegram health check failed: {e}")
            return ComponentStatus(
                name="Telegram",
                is_healthy=False,
                error=str(e)[:50],
            )
    
    async def check_ollama(self) -> ComponentStatus:
        """
        Check Ollama (main LLM) availability.
        
        Returns:
            ComponentStatus with Ollama health info
        """
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=10) as client:
                # Check if Ollama is responding
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                response.raise_for_status()
                latency_ms = (time.perf_counter() - start) * 1000
                
                # Check if the configured model is available
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check for base model (strip tag if present)
                base_model_name = settings.ollama_base_model.split(":")[0]
                model_available = any(base_model_name in m for m in models)
                
                if model_available:
                    return ComponentStatus(
                        name="Ollama (мозг)",
                        is_healthy=True,
                        latency_ms=latency_ms,
                    )
                else:
                    return ComponentStatus(
                        name="Ollama (мозг)",
                        is_healthy=False,
                        error=f"Модель {settings.ollama_base_model} не найдена",
                    )
                    
        except httpx.TimeoutException:
            logger.error("Ollama health check timed out")
            return ComponentStatus(
                name="Ollama (мозг)",
                is_healthy=False,
                error="Таймаут",
            )
        except httpx.RequestError as e:
            logger.error(f"Ollama health check failed: {e}")
            return ComponentStatus(
                name="Ollama (мозг)",
                is_healthy=False,
                error="Нет соединения",
            )
        except Exception as e:
            logger.error(f"Ollama health check error: {e}")
            return ComponentStatus(
                name="Ollama (мозг)",
                is_healthy=False,
                error=str(e)[:50],
            )
    
    async def check_vision(self) -> ComponentStatus:
        """
        Check Vision model availability.
        
        Returns:
            ComponentStatus with Vision model health info
        """
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                response.raise_for_status()
                latency_ms = (time.perf_counter() - start) * 1000
                
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check for vision model
                vision_model_name = settings.ollama_vision_model.split(":")[0]
                model_available = any(vision_model_name in m for m in models)
                
                if model_available:
                    return ComponentStatus(
                        name="Vision (глаза)",
                        is_healthy=True,
                        latency_ms=latency_ms,
                    )
                else:
                    return ComponentStatus(
                        name="Vision (глаза)",
                        is_healthy=False,
                        error=f"Модель {settings.ollama_vision_model} не найдена",
                    )
                    
        except httpx.TimeoutException:
            logger.error("Vision health check timed out")
            return ComponentStatus(
                name="Vision (глаза)",
                is_healthy=False,
                error="Таймаут",
            )
        except httpx.RequestError as e:
            logger.error(f"Vision health check failed: {e}")
            return ComponentStatus(
                name="Vision (глаза)",
                is_healthy=False,
                error="Нет соединения",
            )
        except Exception as e:
            logger.error(f"Vision health check error: {e}")
            return ComponentStatus(
                name="Vision (глаза)",
                is_healthy=False,
                error=str(e)[:50],
            )
    
    async def check_rag(self) -> ComponentStatus:
        """
        Check ChromaDB (RAG memory) availability.
        
        Returns:
            ComponentStatus with RAG health info
        """
        try:
            start = time.perf_counter()
            from app.services.vector_db import vector_db
            
            # Try to access the client and get/create a test collection
            if vector_db.client is None:
                return ComponentStatus(
                    name="RAG (память)",
                    is_healthy=False,
                    error="ChromaDB не инициализирована",
                )
            
            # Try to heartbeat the client
            vector_db.client.heartbeat()
            latency_ms = (time.perf_counter() - start) * 1000
            
            return ComponentStatus(
                name="RAG (память)",
                is_healthy=True,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            logger.error(f"RAG health check failed: {e}")
            return ComponentStatus(
                name="RAG (память)",
                is_healthy=False,
                error=str(e)[:50],
            )
    
    async def check_all(self, message: Message) -> HealthStatus:
        """
        Check all components and return overall health status.
        
        Args:
            message: The incoming message (needed for Telegram latency check)
            
        Returns:
            HealthStatus with all component statuses
        """
        telegram_status = await self.check_telegram(message)
        ollama_status = await self.check_ollama()
        vision_status = await self.check_vision()
        rag_status = await self.check_rag()
        
        return HealthStatus(
            telegram=telegram_status,
            ollama=ollama_status,
            vision=vision_status,
            rag=rag_status,
        )


# Global health checker instance
health_checker = HealthChecker()


def format_health_status(status: HealthStatus) -> str:
    """
    Format health status for display in Telegram.
    
    Args:
        status: The health status to format
        
    Returns:
        Formatted string for Telegram message
    """
    lines = [
        "🏥 <b>Статус систем Олега:</b>",
        "",
        f"{status.telegram.indicator} <b>{status.telegram.name}:</b> {status.telegram.status_text}",
        f"{status.ollama.indicator} <b>{status.ollama.name}:</b> {status.ollama.status_text}",
        f"{status.vision.indicator} <b>{status.vision.name}:</b> {status.vision.status_text}",
        f"{status.rag.indicator} <b>{status.rag.name}:</b> {status.rag.status_text}",
    ]
    
    # Add overall status
    if status.all_healthy:
        lines.append("")
        lines.append("✅ Все системы работают штатно")
    else:
        lines.append("")
        lines.append("⚠️ Есть проблемы с некоторыми компонентами")
    
    return "\n".join(lines)


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    """
    Handle /ping command - show detailed system status.
    
    Args:
        message: Incoming message
    """
    # Send initial "checking" message
    checking_msg = await message.reply("🔍 Проверяю системы...")
    
    try:
        # Run all health checks
        status = await health_checker.check_all(message)
        
        # Format and send result
        result_text = format_health_status(status)
        await checking_msg.edit_text(result_text, parse_mode="HTML")
        
        logger.info(
            f"Health check by @{message.from_user.username or message.from_user.id}: "
            f"telegram={status.telegram.is_healthy}, "
            f"ollama={status.ollama.is_healthy}, "
            f"vision={status.vision.is_healthy}, "
            f"rag={status.rag.is_healthy}"
        )
    except Exception as e:
        logger.error(f"Error in /ping command: {e}")
        await checking_msg.edit_text(
            "❌ Ошибка при проверке систем. Попробуй позже.",
            parse_mode="HTML"
        )
