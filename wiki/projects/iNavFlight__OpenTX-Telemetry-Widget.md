# iNavFlight/OpenTX-Telemetry-Widget

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [iNavFlight/OpenTX-Telemetry-Widget](https://github.com/iNavFlight/OpenTX-Telemetry-Widget) |
| Локальна тека | `fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `fc` |
| Зірки (каталог) | 264 |
| Оновлено upstream | 2026-07-09 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

INAV Lua Telemetry with support for EdgeTX

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

INAV Lua Telemetry with support for EdgeTX

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «inav».
- Інженер радіолінка — у тексті є «crossfire».


Теми GitHub: `hacktoberfest`.

## Функція

Список із розділу features / можливості в README:

- Supported receivers: FrSky (compatible) telemetry receivers (X, R9 and D series) and Crossfire receivers.
- Supported transmitters: FrSky Taranis and Horus transmitters, Jumper T12, T16, FLYSKY Nirvana NV14, Radiomaster TX16S, TX12, Zorro, Boxer (at least).
- Note other transmitters may work, but are not considered "supported".
- Launch/pilot-based model orientation and location indicators (great for lost orientation/losing sight of your model)
- Compass-based direction indicator (with magnetometer sensor on multirotor or fixed-wing with GPS)
- Pilot (glass cockpit) view which includes attitude indicator as well as pilot-familiar layout of additional data
- Radar (map) view shows model in relationship to home position, can be displayed either as launch/pilot-based or compass-based orientation
- Altitude graph view shows altitude for the last 1-6 minutes
- Colour LCD transmitters show all views at the same time, and include additional features like roll scale
- Bar gauges for Fuel (% battery mAh capacity remaining), Battery voltage, RSSI strength, Transmitter battery, GPS accuracy (HDOP), Variometer (and Altitude for X9D, X9D+ and X9E transmitters)
- Display and voice alerts for flight modes and flight mode modifiers (altitude hold, heading hold, home reset, etc.)
- Voice notifications for % battery remaining (based on current), voltage low/critical, high altitude, lost GPS, ready to arm, armed, disarmed, etc.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `3rdparty/`
- `assets/`
- `CONTRIBUTING.md`
- `docs/`
- `LICENSE`
- `Makefile`
- `mkdocs.yml`
- `README.md`
- `release`
- `requirements-docs.txt`
- `src/`

Типи файлів за вибіркою (119 файлів, глибина до 3): C (58), .png (22), Markdown (10), (без суфікса) (9), .pdn (3), Lua (3).


## Що треба

### Requirements

Supported environments are given below, older versions may also work but are unsupported.

* [INAV v6.0+](https://github.com/iNavFlight/inav/releases) running on your flight controller.
* [OpenTX v2.3.14+](http://www.open-tx.org/) running on Taranis Q X7/Q X7S, X9D/X9D+, X9E, X9 Lite, X-Lite/X-Lite Pro, Horus X10/X10S or X12S
* [EdgeTX v2.8.0+](https://edgetx.org/) running on a [supported radio](https://github.com/EdgeTX/edgetx.github.io/wiki/Frequently-Asked-Questions).
* FrSky X, R9 or D series telemetry receiver: X4RSB, X8R, XSR, R-XSR, XSR-M, XSR-E, RX4R, RX6R, R9, R9 Slim, R9 Slim+, R9 Mini, R9 MM, D8R-II plus, D8R-XP, D4R-II, etc. or any Crossfire receiver: Micro, Nano, Diversity, ELRS etc.
* GPS - On the aircraft.

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Setup

* [Lua Telemetry Docs](https://luatelemetry.readthedocs.io/en/latest/)
* [Download latest release](https://github.com/iNavFlight/OpenTX-Telemetry-Widget/releases/latest)
* [Installation Instructions](https://luatelemetry.readthedocs.io/en/latest/Getting-Started/)
* [Upgrade Instructions](https://luatelemetry.readthedocs.io/en/latest/Upgrade/)
* [Download Options](https://luatelemetry.readthedocs.io/en/latest/Getting-Started/#download-options)

## Супутні документи в теці

- [`docs/Configuration-Settings.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/Configuration-Settings.md)
- [`docs/EdgeTX-Compatibility.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/EdgeTX-Compatibility.md)
- [`docs/Getting-Started.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/Getting-Started.md)
- [`docs/Multilingual-Support.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/Multilingual-Support.md)
- [`docs/Screen-Description.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/Screen-Description.md)
- [`docs/Tips-And-Common-Problems.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/Tips-And-Common-Problems.md)
- [`docs/Upgrade.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/Upgrade.md)
- [`docs/index.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/docs/index.md)
- [`CONTRIBUTING.md`](../../fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/OpenTX-Telemetry-Widget-INAV-Lua-Telemetry-with-support-for-Edge/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/iNavFlight__OpenTX-Telemetry-Widget.md`.
