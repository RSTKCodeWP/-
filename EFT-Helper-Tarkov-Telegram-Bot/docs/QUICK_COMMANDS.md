# ⚡ Шпаргалка по командам

## 🎯 Management Scripts (рекомендуется)

### Windows
```cmd
manage.bat
```

### Linux/Mac
```bash
./manage.sh
```

## 🐳 Docker команды (прямые)

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose stop

# Перезапуск
docker-compose restart

# Логи (real-time)
docker-compose logs -f

# Логи (последние 50)
docker-compose logs --tail=50

# Статус
docker-compose ps

# Пересборка
docker-compose build

# Полное обновление
docker-compose down && docker-compose build && docker-compose up -d

# Статистика
docker stats eft-helper-bot

# Вход в контейнер
docker-compose exec eft-helper-bot bash

# Остановка и удаление
docker-compose down
```

## 📦 Poetry команды (локальная разработка)

```bash
# Установка зависимостей
poetry install

# Запуск бота
poetry run python main.py

# Тест API
poetry run python scripts/test_quests_api.py

# Сброс webhook
poetry run python scripts/reset_webhook.py
```

## 🔧 Полезные команды

```bash
# Резервная копия БД
cp data/eft_helper.db backup/eft_helper_$(date +%Y%m%d).db

# Просмотр локальных логов
tail -f logs/bot.log

# Очистка Docker
docker system prune -f

# Список образов
docker images | grep efthelper
```

## 📱 Telegram бот

Найдите в Telegram: `@efthelper_bot`

Команды:
- `/start` - Главное меню
- Выберите функцию из меню кнопок

---

**Совет**: Используйте `manage.bat`/`manage.sh` для удобного управления!

