# Argus

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [L-X-Yao/argus](https://github.com/L-X-Yao/argus) |
| Локальна тека | `fpv-library/repos/argus-Universal-web-based-ground-control-stati` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `link`, `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-17 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

[中文](README.zh.md) | **English**

> Universal web-based ground control station for MAVLink drones.

_З README.md, без переказу._

## Для чого

Universal web-based ground control station for MAVLink drones. Browser-native, 10 languages, ArduPilot production-tested, no install required.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `drone`, `fastapi`, `flight-controller`, `gcs`, `ground-control-station`, `mavlink`, `pwa`, `svelte`, `uav`, `webserial`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Universal web-based ground control station for MAVLink drones. Browser-native, 10 languages, ArduPilot production-tested, no install required.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `backend/`
- `CLAUDE.md`
- `components.json`
- `CONTRIBUTING.md`
- `Dockerfile`
- `docs/`
- `index.html`
- `LICENSE`
- `Makefile`
- `package-lock.json`
- `package.json`
- `public/`
- `pyproject.toml`
- `README.md`
- `README.zh.md`
- `run.py`
- `scripts/`
- `SECURITY.md`
- `src/`
- `src-tauri/`
- `tests/`
- `tsconfig.json`
- `vite.config.ts`

Типи файлів за вибіркою (356 файлів, глибина до 3): TypeScript (106), Python (100), .svelte (78), Markdown (26), JSON (10), .png (9).

Фрагмент README про будову:

### Architecture

```
+------------------------------------------+
|  Browser (Svelte 5 + TypeScript 6)       |
|  78 components + 159 libs, 22K lines     |
|  MAVLink v2 codec (pure TS)              |
|  WebSerial direct USB connection         |
|  43 lazy-loaded panels + view splitting  |
+------------------------------------------+
|          WebSocket (JSON delta push)     |
+------------------------------------------+
|  Python Backend (FastAPI + uvicorn)      |
|  29 modules, 4.9K lines                 |
|  MAVLink dispatch + 32 message handlers  |
|  51 commands, tile/video/firmware API    |
+------------------------------------------+
|          MAVLink v2                      |
|  TCP / UDP / Serial / PL-Link           |
+------------------------------------------+
|  Flight Controller (ArduPilot / PX4)     |
+------------------------------------------+
```

## Що треба

- Маніфести збірки: Node.js (package.json), Python (pyproject.toml), Make.
- npm-скрипти в package.json: `dev`, `build`, `preview`, `check`, `test`, `test:e2e`, `lint:py`, `lint:ts`, `format`, `format:check`.
- dependencies: `@tailwindcss/vite`, `bits-ui`, `clsx`, `leaflet`, `maplibre-gl`, `tailwind-merge`, `tailwindcss`.
- pyproject name: `argus-gcs`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

One-time setup:

```bash
npm install        # Frontend dependencies
pip install -e .   # Backend (uses pyproject.toml — pulls all required deps)
```

> **Windows / recent Node note**: Node ≥17 may resolve `localhost` to IPv6 `::1`, while the backend binds IPv4-only `127.0.0.1` — use `127.0.0.1` in dev URLs.

## Супутні документи в теці

- [`docs/DEV_WORKFLOW.md`](../../fpv-library/repos/argus-Universal-web-based-ground-control-stati/docs/DEV_WORKFLOW.md)
- [`docs/FEATURE_CHECKLIST.md`](../../fpv-library/repos/argus-Universal-web-based-ground-control-stati/docs/FEATURE_CHECKLIST.md)
- [`docs/MIGRATION_TO_WSL.md`](../../fpv-library/repos/argus-Universal-web-based-ground-control-stati/docs/MIGRATION_TO_WSL.md)
- [`docs/PANEL_REALITY_MAP.md`](../../fpv-library/repos/argus-Universal-web-based-ground-control-stati/docs/PANEL_REALITY_MAP.md)
- [`docs/protocol_design.md`](../../fpv-library/repos/argus-Universal-web-based-ground-control-stati/docs/protocol_design.md)
- [`CONTRIBUTING.md`](../../fpv-library/repos/argus-Universal-web-based-ground-control-stati/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/argus-Universal-web-based-ground-control-stati/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/L-X-Yao__argus.md`.
