# Настройка голосовых сообщений (faster-whisper)

## Использование faster-whisper для локальной транскрибации

Для работы с голосовыми сообщениями используется **faster-whisper** - оптимизированная версия Whisper от OpenAI.

### Преимущества:
- ✅ В 4-5 раз быстрее оригинального Whisper
- ✅ Работает на CPU (не требует GPU)
- ✅ Меньше потребление памяти
- ✅ Поддержка Python 3.9+ (включая 3.14)
- ✅ Автоматическое скачивание моделей
- ✅ Docker-образ остаётся лёгким (~500 MB)

---

## Шаг 1: Установка faster-whisper

### 1.1 Установка через Poetry (рекомендуется)

```powershell
# В директории проекта
poetry run pip install faster-whisper
```

### 1.2 Или через pip напрямую

```powershell
pip install faster-whisper
```

### 1.3 Проверить установку

```powershell
python -c "from faster_whisper import WhisperModel; print('faster-whisper installed!')"
```

### Размеры моделей:

| Модель    | Размер | Скорость | Качество |
|-----------|--------|----------|----------|
| `tiny`    | ~75 MB | Очень быстро | Базовое |
| `base`    | ~145 MB | Быстро | Хорошее |
| `small`   | ~460 MB | Средне | Отличное |
| `medium`  | ~1.5 GB | Медленно | Превосходное |
| `large-v2`| ~2.9 GB | Очень медленно | Наилучшее |

**Рекомендация:** `tiny` для быстрой работы, `base` для баланса скорости и качества.

**Модели скачиваются автоматически** при первом использовании.

---

## Шаг 2: Настройка Docker (если используете)

Docker автоматически использует faster-whisper, установленный через pip.

**Важно:** faster-whisper должен быть установлен в виртуальном окружении проекта:

```bash
# Внутри контейнера или локально
poetry run pip install faster-whisper
```

Модели будут скачаны в `~/.cache/huggingface/` и переиспользоваться между запусками.

---

## Шаг 3: Выбор модели в боте

Модель настраивается в переменной окружения:

```bash
# .env
WHISPER_MODEL=tiny  # tiny, base, small, medium, large-v2
```

По умолчанию используется `tiny`.

**При первом запуске** модель скачается автоматически (~75 MB для tiny).

---

## Тестирование

### 1. Запустите бота:
```bash
docker-compose up -d
```

### 2. Отправьте голосовое сообщение боту

### 3. Проверьте логи:
```bash
docker-compose logs -f eft-helper-bot
```

Вы должны увидеть:
```
Loading Whisper model: base
Whisper model loaded successfully
Transcribing audio file: /tmp/eft_voice/...
Transcription successful: ...
```

---

## Устранение проблем

### Ошибка: "faster-whisper not installed"

**Решение:** Установите faster-whisper:
```powershell
poetry run pip install faster-whisper
```

### Ошибка компиляции numpy на Windows

**Решение:** Используйте предсобранные колёса:
```powershell
poetry run pip install faster-whisper
# Вместо poetry add (которое пытается собрать из исходников)
```

### Модель не скачивается

**Решение:** Проверьте интернет-соединение. Модели скачиваются с HuggingFace:
```powershell
# Проверка
python -c "from faster_whisper import WhisperModel; WhisperModel('tiny')"
```

### Медленная транскрипция

**Решение:** 
1. Используйте более лёгкую модель (`tiny` или `base`)
2. Убедитесь, что используется CPU (не GPU в Docker)

---

## Переключение модели

Чтобы изменить модель:

1. Обновить `.env`:
```bash
WHISPER_MODEL=base  # или small, medium, large-v2
```

2. Перезапустить бот:
```bash
# Локально
poetry run python start.py

# Или Docker
docker-compose restart eft-helper-bot
```

3. При первом запуске новая модель скачается автоматически.

---

## Примечания

- **Голосовые сообщения обрабатываются AI-ассистентом Никитой** - транскрибированный текст передаётся как обычное текстовое сообщение
- **Поддерживаются языки:** русский и английский
- **Автоопределение языка:** бот использует язык пользователя из настроек
- **Формат аудио:** Telegram OGG автоматически конвертируется FFmpeg

---

## Дополнительная информация

- faster-whisper GitHub: https://github.com/guillaumekln/faster-whisper
- Оригинальный Whisper: https://github.com/openai/whisper
- HuggingFace модели: https://huggingface.co/guillaumekln

---

## Сравнение с оригинальным Whisper

| Параметр | openai-whisper | faster-whisper |
|----------|----------------|----------------|
| Скорость | Базовая | 4-5x быстрее |
| Память | Высокая | Оптимизированная |
| Точность | Эталон | Идентичная |
| CPU/GPU | Оба | CPU оптимизирован |
| Python | 3.9-3.13 | 3.9+ (включая 3.14) |
