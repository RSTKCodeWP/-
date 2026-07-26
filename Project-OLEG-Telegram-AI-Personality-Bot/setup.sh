#!/usr/bin/env bash
# Скрипт для быстрого запуска бота Олег

set -e

echo "======================================"
echo "  Telegram Bot ОЛЕГ - Setup Script"
echo "======================================"
echo ""

# Проверка Python
echo "1. Проверка Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден! Установите Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION найден"
echo ""

# Проверка зависимостей
echo "2. Установка зависимостей..."
python3 -m pip install -q -r requirements.txt
echo "✅ Зависимости установлены"
echo ""

# Проверка .env
echo "3. Проверка конфигурации..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "⚠️  Файл .env не найден!"
        echo "   Создаю .env из .env.example..."
        cp .env.example .env
        echo "✅ Файл .env создан"
        echo ""
        echo "⚠️  ВАЖНО: Отредактируйте .env и установите:"
        echo "   - TELEGRAM_BOT_TOKEN (токен от @BotFather)"
        echo "   - OWNER_ID (ID вашего Telegram аккаунта для полного доступа)"
        echo ""
        echo "   Затем запустите скрипт снова!"
        exit 1
    else
        echo "❌ Файл .env.example не найден!"
        exit 1
    fi
else
    # Проверка обязательных переменных
    if grep -q "TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE" .env; then
        echo "⚠️  TELEGRAM_BOT_TOKEN не установлен в .env!"
        echo "   Получите токен в https://t.me/BotFather"
        exit 1
    fi
    echo "✅ .env найден и配置"
fi
echo ""

# Создание директорий
echo "4. Подготовка директорий..."
mkdir -p data logs
echo "✅ Директории созданы"
echo ""

# Проверка Ollama
echo "5. Проверка Ollama..."
OLLAMA_URL=$(grep "OLLAMA_BASE_URL" .env | cut -d'=' -f2 || echo "http://localhost:11434")
if curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo "✅ Ollama доступна по адресу $OLLAMA_URL"
    
    # Проверка модели
    OLLAMA_MODEL=$(grep "OLLAMA_MODEL" .env | cut -d'=' -f2 || echo "deepseek-v3.2:cloud")
    if curl -s "$OLLAMA_URL/api/tags" | grep -q "$OLLAMA_MODEL"; then
        echo "✅ Модель $OLLAMA_MODEL установлена"
    else
        echo "⚠️  Модель $OLLAMA_MODEL не найдена!"
        echo "   Установите её командой: ollama pull $OLLAMA_MODEL"
        exit 1
    fi
else
    echo "⚠️  Ollama не доступна по адресу $OLLAMA_URL"
    echo "   Убедитесь, что Ollama запущена: ollama serve"
    exit 1
fi
echo ""

# Готово к запуску
echo "======================================"
echo "✅ ВСЕ ГОТОВО К ЗАПУСКУ!"
echo "======================================"
echo ""
echo "Для запуска бота выполните:"
echo "  python3 -m app.main"
echo ""
echo "Логи будут сохранены в logs/oleg.log"
echo ""
echo "Для остановки бота нажмите Ctrl+C"
echo ""
