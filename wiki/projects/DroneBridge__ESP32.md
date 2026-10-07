# DroneBridge/ESP32

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [DroneBridge/ESP32](https://github.com/DroneBridge/ESP32) |
| Локальна тека | `fpv-library/repos/ESP32-DroneBridge-for-ESP32-A-secure-transpare` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `link`, `osd`, `fc` |
| Зірки (каталог) | 972 |
| Оновлено upstream | 2026-05-23 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

A firmware for the popular ESP32 modules from Espressif Systems. Probably the cheapest way to communicate with your drone, UAV, UAS, ground-based vehicle or whatever you may call them.

It also allows for a fully transparent serial to WiFi pass-through link with variable packet size (As of release v2.0 no continuous stream of data is required anymore in MAVLink and transparent mode).

DroneBridge for ESP32 is a telemetry/low data rate-only solution. There is no support for cameras connected to the ESP32 since it does not support video encoding.

_З README.md, без переказу._

## Для чого

DroneBridge for ESP32. A secure & transparent telemetry link with support for WiFi and ESP-NOW. Supporting MAVLink, MSP, LTM or any other protocol

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «qgroundcontrol».
- Розробник польотного контролера — у тексті є «inav».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `communication-systems`, `datalink`, `drone`, `dronebridge`, `esp32`, `espnow`, `espressif`, `inav`, `ltm`, `mavlink`, `msp`.

## Функція

Список із розділу features / можливості в README:

- Bidirectional: serial-to-WiFi, serial-to-WiFi Long-Range (LR), serial-to-ESP-NOW link, Bluetooth LE
- Support for **MAVLink**, **MSP**, **LTM** or **any other payload** using transparent option
- Affordable: ~7€
- Up to **150m range** using standard WiFi
- Up to **1km of range** using ESP-NOW or Wi-Fi LR Mode - sender & receiver must be ESP32 with LR-Mode enabled
- **Fully encrypted** in all modes including ESP-NOW broadcasts secured using AES-GCM 256 bit!
- Weight: <8 g
- Supported by: QGroundControl, Mission Planner, mwptools, impload etc.
- Easy to set up: Power connection + UART connection to flight controller
- Fully configurable through an easy-to-use web interface
- Parsing of LTM & MSPv2 for more reliable connection and less packet loss
- Parsing of MAVLink with the injection of Radio Status packets for the display of RSSI in the GCS

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `case/`
- `CMakeLists.txt`
- `components/`
- `config_defaults/`
- `create_release_zip.ps1`
- `create_release_zip.sh`
- `db_params.csv`
- `flashing_instructions.txt`
- `frontend/`
- `LICENSE`
- `main/`
- `Makefile`
- `partitions.csv`
- `README.md`
- `sdkconfig.defaults`
- `sdkconfig.defaults.esp32`
- `test/`
- `wiki/`

Типи файлів за вибіркою (359 файлів, глибина до 3): C (271), .png (29), (без суфікса) (6), JSON (5), .svg (5), .txt (4).


## Що треба

- Маніфести збірки: CMake, Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation/Flashing using precompiled binaries

[It is recommended that you use the official online flashing tool!](https://drone-bridge.com/flasher/)

In any other case, there are multiple ways how to flash the firmware.  
**[For further info please check the wiki!](https://dronebridge.gitbook.io/docs/dronebridge-for-esp32/installation)**

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ESP32-DroneBridge-for-ESP32-A-secure-transpare/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/DroneBridge__ESP32.md`.
