# 🧊 Asv.Mavlink

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [asv-soft/asv-mavlink](https://github.com/asv-soft/asv-mavlink) |
| Локальна тека | `fpv-library/repos/asv-mavlink-Mavlink-library-for-NET` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 28 |
| Оновлено upstream | 2026-07-31 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

### Introduction

The [`asv-mavlink`](https://github.com/asv-soft/asv-mavlink) library provides a robust interface for communication with MAVLink compatible vehicles and payloads. This library is designed to facilitate the interaction with drones and other devices using the MAVLink protocol, enabling users to send commands, receive telemetry data, and perform various operations.

Additionally, the library includes a CLI utility [Asv.Mavlink.Shell](https://github.com/asv-soft/asv-mavlink/tree/main/src/Asv.Mavlink.Shell) for simulating, testing and code generation.

This library is part of the open-source cross-platform application for drones [Asv Drones](https://github.com/asv-soft/asv-drones).

_З README.md, без переказу._

## Для чого

Mavlink library for .NET

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `arm`, `linux`, `mac-osx`, `mavlink`, `payload`, `px4`, `uav`, `vehicle`, `vehicles`, `windows`.

## Функція

Список із розділу features / можливості в README:

- Display the full directory structure of the drone's file system in a tree format.
- Automatically refreshes and loads the / and @SYS directories.
- Displays directories and files with visual guides for better clarity.
- FTP Connection: The command connects to a drone via TCP using a specified connection string, establishing an FTP client for file interactions.
- Tree Navigation: The file system is presented in a hierarchical structure using a tree model. The user can browse through directories interactively.
- File and Directory Operations: The user can:
- Open directories.
- Remove, rename, or create directories.
- Perform file operations such as downloading, removing, truncating, renaming, and calculating CRC32.
- Reads binary SDR data from an input file.
- Exports the data to a CSV file for further analysis or storage.
- Provides a simple and automated way to convert SDR logs into human-readable tabular data.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `CLAUDE.md`
- `img/`
- `LICENSE`
- `README.md`
- `regenerate_asv.bat`
- `regenerate_mavlink.bat`
- `src/`

Типи файлів за вибіркою (102 файлів, глибина до 3): .cs (40), .png (23), Markdown (6), .xml (6), .resx (5), .bat (3).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

To install the [`asv-mavlink`](https://github.com/asv-soft/asv-mavlink) library, you can use the following command:

```
dotnet add package Asv.Mavlink --version <Version>
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/asv-mavlink-Mavlink-library-for-NET/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/asv-soft__asv-mavlink.md`.
