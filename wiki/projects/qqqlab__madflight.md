# qqqlab/madflight

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [qqqlab/madflight](https://github.com/qqqlab/madflight) |
| Локальна тека | `fpv-library/repos/madflight-Flight-Controller-for-ESP32-Raspberry-Pi` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 469 |
| Оновлено upstream | 2026-08-01 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

_madflight_ is a toolbox to build high performance flight controllers with Aduino IDE or PlatformIO for ESP32-S3 / ESP32 / RP2350 / RP2040 / STM32. A functional DIY flight controller can be build for under $10 from readily available [development boards](https://madflight.com/Controller-Boards/) and [sensor breakout boards](https://madflight.com/Sensor-Boards/).

Get started with the [Arduino IDE](https://madflight.com/Getting-Started) or [PlatformIO](https://madflight.com/Getting-Started)

Flight tested example programs for quadcopter and airplane are included. The example programs are only a couple hundred lines long, but contain the full flight controller logic. The nitty-gritty low-level sensor and input/output management is done by the _madflight_ library.

The source code and [website](https://madflight.com/) have extensive documentation explaning what the settings and functions do.

_З README.md, без переказу._

## Для чого

Flight Controller for ESP32 / Raspberry Pico / STM32

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `airplane`, `ardupilot`, `autopilot`, `betaflight`, `drone`, `drones`, `esp32`, `flight-controller`, `fpv`, `mavlink`, `multicopter`, `quadcopter`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Flight Controller for ESP32 / Raspberry Pico / STM32

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `examples/`
- `extras/`
- `library.properties`
- `LICENSE`
- `Parameters.md`
- `platformio.ini`
- `README.md`
- `src/`

Типи файлів за вибіркою (1273 файлів, глибина до 3): C (681), .config (431), C++ (89), Markdown (29), (без суфікса) (11), Arduino (9).


## Що треба

- Маніфести збірки: PlatformIO (platformio.ini).
- PlatformIO env: `ESP32`, `ESP32-S3`, `ESP32-S3-SuperMini`, `RP2040`, `RP2350A`, `RP2350B`, `STM32F411`, `STM32F405`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Getting Started

See [Getting Started](https://madflight.com/Getting-Started/) 

For additional help see [Discussions](https://github.com/qqqlab/madflight/discussions)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/madflight-Flight-Controller-for-ESP32-Raspberry-Pi/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/qqqlab__madflight.md`.
