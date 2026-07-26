# 🛰️ Drone GCS — Autonomous Quadcopter Ground Control Station

**A production-grade, web-based Ground Control Station for real Pixhawk hardware and high-fidelity simulation, built on Flask, Flask-SocketIO, and MAVLink.**

Drone GCS is a full-stack telemetry and mission-control system for autonomous quadcopters. It talks to real Pixhawk 2.4.8 flight controllers over MAVLink, or falls back to a physics-aware internal simulation engine when no hardware is present — so the entire stack (mission planning, failsafes, analytics export) can be developed, demoed, and tested without a drone in the room.

---

## 🎬 Demo / Screenshot

> Add a screenshot or short GIF of the live dashboard here (map view, telemetry HUD, and event log recommended).
> `"D:\B.E. PROJECT\drone_mission_20260621_130230.xlsx"`
> `<img width="1600" height="757" alt="Application_Dashboard_image" src="https://github.com/user-attachments/assets/43dd934e-a4d3-4989-a40c-fa75217f14bb" />`

---

## ✨ Key Features

| Capability | Description |
|---|---|
| **Dual Operational Modes** | Connects to real Pixhawk hardware over USB/telemetry radio via MAVLink, or runs a kinematic Simulation Engine when hardware is absent — same UI, same API, zero code changes. |
| **10Hz Real-Time Telemetry** | Full-duplex WebSocket streaming of attitude, airspeed, groundspeed, vibration, and IMU/baro temperatures to the browser dashboard. |
| **Tactical Mapping** | Interactive Leaflet.js map with OpenStreetMap + ESRI Satellite layers, live drone position, home marker, dashed waypoint path, and solid actual-flight-path trail. |
| **Autonomous Mission Execution** | Multi-waypoint AUTO missions with survey and land actions, real-time progress tracking, and MAVLink mission-protocol upload (`MISSION_COUNT` / `MISSION_REQUEST` / `MISSION_ACK`) for real hardware. |
| **Simulated Search & Rescue** | AI/thermal-vision–style victim detection pipeline that logs simulated targets with GPS coordinates, thermal confidence, and AI confidence scores, broadcast live via Socket.IO. |
| **Failsafe & Safety Systems** | Non-linear 4S LiPo discharge modeling, automatic component-health flags (WARNING/CRITICAL), and automatic RTL (Return-to-Launch) trigger when battery crosses critical thresholds. |
| **8-Sheet Excel Mission Export** | One-click `.xlsx` report: mission summary, telemetry timeline, system events, GPS flight path, victims detected, waypoints, component health, and failure analysis. |
| **Hardware-Grade Command Set** | Arm/disarm with COMMAND_ACK verification, flight-mode switching, preflight calibration (gyro/mag/baro/radio/accel/level), and parameter writes (e.g. failsafe config) over MAVLink. |

---

## 🏗️ System Architecture

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

## 🛠️ Tech Stack

- **Backend:** Python 3.11+, Flask, Flask-SocketIO (threading async mode)
- **Drone Comms:** PyMavlink (MAVLink v2.0)
- **Data/Export:** Pandas, OpenPyXL (8-sheet `.xlsx` mission reports)
- **Frontend:** Leaflet.js (mapping), Chart.js (live telemetry charts), Socket.IO client
- **Transport:** WebSockets (telemetry) + REST (control/mission endpoints)

---

## 💻 Hardware Requirements

### Ground Control Station (Laptop / PC)

| Component | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 / Ubuntu 20.04 / macOS 12 | Windows 11 / Ubuntu 22.04 |
| CPU | Intel i5 / AMD Ryzen 5 | Intel i7 / AMD Ryzen 7 |
| RAM | 8 GB | 16 GB |
| USB | 1× USB-A | 2× USB-A (telemetry + direct) |

### Vehicle / Drone Hardware (real-hardware mode only)

| Component | Spec |
|---|---|
| Flight Controller | Pixhawk 2.4.8, ArduCopter firmware ≥ 4.3 |
| Telemetry Radio | 3DR SiK Radio (433/915 MHz) or RFD900x |
| GPS Module | Ublox Neo-M8N |
| Battery | 4S LiPo + calibrated power module |

> 💡 No drone? No problem — the app boots directly into **Simulation Mode** by default.

---

## 📦 Installation

