# 🔧 Установка — Олег 5.0

> Подробное руководство по установке и настройке

---

## 📋 Требования

| Компонент | Версия | Обязательно |
|-----------|--------|-------------|
| Python | 3.10 - 3.14 | ✅ |
| Docker | 20.10+ | Рекомендуется |
| Ollama | Latest | ✅ |
| ffmpeg | Latest | Для голосовых |
| Redis | 7.x | Для продакшена |

---

## 🐳 Вариант 1: Docker (рекомендуется)

### 1. Клонирование

```bash
git clone https://github.com/your-repo/oleg-bot
cd oleg-bot
```

### 2. Конфигурация

```bash
cp .env.docker .env
nano .env
```

**Минимум:**
```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
OWNER_ID=123456789
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### 3. Запуск

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Проверка

```bash
docker-compose logs -f oleg-bot
```

---

## 🐍 Вариант 2: Python

### 1. Виртуальное окружение

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Зависимости

```bash
pip install -r requirements.txt
```

### 3. ffmpeg (для голосовых)

```bash
# Windows
choco install ffmpeg

# Ubuntu/Debian
apt install ffmpeg

# Mac
brew install ffmpeg
```

### 4. Ollama модели

```bash
ollama pull deepseek-v3.2:cloud
ollama pull qwen3-vl:235b-cloud
ollama pull glm-4.6:cloud
```

### 5. Миграции базы данных

```bash
alembic upgrade head
```

### 6. Запуск

```bash
python -m app.main
```

---

## ⚙️ Конфигурация

### Основные параметры

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_token
OWNER_ID=your_id

# Ollama — три модели
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_BASE_MODEL=deepseek-v3.2:cloud    # Текст
OLLAMA_VISION_MODEL=qwen3-vl:235b-cloud       # Изображения
OLLAMA_MEMORY_MODEL=glm-4.6:cloud             # RAG
OLLAMA_TIMEOUT=90

# Голосовые
VOICE_RECOGNITION_ENABLED=true
WHISPER_MODEL=base  # tiny/base/small/medium/large

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/oleg.db

# Redis
REDIS_ENABLED=true
REDIS_HOST=redis

# Metrics
METRICS_ENABLED=true
METRICS_PORT=9090

# Logging
LOG_LEVEL=INFO
```

### Whisper модели

| Модель | Размер | Скорость | Качество |
|--------|--------|----------|----------|
| tiny | 39 MB | Быстро | Базовое |
| base | 74 MB | Быстро | Хорошее |
| small | 244 MB | Средне | Отличное |
| medium | 769 MB | Медленно | Превосходное |
| large | 1550 MB | Очень медленно | Максимальное |

---

## 🗄️ База данных

### SQLite (development)

```bash
mkdir -p data
python -m app.main  # Создаётся автоматически
```

### PostgreSQL (production)

```bash
# 1. Обнови DATABASE_URL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/oleg

# 2. Запусти миграции
alembic upgrade head
```

### Новые модели в v5.0

- **GameChallenge** — вызовы на PvP игры
- **UserBalance** — баланс пользователей для игр

---

## 📊 Мониторинг

### Метрики

```bash
METRICS_ENABLED=true
METRICS_PORT=9090

curl http://localhost:9090/metrics
curl http://localhost:9090/health
```

### Grafana

```bash
# Открой http://localhost:3000
# Login: admin / admin
```

---

## 🧪 Тестирование

```bash
# Все тесты
pytest

# Property-based тесты (46 тестов)
pytest tests/property/ -v

# Unit тесты
pytest tests/unit/ -v

# С покрытием
pytest --cov=app
```

---

## 🐛 Troubleshooting

### "No module named 'aiogram'"
```bash
pip install -r requirements.txt
```

### "TELEGRAM_BOT_TOKEN must be set"
```bash
cat .env | grep TELEGRAM_BOT_TOKEN
```

### "Ollama connection failed"
```bash
curl http://localhost:11434/api/tags
ollama serve
```

### "ffmpeg not found"
```bash
# Установи ffmpeg
choco install ffmpeg  # Windows
apt install ffmpeg    # Linux
brew install ffmpeg   # Mac
```

### "Vision returns empty"
Cloud-модели могут не поддерживать изображения. Попробуй локальную:
```bash
ollama pull llava:7b
# И в .env: OLLAMA_VISION_MODEL=llava:7b
```

### Docker: "Cannot connect to host.docker.internal"
```bash
# Linux: добавь в docker-compose.yml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### "Think tags in response"
Проверь что ThinkTagFilter интегрирован в ollama_client.py

---

## 📁 Структура проекта

```
oleg-bot/
├── app/
│   ├── handlers/          # Обработчики команд
│   │   ├── qna.py         # Q&A
│   │   ├── vision.py      # Изображения
│   │   ├── voice.py       # Голосовые
│   │   ├── games.py       # Игры
│   │   ├── challenges.py  # PvP вызовы
│   │   ├── admin_dashboard.py  # Админка
│   │   ├── health.py      # /ping
│   │   └── topic_listener.py   # Cross-topic
│   ├── services/          # Бизнес-логика
│   │   ├── ollama_client.py
│   │   ├── think_filter.py     # Think tags
│   │   ├── vision_pipeline.py  # 2-step vision
│   │   ├── auto_reply.py       # Авто-ответы
│   │   ├── game_engine.py      # Игровой движок
│   │   ├── voice_recognition.py
│   │   ├── redis_client.py
│   │   └── vector_db.py        # RAG
│   ├── middleware/        # Rate limit, spam
│   ├── database/          # Модели SQLAlchemy
│   └── main.py
├── tests/
│   ├── property/          # Property-based тесты
│   ├── unit/              # Unit тесты
│   └── integration/       # Integration тесты
├── monitoring/
├── migrations/
├── docker-compose.yml
└── requirements.txt
```

---

## 📚 Следующие шаги

1. [QUICKSTART.md](QUICKSTART.md) — Быстрый старт
2. [TESTING.md](TESTING.md) — Тестирование
3. [CHANGELOG.md](CHANGELOG.md) — История изменений

---

**Удачи с Олегом! 🤖**
