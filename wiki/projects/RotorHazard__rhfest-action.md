# RHFest Action

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RotorHazard/rhfest-action](https://github.com/RotorHazard/rhfest-action) |
| Локальна тека | `fpv-library/repos/rhfest-action-GitHub-Action-that-validates-a-RotorHaz` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

A reusable GitHub Action that validates `manifest.json` files for RotorHazard plugins. It checks for missing fields, invalid formats, and unsupported values, and logs validation errors directly in GitHub Actions logs using **GitHub-friendly annotations**.

_З README.md, без переказу._

## Для чого

📋 GitHub Action that validates a RotorHazard plugin

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `actions`, `plugin`, `rotorhazard`.

## Функція

Список із розділу features / можливості в README:

- ✅ Schema validation for keys in `manifest.json`
- ✅ Plugin repository structure validation
- 📁 Presence of `custom_plugins` folder
- 📁 Presence of single plugin domain folder
- 📄 Presence of `manifest.json` file
- 🔁 Plugin domain folder matches the `domain` in `manifest.json`
- 🚨 GitHub Action annotations for validation errors
- ⚠️ Warnings for missing required fields
- 🐳 Docker image for local testing (manual or pre-commit)
- 📋 Validates for example:
- **domain** format (e.g., lowercase letters, numbers, underscores)
- **version** [semver](https://semver.org) format (e.g., `X.Y.Z`)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `action.yml`
- `Dockerfile`
- `LICENSE`
- `pyproject.toml`
- `README.md`
- `rhfest/`
- `uv.lock`

Типи файлів за вибіркою (18 файлів, глибина до 3): Python (7), (без суфікса) (5), YAML (2), .lock (1), Markdown (1), TOML (1).


## Що треба

### Prerequisites

You need the following tools to get started:

- [uv] - A python virtual environment/package manager
- [Python] 3.13 - The programming language

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `rhfest-action`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 🚀 How to Use

Create a file `.github/workflows/validate.yml` in your plugin repository with the following content:

```yaml
name: Validate Plugin Manifest

on:
  push:
  pull_request:

jobs:
  validate:
    name: Run RHFest validation
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Run RHFest validation
        uses: docker://ghcr.io/rotorhazard/rhfest-action:v3
```
### Installation

1. Clone the repository
2. Install all dependencies with UV. This will create a virtual environment and install all dependencies

```bash
uv sync
```

3. Setup the pre-commit check, you must run this inside the virtual environment

```bash
uv run pre-commit install
```

4. Run the application

```bash
uv run python rhfest/core.py
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/rhfest-action-GitHub-Action-that-validates-a-RotorHaz/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RotorHazard__rhfest-action.md`.
