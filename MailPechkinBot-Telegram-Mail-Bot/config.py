"""
Конфигурационный файл бота
"""

import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки бота
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Настройки базы данных
DATABASE_PATH = "users.db"

# Настройки API 1secmail
TEMPMAIL_API_URL = "https://www.1secmail.com/api/v1/"
TEMPMAIL_DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net"]

# Настройки сообщений
MAX_MESSAGE_LENGTH = 3000
MAX_MESSAGES_DISPLAY = 10

# Логирование
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
