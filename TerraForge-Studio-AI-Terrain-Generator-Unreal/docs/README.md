# 📚 Документация TerraForge Studio / TerraForge Studio Documentation

Добро пожаловать в документацию TerraForge Studio! / Welcome to TerraForge Studio documentation!

## 🚀 Начало работы / Getting Started

- [Быстрый старт / Quick Start](QUICK_START.md) - Начните за 5 минут / Get started in 5 minutes
- [Руководство пользователя / User Guide](USER_GUIDE.md) - Полное руководство / Complete guide
- [Настройки / Settings Guide](SETTINGS_GUIDE.md) - Конфигурация системы / System configuration

## 🔧 Технические руководства / Technical Guides

- [Спецификация API / API Specification](API_SPECIFICATION.md) - REST API документация / REST API docs
- [Примеры API / API Examples](API_EXAMPLES.md) - Примеры использования / Usage examples
- [Экспортеры / Exporters Guide](EXPORTERS_GUIDE.md) - Экспорт для движков / Game engine export
- [AI интеграция / AI Integration](AI_INTEGRATION.md) - Интеграция с AI (Ollama/Qwen3)

## 📖 Дополнительно / Additional

- [Возможности / Features](FEATURES.md) - Полный список / Complete list
- [Развертывание / Deployment](DEPLOYMENT.md) - Production развертывание / Production deployment
- [Участие / Contributing](CONTRIBUTING.md) - Как помочь проекту / How to contribute
- [Roadmap](ROADMAP_v4.x.md) - План развития / Development plan

## 🏗️ Архитектура / Architecture

### Frontend / Фронтенд
- **React 18** + TypeScript + Vite
- **Leaflet** - 2D карты / 2D maps
- **Cesium** - 3D превью / 3D preview
- **Tauri 2.0** - Desktop wrapper / Десктоп обертка

### Backend / Бэкенд
- **FastAPI** - REST API
- **Python 3.10+** - Бизнес-логика / Business logic
- **Pydantic** - Валидация данных / Data validation

### Data Sources / Источники данных
- OpenStreetMap
- SRTM Elevation / Высоты SRTM
- OpenTopography
- SentinelHub (опционально / optional)
- Azure Maps (опционально / optional)
- Google Earth Engine (опционально / optional)

## 🤖 AI возможности / AI Features

- **Qwen3-VL** - Vision model для анализа местности / Vision model for terrain analysis
- **Qwen3-Coder** - Генерация конфигураций / Configuration generation
- **Ollama** - Локальный запуск моделей / Local model execution

## 📁 Структура проекта / Project Structure

```
TerraForge-Studio/
├── frontend-new/          # React frontend / Фронтенд
│   ├── src/
│   │   ├── components/    # UI компоненты / UI components
│   │   ├── services/      # API клиенты / API clients
│   │   ├── i18n/          # Локализация / Localization
│   │   └── types/         # TypeScript типы / TypeScript types
│   └── src-tauri/         # Tauri wrapper / Tauri обертка
│
├── realworldmapgen/       # Python backend / Бэкенд
│   ├── api/               # FastAPI routes / API маршруты
│   ├── core/              # Бизнес-логика / Business logic
│   ├── ai/                # AI интеграция / AI integration
│   ├── settings/          # Settings manager / Менеджер настроек
│   └── exporters/         # Export engines / Экспортеры
│
└── docs/                  # Документация / Documentation
```

## 🔗 Полезные ссылки / Useful Links

- [Главная / Main README](../README.md)
- [Установка / Setup Guide](../SETUP.md)
- [Ollama настройка / Ollama Setup](../OLLAMA_SETUP.md)
- [История изменений / Changelog](../CHANGELOG.md)

---

# TerraForge Studio Documentation

Complete documentation for TerraForge Studio v4.0.0

---


- **[Installation Guide](INSTALLATION.md)** - Setup and installation
- **[Quick Start](QUICK_START.md)** - Get up and running in 5 minutes
- **[Windows Setup](WINDOWS_SETUP.md)** - Windows-specific instructions

---

## 📖 Core Documentation
## 🔧 Configuration & Usage

### Settings & API Keys
- **[SETTINGS_GUIDE.md](SETTINGS_GUIDE.md)** - Complete settings management
  - Data source configuration
  - API key management (encrypted)
  - Export profiles
  - UI preferences
  - Cache management

### API Reference
- **[API_EXAMPLES.md](API_EXAMPLES.md)** - API usage examples
- **Swagger UI**: http://localhost:8000/docs (when running)
- **ReDoc**: http://localhost:8000/redoc (when running)

---

## 👨‍💻 Development

### Contributing
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development guidelines
  - Code style
  - Testing
  - Pull request process
  - Architecture overview

### Testing
```bash
# Run all tests
pytest tests/ -v

# Frontend tests
pytest tests/test_frontend.py -v

# API tests  
pytest tests/test_api_integration.py -v
```

---

## 📖 Documentation Structure

```
docs/
├── README.md              # This file - documentation index
├── QUICKSTART.md          # 5-minute quick start
├── RUN_INSTRUCTIONS.md    # Detailed running guide
├── SETTINGS_GUIDE.md      # Settings and API keys
├── INSTALLATION.md        # Installation guide
├── API_EXAMPLES.md        # API usage examples
└── CONTRIBUTING.md        # Development guide
```

---

## 🎯 Quick Navigation

### I want to...
- **Install and run** → [QUICKSTART.md](QUICKSTART.md)
- **Detailed setup** → [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md)
- **Configure API keys** → [SETTINGS_GUIDE.md](SETTINGS_GUIDE.md)
- **Use the API** → [API_EXAMPLES.md](API_EXAMPLES.md)
- **Contribute code** → [CONTRIBUTING.md](CONTRIBUTING.md)
- **Install from scratch** → [INSTALLATION.md](INSTALLATION.md)

---

## 🌍 Supported Formats

### Game Engines
- **Unreal Engine 5** - Landscape heightmaps + weightmaps
- **Unity** - Terrain heightmaps + splatmaps
- **Generic** - GLTF/GLB 3D meshes

### GIS Software
- **GeoTIFF** - Georeferenced rasters for QGIS, ArcGIS

### Data Sources
- **Free**: OpenStreetMap, SRTM
- **Premium**: Sentinel Hub, OpenTopography, Azure Maps

---

## 🔗 External Links

- **Main Repository**: [GitHub](https://github.com/your-org/terraforge-studio)
- **API Documentation**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

## 📞 Need Help?

1. **Check this documentation** - Most questions are answered here
2. **Try the quick start** - [QUICKSTART.md](QUICKSTART.md)
3. **Check troubleshooting** - [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md) → Troubleshooting
4. **Create an issue** - GitHub Issues
5. **Start a discussion** - GitHub Discussions

---

<div align="center">

# 📚 Complete Documentation

**Everything you need to use TerraForge Studio**

---

**[Quick Start](QUICKSTART.md)** • **[Settings](SETTINGS_GUIDE.md)** • **[API](API_EXAMPLES.md)**

</div>