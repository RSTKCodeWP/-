"""Система логирования для бота Олег."""

import logging
import logging.handlers
import pathlib
import sys
from typing import Optional
from app.config import settings

# Флаг для предотвращения повторной инициализации
_logging_initialized = False

# Директория для логов
LOG_DIR = pathlib.Path("logs")

# Цвета для консоли (ANSI)
COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли."""
    
    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"
        result = super().format(record)
        record.levelname = levelname
        return result


class ContextFilter(logging.Filter):
    """Фильтр для добавления контекста к записям."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name:
            parts = record.name.split(".")
            record.short_name = parts[-1] if len(parts) > 1 else record.name
        else:
            record.short_name = "root"
        return True


def setup_logging() -> None:
    """Инициализировать систему логирования."""
    global _logging_initialized
    
    if _logging_initialized:
        return
    _logging_initialized = True
    
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)
    
    # Отключаем propagate для всех логгеров чтобы избежать дублирования
    root_logger.propagate = False
    
    context_filter = ContextFilter()
    
    # Форматы
    file_format = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s [%(short_name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_format = ColoredFormatter(
        "[%(asctime)s] %(levelname)-8s [%(short_name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    error_format = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s [%(name)s:%(lineno)d] %(message)s\n"
        "    File: %(pathname)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # 1. Основной лог (INFO+)
    main_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "oleg.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    main_handler.setLevel(getattr(logging, settings.log_level))
    main_handler.setFormatter(file_format)
    main_handler.addFilter(context_filter)
    root_logger.addHandler(main_handler)
    
    # 2. Только ошибки (ERROR+)
    error_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "errors.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(error_format)
    error_handler.addFilter(context_filter)
    root_logger.addHandler(error_handler)
    
    # 3. Debug лог (DEBUG+)
    debug_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "debug.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(file_format)
    debug_handler.addFilter(context_filter)
    root_logger.addHandler(debug_handler)
    
    # 4. Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level))
    console_handler.setFormatter(console_format)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)
    
    # Уменьшаем шум от библиотек и отключаем их собственные handlers
    # ВАЖНО: очищаем handlers ПОСЛЕ добавления наших, чтобы библиотеки не добавили свои позже
    lib_loggers = [
        "httpx", "httpcore", "aiogram", "apscheduler", 
        "sqlalchemy.engine", "chromadb", "urllib3", "asyncio",
        "aiosqlite", "aiohttp", "arq", "default",  # default - это APScheduler jobs
        "apscheduler.scheduler", "apscheduler.executors", "apscheduler.executors.default"
    ]
    for lib_name in lib_loggers:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.handlers.clear()  # Убираем их собственные handlers
        lib_logger.propagate = True  # Пусть идут через root
    
    # Устанавливаем уровни
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)  # Меньше шума от scheduler
    logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    logging.getLogger("default").setLevel(logging.WARNING)  # APScheduler jobs
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logging.info(f"Логирование: level={settings.log_level} | dir={LOG_DIR.absolute()}")
    logging.info(f"  oleg.log (INFO+), errors.log (ERROR+), debug.log (DEBUG+)")


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с указанным именем."""
    return logging.getLogger(name)
