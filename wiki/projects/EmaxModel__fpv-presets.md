# OpenIPC FPV Presets

> Картка виставки. Зал: [OpenIPC](../halls/openipc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [EmaxModel/fpv-presets](https://github.com/EmaxModel/fpv-presets) |
| Локальна тека | `fpv-library/repos/fpv-presets-Presets-for-configuring-OpenIPC-FPV-syst` |
| У бібліотеці | keep |
| Категорії каталогу | `openipc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2025-03-24 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Collection of preconfigured presets for OpenIPC FPV Configurator application.

_З README.md, без переказу._

## Для чого

Presets for configuring OpenIPC FPV systems

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «openipc».


## Функція

Список із розділу features / можливості в README:

- **Dynamic Preset Management**:
- Add/remove presets by simply editing the `presets/` directory.
- **File Abstraction**:
- Presets only define attributes; the app handles file locations.
- **Sensor File Handling**:
- Automatically transfers sensor binaries if specified.
- **User-Friendly UI**:
- Select a preset, view details, and apply it with a single click.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `build.sh`
- `create_preset.sh`
- `images/`
- `package-lock.json`
- `package.json`
- `PRESET_INDEX.yaml`
- `presets/`
- `README.md`

Типи файлів за вибіркою (18 файлів, глибина до 3): YAML (5), (без суфікса) (5), JSON (3), shell (2), .png (2), Markdown (1).


## Що треба

- Маніфести збірки: Node.js (package.json).
- dependencies: `js-yaml`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### How to Add a Preset

Adding a new preset to this repository is straightforward. Follow these steps to contribute your FPV camera configuration:

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-presets-Presets-for-configuring-OpenIPC-FPV-syst/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/EmaxModel__fpv-presets.md`.
