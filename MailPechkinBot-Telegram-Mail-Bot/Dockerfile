# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
RUN pip install poetry==1.7.1

# Копируем файлы проекта
COPY pyproject.toml poetry.lock* ./

# Настраиваем Poetry для установки зависимостей в системное окружение
RUN poetry config virtualenvs.create false

# Устанавливаем зависимости
RUN poetry install --no-dev --no-interaction --no-ansi

# Копируем весь код приложения
COPY . .

# Создаем директорию для базы данных
RUN mkdir -p /app/data

# Указываем команду запуска
CMD ["python", "bot.py"]
