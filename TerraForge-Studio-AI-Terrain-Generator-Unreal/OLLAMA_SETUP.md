# Установка Qwen3-VL и Qwen3-Coder в Ollama

## 1. Установка Ollama

```bash
# Windows
winget install Ollama.Ollama

# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh
```

## 2. Загрузка моделей (Ollama Cloud)

```bash
# Qwen3-VL Cloud (235B параметров)
# Работает через Ollama Cloud API - не требует локальной загрузки
ollama pull qwen3-vl:235b-cloud

# Qwen3-Coder Cloud (480B параметров)
# Работает через Ollama Cloud API - не требует локальной загрузки
ollama pull qwen3-coder:480b-cloud
```

**✨ Cloud модели:**
- Не занимают место на диске
- Работают через Ollama Cloud API
- Требуют интернет-соединения
- Бесплатные для разработки

## 3. Проверка установки

```bash
# Список установленных моделей
ollama list

# Тест Qwen3-VL
ollama run qwen3-vl:235b-cloud "Что ты видишь на этом изображении?"

# Тест Qwen3-Coder
ollama run qwen3-coder:480b-cloud "Напиши Python функцию для генерации terrain"
```

## 4. Конфигурация Ollama

Создайте файл `~/.ollama/config.json`:

```json
{
  "gpu_layers": 35,
  "num_threads": 8,
  "num_gpu": 1,
  "low_vram": false
}
```

## 5. Запуск Ollama Server

```bash
# Запустить сервер (по умолчанию на :11434)
ollama serve

# Или с кастомным портом
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

## 6. Проверка в TerraForge

```bash
# Перейти в backend
cd realworldmapgen

# Активировать venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Тест Qwen3-VL
python ai/qwen_vision_ollama.py

# Тест Qwen3-Coder
python ai/qwen_coder_ollama.py
```

## 7. Интеграция в API

Backend автоматически определит доступность моделей при старте:

```bash
# Запустить backend
python -m uvicorn realworldmapgen.main:app --reload --port 8000
```

Проверь в логах:
```
INFO: Qwen3-VL (235b-cloud) доступен: True
INFO: Qwen3-Coder (480b-cloud) доступен: True
```

## 8. Системные требования

### Для Cloud моделей (qwen3-vl:235b-cloud, qwen3-coder:480b-cloud):
- **GPU:** Не требуется (работает через облако)
- **RAM:** 8GB+ (только для локального кода)
- **Диск:** Минимально (без загрузки моделей)
- **Интернет:** Стабильное соединение (обязательно)

## 9. Использование в TerraForge

### Frontend (AI кнопка):

1. Выберите область на карте
2. Нажмите **"Analyze Terrain"** (AI кнопка)
3. Ждите анализ (~30-60 сек через Ollama Cloud)
4. Получите рекомендации и оптимальную конфигурацию

### Backend API:

```python
# POST /api/ai/analyze-vision
{
  "bbox": {
    "north": 55.8,
    "south": 55.7,
    "east": 37.7,
    "west": 37.5
  }
}

# Response:
{
  "terrain_type": "urban",
  "vegetation": {"density": 20, "type": "parks"},
  "buildings": {"present": true, "density": "high"},
  "recommended_resolution": 4096,
  "quality_prediction": 92
}
```

```python
# POST /api/ai/generate-config
{
  "vision_analysis": {...},
  "user_preferences": {
    "resolution": 2048,
    "enable_roads": true
  }
}

# Response:
{
  "config": {
    "resolution": 2048,
    "elevation": {...},
    "vegetation": {...},
    "roads": {"enabled": true, "width": 6},
    ...
  }
}
```

## 10. Troubleshooting

### Модель не загружается:
```bash
# Очистить кэш
ollama rm qwen3-vl:235b-cloud
ollama pull qwen3-vl:235b-cloud
```

### Out of Memory:
```bash
# Использовать CPU (медленно)
OLLAMA_NUM_GPU=0 ollama serve

# Или уменьшить контекст
ollama run qwen3-vl:235b-cloud --num-ctx 2048
```

### Ollama не отвечает:
```bash
# Перезапустить сервер
pkill ollama
ollama serve
```

## Готово! 🚀

Теперь TerraForge может:
- Анализировать спутниковые снимки
- Генерировать умные конфигурации
- Создавать скрипты для Unreal/Unity
