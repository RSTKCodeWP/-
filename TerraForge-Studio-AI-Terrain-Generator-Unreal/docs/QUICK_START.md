# 🚀 Руководство по быстрому старту / Quick Start Guide

## Системные требования / System Requirements

- **Python** 3.10+ или выше / or higher
- **Node.js** 18+ или выше / or higher  
- **Rust** (для Tauri / for Tauri)
- **Windows** 10/11 (Linux/macOS поддерживаются / supported)

---

## Установка / Installation

### 1. Backend Setup / Настройка бэкенда

```powershell
cd TerraForge-Studio

# Активировать виртуальное окружение / Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Установить зависимости (если нужно) / Install dependencies (if needed)
pip install -r requirements.txt

# Запустить backend / Start backend
python -m uvicorn realworldmapgen.api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend запущен на / runs at: `http://localhost:8000`

### 2. Frontend Setup / Настройка фронтенда

```powershell
cd frontend-new

# Установить зависимости / Install dependencies
npm install

# Собрать production build / Build for production
npm run build

# Запустить Tauri / Start Tauri
npm run tauri:dev
```

Десктопное приложение откроется автоматически / Desktop app will open automatically

---

## Первое использование / First Use

### 1. Выбор области / Select Area

1. Откройте **2D Map Selector** / Open **2D Map Selector**
2. Выберите тип карты / Choose map type:
   - **OSM** - OpenStreetMap
   - **Satellite** - Спутниковые снимки / Satellite imagery
   - **Hybrid** - Спутник + названия / Satellite + labels
   - **Topographic** - Топографическая / Topographic
3. Используйте инструмент / Use tool:
   - **Rectangle** - прямоугольник / rectangle
   - **Polygon** - многоугольник / polygon
4. Нарисуйте область на карте / Draw area on map
5. Выделение сохранится автоматически! / Selection is saved automatically!

### 2. Настройка экспорта / Configure Export

1. **Export Configuration** панель справа / panel on the right
2. **Terrain Name** - название местности / terrain name
3. **Heightmap Resolution** - разрешение карты высот / heightmap resolution:
   - **1009, 2017, 4033** - Unreal Engine 5
   - **513, 1025, 2049** - Unity
   - **2048, 4096** - Универсальные / Universal
4. **Export Formats** - выберите форматы / choose formats:
   - ✅ Unreal Engine 5
   - ✅ Unity
   - ✅ GLTF
   - ✅ GeoTIFF

### 3. Генерация / Generation

1. Нажмите / Click **"Generate Terrain"**
2. Следите за прогрессом в реальном времени / Monitor progress in real-time
3. После завершения скачайте архив / After completion, download archive
4. Импортируйте в ваш движок! / Import to your game engine!

---

## Настройки (опционально) / Settings (optional)

### Data Sources / Источники данных

Settings → Data Sources → настройте API keys / configure API keys:
- SentinelHub
- OpenTopography
- Azure Maps
- Google Earth Engine

### AI Assistant / AI Ассистент (опционально / optional)

1. Установите / Install Ollama: https://ollama.ai
2. Запустите / Start: `ollama serve`
3. Установите модели / Install models:
   ```bash
   ollama pull qwen3-vl:235b-cloud
   ollama pull qwen3-coder:480b-cloud
   ```
4. Settings → AI Assistant → Enable → Save
5. Страница перезагрузится / Page will reload
6. Чекбокс "Use AI" появится в Export Panel / "Use AI" checkbox will appear in Export Panel

Подробнее / More info: [OLLAMA_SETUP.md](../OLLAMA_SETUP.md)

---

## Следующие шаги / Next Steps

- [Руководство пользователя / User Guide](USER_GUIDE.md)
- [Настройки / Settings Guide](SETTINGS_GUIDE.md)
- [API документация / API Documentation](API_SPECIFICATION.md)
- [Экспорт для движков / Exporters Guide](EXPORTERS_GUIDE.md)

---

**Вот и всё! / That's it!** Вы готовы создавать красивые ландшафты! / You're ready to generate beautiful terrains! 🌍✨
