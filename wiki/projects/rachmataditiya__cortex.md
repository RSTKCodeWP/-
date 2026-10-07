# Cortex

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rachmataditiya/cortex](https://github.com/rachmataditiya/cortex) |
| Локальна тека | `fpv-library/repos/cortex-ESP32-S3-flight-controller-for-DIY-quadc` |
| У бібліотеці | watch |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-02-19 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

A professional-grade ESP32-S3 flight controller for DIY quadcopter drones, featuring real-time attitude stabilization, DShot ESC control, and wireless command reception. This project pairs with [Synapse](https://github.com/sergiovirahonda/synapse), the transmitter controller that sends flight commands via joystick.

_З README.md, без переказу._

## Для чого

ESP32-S3 flight controller for DIY quadcopters: real-time PID stabilization, DShot ESCs, nRF24 radio, telemetry downlink. Pairs with Synapse TX.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «flight controller».


## Функція

Список із розділу features / можливості в README:

- 🚁 **Real-time Stabilization**: PD controllers for roll/pitch, P controller for yaw
- ⚡ **Native DShot ESC Control**: Direct hardware-level DShot600 protocol via ESP32 RMT
- 📡 **Wireless Communication**: nRF24L01 radio module for low-latency command reception
- 🎯 **MPU6050 Integration**: Hardware DLPF filtering and software calibration for accurate attitude sensing
- 📺 **OLED Telemetry Display**: Real-time flight data on the drone (attitude, throttle, motor outputs, trims)
- 📤 **Radio Telemetry Downlink**: Sends throttle, roll, and pitch back to the transmitter via nRF24 ACK payload (for Synapse display)
- 🔒 **Safety Features**: Arming sequence, throttle limits, and hardware initialization checks
- 🏗️ **Clean Architecture**: Modular design with adapters, models, and controllers
- ⚙️ **PlatformIO Integration**: Modern build system with dependency management
- **Altitude Hold**: BME280 adapter exists (feature-flagged); add altitude PID loop
- **GPS Navigation**: Integrate GPS module for position hold
- **Telemetry Downlink**: Implemented (throttle, roll, pitch via ACK payload); extend `TelemetryPacket` for more fields if Synapse supports it

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `LICENSE`
- `platformio.ini`
- `README.md`
- `src/`

Типи файлів за вибіркою (28 файлів, глибина до 3): C++ (12), C (11), (без суфікса) (2), .ini (1), Markdown (1), JSON (1).

Фрагмент README про будову:

### Software Architecture

```
cortex/
├── src/
│   ├── main.cpp                    # Main control loop & initialization
│   ├── config/
│   │   └── drone_config.*          # PID gains, throttle bands, limits, trim steps
│   ├── controllers/
│   │   └── flight_controller.*     # Throttle stages, mixing matrix, trims, failsafe
│   ├── adapters/
│   │   ├── radio_adapter.*         # nRF24L01: receive commands, send telemetry (ACK payload)
│   │   ├── mpu_adapter.*           # MPU6050 sensor interface
│   │   ├── motor_adapter.*         # DShot ESC control (native)
│   │   └── bmp280_adapter.*        # BME280 barometer (optional, feature-flagged)
│   └── models/
│       ├── attitude.*              # Attitude state & PID (roll/pitch/yaw)
│       ├── drone_command.*         # DronePacket (commands), TelemetryPacket (downlink)
│       ├── motor_output.*          # Motor speed outputs
│       └── ...
└── platformio.ini                  # Build configuration
```

## Що треба

### Prerequisites

1. **PlatformIO**: Install [PlatformIO IDE](https://platformio.org/install/ide?install=vscode) or use the CLI
2. **USB Cable**: For uploading firmware to ESP32-S3
3. **Synapse Transmitter**: Ensure the [Synapse](https://github.com/sergiovirahonda/synapse) transmitter is configured with matching radio address

- Маніфести збірки: PlatformIO (platformio.ini).
- PlatformIO env: `esp32-s3-n16r8`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/sergiovirahonda/cortex.git
   cd cortex
   ```

2. **Install dependencies**
   
   PlatformIO will automatically install required libraries:
   * `RF24` - nRF24L01 radio driver
   * `MPU6050_light` - MPU6050 sensor library
   * `Adafruit SSD1306` - OLED display driver
   * `Adafruit GFX Library` - Graphics library for display

3. **Configure radio address**
   
   Edit `src/main.cpp` to match your Synapse transmitter address:
   ```cpp
   byte NRF_RX_ADDRESS[6] = "00001";  // Must match transmitter address
   ```

4. **Build and upload**
   ```bash
   pio run -t upload
   ```

5. **Monitor serial output**
   ```bash
   pio device monitor
   ```
   
   You should see initialization messages, calibration progress, and arming sequence.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/cortex-ESP32-S3-flight-controller-for-DIY-quadc/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rachmataditiya__cortex.md`.