### Prerequisites
- Python **3.11+**

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/drone-gcs.git
cd drone-gcs
```

### 2. Create a virtual environment
```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```
> Core packages: `Flask`, `flask-socketio`, `pymavlink`, `pandas`, `openpyxl`. If `pymavlink` isn't installed, the app runs fine in simulation mode.

### 4. (Linux only) Grant serial port access
```bash
sudo usermod -a -G dialout $USER
newgrp dialout
```

---

## 🚀 Running the App

```bash
python app.py
```

Then open:
```
http://localhost:5000
```

To access from another device on the same network:
```
http://<YOUR_LAN_IP>:5000
```

Chrome or Firefox recommended.

---

## 🔌 Connecting Real Hardware

The app starts in **Simulation Mode** by default. To switch to a live Pixhawk:

1. Plug in your telemetry radio dongle (or USB cable directly to Pixhawk).
2. Identify the serial port:

| Connection | Windows | Linux | macOS |
|---|---|---|---|
| 3DR Radio (57600 baud) | `COM3` | `/dev/ttyUSB0` | `/dev/cu.usbserial-xxx` |
| USB Direct (115200 baud) | `COM4` | `/dev/ttyACM0` | `/dev/cu.usbmodem1` |
| TCP (companion computer) | `tcp:192.168.1.100:5760` | same | same |
| UDP (SITL) | `udp:127.0.0.1:14550` | same | same |

3. Enter the port in the dashboard's **CONNECT HW** field and click connect.
4. Status badge flips from `SIMULATION` → `MAVLINK LIVE`.

Click **DISCONNECT** at any time to fall back to simulation.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Core connection config and arm state |
| `/api/connect` | POST | Open a MAVLink serial connection (`port`, `baud`) |
| `/api/disconnect` | POST | Close hardware connection, revert to simulation |
| `/api/arm` | POST | Arm/disarm (real hardware waits for `COMMAND_ACK`) |
| `/api/mode` | POST | Change flight mode (`STABILIZE`, `AUTO`, `RTL`, `LOITER`, etc.) |
| `/api/start_mission` | POST | Upload and begin an autonomous waypoint mission |
| `/api/rtl` | POST | Trigger Return-to-Launch |
| `/api/abort` | POST | Immediately abort to LOITER |
| `/api/calibrate` | POST | Run preflight calibration (`gyro`, `mag`, `baro`, `accel`, `radio`, `level`, `all`) |
| `/api/update_waypoints` | POST | Replace the active waypoint list |
| `/api/add_waypoint` | POST | Append a single waypoint |
| `/api/clear_mission` | POST | Reset mission progress and detected victims |
| `/api/telemetry_snapshot` | GET | One-shot telemetry packet |
| `/api/flight_log` | GET | Last 200 mission log entries |
| `/api/victims` | GET | All detected victim records |
| `/api/export_excel` | GET | Download the full 8-sheet mission report |

### Socket.IO Events

| Event | Direction | Payload |
|---|---|---|
| `telemetry` | server → client | Full drone state @ 10Hz |
| `system_event` | server → client | Timestamped, severity-tagged log entry |
| `victim_detected` | server → client | New victim detection record |
| `request_telemetry` | client → server | Requests an immediate snapshot |

---

## 📊 Excel Mission Export

`GET /api/export_excel` generates a timestamped `drone_mission_YYYYMMDD_HHMMSS.xlsx` with 8 sheets:

1. **Mission Summary** — duration, max altitude/speed, waypoints, firmware, GPS fix
2. **Telemetry Timeline** — 1Hz time series (roll/pitch, current, voltage, climb rate)
3. **System Events Log** — full severity-tagged event trace with GPS context
4. **GPS Flight Path** — chronological lat/lon/alt log
5. **Victims Detected** — coordinates, thermal & AI confidence, timestamps
6. **Waypoints** — planned route with reached/unreached status
7. **Component Health** — final GPS/IMU/baro/compass/battery/motor/RC/datalink states
8. **Failure Analysis** — failure mode, component, GPS location, and last status text

---

## 🛡️ Safety & Failsafe Systems

- **Voltage Sag Monitoring** — tracks a non-linear 4S discharge curve; drops below critical voltage trigger automatic RTL.
- **Vibration Envelope** — flags sustained vibration > 0.4 on any axis as a mechanical health concern.
- **Component Health Grid** — live NOMINAL / WARNING / CRITICAL states for GPS, IMU, baro, compass, battery, motors, RC, and datalink.

### Pre-Flight Checklist

- [ ] Props removed for bench testing
- [ ] Battery charged and voltage-checked (4S full ≈ 16.8V)
- [ ] All motors spin freely
- [ ] GPS fix ≥ 14 satellites, HDOP < 1.5
- [ ] EKF status GREEN
- [ ] All component health indicators NOMINAL
- [ ] RC transmitter powered on and bound
- [ ] Home location set outdoors with GPS lock
- [ ] Vibration < 0.4 on all axes
- [ ] Wind speed < 8 m/s

### During Flight

- [ ] Maintain visual line of sight at all times
- [ ] Battery warning at 30%, auto-RTL at 15%
- [ ] Monitor signal strength (> 70%)
- [ ] Keep ABORT ready at all times

---

## 🧩 Project Structure

```
drone-gcs/
├── app.py                 # Flask + Socket.IO backend, MAVLink & simulation engine
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Tactical dashboard UI
└── SETUP_GUIDE.md          # Full hardware + software setup walkthrough
```

---

## 🩺 Troubleshooting

| Issue | Fix |
|---|---|
| "Port not found" / can't connect | Confirm the device is plugged in, port name is correct, and no other app (Mission Planner, QGC) has it open. Linux: rerun `sudo usermod -a -G dialout $USER`. |
| Map not loading | Check internet connectivity (tiles load from OpenStreetMap); try the satellite layer or hard refresh. |
| Charts not updating | WebSocket may have dropped — refresh the browser tab. |
| `ModuleNotFoundError: flask_socketio` | `pip install flask-socketio eventlet` inside the active venv. |
| `pymavlink` warning at startup | Harmless — app runs fine in simulation. Install with `pip install pymavlink` to enable real hardware. |

---

## 🗺️ Roadmap Ideas

- [ ] Multi-vehicle swarm support
- [ ] Persistent mission/telemetry database (SQLite/Postgres)
- [ ] JWT-authenticated multi-user GCS access
- [ ] Real computer-vision victim detection (replacing simulated pipeline)
- [ ] Dockerized deployment

---

## 🤝 Contributing

Issues and pull requests are welcome. If you're extending the MAVLink layer or simulation physics, please include a brief description of testing performed (SITL, real hardware, or simulation-only).

---

## 📄 License

This project is a part of the Final Year B.E. Mechanical Engineering Project executed by Engineering Students for demonstrating the Autonomous Quadcopter Mission planning and controlling, also Analysing the Data Real-time and proving the accuracy of the mission.

---

## 👤 Author

Built by **Aaryan Patil** — engineered for precision, reliability, and automated flight safety.

Compatible with **Pixhawk 2.4.8**, **ArduCopter 4.x**, and **MAVLink 2.0**.
