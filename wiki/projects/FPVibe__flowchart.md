# flowchart

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [FPVibe/flowchart](https://github.com/FPVibe/flowchart) |
| Локальна тека | `flowchart-Node-FPV-Training-Tracker-PWA` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | CC |

## Ідея

A self-hostable PWA for tracking FPV freestyle training progress, session logs, trick mastery, and the 20-week "Plan to Denver."

_З README.md, без переказу._

## Для чого

A self-hostable PWA for tracking FPV freestyle training progress, session logs, trick mastery, and the 20-week "Plan to Denver."

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Список із розділу features / можливості в README:

- **Session logging** - Track practice sessions with packs, trick attempts, crashes, and post-session reviews
- **Trick mastery** - Monitor progress across 5 skill levels with computed success rates
- **Phase progression** - 20-week training program with gate checks
- **Denver countdown** - Prep checklist for the July 2026 trip
- **Offline-capable** - PWA with service worker (see known limitations below)
- **Self-hosted** - Single SQLite file, Docker-ready

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `data/`
- `docker-compose.yml`
- `Dockerfile`
- `fpv training complete.pdf`
- `ISSUE-offline-first.md`
- `LICENSE`
- `package-lock.json`
- `package.json`
- `PLAN.md`
- `public/`
- `README.md`
- `src/`
- `TODO.md`

Типи файлів за вибіркою (32 файлів, глибина до 3): TypeScript (9), (без суфікса) (5), Markdown (5), JSON (3), JavaScript (2), .svg (2).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `start`, `dev`.
- dependencies: `@hono/node-server`, `better-sqlite3`, `hono`, `tsx`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

```bash
npm install
npm start          # http://localhost:3000
```

For development with auto-restart:

```bash
npm run dev
```

## З чого зібрана картка

`catalog.json`, `flowchart-Node-FPV-Training-Tracker-PWA/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/FPVibe__flowchart.md`.
