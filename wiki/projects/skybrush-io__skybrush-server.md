# Skybrush Server

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [skybrush-io/skybrush-server](https://github.com/skybrush-io/skybrush-server) |
| Локальна тека | `fpv-library/repos/skybrush-server-Server-component-for-Skybrush-an-open-so` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 122 |
| Оновлено upstream | 2026-07-28 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Skybrush Server is the server component behind the Skybrush ecosystem; it handles communication channels to drones and provides an abstraction layer on top of them so frontend apps (like Skybrush Live) do not need to know what type of drones they are communicating with.

The server also provides additional facilities like clocks, RTK correction sources, weather providers and so on. It is extensible via extension modules that can be loaded automatically at startup or dynamically while the server is running. In fact, most of the functionality in the server is implemented in the form of extensions; see the `flockwave.server.ext` module in the source code for the list of built-in extensions. You may also develop your own extensions to extend the functionality of the server.

_З README.md, без переказу._

## Для чого

Server component for Skybrush, an open-source drone light show and drone swarm management framework

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `drone`, `drone-show`, `drone-swarm`, `skybrush`, `uav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Server component for Skybrush, an open-source drone light show and drone swarm management framework

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `CHANGELOG.md`
- `DEPENDENCIES.md`
- `doc/`
- `etc/`
- `LICENSE.txt`
- `pyproject.toml`
- `README.md`
- `src/`
- `tbump.toml`
- `test/`
- `uv.lock`

Типи файлів за вибіркою (83 файлів, глибина до 3): Python (51), .jsonc (6), (без суфікса) (5), Markdown (4), JSON (3), .conf (3).


## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `flockwave-server`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

1. Install `uv`. `uv` will manage a virtual environment for this project to keep
   things nicely separated. You won't pollute the system Python with the
   dependencies of the Skybrush server and everyone will be happier.
   See <https://docs.astral.sh/uv/> for installation instructions.

2. Check out the source code of the server.

3. Run `uv sync` to install all the dependencies and the server itself in a
   separate virtualenv. The virtualenv will be created in a folder named
   `.venv` in the project folder.

4. Run `uv run skybrushd` to start the server.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/skybrush-server-Server-component-for-Skybrush-an-open-so/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/skybrush-io__skybrush-server.md`.
