"""Tests for configuration."""

import pytest
from pydantic import ValidationError
from app.config import Settings


def test_settings_default_values():
    """Test that settings have correct default values."""
    # Create settings with minimal required fields
    settings = Settings(telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_base_model == "deepseek-v3.2:cloud"
    assert settings.ollama_timeout == 90
    assert settings.rate_limit_enabled is True
    assert settings.rate_limit_requests == 10
    assert settings.rate_limit_window == 60
    assert settings.redis_enabled is False


def test_settings_validation_invalid_token():
    """Test that invalid bot token raises validation error."""
    with pytest.raises(ValidationError):
        Settings(telegram_bot_token="YOUR_BOT_TOKEN_HERE")


def test_settings_validation_invalid_log_level():
    """Test that invalid log level raises validation error."""
    with pytest.raises(ValidationError):
        Settings(
            telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            log_level="INVALID"
        )


def test_settings_log_level_case_insensitive():
    """Test that log level is case insensitive."""
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        log_level="debug"
    )
    assert settings.log_level == "DEBUG"


def test_settings_redis_configuration():
    """Test Redis configuration."""
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        redis_enabled=True,
        redis_host="redis.example.com",
        redis_port=6380,
        redis_db=1,
        redis_password="secret"
    )
    
    assert settings.redis_enabled is True
    assert settings.redis_host == "redis.example.com"
    assert settings.redis_port == 6380
    assert settings.redis_db == 1
    assert settings.redis_password == "secret"


def test_settings_postgresql_url():
    """Test PostgreSQL database URL."""
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        database_url="postgresql+asyncpg://user:pass@localhost/oleg"
    )
    
    assert "postgresql+asyncpg" in settings.database_url
