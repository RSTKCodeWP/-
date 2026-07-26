# Интеграция Qwen3-VL и Qwen3-Coder для генерации местности

## Текущая реализация (Ollama)
- Использует простую LLM для анализа координат
- Файл: `realworldmapgen/ai/ollama_client.py`
- Возможности: текстовый анализ, рекомендации параметров

## Улучшение с Qwen3-VL + Qwen3-Coder

### 1. **Qwen3-VL (Vision-Language)**
Анализирует спутниковые снимки выбранной области:

**Задачи:**
- Распознавание типа местности (горы, лес, город, вода)
- Определение растительности, зданий, дорог
- Оценка рельефа по теням
- Детектирование особенностей (реки, озера, скалы)

**Интеграция:**
```python
# realworldmapgen/ai/qwen_vision.py
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

class QwenVisionAnalyzer:
    def __init__(self):
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen2-VL-7B-Instruct",
            device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")
    
    async def analyze_satellite_image(self, bbox, satellite_image_url):
        """Анализирует спутниковое изображение выбранной области"""
        
        # Загрузить спутниковый снимок (Sentinel, Google Earth)
        image = await self.fetch_satellite_image(bbox, satellite_image_url)
        
        prompt = """Проанализируй этот спутниковый снимок местности.
        Определи:
        1. Тип местности (горы/равнина/лес/город/вода)
        2. Наличие растительности (тип, плотность)
        3. Наличие строений (города, деревни)
        4. Дороги и инфраструктура
        5. Водоемы (реки, озера)
        6. Рельеф (плоский/холмистый/горный)
        7. Оптимальное разрешение для генерации
        """
        
        inputs = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt"
        ).to(self.model.device)
        
        outputs = self.model.generate(**inputs, max_new_tokens=512)
        result = self.processor.decode(outputs[0], skip_special_tokens=True)
        
        return self.parse_analysis(result)
```

### 2. **Qwen3-Coder (Code Generation)**
Генерирует код конфигурации для процедурной генерации:

**Задачи:**
- Генерация Python скриптов для настройки параметров
- Создание процедурных правил для растительности
- Оптимизация pipeline генерации
- Генерация Unreal/Unity скриптов импорта

**Интеграция:**
```python
# realworldmapgen/ai/qwen_coder.py
from transformers import AutoModelForCausalLM, AutoTokenizer

class QwenCoderGenerator:
    def __init__(self):
        self.model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen2.5-Coder-7B-Instruct",
            device_map="auto"
        )
        self.tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct")
    
    async def generate_terrain_config(self, vision_analysis):
        """Генерирует оптимальную конфигурацию на основе анализа"""
        
        prompt = f"""На основе анализа местности создай оптимальную конфигурацию генерации:

Анализ местности: {vision_analysis}

Сгенерируй Python код для настройки параметров генерации:
- Разрешение heightmap
- Настройки эрозии
- Параметры растительности (типы, плотность, распределение)
- Настройки дорог (ширина, извилистость)
- Параметры зданий (стиль, размер)
- Weightmaps для текстур

Формат: Python dict с параметрами.
"""
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=1024)
        code = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Безопасное выполнение сгенерированного кода
        config = self.safe_eval_config(code)
        return config
    
    async def generate_unreal_import_script(self, terrain_data):
        """Генерирует Blueprint скрипт для Unreal Engine"""
        prompt = f"""Создай Blueprint Python скрипт для импорта местности в Unreal Engine 5:
        
Данные местности: {terrain_data}

Скрипт должен:
1. Импортировать heightmap как Landscape
2. Настроить материалы с weightmaps
3. Расставить vegetation (foliage)
4. Создать splines для дорог
5. Настроить освещение
"""
        # ... генерация скрипта
```

### 3. **Комбинированный pipeline**

```python
# realworldmapgen/ai/terrain_ai_pipeline.py

class TerrainAIPipeline:
    def __init__(self):
        self.vision = QwenVisionAnalyzer()
        self.coder = QwenCoderGenerator()
    
    async def generate_terrain_with_ai(self, bbox, user_preferences):
        # Шаг 1: Получить спутниковый снимок
        satellite_image = await self.fetch_satellite_image(bbox)
        
        # Шаг 2: Qwen3-VL анализирует изображение
        vision_analysis = await self.vision.analyze_satellite_image(bbox, satellite_image)
        
        # Шаг 3: Qwen3-Coder генерирует оптимальную конфигурацию
        optimal_config = await self.coder.generate_terrain_config(vision_analysis)
        
        # Шаг 4: Применяем пользовательские предпочтения
        final_config = self.merge_with_user_prefs(optimal_config, user_preferences)
        
        # Шаг 5: Генерируем местность
        terrain_result = await self.generate_terrain(bbox, final_config)
        
        # Шаг 6: Генерируем скрипты импорта для движков
        if user_preferences['export_engine'] == 'unreal5':
            import_script = await self.coder.generate_unreal_import_script(terrain_result)
        
        return {
            'terrain': terrain_result,
            'analysis': vision_analysis,
            'config': final_config,
            'import_script': import_script
        }
```

### 4. **API эндпоинты**

Добавь в `realworldmapgen/api/ai_routes.py`:

```python
@router.post("/ai/analyze-vision")
async def analyze_terrain_vision(bbox: BoundingBox):
    """Анализ местности с помощью Qwen3-VL"""
    pipeline = TerrainAIPipeline()
    analysis = await pipeline.vision.analyze_satellite_image(bbox, None)
    return analysis

@router.post("/ai/generate-with-ai")
async def generate_terrain_ai(request: TerrainGenerationRequest):
    """Полная генерация с AI (VL + Coder)"""
    pipeline = TerrainAIPipeline()
    result = await pipeline.generate_terrain_with_ai(
        request.bbox,
        request.user_preferences
    )
    return result
```

### 5. **Frontend интеграция**

В `AIAssistant.tsx` добавь новую кнопку:

```typescript
<button
  onClick={analyzeWithVision}
  className="px-4 py-2 bg-purple-600 text-white rounded-md"
>
  🔮 AI Vision Analysis (Qwen3-VL)
</button>
```

## Системные требования

**GPU:** 
- Минимум: RTX 3060 (12GB VRAM) для 7B моделей
- Рекомендуется: RTX 4090 (24GB VRAM) для комфортной работы

**RAM:** 32GB+

**Установка моделей:**
```bash
# Qwen3-VL
pip install transformers accelerate
huggingface-cli download Qwen/Qwen2-VL-7B-Instruct

# Qwen3-Coder
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct
```

## Преимущества

1. **Умный анализ**: Видит что реально на местности (леса, города, горы)
2. **Автоматическая настройка**: AI подбирает оптимальные параметры
3. **Процедурные правила**: Coder генерирует сложные распределения растительности
4. **Скрипты импорта**: Автоматическая генерация Blueprint/C# кода

## Альтернатива (облачная)

Если нет мощной GPU, можно использовать:
- **OpenAI GPT-4 Vision** (платно)
- **Google Gemini Vision** (бесплатно с лимитами)
- **Anthropic Claude 3.5 Sonnet** (платно)

```python
# Используй API вместо локальной модели
vision_result = await openai_vision_api.analyze(satellite_image)
```
