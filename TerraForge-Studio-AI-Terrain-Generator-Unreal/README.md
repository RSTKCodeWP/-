# 🌍 TerraForge Studio

**Professional 3D Terrain Generator for Game Engines**

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/react-18+-61DAFB.svg)](https://react.dev)
[![Tauri](https://img.shields.io/badge/tauri-2.0+-FFC131.svg)](https://tauri.app)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Создавайте реалистичные 3D ландшафты на основе реальных геоданных для Unreal Engine 5, Unity и других игровых движков.

![TerraForge Studio](docs/images/screenshot.png)

---

## ✨ Возможности

### 🗺️ Картографирование
- **Интерактивная 2D карта** - Leaflet с поддержкой OSM, спутниковых снимков, гибридного режима
- **3D превью** - Cesium для предпросмотра рельефа в реальном времени
- **Выделение областей** - Rectangle/Polygon инструменты с сохранением между сеансами
- **Типы карт** - OpenStreetMap, Satellite, Hybrid (спутник + названия), Topographic

### 🎮 Экспорт для движков
- **Unreal Engine 5** - оптимизированные landscape (1009, 2017, 4033, 8129)
- **Unity** - terrain heightmaps (513, 1025, 2049, 4097)
- **GLTF 2.0** - универсальный 3D формат
- **GeoTIFF** - для GIS и картографических приложений

### 🏔️ Реальные данные высот / Real elevation data
- **Работает без API-ключей** - источник SRTM на базе открытых Terrain Tiles (AWS Open Data) включён по умолчанию
- **Глобальное покрытие** - SRTM, ASTER, NED, GMTED; высоты в метрах над уровнем моря
- **Точная привязка** - тайлы Web Mercator подбираются по разрешению, склеиваются и обрезаются ровно по запрошенному bbox
- **Кэш тайлов на диске** - повторные генерации в той же области не ходят в сеть
- **Честная провенанс-метка** - ответ API всегда сообщает, из какого источника пришли высоты и не является ли рельеф синтетическим

### 🤖 AI Интеграция (опционально)
- **Qwen3-VL** - анализ местности по спутниковым снимкам
- **Qwen3-Coder** - умная генерация конфигураций
- **Ollama** - локальный запуск моделей через cloud API
- **Автоанализ** - опциональный автоматический анализ при выборе области

### 🛣️ Дороги и здания
- **Работает без ключей и без тяжёлых зависимостей** - Overpass API поверх обычного HTTP
- **Резервные серверы** - цепочка зеркал с ретраями на 429/504
- **GeoJSON на выходе** - `vectors.geojson` рядом с ландшафтом, попадает в zip
- **Атрибуты OSM** - полосы, скоростной режим, покрытие, односторонность, этажность зданий

### 🔌 API и интеграция
- **Вебхуки** - события `generation.started/completed/failed` с подписью HMAC-SHA256 по точным байтам тела
- **Rate limiting** - лимиты на минуту/час/сутки, health-пробы и метрики не throttling'уются
- **Пробы для k8s** - `/health/live`, `/health/ready` (проверяет запись на диск и доступность источника), `/metrics` для Prometheus
- **WebSocket** - живой прогресс генерации

### 🔐 Учётные записи и секреты / Accounts and secrets
- **Пароли** - PBKDF2-HMAC-SHA256, случайная соль на пользователя, 260 000 итераций; старые SHA-256 хеши принимаются и перехешируются при входе
- **Роли** - `role` меняет только администратор, в том числе для собственной учётной записи
- **Хранилище** - `AUTH_STORAGE_FILE` вне каталога кеша: очистка кеша не удаляет учётные записи
- **Ключи API** - шифруются Fernet, ключ генерируется случайно при первом запуске (`SECRET_KEY_FILE`, права `0600`)

### ⚙️ Настройки и управление
- **Data Sources** - SRTM (бесплатно, без ключа) + SentinelHub, OpenTopography, Azure Maps, Google Earth Engine
- **Export Profiles** - настраиваемые профили для разных движков
- **Локализация** - полная поддержка English/Русский
- **Темы** - Light/Dark/Auto режимы  

---

## 🚀 Быстрый старт / Quick Start

### Требования / Requirements
- Python 3.10+
- Node.js 18+
- Rust (только для сборки Tauri / only for the Tauri desktop build)

### 1. Backend (FastAPI)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
uvicorn realworldmapgen.api.main:app --reload --port 8000
```

Ключи API не нужны: свободный источник высот SRTM включён по умолчанию.  
No API keys required - the free SRTM elevation source is enabled by default.

Опциональные возможности (GLTF/GeoTIFF, данные OSM, премиум-провайдеры, AI):  
Optional capabilities (GLTF/GeoTIFF export, OSM vector data, premium providers, AI):

```bash
pip install -r requirements-optional.txt
```

### 2. Frontend (React + Vite)

```bash
cd frontend-new
npm install
npm run dev          # http://localhost:5173
```

### 3. Desktop (Tauri)

```bash
cd frontend-new
npm run tauri:dev
```

### 4. Конфигурация / Configuration

```bash
cp .env.example .env    # все ключи опциональны / every key is optional
```

**Смотрите [Руководство по быстрому старту](docs/QUICK_START.md) для подробных инструкций.**  
**See [Quick Start Guide](docs/QUICK_START.md) for detailed instructions.**

---

## 🧪 Разработка / Development

```bash
# Backend: линтер и тесты / linter and tests
pip install -r requirements-dev.txt
ruff check realworldmapgen cli tests
pytest

# Тесты, требующие сети (проверка реального источника высот)
# Network-dependent tests (verify the live elevation source)
pytest -m network

# Frontend
cd frontend-new
npm run lint && npm run type-check && npm run test -- --run && npm run build
```

---

## 📚 Документация / Documentation

- **[Быстрый старт / Quick Start](docs/QUICK_START.md)** - Начните работу за 5 минут / Get running in 5 minutes
- **[Руководство по сборке / Build Guide](BUILD.md)** - Сборка .exe и бинарников / Building .exe and binaries
- **[Спецификация API / API Specification](docs/API_SPECIFICATION.md)** - Полная документация REST API / Complete REST API docs
- **[Руководство по развертыванию / Deployment Guide](docs/DEPLOYMENT.md)** - Production развертывание / Production deployment
- **[Руководство по экспортерам / Exporters Guide](docs/EXPORTERS_GUIDE.md)** - Интеграция с игровыми движками / Game engine integration
- **[Полная документация / Full Documentation](docs/README.md)** - Индекс всей документации / Complete documentation index

---

## 🎯 Технологический стек / Technology Stack

**Frontend / Фронтенд**: React 18 + TypeScript + Vite + TailwindCSS  
**Backend / Бэкенд**: FastAPI (Python 3.10+) + Pydantic  
**Maps / Карты**: Leaflet + Cesium  
**Desktop / Десктоп**: Tauri 2.0  
**AI / ИИ**: Ollama + Qwen3 models (опционально / optional)

---

## 🎮 Форматы экспорта / Export Formats

- **Unreal Engine 5** - PNG landscape (1009, 2017, 4033, 8129)
- **Unity** - RAW heightmap (513, 1025, 2049, 4097)
- **GLTF 2.0** - Универсальный 3D формат / Universal 3D format
- **GeoTIFF** - Для GIS приложений / For GIS applications

---

## 🗻 Источники высот / Elevation sources

| Источник / Source | Ключ / API key | Покрытие / Coverage | Разрешение / Resolution |
|---|---|---|---|
| **SRTM (Open Terrain Tiles)** | не нужен / none | глобальное / global | 30-90 м |
| OpenTopography | требуется / required | LiDAR по регионам + глобальный SRTM/ASTER | 0.5-30 м |
| Azure Maps | требуется / required | глобальное / global | переменное / varies |

По умолчанию используется SRTM. При `elevation_source: "auto"` источники перебираются
в порядке `ELEVATION_SOURCE_PRIORITY`, а SRTM всегда остаётся последним запасным вариантом.

SRTM is used by default. With `elevation_source: "auto"` the sources are tried in
`ELEVATION_SOURCE_PRIORITY` order, with SRTM always kept as the final fallback.

Каждый ответ содержит поле `result.elevation`, где указан фактический источник и флаг
`synthetic` — если все источники недоступны и включён процедурный запасной вариант,
это будет явно видно в ответе и в предупреждениях задачи.

Every response carries `result.elevation` naming the source that actually supplied the
data, plus a `synthetic` flag - if all sources failed and the procedural fallback kicked
in, the response and the task warnings say so explicitly.

Данные высот предоставлены [AWS Open Data Terrain Tiles](https://registry.opendata.aws/terrain-tiles/)
(SRTM / ASTER / NED / GMTED).

---

## 🎯 Использование / Usage

### 1. Выбор области / Select Area
1. Откройте 2D Map Selector / Open 2D Map Selector
2. Выберите тип карты (OSM/Satellite/Hybrid) / Choose map type
3. Используйте Rectangle или Polygon / Use Rectangle or Polygon tool
4. Нарисуйте область на карте / Draw area on map
5. Выделение сохраняется автоматически / Selection is saved automatically

### 2. Настройка экспорта / Configure Export
1. Export Configuration → параметры / parameters
2. Выберите формат (UE5/Unity/GLTF) / Choose format
3. Настройте разрешение / Set resolution
4. Включите нужные features / Enable features

### 3. Генерация / Generation
1. Нажмите Generate Terrain / Click Generate Terrain
2. Следите за прогрессом / Monitor progress
3. Скачайте результат / Download result  

---

## 🤖 AI Ассистент / AI Assistant (опционально / optional)

Для использования AI функций / To use AI features:

1. Установите Ollama / Install Ollama: https://ollama.ai
2. Запустите сервер / Start server: `ollama serve`
3. Установите модели / Install models:
   ```bash
   ollama pull qwen3-vl:235b-cloud
   ollama pull qwen3-coder:480b-cloud
   ```
4. Settings → AI Assistant → Enable → Save
5. Страница перезагрузится автоматически / Page will reload automatically

Подробнее / More info: [OLLAMA_SETUP.md](OLLAMA_SETUP.md)

---

## 🤝 Участие в разработке / Contributing

Мы приветствуем вклад в проект! / We welcome contributions!  
Смотрите / See [CONTRIBUTING.md](docs/CONTRIBUTING.md) для руководства / for guidelines.

```bash
git clone https://github.com/your-username/terraforge-studio.git
git checkout -b feature/amazing-feature
git commit -m "Add amazing feature"
git push origin feature/amazing-feature
```

---

## 📄 Лицензия / License

MIT License - смотрите / see [LICENSE](LICENSE) для деталей / for details.

---

## 📞 Поддержка / Support

- **Документация / Documentation**: [docs/](docs/README.md)
- **Проблемы / Issues**: https://github.com/terraforge/studio/issues

---

<div align="center">

**Сделано с ❤️ bobberdolle 1**  
**Built with ❤️ by bobberdolle1**

• [Документация / Docs](docs/README.md) • [API](docs/API_SPECIFICATION.md) • 

</div>
