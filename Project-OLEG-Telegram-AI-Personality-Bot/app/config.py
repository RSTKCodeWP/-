"""Application configuration with validation."""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Telegram
    telegram_bot_token: str = Field(..., min_length=10, description="Telegram bot token from BotFather")
    owner_id: Optional[int] = Field(None, description="Bot owner's Telegram ID")

    # MTProto Proxy (for bypassing Telegram blocks in Russia)
    # Proxy server: max.ru.rightarion.ru:443
    mtproto_enabled: bool = Field(default=False, description="Enable MTProto proxy for Telegram connection")
    mtproto_server: str = Field(default="", description="MTProto proxy server hostname (e.g. max.ru.rightarion.ru)")
    mtproto_port: int = Field(default=443, ge=1, le=65535, description="MTProto proxy server port")
    mtproto_secret: str = Field(default="", description="MTProto proxy secret (hex format, e.g. eedcaae509a2455bbfc6165f1708fd5c586d61782e7275)")
    
    # SDOC (Steam Deck OC) - родной дом Олега
    sdoc_chat_id: Optional[int] = Field(default=None, description="SDOC group chat ID (Олег работает только тут)")
    sdoc_chat_username: str = Field(default="steamdeckoverclock", description="SDOC group username")
    sdoc_owner_id: int = Field(default=703959426, description="SDOC owner Telegram ID (@k1gsss)")
    sdoc_exclusive_mode: bool = Field(default=True, description="Олег работает только в SDOC и ЛС")

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    ollama_base_model: str = Field(
        default="deepseek-v3.2:cloud",
        description="Main model for text generation"
    )
    ollama_vision_model: str = Field(
        default="qwen3-vl:4b",
        description="Model for image analysis"
    )
    ollama_memory_model: str = Field(
        default="glm-4.6:cloud",
        description="Model for RAG and memory search"
    )
    ollama_timeout: int = Field(default=120, ge=10, le=300, description="Ollama request timeout in seconds")
    ollama_cache_enabled: bool = Field(default=True, description="Enable response caching")
    ollama_cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    ollama_cache_max_size: int = Field(default=128, ge=10, description="Max cache size")
    ollama_web_search_enabled: bool = Field(default=True, description="Enable web search tool for LLM")
    
    # Web Search (anti-hallucination)
    searxng_url: Optional[str] = Field(default=None, description="SearXNG instance URL (self-hosted, unlimited)")
    brave_search_api_key: Optional[str] = Field(default=None, description="Brave Search API key (free tier: 2000 req/month)")
    
    # Tool model (для fallback режима — когда основная модель недоступна)
    # Используется для function calling (веб-поиск) вместе с fallback_model
    ollama_tool_model: str = Field(
        default="qwen3:8b",
        description="Model for tools in fallback mode (web search). Must support function calling."
    )
    
    # Fallback models (локальные модели когда cloud недоступен)
    ollama_fallback_enabled: bool = Field(default=True, description="Enable fallback to local models when cloud unavailable")
    ollama_fallback_model: str = Field(default="gemma3:12b", description="Fallback model for text generation")
    ollama_fallback_vision_model: str = Field(default="qwen3-vl:4b-instruct", description="Fallback model for vision")
    ollama_fallback_memory_model: str = Field(default="qwen3:8b", description="Fallback model for memory/RAG")
    
    # Toxicity analysis
    toxicity_analysis_enabled: bool = Field(default=True, description="Enable toxicity analysis")
    toxicity_threshold: int = Field(default=75, ge=0, le=100, description="Toxicity threshold (0-100)")

    # ChromaDB (RAG)
    chromadb_persist_dir: str = Field(default="./data/chroma", description="ChromaDB persistence directory")
    chromadb_collection_name: str = Field(default="oleg_kb", description="ChromaDB collection name")
    chromadb_host: str = Field(default="", description="ChromaDB server host (empty for local persistent)")
    chromadb_port: int = Field(default=8000, description="ChromaDB server port")

    # Vector store
    embedding_model: str = Field(default="nomic-embed-text", description="Embedding model name (nomic лучше для русского)")
    similarity_threshold: float = Field(default=0.65, ge=0.0, le=1.0, description="Similarity threshold for RAG")
    kb_max_results: int = Field(default=5, ge=1, le=20, description="Max KB facts to return per search")
    kb_distance_threshold: float = Field(default=0.8, ge=0.1, le=2.0, description="Max distance for KB facts (lower = stricter, ChromaDB L2 distance)")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/oleg.db",
        description="Database connection URL (supports PostgreSQL: postgresql+asyncpg://user:pass@host/db)"
    )
    
    # Redis
    redis_enabled: bool = Field(default=False, description="Enable Redis for caching and rate limiting")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    redis_db: int = Field(default=0, ge=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    
    # Worker (Arq)
    worker_enabled: bool = Field(default=False, description="Enable Arq worker for heavy tasks")
    worker_max_tries: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts for worker tasks")
    worker_job_timeout: int = Field(default=300, ge=30, le=600, description="Worker job timeout in seconds")
    worker_queue_warning_threshold: int = Field(default=100, ge=10, description="Queue size warning threshold")

    # Timezone
    timezone: str = Field(default="Europe/Moscow", description="Bot timezone")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/oleg.log", description="Log file path")

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=15, ge=1, description="Max requests per window")
    rate_limit_window: int = Field(default=60, ge=1, description="Rate limit window in seconds")
    
    # Antispam (лимит запросов к боту)
    antispam_enabled: bool = Field(default=True, description="Enable request limits (antispam)")
    antispam_burst: int = Field(default=5, ge=1, description="Max requests per minute (burst)")
    antispam_hourly: int = Field(default=50, ge=5, description="Max requests per hour")

    # Metrics
    metrics_enabled: bool = Field(default=False, description="Enable Prometheus metrics endpoint")
    metrics_port: int = Field(default=9090, ge=1, le=65535, description="Metrics server port")

    # Media features
    voice_recognition_enabled: bool = Field(default=True, description="Enable voice message recognition (STT)")
    whisper_model: str = Field(default="base", description="Whisper model size: tiny, base, small, medium, large")
    content_download_enabled: bool = Field(default=True, description="Enable auto-download of media from links")
    huggingface_mirror: str = Field(default="", description="HuggingFace mirror URL (e.g. https://hf-mirror.com for Russia)")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate bot token format."""
        if not v or v == "YOUR_BOT_TOKEN_HERE":
            raise ValueError("telegram_bot_token must be set to a valid token")
        return v

    @property
    def bot_token(self) -> str:
        """Alias for backward compatibility."""
        return self.telegram_bot_token

    @property
    def ollama_model(self) -> str:
        """Alias for backward compatibility."""
        return self.ollama_base_model


# Global settings instance
settings = Settings()
