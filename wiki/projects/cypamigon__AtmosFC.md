# AtmosFC

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [cypamigon/AtmosFC](https://github.com/cypamigon/AtmosFC) |
| Локальна тека | `fpv-library/repos/AtmosFC-Quadcopter-flight-controller-based-on-ST` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2025-09-04 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

AtmosFC is an open-hardware quadcopter flight controller designed in KiCad. Powered by an STM32G4 MCU, it integrates high-performance sensors and peripherals, and is fully compatible with Betaflight (≥ 4.5).

_З README.md, без переказу._

## Для чого

Quadcopter flight controller based on STM32G4 with IMU (ICM-468-P), barometer (DPS-386), OSD (MAX7456) and 32MB flash memory for blackbox logging — running Betaflight.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».
- Майстерня обладнання — у тексті є «kicad».


## Функція

Список із розділу features / можливості в README:

- **MCU**: STM32G473CEU6
- **IMU**: ICM-468-P
- **Barometer**: DPS-386
- **OSD**: MAX7456 for analog on-screen display
- **Blackbox**: 32MB onboard flash memory for log recording
- **Power input**: Up to 6S
- **Power monitoring**: Battery voltage and current sensing
- **Status indicators**: Green, Blue, and Amber LEDs
- **Dimensions**: 40x40mm
- **Mounting holes**: 30.5×30.5 mm (M4 holes for silicone inserts with M3 screws)
- **Weight**: 8.2g

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `betaflight_config/`
- `documentation/`
- `hardware/`
- `LICENSE.txt`
- `README.md`

Типи файлів за вибіркою (70 файлів, глибина до 3): .gbr (13), .step (12), .kicad_sch (9), .png (9), .kicad_sym (7), (без суфікса) (3).

Фрагмент README про будову:

### Hardware Architecture

The block diagram below shows the main hardware components and their interconnections.

## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/AtmosFC-Quadcopter-flight-controller-based-on-ST/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/cypamigon__AtmosFC.md`.
