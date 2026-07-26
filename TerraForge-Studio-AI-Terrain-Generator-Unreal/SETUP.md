# TerraForge Studio - Руководство по установке / Setup Guide

> 📘 Также смотрите / Also see: [README.md](README.md) для общей информации о проекте / for general project information

## Архитектура / Architecture

- **Frontend:** React + TypeScript + Vite
- **Backend:** FastAPI + Python
- **Desktop:** Tauri
- **Map:** Leaflet + Cesium

---

## 🚀 Быстрый старт

### 1. Backend (FastAPI)

```powershell
cd F:\Projects\TerraForge-Studio
.venv\Scripts\activate
python -m uvicorn realworldmapgen.api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend будет доступен: http://localhost:8000

### 2. Frontend (React + Tauri)

```powershell
cd frontend-new
npm run build
npm run tauri:dev
```

---

## 📦 Требования / Requirements

### Backend / Бэкенд
- Python 3.10+
- Virtual environment (.venv) / Виртуальное окружение
- Dependencies / Зависимости: `pip install -r requirements.txt`

### Frontend / Фронтенд
- Node.js 18+
- npm
- Rust (для Tauri / for Tauri)

---

## ⚙️ Конфигурация / Configuration

### Настройки хранятся в / Settings are stored in:
- Backend / Бэкенд: `~/.terraforge/settings.json`
- Frontend / Фронтенд: localStorage в браузере / in browser

### Ключевые настройки / Key settings:
- **AI Ассистент / AI Assistant:** Settings → AI Assistant → Enable
- **Источники данных / Data Sources:** Settings → Data Sources (API keys)
- **Профили экспорта / Export Profiles:** Settings → Export Profiles (UE5/Unity/Generic)

---

## 🤖 AI интеграция / AI Integration (опционально / optional)

Для AI функций требуется Ollama / Ollama is required for AI features:

1. Установить / Install Ollama: https://ollama.ai
2. Запустить / Start: `ollama serve`
3. Установить модели / Install models:
   ```bash
   ollama pull qwen3-vl:235b-cloud
   ollama pull qwen3-coder:480b-cloud
   ```
4. Settings → AI Assistant → Enable → Save

Подробнее / More info: [OLLAMA_SETUP.md](OLLAMA_SETUP.md)

---

## 🗺️ Использование / Usage

### Выбор области / Select Area:
1. Откройте карту (2D Map Selector) / Open map (2D Map Selector)
2. Выберите инструмент Rectangle или Polygon / Choose Rectangle or Polygon tool
3. Нарисуйте область на карте / Draw area on map
4. Выделение сохраняется автоматически / Selection is saved automatically

### Генерация / Generation:
1. Export Configuration → настройте параметры / configure parameters
2. Выберите формат (UE5/Unity/GLTF/GeoTIFF) / Choose format
3. Generate Terrain
4. Скачайте результат / Download result

---

## 🐛 Решение проблем / Troubleshooting

### Tauri кэширует старый билд / Tauri caches old build:
```powershell
cd frontend-new
Remove-Item -Recurse -Force src-tauri\target
Remove-Item -Recurse -Force dist
npm run build
npm run tauri:dev
```

### AI настройки не применяются / AI settings not applying:
- После сохранения AI настроек страница перезагружается автоматически / Page reloads automatically after saving AI settings
- Проверьте Console (F12): должно быть / Check Console (F12): should show `AI enabled: true/false`

### Backend ошибки / Backend errors:
- Проверьте что backend запущен на порту 8000 / Check that backend is running on port 8000
- Проверьте логи в консоли / Check console logs

---

## 📁 Структура проекта / Project Structure

```
TerraForge-Studio/
├── frontend-new/          # React + Tauri frontend / Фронтенд
│   ├── src/
│   │   ├── components/    # UI компоненты / UI components
│   │   ├── services/      # API клиенты / API clients
│   │   └── i18n/          # Локализация (en/ru) / Localization
│   └── src-tauri/         # Tauri desktop wrapper / Десктоп обертка
├── realworldmapgen/       # FastAPI backend / Бэкенд
│   ├── api/               # API routes / API маршруты
│   ├── core/              # Бизнес логика / Business logic
│   ├── ai/                # AI интеграция / AI integration
│   └── settings/          # Settings manager / Менеджер настроек
└── docs/                  # Документация / Documentation
```

---

## 🔧 Разработка / Development

### Frontend Dev Server (без Tauri / without Tauri):
```powershell
cd frontend-new
npm run dev
```
Откройте / Open http://localhost:5173

### Build Production / Продакшн сборка:
```powershell
cd frontend-new
npm run tauri:build
```

---

## 🔨 Сборка релизов / Building Releases

Смотрите полное руководство / See complete guide: **[BUILD.md](BUILD.md)**

- Автоматическая сборка для Windows/Linux/macOS / Automated builds for Windows/Linux/macOS
- GitHub Actions для релизов / GitHub Actions for releases
- Скрипты локальной сборки / Local build scripts
