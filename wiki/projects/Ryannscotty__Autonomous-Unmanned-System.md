# UAS Top-Level Diagram

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [Ryannscotty/Autonomous-Unmanned-System](https://github.com/Ryannscotty/Autonomous-Unmanned-System) |
| Локальна тека | `fpv-library/repos/Autonomous-Unmanned-System-An-open-source-Unmanned-Aircraft-System` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-31 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

The companion ground station (HTML/JS GCS with a live mission planning) and the FPGA/SDR telemetry link this firmware is designed to pair with live in separate repos — see [Related work](#related-work).

_З README.md, без переказу._

## Для чого

An open-source Unmanned Aircraft System (UAS) built around a custom FPV drone, ground control station (GCS), and RC controller — designed as an end-to-end embedded systems and RF project

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: An open-source Unmanned Aircraft System (UAS) built around a custom FPV drone, ground control station (GCS), and RC controller — designed as an end-to-end embedded systems and RF project

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `Build/`
- `Clocks/`
- `CMakeLists.txt`
- `compile_commands.json`
- `Flight Controller Hardware/`
- `FlightController_FW.bin`
- `headers/`
- `HIL_UNIT_TEST/`
- `Linker/`
- `PeriphDrivers/`
- `README.md`
- `scheduler/`
- `src/`
- `STM32H7/`

Типи файлів за вибіркою (152 файлів, глибина до 3): C (50), .make (28), .cmake (24), .txt (9), TypeScript (6), .internal (6).

Фрагмент README про будову:

### Scheduler Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  STM32H743 — bare-metal                                           │
│                                                                   │
│  SysTick ISR (1 kHz)  ──sets pending flags──▶  superloop          │
│         │                                          │              │
│         │                                  watchdog_task_start()  │
│         │                                          ▼              │
│         │                                    tasklist.fn() runs   │
│         │                                          │              │
│         ▼                                   watchdog_task_end()   │
│  IWDG (hardware) ◀── kicked once per loop pass, never inside a    │
│  TIM7 deadman timer ── fires independently if a task hangs        │
│                                                                   │
│  ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐ │|
│  │ 1 kHz tier     │   │ 10 Hz tier     │   │ Flight mode FSM     ││
│  │ IMU → AHRS     │──▶│ GPS/baro/batt  │──▶│ STABILIZE→ALT_HOLD  ││
│  │ → rate PID     │   │ → position PID │   │ →LOITER→RTL→FAILSAFE││
│  └───────────────┘   └────────────────┘   └────────────────────┘ │|
└─────────────────────────────────────────────────────────────────┘
```

## Що треба

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build & flash

```
sudo apt install gcc-arm-none-eabi cmake openocd
mkdir build && cd build
cmake --build build
make -j$(nproc)
make flash    # requires ST-Link V3 + OpenOCD
```
---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Autonomous-Unmanned-System-An-open-source-Unmanned-Aircraft-System/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/Ryannscotty__Autonomous-Unmanned-System.md`.
