# 🛰️ Drone GCS — Autonomous Quadcopter Ground Control Station

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [aaryanvpatil2004-alt/Drone_CGS_Autonomous_Quadcopter_Command_Center](https://github.com/aaryanvpatil2004-alt/Drone_CGS_Autonomous_Quadcopter_Command_Center) |
| Локальна тека | `fpv-library/repos/Drone_CGS_Autonomous_Quadcopter_Command_Center-A-web-based-Ground-Control-Station-GCS-f` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-10 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**A production-grade, web-based Ground Control Station for real Pixhawk hardware and high-fidelity simulation, built on Flask, Flask-SocketIO, and MAVLink.**

Drone GCS is a full-stack telemetry and mission-control system for autonomous quadcopters. It talks to real Pixhawk 2.4.8 flight controllers over MAVLink, or falls back to a physics-aware internal simulation engine when no hardware is present — so the entire stack (mission planning, failsafes, analytics export) can be developed, demoed, and tested without a drone in the room.

_З README.md, без переказу._

## Для чого

A web-based Ground Control Station (GCS) for autonomous quadcopter control and real-time telemetry tracking. Built with a Flask backend and Socket.IO, it integrates MAVLink communication with Pixhawk controllers. Features interactive Leaflet maps for waypoint planning, safety functions like RTL, and structured Excel flight logging.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «flight controller».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A web-based Ground Control Station (GCS) for autonomous quadcopter control and real-time telemetry tracking. Built with a Flask backend and Socket.IO, it integrates MAVLink communication with Pixhawk controllers. Features interactive Leaflet maps for waypoint planning, safety functions like RTL, and structured Excel flight logging.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `app.py`
- `Drone_GCS_Interface/`
- `README.md`
- `requirements.txt`
- `SETUP_GUIDE.md`
- `templates/`

Типи файлів за вибіркою (13 файлів, глибина до 3): .png (4), .jpg (3), Markdown (2), .txt (1), JSON (1), Python (1).

Фрагмент README про будову:

### 🏗️ System Architecture

The backend runs an asynchronous telemetry worker thread that is fully decoupled from the Flask REST layer, so mission-critical polling never blocks on HTTP request handling:

```
┌──────────────────────────────────────┐
│         Web Dashboard (UI)            │
│  (Leaflet.js, Chart.js, Socket.IO)    │
└──────────────────┬────────────────────┘
                    │
     HTTP REST API  │  WebSockets (10Hz)
     & Waypoints     │  Telemetry & Logs
                    ▼
┌──────────────────────────────────────┐
│         Flask Web Server              │
│      & Socket.IO Event Hub            │
└──────────────────┬────────────────────┘
                    │
         Thread-Safe Shared State
                    ▼
┌──────────────────────────────────────┐
│       Telemetry Worker Thread         │
└───────┬──────────────────────┬────────┘
        │                      │
 [Simulation Mode]       [Hardware Mode]
        ▼                      ▼
┌───────────────┐      ┌───────────────┐
│  Kinematic     │      │   PyMavlink   │
│  Simulation    │      │  Connection   │
│    Engine      │      │    Manager    │
└───────────────┘      └───────┬───────┘
                                │  MAVLink v2.0
                                ▼
                        ┌───────────────┐
                        │ Pixhawk 2.4.8 │
                        └───────────────┘
```

**Design highlights:**
- `SimulationEngine` — a self-contained kinematic model handling hover, waypoint-seeking, and RTL flight physics, complete with battery drain curves and sensor noise injection.
- `MAVLinkManager` — manages heartbeats, keepalive polling, arm/disarm ACK verification, mission upload, preflight calibration, and live telemetry parsing (`GLOBAL_POSITION_INT`, `ATTITUDE`, `SYS_STATUS`, `VFR_HUD`, `GPS_RAW_INT`, `STATUSTEXT`, `VIBRATION`).
- A single `telemetry_worker` background thread drives both modes interchangeably and emits a unified `telemetry` packet over Socket.IO at 10Hz.

---

## Що треба

### Prerequisites

- Python **3.11+**

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `flask>=3.0.0`, `flask-socketio>=5.3.6`, `eventlet>=0.35.2`, `pandas>=2.2.0`, `openpyxl>=3.1.2`, `pymavlink>=2.4.41`, `requests>=2.31.0`, `numpy>=1.26.0`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```
> Core packages: `Flask`, `flask-socketio`, `pymavlink`, `pandas`, `openpyxl`. If `pymavlink` isn't installed, the app runs fine in simulation mode.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Drone_CGS_Autonomous_Quadcopter_Command_Center-A-web-based-Ground-Control-Station-GCS-f/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/aaryanvpatil2004-alt__Drone_CGS_Autonomous_Quadcopter_Command_Center.md`.
