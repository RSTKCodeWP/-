"""Prometheus metrics for monitoring."""

import logging
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Simple metrics collector for Prometheus-style metrics."""
    
    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict] = None):
        """Increment a counter metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value
            logger.debug(f"Counter {key} incremented by {value}")
    
    async def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """Set a gauge metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            logger.debug(f"Gauge {key} set to {value}")
    
    async def observe_histogram(self, name: str, value: float, labels: Optional[Dict] = None):
        """Observe a value for histogram metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append(value)
            # Keep only last 1000 observations
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
            logger.debug(f"Histogram {key} observed value {value}")
    
    def _make_key(self, name: str, labels: Optional[Dict] = None) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    async def get_metrics(self) -> str:
        """Get all metrics in Prometheus text format."""
        async with self._lock:
            lines = []
            
            # Counters
            for key, value in self._counters.items():
                lines.append(f"# TYPE {key.split('{')[0]} counter")
                lines.append(f"{key} {value}")
            
            # Gauges
            for key, value in self._gauges.items():
                lines.append(f"# TYPE {key.split('{')[0]} gauge")
                lines.append(f"{key} {value}")
            
            # Histograms (simplified - just count and sum)
            for key, values in self._histograms.items():
                base_name = key.split('{')[0]
                lines.append(f"# TYPE {base_name} histogram")
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_sum {sum(values)}")
                if values:
                    lines.append(f"{key}_avg {sum(values) / len(values)}")
            
            return "\n".join(lines)
    
    async def reset(self):
        """Reset all metrics."""
        async with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            logger.info("All metrics reset")


# Global metrics collector
metrics = MetricsCollector()


# Convenience functions for common metrics
async def track_message_processed(chat_type: str = "unknown"):
    """Track a processed message."""
    await metrics.increment_counter("bot_messages_processed_total", labels={"chat_type": chat_type})


async def track_command_executed(command: str):
    """Track an executed command."""
    await metrics.increment_counter("bot_commands_executed_total", labels={"command": command})


async def track_ollama_request(model: str, duration: float, success: bool):
    """Track an Ollama API request."""
    await metrics.increment_counter(
        "bot_ollama_requests_total",
        labels={"model": model, "success": str(success).lower()}
    )
    await metrics.observe_histogram(
        "bot_ollama_request_duration_seconds",
        duration,
        labels={"model": model}
    )


async def track_rate_limit_hit(user_id: int):
    """Track a rate limit hit."""
    await metrics.increment_counter("bot_rate_limit_hits_total")


async def track_error(error_type: str):
    """Track an error."""
    await metrics.increment_counter("bot_errors_total", labels={"type": error_type})


async def set_active_users(count: int):
    """Set the number of active users."""
    await metrics.set_gauge("bot_active_users", count)


async def set_cache_size(size: int):
    """Set the cache size."""
    await metrics.set_gauge("bot_cache_size", size)
