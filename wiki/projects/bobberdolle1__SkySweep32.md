# SkySweep32 | Пассивный детектор БПЛА

> Картка виставки. Зал: [Виявлення](../halls/detection.md).

Каталог тримає категорію `other`. Зал «Виявлення» поставлено, бо в назві, описі або шляху є «детектор».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [bobberdolle1/SkySweep32](https://github.com/bobberdolle1/SkySweep32) |
| Локальна тека | `SkySweep32-ESP32-Drone-Detector` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

**Multi-band passive drone detector | Мультидиапазонный пассивный детектор дронов**

_З README.md, без переказу._

## Для чого

**Multi-band passive drone detector | Мультидиапазонный пассивный детектор дронов**

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «elrs».
- Розробник відеотракту — у тексті є «openipc».


## Функція

Список із розділу features / можливості в README:

- **Multi-band RF & Spectrum Scanning**: Hardware sweeping across 900 MHz, 2.4 GHz, and 5.8 GHz bands checking for analog and digital drone links.
- **Web Dashboard & Map**: Real-time dark-themed dashboard via WiFi with Leaflet.js interactive map, drone lists, and RSSI graphs.
- **Signal Fingerprinting**: Built-in `SignalDatabase` identifying known drone patterns (e.g., DJI OcuSync, FPV Analog, Crossfire) via band-matching and RSSI variance.
- **ESP-NOW Mesh**: Free, autonomous node-to-node network sharing threat alerts, heartbeats, and GPS telemetry across massive areas without extra hardware.
- **Power Management**: 4 dynamic power states (Full, Balanced, Low, Deep Sleep) with battery ADC monitoring and runtime estimates.
- **Countermeasures (Juggernaut)**: Optional VCO signal injection covering DJI, Walksnail, OpenIPC, ELRS, and GPS Denial.
- **ATAK Integration (Cursor on Target)**: Native UDP broadcast of CoT packets to the Android Team Awareness Kit, showing drone targets and operator heading on tactical maps.
- **Hardware Compass (QMC5883L)**: Direction finding via I2C magnetometer, calculating the vector of incoming drone signals.
- **TinyML AI Classification**: TensorFlow Lite for Microcontrollers engine for predicting drone classes (DJI, FPV, etc.) based on RSSI variance and multi-band tensors.
- **Stealth Mode (Dark Mode)**: Hardware/Software toggle to instantly disable OLED and buzzers, transferring all alerts to a covert vibration motor.
- **Auto-Calibration Tool**: Integrated baseline noise calibration directly from the Web-UI.
- **Alert System**: Non-blocking intelligent Buzzer and LED patterns scaling with Threat Levels (Info → Critical).

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/`
- `flash.bat`
- `hardware/`
- `LICENSE`
- `lua/`
- `platformio.ini`
- `README.md`
- `scripts/`
- `src/`
- `test/`
- `TODO.md`

Типи файлів за вибіркою (96 файлів, глибина до 3): C (24), Markdown (23), C++ (23), (без суфікса) (6), .png (5), Lua (4).

Фрагмент README про будову:

### Software Architecture

```
src/
├── main.cpp                    # FreeRTOS tasks & app orchestration
├── config.h                    # Central config: tiers, pins, feature flags
├── config_manager.h/cpp        # Runtime JSON config (SPIFFS)
├── spi_manager.h/cpp           # Thread-safe shared-SPI bus (mutex)
├── power_manager.h/cpp         # Power modes, battery ADC, deep sleep
├── alert_manager.h/cpp         # Non-blocking buzzer/LED alert patterns
├── countermeasures.h/cpp       # Threat assessment + optional EW (Juggernaut)
├── signal_database.h/cpp       # Drone signal fingerprinting
├── espnow_mesh.h/cpp           # ESP-NOW node-to-node mesh alerts
├── web_server.h/cpp            # WiFi AP, dashboard, REST + WebSocket
├── remote_id_detector.h/cpp    # BLE Remote ID scanner
├── ml_classifier.h/cpp         # Drone classification (rules + TFLite)
├── model_data.h                # TinyML model blob
├── gps_module.h/cpp            # GPS (NEO-6M/7M)            [Pro]
├── data_logger.h/cpp           # SD-card forensic logging   [Pro]
├── meshtastic_client.h/cpp     # LoRa mesh + trilateration  [Pro]
├── atak_client.h/cpp           # ATAK Cursor-on-Target UDP  [optional]
├── compass_module.h/cpp        # QMC5883L direction finding [optional]
├── acoustic_detector.h/cpp     # I2S MEMS acoustic detection[optional]
├── drivers/
│   ├── cc1101.h/cpp            # CC1101 900 MHz driver
│   ├── nrf24l01.h/cpp          # NRF24L01+ 2.4 GHz driver
│   └── rx5808.h/cpp            # RX5808 5.8 GHz driver
└── protocols/
    ├── mavlink_parser.h/cpp    # MAVLink protocol decoder
    └── crsf_parser.h/cpp       # CRSF/ExpressLRS decoder

test/host/                      # Desktop unit tests (g++ + ASan/UBSan)
```
### Архитектура ПО

```
src/
├── main.cpp                    # Задачи FreeRTOS и оркестрация приложения
├── config.h                    # Центральный конфиг: уровни, пины, флаги функций
├── config_manager.h/cpp        # Runtime JSON-конфиг (SPIFFS)
├── spi_manager.h/cpp           # Потокобезопасная общая шина SPI (мьютекс)
├── power_manager.h/cpp         # Режимы питания, ADC батареи, глубокий сон
├── alert_manager.h/cpp         # Неблокирующие паттерны зуммера/LED
├── countermeasures.h/cpp       # Оценка угроз + опциональный РЭБ (Juggernaut)
├── signal_database.h/cpp       # Сигнатурная база дронов
├── espnow_mesh.h/cpp           # Mesh-оповещения ESP-NOW между узлами
├── web_server.h/cpp            # WiFi AP, дашборд, REST + WebSocket
├── remote_id_detector.h/cpp    # Сканер BLE Remote ID
├── ml_classifier.h/cpp         # Классификация дронов (правила + TFLite)
├── model_data.h                # Блоб модели TinyML
├── gps_module.h/cpp            # GPS (NEO-6M/7M)             [Pro]
├── data_logger.h/cpp           # Логирование на SD-карту     [Pro]
├── meshtastic_client.h/cpp     # LoRa mesh + трилатерация    [Pro]
├── atak_client.h/cpp           # ATAK Cursor-on-Target UDP   [опц.]
├── compass_module.h/cpp        # QMC5883L пеленгация          [опц.]
├── acoustic_detector.h/cpp     # Акустика I2S MEMS            [опц.]
├── drivers/
│   ├── cc1101.h/cpp            # Драйвер CC1101 900 МГц
│   ├── nrf24l01.h/cpp          # Драйвер NRF24L01+ 2.4 ГГц
│   └── rx5808.h/cpp            # Драйвер RX5808 5.8 ГГц
└── protocols/
    ├── mavlink_parser.h/cpp    # Декодер протокола MAVLink
    └── crsf_parser.h/cpp       # Декодер CRSF/ExpressLRS

test/host/                      # Юнит-тесты на хосте (g++ + ASan/UBSan)
```

## Що треба

- Маніфести збірки: PlatformIO (platformio.ini).
- PlatformIO env: `esp32dev_base`, `esp32dev_standard`, `esp32dev_pro`, `esp32dev_full`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build Instructions

```bash
# Clone repository
git clone https://github.com/bobberdolle1/SkySweep32.git
cd SkySweep32

# Build firmware
pio run

# Upload to ESP32
pio run --target upload

# Monitor serial output
pio device monitor
```
### Инструкции по сборке

```bash
# Клонировать репозиторий
git clone https://github.com/bobberdolle1/SkySweep32.git
cd SkySweep32

# Собрать прошивку
pio run

# Загрузить на ESP32
pio run --target upload

# Мониторинг Serial
pio device monitor
```

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../SkySweep32-ESP32-Drone-Detector/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `SkySweep32-ESP32-Drone-Detector/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/bobberdolle1__SkySweep32.md`.
