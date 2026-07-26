"""Configuration management for CoinFlow bot."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///coinflow.db")
    
    # Cache settings
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))
    
    # Alert check interval (minutes)
    ALERT_CHECK_INTERVAL = int(os.getenv('ALERT_CHECK_INTERVAL', '5'))
    
    # Web App URL
    WEBAPP_URL = os.getenv('WEBAPP_URL', 'http://localhost:8000')
    
    # Ollama AI settings (Qwen3 Cloud Models)
    OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    OLLAMA_TEXT_MODEL = os.getenv('OLLAMA_TEXT_MODEL', 'qwen3-coder:480b-cloud')  # Qwen3-Coder for text
    OLLAMA_VISION_MODEL = os.getenv('OLLAMA_VISION_MODEL', 'qwen3-vl:235b-cloud')  # Qwen3-VL for vision
    
    # Admin settings
    ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
    
    # Chart settings
    CHART_DPI = int(os.getenv("CHART_DPI", "150"))
    DEFAULT_CHART_PERIOD = int(os.getenv("DEFAULT_CHART_PERIOD", "30"))
    
    # Prediction settings
    DEFAULT_PREDICTION_DAYS = int(os.getenv("DEFAULT_PREDICTION_DAYS", "90"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "coinflow.log")
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))


config = Config()
