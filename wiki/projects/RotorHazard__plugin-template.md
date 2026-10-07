# RotorHazard Plugin Template

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RotorHazard/plugin-template](https://github.com/RotorHazard/plugin-template) |
| Локальна тека | `fpv-library/repos/plugin-template-Template-repository-for-creating-RotorHa` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

This is a basic template repository for creating a plugin for the RotorHazard timing platform. It is intended to be used as a starting point for creating a new plugin.

> [!WARNING] > If you apply this plugin template to an existing RotorHazard plugin that uses GitHub releases, please note that the [community plugins](https://github.com/RotorHazard/community-plugins) database is only compatible with published releases that also pass the [RHFest](https://github.com/RotorHazard/rhfest-action) checks.

_З README.md, без переказу._

## Для чого

Template repository for creating RotorHazard plugins

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Список із розділу features / можливості в README:

- **Pre-commit checks**: to run checks and tests on each commit.
- **Python virtual environment**: uses [uv] to manage the python virtual environment and dependencies.
- **RHFest validation**: GitHub action to validate the plugin manifest file against the RHFest schema.
- **Renovate**: uses [Renovate](https://docs.renovatebot.com/) to keep dependencies up to date.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `custom_plugins/`
- `LICENSE`
- `pyproject.toml`
- `README.md`
- `uv.lock`

Типи файлів за вибіркою (9 файлів, глибина до 3): (без суфікса) (2), JSON (2), YAML (1), .lock (1), Markdown (1), TOML (1).


## Що треба

### Prerequisites

You need the following tools to get started:

- [uv] - A python virtual environment/package manager
- [Python] 3.13 - The programming language

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `rh-plugin-template`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

1. Clone the repository
2. Install all dependencies with UV. This will create a virtual environment and install all dependencies

```bash
uv sync
```

3. Setup the prek check, you must run this inside the virtual environment

```bash
uv run prek install
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/plugin-template-Template-repository-for-creating-RotorHa/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RotorHazard__plugin-template.md`.
