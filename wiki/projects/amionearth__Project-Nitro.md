# Project-Nitro 🏎️💨

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [amionearth/Project-Nitro](https://github.com/amionearth/Project-Nitro) |
| Локальна тека | `fpv-library/repos/Project-Nitro-An-RC-FPV-mini-racing-car-with-special-e` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

An RC FPV mini racing car with special effects like in games

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

An RC FPV mini racing car with special effects like in games

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: An RC FPV mini racing car with special effects like in games

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `cad/`
- `circuit/`
- `doc/`
- `firmware/`
- `image/`
- `pcb/`
- `README.md`

Типи файлів за вибіркою (63 файлів, глибина до 3): .png (12), C++ (9), C (8), .zip (4), .step (4), .kicad_pcb (3).

Фрагмент README про будову:

### How It Works ⚙️

This all works with ESP-NOW protocol. The host's car maintains the rules and everything:

- `car ↔ remote` - Direct communication between each unit  
- `car(host) ↔ car(client)` - Host communicates with client cars  
- `camera → WiFi web → phone, laptop...` - Video stream to viewer devices

## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### How to Play/Setup 🎮

When you turn on the remote and car, it will connect (if it's your first time,you may need to pair them) You'll get a web interface in phone or laptop for FPV. Once connected you have two modes:

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Project-Nitro-An-RC-FPV-mini-racing-car-with-special-e/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/amionearth__Project-Nitro.md`.
