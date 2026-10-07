# Meshtastic Drone Swarm Telemetry & Control

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [AkitaEngineering/Meshtastic-Integration-for-DroneBridge32-Swarm](https://github.com/AkitaEngineering/Meshtastic-Integration-for-DroneBridge32-Swarm) |
| Локальна тека | `fpv-library/repos/Meshtastic-Integration-for-DroneBridge32-Swarm-This-project-provides-a-comprehensive-fr` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `ai` |
| Зірки (каталог) | 15 |
| Оновлено upstream | 2026-07-17 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This project provides a comprehensive framework for integrating Meshtastic mesh networking with DroneBridge32 for telemetry and control of a drone swarm. It encompasses features like swarm coordination, geofencing, emergency landing, data logging, visualization, dynamic channel switching, AI integration (conceptual), encryption, and fail-safes.

_З README.md, без переказу._

## Для чого

This project provides a comprehensive framework for integrating Meshtastic mesh networking with DroneBridge32 for telemetry and control of a drone swarm. It encompasses features like swarm coordination, geofencing, emergency landing, data logging, visualization, dynamic channel switching, AI integration (conceptual), encryption, and fail-safes.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «flight controller».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `control`, `drone`, `dronebridge`, `mesh-networks`, `meshtatic`, `swarm`, `telemetry`.

## Функція

Список із розділу features / можливості в README:

- **Decentralized Control:** Operate your drone swarm over a resilient Meshtastic mesh network.
- **Encrypted Communication:** Secure communication using AES encryption.
- **Telemetry:** Real-time data including position, altitude, and battery voltage.
- **Control:** Commands for individual drones or the entire swarm.
- **MAVLink Integration:** Seamlessly works with MAVLink for flight controller communication.
- **Geofencing:** Prevents drones from entering restricted areas.
- **Emergency Landing:** Robust emergency landing protocol.
- **Data Logging:** Logs telemetry data for post-flight analysis.
- **Map Visualization:** Interactive map display of drone locations.
- **Dynamic Channel Switching:** Adapts to network conditions.
- **AI Integration (Conceptual):** Provides a framework for AI-driven insights.
- **Fail-Safes:** Signal loss and low battery protections.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CMakeLists.txt`
- `gcs_app.py`
- `LICENSE`
- `main/`
- `meshtastic_control.py`
- `meshtastic_crypto.py`
- `meshtastic_telemetry.py`
- `provisioning_pubkey.h`
- `qa_simulator.py`
- `README.md`
- `requirements-dev.txt`
- `requirements.txt`
- `scripts/`
- `templates/`
- `tests/`
- `use_cases.md`

Типи файлів за вибіркою (29 файлів, глибина до 3): Python (15), .txt (4), (без суфікса) (3), Markdown (2), C (1), JSON (1).


## Що треба

- Маніфести збірки: Python (requirements.txt), CMake.
- requirements.txt: `cryptography`, `flask`, `meshtastic`, `pyserial`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

1.  **ESP32 Firmware Integration (ESP-IDF):**
    *   Install the Espressif IoT Development Framework (ESP-IDF).
    *   Compile and flash the firmwware using `idf.py build` and `idf.py flash monitor`.
    *   Ensure MAVLink TX/RX is wired to `Serial2` (Pins 16/17) and Meshtastic to `Serial1` (Pins 4/5).
2.  **Meshtastic Node:**
    * Connect a Meshtastic-compatible device to your drone.
    * Configure the network settings.
3.  **Ground Control Station:**
    *   Install Python dependencies: `pip install -r requirements.txt`
    *   Start the server: `python gcs_app.py`
### Usage

1.  **Launch Web App:** Run `python gcs_app.py` in your terminal.
2.  **Open Dashboard:** Navigate to `http://localhost:5000` in your web browser.
3.  **Monitor & Control:** Observe real-time telemetry on the live map and use the control panels to send commands.

For app-level QA without radios or ESP-IDF hardware, run:

```bash
MESHTASTIC_FAKE=1 MESHTASTIC_API_TOKEN=qa-token python gcs_app.py
```

The fake interface emits encrypted telemetry and encrypted command ACKs through the same Python receive path as the real Meshtastic interface.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Meshtastic-Integration-for-DroneBridge32-Swarm-This-project-provides-a-comprehensive-fr/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/AkitaEngineering__Meshtastic-Integration-for-DroneBridge32-Swarm.md`.
