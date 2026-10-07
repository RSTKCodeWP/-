# ap-swarm-launcher

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [skybrush-io/ap-swarm-launcher](https://github.com/skybrush-io/ap-swarm-launcher) |
| Локальна тека | `fpv-library/repos/ap-swarm-launcher-Simplified-ArduPilot-SITL-launcher-for-m` |
| У бібліотеці | keep |
| Категорії каталогу | `fc`, `tools` |
| Зірки (каталог) | 20 |
| Оновлено upstream | 2026-07-15 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Simplified ArduPilot SITL launcher for multi-drone simulations. Runs multiple ArduPilot SITL instances in parallel, managed by a central process supervisor that merges the standard output streams of individual processes and configures the SITL instances to start the drones from a grid-like formation.

_З README.md, без переказу._

## Для чого

Simplified ArduPilot SITL launcher for multi-drone simulations

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».


Теми GitHub: `drone`, `drone-show`, `drone-swarm`, `skybrush`, `uav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Simplified ArduPilot SITL launcher for multi-drone simulations

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `LICENSE.md`
- `pyproject.toml`
- `README.md`
- `src/`
- `tbump.toml`
- `uv.lock`

Типи файлів за вибіркою (24 файлів, глибина до 3): Python (13), Markdown (3), TOML (2), .parm (2), YAML (1), .lock (1).


## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `ap-swarm-launcher`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

We use `uv` to manage a Python virtual environment that will contain all
the dependencies. Install `uv` first if you don't have it yet, then follow
these steps:

1. Clone this repository.

2. Run `uv sync` to create a virtualenv and install all the dependencies
   in it.

3. Run `uv run ap-sitl-swarm SITL_PATH` to launch a single SITL instance
   with a pre-compiled SITL executable at `${SITL_PATH}`. Use the `-h` switch
   for more options.

Tested on Linux and macOS. May or may not work on Windows.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ap-swarm-launcher-Simplified-ArduPilot-SITL-launcher-for-m/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/skybrush-io__ap-swarm-launcher.md`.
