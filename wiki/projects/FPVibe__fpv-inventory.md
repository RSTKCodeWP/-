# fpv-inventory

> Картка виставки. Зал: [Інструменти](../halls/tools.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [FPVibe/fpv-inventory](https://github.com/FPVibe/fpv-inventory) |
| Локальна тека | `fpv-inventory-Deno-FPV-Parts-Inventory` |
| У бібліотеці | keep |
| Категорії каталогу | `tools` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

An inventory app for FPV quads and parts bins — track parts, builds, and gear, nest components into assemblies, and keep a history of what's moved where. Part of the FPVibe federation of tools.

_З README.md, без переказу._

## Для чого

An inventory app for FPV quads and parts bins — track parts, builds, and gear, nest components into assemblies, and keep a history of what's moved where. Part of the FPVibe federation of tools.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `api.ts`
- `CLAUDE.md`
- `db.ts`
- `deno.json`
- `docker-compose.yml`
- `Dockerfile`
- `main.ts`
- `README.md`
- `tests/`
- `version.ts`

Типи файлів за вибіркою (14 файлів, глибина до 3): TypeScript (8), Markdown (2), (без суфікса) (2), JSON (1), YAML (1).


## Що треба

- Маніфести збірки: Deno.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

1. **Open in a dev container**
   - GitHub Codespaces: Click "Code" → "Create codespace"
   - VS Code: "Reopen in Container"
   - Claude Code on web: Will automatically use the devcontainer

2. **Run it**
   - `deno task dev` — starts the server with `--watch`
   - `deno task test` — run the test suite
   - `deno task check` — type-check the repo

## З чого зібрана картка

`catalog.json`, `fpv-inventory-Deno-FPV-Parts-Inventory/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/FPVibe__fpv-inventory.md`.
