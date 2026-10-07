# RotorHazard

> Картка виставки. Зал: [Інструменти](../halls/tools.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RotorHazard/RotorHazard](https://github.com/RotorHazard/RotorHazard) |
| Локальна тека | `fpv-library/repos/RotorHazard-FPV-race-timing-and-event-management` |
| У бібліотеці | keep |
| Категорії каталогу | `tools` |
| Зірки (каталог) | 259 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**FPV Race Timing and Event Management**

RotorHazard is an open-source timing and event management system for FPV drone racing. It tracks the video signals broadcast by race drones to trigger lap times, and processes them with a central server (usually a Raspberry Pi). The server's front-end web interface provides race organizer management, pilot/spectator information, and race results. Supports up to 16 simultaneous racers.

> [!TIP] >Join a community to discuss RotorHazard: [Discord](https://discord.gg/ANKd2pzBKH) | [Facebook](https://www.facebook.com/groups/rotorhazard) > > Sponsor RtorHazard's development:[GitHub](https://github.com/sponsors/HazardCreative) | [Patreon](https://www.patreon.com/rotorhazard)

_З README.md, без переказу._

## Для чого

FPV race timing and event management

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Список із розділу features / можливості в README:

- Self-contained on local hardware, no internet connection needed
- Server synchronized with user interface for accurate start/end signals; compensates for poor network connectivity
- Connect other systems and extend functionality via [plugins](doc/Plugins.md)
- Server runs on any device supporting Python

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `doc/`
- `firmware/`
- `LICENSE`
- `project/`
- `README.md`
- `resources/`
- `src/`
- `tools/`

Типи файлів за вибіркою (374 файлів, глибина до 3): Markdown (99), Python (62), .jpg (29), HTML (27), C (20), .bat (17).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Getting Started

RotorHazard consists of three primary components: Timing hardware, server, and frontend interface. **Most users will begin with RotorHazard by building or buying timing hardware and then installing the server software on it.**

> [!IMPORTANT]
> Live documentation may contain information that does not apply to the current release. For documentation relating to the *current stable version only*, follow the [Documentation](https://github.com/RotorHazard/RotorHazard/releases/latest#documentation) link on the [latest-release page](https://github.com/RotorHazard/RotorHazard/releases/latest).

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/RotorHazard-FPV-race-timing-and-event-management/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RotorHazard__RotorHazard.md`.
