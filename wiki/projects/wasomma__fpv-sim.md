# FPV sUAS vs cUAS — Force-on-Force Demonstration

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [wasomma/fpv-sim](https://github.com/wasomma/fpv-sim) |
| Локальна тека | `fpv-library/repos/fpv-sim-Single-file-interactive-FPV-sUAS-vs-cUAS` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-23 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**Live demo: https://wasomma.github.io/fpv-sim/** · **Results dashboard: https://wasomma.github.io/fpv-sim/dashboard.html**

A single-file, zero-dependency interactive simulation of a force-on-force engagement between two teams, each fielding an armed FPV small-UAS (sUAS) and a pair of counter-UAS (cUAS) radio-frequency direction-finding nodes. Everything — terrain, RF propagation, DF geolocation math, drone behavior, and rendering — lives in one HTML file (`index.html`) with no external libraries, build step, or server.

All data is **notional**. The banner says it and it's true: the area of operations ("AO KATANA"), unit positions, sensor parameters, and outcomes are invented for demonstration purposes. Unclassified throughout.

_З README.md, без переказу._

## Для чого

Single-file interactive FPV sUAS vs cUAS force-on-force simulation (notional demo) - EMCON discipline decides the fight

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Single-file interactive FPV sUAS vs cUAS force-on-force simulation (notional demo) - EMCON discipline decides the fight

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `CLAUDE.md`
- `dashboard.html`
- `DESIGN_NOTES.md`
- `DEVELOPMENT_HISTORY.md`
- `index.html`
- `LICENSE.md`
- `MONTE_CARLO.md`
- `PARAMETERS.md`
- `README.md`
- `results/`
- `scripts/`

Типи файлів за вибіркою (19 файлів, глибина до 3): Markdown (8), JSON (4), .mjs (4), HTML (2), (без суфікса) (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick start

Open the [live demo](https://wasomma.github.io/fpv-sim/) or just open
`index.html` in any modern browser. Press **Play**.

| Control | What it does |
|---|---|
| Play / Reset | Start, pause, or restart the current engagement |
| 1x / 2x / 4x / 8x | Playback speed (simulation steps at fixed 0.1 s physics ticks) |
| RF Coverage | Dashed rings showing each DF node's maximum detection range |
| LOBs | Recent lines of bearing from DF intercepts (fade over 30 s) |
| Ellipses | Each side's error ellipse and CEP for its fix on the enemy GCS |
| Flight Paths | Breadcrumb trails behind each drone |
| Canopy | Vegetation overlay (canopy also degrades RF in the model) |
| Status HUD | Team status cards in the upper map corners: drone state, battery, LOBs held, fix CEP, and engagement status — the race-to-fix at a glance |
| Scenario | Curated seeds with known outcomes (see below) |
| Random | Any seed; same seed always replays the identical engagement |

Click any unit on the map (GCS, DF node, or drone) for a live detail panel:
airspeed, altitude, battery, link state, intercept counts, current fix quality.
The event log on the right narrates the engagement in message-traffic style.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-sim-Single-file-interactive-FPV-sUAS-vs-cUAS/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/wasomma__fpv-sim.md`.
