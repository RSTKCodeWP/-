# MAVLink ELRS Backpack TX <-> Serial Forwarder (ESP32)

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [BartlomiejZalas/mavlink-backpack-esp-serial-forwarder](https://github.com/BartlomiejZalas/mavlink-backpack-esp-serial-forwarder) |
| Локальна тека | `fpv-library/repos/mavlink-backpack-esp-serial-forwarder-A-MAVLink-packet-forwarder-bridging-Expr` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `bridge`, `radio`, `elrs` |
| Зірки (каталог) | 3 |
| Оновлено upstream | 2025-09-07 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A MAVLink packet forwarder bridging ExpressLRS Backpack TX and a serial port (USB), built on the ESP32 platform. This project enables MAVLink packet forwarding between the ELRS TX Backpack and a serial port in both directions using internal built-in ELRS module.

It allows you to connect a UAV to a GCS via USB using the MAVLink protocol. This may be helpful when a WiFi connection is not suitable (multiple UAV connections,the GCS device lacks WiFi support, etc.).

_З README.md, без переказу._

## Для чого

A MAVLink packet forwarder bridging ExpressLRS Backpack TX and a serial port (USB), built on the ESP32 platform. This project enables MAVLink packet forwarding between the ELRS TX Backpack and a serial port in both directions using internal built-in ELRS module. It allows you to connect a UAV to a GCS via USB using the MAVLink protocol.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «expresslrs».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A MAVLink packet forwarder bridging ExpressLRS Backpack TX and a serial port (USB), built on the ESP32 platform. This project enables MAVLink packet forwarding between the ELRS TX Backpack and a serial port in both directions using internal built-in ELRS module. It allows you to connect a UAV to a GCS via USB using the MAVLink protocol.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `doc/`
- `platformio.ini`
- `README.md`
- `src/`

Типи файлів за вибіркою (19 файлів, глибина до 3): C++ (6), C (5), .png (4), .ini (1), Markdown (1), JSON (1).


## Що треба

### Hardware Requirements

- ESP32-based development board (e.g., ESP32 DevKit, TTGO T-Beam, etc.)
- ExpressLRS TX device with Backpack functionality (with an ELRS internal module)
- Flight controller firmware with bidirectional MAVLink support (Command and Control, e.g., ArduPilot)

- Маніфести збірки: PlatformIO (platformio.ini).
- PlatformIO env: `esp32dev`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### ESP32 Setup

1. Clone the repo.  
2. Build and upload the software to the ESP32 device ([guide](https://docs.platformio.org/en/stable/tutorials/espressif32/arduino_debugging_unit_testing.html#compiling-and-uploading-the-firmware)).  
3. Make sure that the Backpack TX WiFi network is enabled.  
4. About 30 seconds after upload, the device should start a WiFi access point (SSID: `MAVLink Serial Forwarder`, password: `mavlink123`). Connect to it and open `10.10.0.1` in your browser.  
5. Configure the Backpack SSID (e.g., `ExpressLRS TX Backpack xxx`, where `xxx` is part of your UID) and password (usually `expresslrs`).  
6. Click `Save & Reboot`.  
7. The device will reboot. If the WiFi connection to the Backpack is successful, the LED will start blinking.  
8. The device is ready to be connected to the GCS. Use USB as the connection type in your GCS.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/mavlink-backpack-esp-serial-forwarder-A-MAVLink-packet-forwarder-bridging-Expr/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/BartlomiejZalas__mavlink-backpack-esp-serial-forwarder.md`.
