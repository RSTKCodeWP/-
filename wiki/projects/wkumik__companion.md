# Companion

> Картка виставки. Зал: [OpenIPC](../halls/openipc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [wkumik/companion](https://github.com/wkumik/companion) |
| Локальна тека | `fpv-library/repos/companion-An-official-multi-platform-configuration` |
| У бібліотеці | skip |
| Категорії каталогу | `openipc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-17 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

An official multi-platform configuration tool for OpenIPC cameras, built with Avalonia UI. The app manages camera settings, telemetry, presets, and firmware updates.

**Note: NVR is not supported yet. Please use MarioFPV's [OpenIPC Config](https://github.com/OpenIPC/configurator) for NVR support.**

_З README.md, без переказу._

## Для чого

An official multi-platform configuration tool for OpenIPC cameras, built using Avalonia UI.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «openipc».


## Функція

Список із розділу features / можливості в README:

- **Camera settings management**: configure resolution, frame rate, and exposure
- **Telemetry**: view real-time metrics like temperature, voltage, and signal strength
- **Setup wizards**: guided setup for device and network configuration
- **Multi-platform support**: Windows, macOS, Linux, Android, and iOS targets
- **YAML-based configuration files**: edit and customize settings with YAML

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `build-them.sh`
- `clean.sh`
- `Companion/`
- `Companion.Android/`
- `Companion.Desktop/`
- `Companion.iOS/`
- `Companion.Tests/`
- `coverage-report.sh`
- `Directory.Build.props`
- `docs/`
- `get-latest-binaries.sh`
- `global.json`
- `OpenIPC.sln`
- `README.md`
- `test-script.sh`
- `version.json`

Типи файлів за вибіркою (271 файлів, глибина до 3): .cs (147), .svg (26), .axaml (25), Markdown (9), .bin (9), shell (8).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Getting started (desktop)

```bash
dotnet build Companion.Desktop/Companion.Desktop.csproj -c Release
dotnet run --project Companion.Desktop/Companion.Desktop.csproj
```

For local cross-platform packaging checks, use `./build-them.sh`. That script is intended for developer testing before pushing changes. GitHub Actions is the source of truth for official CI builds, release artifacts, and published releases.

## Супутні документи в теці

- [`docs/0.9.0-to-0.9.1-sysupgrade-hotfix.md`](../../fpv-library/repos/companion-An-official-multi-platform-configuration/docs/0.9.0-to-0.9.1-sysupgrade-hotfix.md)
- [`docs/architecture.md`](../../fpv-library/repos/companion-An-official-multi-platform-configuration/docs/architecture.md)
- [`docs/configuration.md`](../../fpv-library/repos/companion-An-official-multi-platform-configuration/docs/configuration.md)
- [`docs/development.md`](../../fpv-library/repos/companion-An-official-multi-platform-configuration/docs/development.md)
- [`docs/firmware-backup-restore.md`](../../fpv-library/repos/companion-An-official-multi-platform-configuration/docs/firmware-backup-restore.md)
- [`docs/presets.md`](../../fpv-library/repos/companion-An-official-multi-platform-configuration/docs/presets.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/companion-An-official-multi-platform-configuration/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/wkumik__companion.md`.
