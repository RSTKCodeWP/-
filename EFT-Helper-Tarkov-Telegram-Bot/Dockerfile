# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем метаданные
LABEL maintainer="EFT Helper Bot"
LABEL description="Telegram bot for Escape from Tarkov players"

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir poetry==1.8.3

# Настраиваем Poetry (не создавать виртуальное окружение в контейнере)
RUN poetry config virtualenvs.create false

# Копируем файлы зависимостей Poetry
COPY pyproject.toml poetry.lock* ./

# Устанавливаем зависимости через Poetry
RUN poetry install --no-interaction --no-ansi --only main

# Устанавливаем faster-whisper для голосовых сообщений
RUN pip install --no-cache-dir faster-whisper

# Копируем весь проект
COPY . .

# Создаем директорию для базы данных
RUN mkdir -p /app/data

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Открываем порт (если потребуется в будущем для webhook)
EXPOSE 8080

# Создаем директорию для логов
RUN mkdir -p /app/logs

# Запускаем бота через main.py (с поддержкой AI)
CMD ["python", "main.py"]
