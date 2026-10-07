# Just4Stan/betaflight

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [Just4Stan/betaflight](https://github.com/Just4Stan/betaflight) |
| Локальна тека | `fpv-library/repos/betaflight-Open-Source-Flight-Controller-Firmware` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-11 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Betaflight is flight controller software (firmware) used to fly multi-rotor craft and fixed wing craft. Betaflight focuses on flight performance, leading-edge feature additions, and wide target support.

_З README.md, без переказу._

## Для чого

Open Source Flight Controller Firmware

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Список із розділу features / можливості в README:

- Multi-color RGB LED strip support (each LED can be a different color using variable length WS2811 Addressable RGB strips - use for Orientation Indicators, Low Battery Warning, Flight Mode Status, Initialization Troubleshooting, etc)
- DShot (150, 300 and 600), Multishot, Oneshot (125 and 42) and Proshot1000 motor protocol support
- Blackbox flight recorder logging (to onboard flash or external microSD card where equipped)
- Support for targets that use the STM32 F4, G4, F7 and H7 processors
- PWM, PPM, SPI, and Serial (SBus, SumH, SumD, Spektrum 1024/2048, XBus, etc) RX connection with failsafe detection
- Multiple telemetry protocols (CRSF, FrSky, HoTT smart-port, MSP, etc)
- RSSI via ADC - Uses ADC to read PWM RSSI signals, tested with FrSky D4R-II, X8R, X4R-SB, & XSR
- OSD support & configuration without needing third-party OSD software/firmware/comm devices
- OLED Displays - Display information on: Battery voltage/current/mAh, profile, rate profile, mode, version, sensors, etc
- In-flight manual PID tuning and rate adjustment
- PID and filter tuning using sliders
- Rate profiles and in-flight selection of them

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `DEFAULT_LICENSE.md`
- `images/`
- `lib/`
- `LICENSE`
- `Makefile`
- `mk/`
- `README.md`
- `SECURITY.md`
- `src/`

Типи файлів за вибіркою (1112 файлів, глибина до 3): C (1001), C++ (66), .mk (13), (без суфікса) (7), Markdown (6), Python (4).


## Що треба

### Requirements for the submission of new and updated target configuration

The requirements for pull requests adding new targets or modifying existing targets are available on the [betaflight.com website](https://www.betaflight.com/docs/development/manufacturer/requirements-for-submission-of-targets).

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation & Documentation

See: https://betaflight.com/docs/wiki

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/betaflight-Open-Source-Flight-Controller-Firmware/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/betaflight-Open-Source-Flight-Controller-Firmware/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/Just4Stan__betaflight.md`.
