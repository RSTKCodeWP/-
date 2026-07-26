# ✅ Проверка — Олег 5.0

Команды для проверки всех компонентов v5.0.

---

## 1. Property-Based тесты (46 тестов)

```bash
pytest tests/property/ -v
```

**Ожидаемый результат:** 46 passed

---

## 2. Проверка новых компонентов

```bash
# Think Filter
python -c "from app.services.think_filter import ThinkTagFilter; print('✓ Think Filter OK')"

# Vision Pipeline
python -c "from app.services.vision_pipeline import VisionPipeline; print('✓ Vision Pipeline OK')"

# Auto-Reply
python -c "from app.services.auto_reply import AutoReplySystem; print('✓ Auto-Reply OK')"

# Game Engine
python -c "from app.services.game_engine import GameEngine; print('✓ Game Engine OK')"
```

---

## 3. Проверка handlers

```bash
python -c "from app.handlers.admin_dashboard import router; print('✓ Admin Dashboard OK')"
python -c "from app.handlers.health import router; print('✓ Health OK')"
python -c "from app.handlers.challenges import router; print('✓ Challenges OK')"
python -c "from app.handlers.topic_listener import router; print('✓ Topic Listener OK')"
```

---

## 4. Проверка миграций

```bash
alembic current
alembic upgrade head
```

---

## 5. Проверка Docker

```bash
docker-compose config
docker build -t oleg-bot:test .
```

---

## 6. Полная проверка

```bash
# Все тесты
pytest

# Линтинг
make lint

# Форматирование
make format
```

---

## Чеклист v5.0

- [x] Think Tag Filter
- [x] 2-Step Vision Pipeline
- [x] Cross-Topic Perception
- [x] Auto-Reply System
- [x] Owner Dashboard
- [x] PvP Games with Consent
- [x] Russian Roulette
- [x] Coin Flip
- [x] Enhanced /ping
- [x] Video Notes
- [x] Media Download
- [x] Property-Based Testing (46 тестов)
- [x] Database migrations

**Проект готов! 🚀**
