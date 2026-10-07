# YouTube Chapters

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [dutchdronesquad/rh-youtube-chapters](https://github.com/dutchdronesquad/rh-youtube-chapters) |
| Локальна тека | `fpv-library/repos/rh-youtube-chapters-YouTube-chapters-plugin-made-for-RotorH` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

When you publish a video on YouTube, you have the option to add a [chapters list](https://support.google.com/youtube/answer/9884579) in the description, which divides the video timeline into chapters for easier navigation.

This [RotorHazard](https://github.com/RotorHazard/RotorHazard) plugin will help you to generate a chapters list based on the start time of each heat. Ideal for when you want to publish the VOD of your livestream afterwards and make it easier for viewers to navigate to a specific round / heat of the race.

_З README.md, без переказу._

## Для чого

📋 YouTube chapters plugin made for RotorHazard

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `rotorhazard`, `youtube`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: 📋 YouTube chapters plugin made for RotorHazard

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `assets/`
- `custom_plugins/`
- `LICENSE`
- `pyproject.toml`
- `README.md`
- `tools/`
- `uv.lock`

Типи файлів за вибіркою (14 файлів, глибина до 3): (без суфікса) (3), Python (3), JSON (2), YAML (1), .lock (1), Markdown (1).


## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `youtube-chapters`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

> [!WARNING]
> This plugin is still in development and only works currently with the dev branch of RotorHazard.
### Install script (CLI)

_This method is for more advanced users who are comfortable with the command line._

1. Install the **YouTube Chapters** plugin, by running the following command in your terminal at the device where RotorHazard is installed:
```bash
bash -c "$(curl -fsSL https://short.dutchdronesquad.nl/install-youtube-chapters)"
```

2. You'll be prompted to choose between **stable** or **development**:
    - **stable**: Choose this option if you want to install a stable release.
        - The script will fetch the last 5 stable releases from GitHub.
        - Choose the version you want to install and press enter.
    - **development**: Choose this option if you want to install the latest development version.
        - The script will fetch the main branch from GitHub.
3. If the plugin is already in RotorHazard, you'll be prompted to update it.
    - Choose **y (yes)** to update the plugin.
    - Choose **n (no)** to exit the script.
4. When the installation is finished, restart RotorHazard to load the plugin.
### Getting started

1. Note when you started live streaming (local time).
2. Do the race timing as you are used to, each heat start will be logged automatically.
3. When you are done, fill in the start time and confirm with the `Set Start Time` button.
4. Click on `Export Chapters` to generate a txt file with the chapters.
    - You will see the download link after page refresh under **Exported Chapters List**.
5. Don't forget to reset the logging every time you have a new event.
### Installation

1. Clone the repository
2. Install all dependencies with UV. This will create a virtual environment and install all dependencies

```bash
uv sync --all-groups
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/rh-youtube-chapters-YouTube-chapters-plugin-made-for-RotorH/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/dutchdronesquad__rh-youtube-chapters.md`.
