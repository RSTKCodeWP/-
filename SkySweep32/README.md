# SkySweep32 | Пассивный детектор БПЛА

**Multi-band passive drone detector | Мультидиапазонный пассивный детектор дронов**

[![CI](https://github.com/bobberdolle1/SkySweep32/actions/workflows/platformio.yml/badge.svg)](https://github.com/bobberdolle1/SkySweep32/actions/workflows/platformio.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform: ESP32](https://img.shields.io/badge/Platform-ESP32-blue.svg)](https://www.espressif.com/en/products/socs/esp32)
[![Build: PlatformIO](https://img.shields.io/badge/Build-PlatformIO-orange.svg)](https://platformio.org/)

[English](#english) | [Русский](#russian)

---

<a name="english"></a>
## 🇬🇧 English

### Overview

SkySweep32 is an advanced passive drone detection system based on the ESP32 microcontroller. It monitors radio spectrum across three frequency bands (900 MHz, 2.4 GHz, 5.8 GHz) to detect UAV control signals and video transmission. **Built with a modular, budget-friendly architecture** — start with a ~$15 base kit and upgrade as needed.

### 📦 Modular Tiers

| Tier | Name | Cost | Includes |
|------|------|------|----------|
| 🟢 **Base** | Starter | ~$15-20 | ESP32 + OLED + NRF24L01+ (2.4 GHz) + Web Dashboard + BLE Remote ID |
| 🟡 **Standard** | Hunter | ~$35-45 | Base + CC1101 (900 MHz) + RX5808 (5.8 GHz) + ML Classification |
| 🔴 **Pro** | Sentinel | ~$60-80 | Standard + GPS + SD Card Logger + LoRa Mesh Network |
| 🟣 **EW Mode** | Juggernaut | ~$100+ | Sentinel + 4x VCO Jamming Modules (5.8G, 2.4G, 900M, 1.5G) |

**Optional add-ons**: 🎤 Acoustic Detection (~$5) | ⚔️ Countermeasures (auth required)

> 📖 **[Full Modular Guide →](docs/en/modules.md)**

### Features

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
- **Remote ID**: FAA ANSI/CTA-2063 compliant BLE drone identification natively on the ESP32.
- **FreeRTOS Architecture**: Safe concurrent processing with hardware Watchdogs and SPI mutexes.

### Hardware Components (Standard Tier)

| Component | Model | Frequency | Purpose |
|-----------|-------|-----------|---------| 
| Microcontroller | ESP32 DevKit | - | Main processor + WiFi + BLE |
| RF Module 1 | CC1101 | 900 MHz | ISM band monitoring |
| RF Module 2 | NRF24L01+ | 2.4 GHz | WiFi/RC monitoring |
| RF Module 3 | RX5808 | 5.8 GHz | Video link monitoring |
| Display | OLED 128x64 (I2C) | - | Visual interface |
| Microphone (optional) | ICS-43434 MEMS | I2S | Acoustic detection |

> 🛠️ **Ready to Build?**
> See the [PCB Assembly Guide (Pro Tier)](docs/en/pcb_assembly.md) for full BOM, KiCad files, and soldering instructions.
> Looking for a case? We have official FreeCAD/STL designs in the [Enclosures Guide](docs/en/enclosures.md).

### Pinout Configuration (Conflict-Free)

#### SPI Bus (Shared)
| Signal | ESP32 Pin |
|--------|-----------|
| MOSI   | GPIO 23   |
| MISO   | GPIO 19   |
| SCK    | GPIO 18   |

#### Chip Select Pins
| Module      | CS Pin    | CE Pin | Tier |
|-------------|-----------|--------|------|
| NRF24L01+   | GPIO 15   | GPIO 2 | Base+ |
| CC1101      | GPIO 5    | -      | Standard+ |
| RX5808      | GPIO 13   | -      | Standard+ |
| LoRa SX1276 | GPIO 14   | -      | Pro (Changed in v0.4) |
| SD Card     | GPIO 27   | -      | Pro |

#### EW Output Pins (Juggernaut)
| Signal | ESP32 Pin | Purpose |
|--------|-----------|---------|
| DAC 1  | GPIO 25   | 5.8GHz / 2.4GHz VCO Sweep |
| DAC 2  | GPIO 26   | 900MHz / 1.5GHz GPS VCO Sweep |
| LORA_R | GPIO 12   | LoRa Reset moved here |

#### I2C Bus (OLED Display)
| Signal | ESP32 Pin |
|--------|-----------|
| SDA    | GPIO 21   |
| SCL    | GPIO 22   |

#### Additional Connections
- **RX5808 RSSI**: GPIO 34 (ADC1_CH6)
- **Power**: 3.3V and GND to all modules

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

### Testing

The protocol parsers (CRSF/MAVLink), which decode untrusted over-the-air input, have
desktop unit tests that build with the host `g++` — no ESP32 toolchain required:

```bash
make -C test/host      # builds with AddressSanitizer/UBSan and runs the suite
```

These run in CI (`.github/workflows/host-tests.yml`) alongside a `cppcheck`
static-analysis pass. See [`test/host/README.md`](test/host/README.md).

### Configuration

#### Enable Countermeasures (REQUIRES LEGAL AUTHORIZATION)

Edit `platformio.ini`:
```ini
build_flags = -DENABLE_COUNTERMEASURES
```

Edit `src/main.cpp`:
```cpp
counterMeasures.armSystem(true);  // Uncomment this line
```

### Legal Notice

⚠️ **WARNING**: Active RF countermeasures (jamming, protocol injection) are **ILLEGAL** in most jurisdictions without explicit authorization from regulatory authorities. Use of these features may result in:

- Criminal prosecution
- Heavy fines
- Equipment confiscation
- Interference with critical communications

**Authorized Use Cases**:
- Military and law enforcement operations
- Critical infrastructure protection (with permits)
- Conflict zones with appropriate authorization
- Research and development in controlled environments

**This project is for educational and authorized defense purposes only.**

### Documentation

- 🍼 **[Absolute Beginner Guide (Start Here)](docs/en/start_from_zero.md)** — No soldering, Lego-style assembly for beginners
- 📘 [Hardware Setup Guide](docs/en/hardware.md) — Advanced wiring & BOM
- 💻 [Software API Reference](docs/en/software.md) — REST & WebSocket APIs
- ⚖️ [Legal Compliance](docs/en/legal.md) — Responsible use

### License

GNU General Public License v3.0 - See [LICENSE](LICENSE) file for details.

---

<a name="russian"></a>
## 🇷🇺 Русский

### Обзор

SkySweep32 — продвинутая система пассивного обнаружения дронов на базе микроконтроллера ESP32. Система мониторит радиоэфир в трех диапазонах (900 МГц, 2.4 ГГц, 5.8 ГГц) для детекции сигналов управления БПЛА и видеопередачи. Включает опциональные возможности активного противодействия для авторизованных оборонных применений.

### Возможности

- **Мультидиапазонное и Спектральное сканирование**: Аппаратный скан эфира на 900 МГц, 2.4 ГГц и 5.8 ГГц диапазонах для детекции пультов, телеметрии и видеолинков.
- **Web-Дашборд и Интерактивная Карта**: Локальный веб-интерфейс по WiFi с картой (Leaflet.js) для трекинга дронов и операторов через Remote ID.
- **Сигнатурная База (Fingerprinting)**: Динамическое распознавание 8 типов дронов (DJI OcuSync, FPV, Crossfire и др.) через анализ дисперсии RSSI и паттернов "прыжков".
- **Своя Mesh-сеть (ESP-NOW)**: Самоорганизующаяся децентрализованная сеть оповещения между детекторами (0 рублей стоимости, использует WiFi чип ESP32).
- **Активный РЭБ (Juggernaut)**: Управление каскадом из 4-х внешних VCO-генераторов (5.8GHz, 2.4GHz, 900MHz, 1.5GHz GPS) через DAC-пины для подавления DJI, Walksnail, BetaFPV, OpenIPC и ELRS.
- **Power Management (Батарея)**: Глубокий сон, скалер частоты ЦП и ADC-отслеживание батареи. Позволяет работать от 18650 днями. Автоматическая калибровка шума из UI.
- **Умная Система Уведомлений**: Неблокирующий диспетчер сигналов для зуммера (Buzzer) и LED с динамическими паттернами под каждый уровень угрозы.
- **Оценка угроз**: 5-уровневая классификация (НЕТ/НИЗКАЯ/СРЕДНЯЯ/ВЫСОКАЯ/КРИТИЧЕСКАЯ).
- **Активное противодействие (опционально, требуется легальная авторизация)**.

### Компоненты (Уровень Hunter)

| Компонент | Модель | Частота | Назначение |
|-----------|--------|---------|------------|
| Микроконтроллер | ESP32 DevKit | - | Основной процессор + WiFi/BLE |
| РЧ-модуль 1 | CC1101 | 900 МГц | Мониторинг ISM-диапазона |
| РЧ-модуль 2 | NRF24L01+ | 2.4 ГГц | Спектральное сканирование / RC |
| РЧ-модуль 3 | RX5808 | 5.8 ГГц | Мониторинг видеолинка |
| Дисплей | OLED 128x64 | - | Визуальный интерфейс |
| Индикация | Passive Buzzer | - | Алерты и ошибки |

> 🛠️ **Готовы к сборке?**
> Смотрите [Руководство по сборке платы (Pro Tier)](docs/ru/pcb_assembly.md) — там полный список деталей (BOM), KiCad проекты и инструкции по пайке.
> Ищете корпус? Официальные 3D-модели (STL) и чертежи находятся в [Руководстве по корпусам](docs/ru/enclosures.md).

### Распиновка (Бесконфликтная)

#### Шина SPI (общая)
| Сигнал | Пин ESP32 |
|--------|-----------|
| MOSI   | GPIO 23   |
| MISO   | GPIO 19   |
| SCK    | GPIO 18   |

#### Пины Chip Select (индивидуальные)
| Модуль      | CS пин    | CE пин (если есть) |
|-------------|-----------|--------------------|
| NRF24L01+   | GPIO 15   | GPIO 2             |
| CC1101      | GPIO 5    | -                  |
| RX5808      | GPIO 13   | -                  |
| LoRa SX1276 | GPIO 14   | -                  |
| SD Card     | GPIO 27   | -                  |

#### Пины генерации помех (Уровень Juggernaut)
| Пин | Функция | 
|-----|---------|
| GPIO 25 | DAC 1 (Шум для 5.8GHz и 2.4GHz VCO) |
| GPIO 26 | DAC 2 (Шум для 900MHz и 1.5GHz GPS VCO) |
| GPIO 12 | LoRa RESET (перенесен с GPIO 25) |

#### Шина I2C (OLED-дисплей)
| Сигнал | Пин ESP32 |
|--------|-----------|
| SDA    | GPIO 21   |
| SCL    | GPIO 22   |

#### Дополнительные подключения (Питание и Алерты)
- **Зуммер (Buzzer)**: GPIO 4
- **LED оповещения**: GPIO 2
- **ADC Батареи (100k/100k)**: GPIO 36
- **RX5808 RSSI**: GPIO 34 (ADC1_CH6)
- **Питание**: 3.3V и GND на все модули (регулятор LDO 1117 обязателен!)

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

### Тестирование

Парсеры протоколов (CRSF/MAVLink), разбирающие недоверенный ввод из эфира, покрыты
юнит-тестами, которые собираются хостовым `g++` — тулчейн ESP32 не нужен:

```bash
make -C test/host      # сборка с AddressSanitizer/UBSan и запуск тестов
```

Они гоняются в CI (`.github/workflows/host-tests.yml`) вместе со статическим
анализом `cppcheck`. Подробнее — [`test/host/README.md`](test/host/README.md).

### Конфигурация

#### Включение противодействия (ТРЕБУЕТСЯ ЛЕГАЛЬНАЯ АВТОРИЗАЦИЯ)

Редактировать `platformio.ini`:
```ini
build_flags = -DENABLE_COUNTERMEASURES
```

Редактировать `src/main.cpp`:
```cpp
counterMeasures.armSystem(true);  // Раскомментировать эту строку
```

### Правовое уведомление

⚠️ **ВНИМАНИЕ**: Активные РЧ-противодействия (глушение, инъекция протоколов) **НЕЗАКОННЫ** в большинстве юрисдикций без явного разрешения регуляторных органов. Использование этих функций может привести к:

- Уголовному преследованию
- Крупным штрафам
- Конфискации оборудования
- Помехам критическим коммуникациям

**Разрешенные случаи использования**:
- Военные и правоохранительные операции
- Защита критической инфраструктуры (с разрешениями)
- Зоны боевых действий с соответствующей авторизацией
- Исследования и разработка в контролируемых условиях

**Этот проект предназначен только для образовательных и авторизованных оборонных целей.**

### Документация

- 🍼 **[Сборка с Абсолютного Нуля (Начни отсюда)](docs/ru/start_from_zero.md)** — Никакой пайки, Лего-сборка для новичков (рядового бойца)
- 📘 [Руководство по аппаратной части](docs/ru/hardware.md) — Инструкция для инженеров с полным BOM
- 💻 [Справочник API ПО](docs/ru/software.md) — Документация REST и WebSocket
- ⚖️ [Правовое соответствие](docs/ru/legal.md) — Правила использования

### Лицензия

Стандартная общественная лицензия GNU v3.0 - См. файл [LICENSE](LICENSE) для деталей.

---

## Contributing | Вклад в проект

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

Приветствуются вклады! Пожалуйста, прочитайте [CONTRIBUTING.md](CONTRIBUTING.md) для деталей.

## Support | Поддержка

- GitHub Issues: [Report bugs](https://github.com/bobberdolle1/SkySweep32/issues)
- Discussions: [Community forum](https://github.com/bobberdolle1/SkySweep32/discussions)

---

**Developed with ❤️ for drone defense research | Разработано с ❤️ для исследований противодроновой защиты**
