# 🧪 Тестирование — Олег 4.5

> Тесты для уверенности в коде

---

## ⚡ Быстрый запуск

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Подробный вывод
pytest -v
```

---

## 📁 Структура тестов

```
tests/
├── conftest.py              # Фикстуры
├── unit/                    # Unit тесты
│   ├── test_rate_limiter.py
│   ├── test_redis_client.py
│   ├── test_config.py
│   ├── test_utils.py
│   ├── test_metrics.py
│   └── test_ollama_fallback.py
└── integration/             # Integration тесты
    └── test_database.py
```

---

## 🎯 Запуск по категориям

```bash
# Только unit
pytest tests/unit/

# Только integration
pytest tests/integration/

# Конкретный файл
pytest tests/unit/test_rate_limiter.py

# Тесты с "redis" в имени
pytest -k "redis"
```

---

## 🔧 Полезные флаги

```bash
pytest -v              # Подробный вывод
pytest -s              # Показать print()
pytest -x              # Остановиться на первой ошибке
pytest --pdb           # Отладчик при ошибке
pytest -m "not slow"   # Пропустить медленные
```

---

## 📈 Покрытие кода

```bash
# HTML отчет
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Terminal
pytest --cov=app --cov-report=term-missing
```

---

## ✍️ Написание тестов

### Unit тест

```python
def test_my_function():
    result = my_function(42)
    assert result == 84
```

### Async тест

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

### С моками

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    with patch('app.services.ollama_client._ollama_chat') as mock:
        mock.return_value = "Mocked"
        result = await generate_reply("test")
        assert result == "Mocked"
```

---

## 🐛 Отладка

```bash
pytest --pdb           # Отладчик
pytest --tb=long       # Полный traceback
pytest -x --pdb        # Остановка + отладчик
```

---

## 📝 Best Practices

1. **Именование**: `test_<что>_<ожидание>`
2. **AAA паттерн**: Arrange → Act → Assert
3. **Изоляция**: Каждый тест независим
4. **Моки**: Для внешних зависимостей

---

## ❓ FAQ

**Q: "No module named 'app'"**
```bash
cd oleg-bot && pytest
```

**Q: Как пропустить медленные?**
```bash
pytest -m "not slow"
```

---

**Версия:** 4.5.0
