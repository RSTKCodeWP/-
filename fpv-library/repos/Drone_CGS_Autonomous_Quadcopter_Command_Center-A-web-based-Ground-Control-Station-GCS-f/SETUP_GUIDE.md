# 🚁 DRONE GCS — Complete Setup \& Hardware Guide

## Autonomous Quadcopter Ground Control Station

\---

## 📋 TABLE OF CONTENTS

1. [What You Get](#what-you-get)
2. [Hardware Requirements](#hardware-requirements)
3. [Hardware Connection Guide](#hardware-connection-guide)
4. [Software Prerequisites](#software-prerequisites)
5. [Installation Steps](#installation-steps)
6. [Running the Application](#running-the-application)
7. [Switching from Simulation to Real Hardware](#switching-from-simulation-to-real-hardware)
8. [Understanding the Dashboard](#understanding-the-dashboard)
9. [Excel Export Explained](#excel-export-explained)
10. [Troubleshooting](#troubleshooting)
11. [Safety Checklist](#safety-checklist)

\---

## 1\. WHAT YOU GET

|File|Purpose|
|-|-|
|`app.py`|Flask + Socket.IO backend server (brain of the GCS)|
|`templates/index.html`|Full tactical dashboard UI (runs in browser)|
|`requirements.txt`|All Python packages needed|
|`SETUP\_GUIDE.md`|This file|

**Features:**

* Real-time telemetry at 10Hz via WebSocket
* Live GPS map (OpenStreetMap + ESRI Satellite)
* Artificial Horizon (ADI) + Compass instruments
* Real-time charts: Altitude, Speed, Battery
* Battery analytics (voltage, current, cell estimate, time remaining)
* Victim detection log with modal alerts (thermal + AI confidence)
* Component health dashboard (GPS, IMU, Baro, Motors, RC, Datalink)
* Vibration analysis (X/Y/Z axes)
* Motor PWM status per motor
* 8-sheet Excel mission export
* Full failure analysis log
* MAVLink real hardware integration (Pixhawk 2.4.8 compatible)
* Simulation mode when no hardware is connected

\---

## 2\. HARDWARE REQUIREMENTS

### 2a. Minimum Laptop/PC Specs

|Component|Minimum|Recommended|
|-|-|-|
|OS|Windows 10 / Ubuntu 20.04 / macOS 12|Windows 11 / Ubuntu 22.04|
|CPU|Intel i5 / Ryzen 5|Intel i7 / Ryzen 7|
|RAM|8 GB|16 GB|
|USB Ports|1 × USB-A or USB-C|2+ USB-A|
|Internet|Required for map tiles|Required|

### 2b. Drone Hardware (for real-hardware mode)

|Component|Details|
|-|-|
|**Flight Controller**|Pixhawk 2.4.8 (ArduCopter firmware ≥ 4.3)|
|**Telemetry Radio**|3DR SiK Radio (433 MHz or 915 MHz), or RFD900x, or SkyDroid|
|**GPS Module**|Ublox Neo-M8N (included with Pixhawk kit)|
|**RC Receiver**|FrSky, FlySky, Spektrum, or SBUS compatible|
|**Battery**|4S LiPo 3300–5200 mAh|
|**USB Cable**|Micro-USB (for direct USB connection)|

\---

## 3\. HARDWARE CONNECTION GUIDE

### 3a. Telemetry Radio (Recommended for GCS)

```
\[Drone Side]                    \[Laptop Side]
Pixhawk TELEM1 port  ←——433/915MHz radio link——→  USB Telemetry Dongle
(6-pin JST-GH)                                    (plugs into USB-A port)
```

**Step-by-step:**

1. Connect the **air-side** 3DR radio to Pixhawk **TELEM1** port using JST-GH cable
2. Connect the **ground-side** 3DR radio dongle to your **laptop's USB-A port**
3. On Windows: Device Manager → Ports → note the COM port (e.g. `COM3`, `COM4`)
4. On Linux/Mac: `ls /dev/tty\*` → note the port (e.g. `/dev/ttyUSB0`, `/dev/cu.usbserial-xxx`)
5. In GCS dashboard, type the port in the **CONNECT HW** field and click the button

**Default baud rate:** `57600` (3DR radios default)

\---

### 3b. Direct USB Connection (USB cable to Pixhawk)

```
Pixhawk USB port (Micro-USB)  ←——USB cable——→  Laptop USB-A port
```

1. Connect Micro-USB cable from Pixhawk to laptop
2. Pixhawk will enumerate as a serial COM port
3. Windows: `COM3` / `COM4` (check Device Manager)
4. Linux: `/dev/ttyACM0` or `/dev/ttyACM1`
5. macOS: `/dev/cu.usbmodem1`
6. Use baud rate `115200` for USB direct connection

\---

### 3c. Connection String Examples

|Connection Type|Windows|Linux|macOS|
|-|-|-|-|
|3DR Radio (57600)|`COM3`|`/dev/ttyUSB0`|`/dev/cu.usbserial-xxx`|
|USB Direct (115200)|`COM4`|`/dev/ttyACM0`|`/dev/cu.usbmodem1`|
|TCP (companion comp.)|`tcp:192.168.1.100:5760`|same|same|
|UDP (SITL)|`udp:127.0.0.1:14550`|same|same|

\---

### 3d. Pixhawk 2.4.8 Port Reference

```
┌─────────────────────────────────────────┐
│           PIXHAWK 2.4.8                │
│                                         │
│  \[USB]  ← Direct laptop connection      │
│  \[TELEM1] ← 3DR Air Radio              │
│  \[TELEM2] ← Optional secondary          │
│  \[GPS]   ← M8N GPS module              │
│  \[RCIN]  ← RC Receiver (SBUS/PPM)      │
│  \[MAIN 1-4] ← ESC signal wires        │
│  \[POWER] ← Power module               │
│  \[I2C]  ← Compass (usually on GPS)    │
└─────────────────────────────────────────┘
```

\---

## 4\. SOFTWARE PREREQUISITES

### 4a. Python Installation

**Windows:**

1. Download Python 3.11+ from https://python.org
2. ✅ Check "Add Python to PATH" during install
3. Verify: open CMD, run `python --version`

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
python3 --version
```

**macOS:**

```bash
brew install python3
python3 --version
```

\---

### 4b. Pixhawk Firmware

* Install **ArduCopter 4.3 or later** via Mission Planner
* Go to: Initial Setup → Install Firmware → Multi-Rotor → Choose ArduCopter

\---

## 5\. INSTALLATION STEPS

### Step 1 — Create Project Folder

```bash
# Windows (CMD or PowerShell)
mkdir C:\\DroneGCS
cd C:\\DroneGCS

# Linux/Mac
mkdir \~/DroneGCS
cd \~/DroneGCS
```

### Step 2 — Copy Project Files

Place these files in your project folder:

```
DroneGCS/
├── app.py
├── requirements.txt
└── templates/
    └── index.html
```

### Step 3 — Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\\Scripts\\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

> You should see `(venv)` at the start of your terminal prompt.

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

Expected output — all packages installed successfully:

```
Successfully installed flask-3.x.x flask-socketio-5.x.x pymavlink-2.x.x pandas-2.x.x ...
```

### Step 5 — Linux/Mac Serial Port Permissions

```bash
# Linux only — add yourself to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in, or run:
newgrp dialout
```

\---

## 6\. RUNNING THE APPLICATION

### Start the Server

```bash
# Make sure virtual environment is active
# Windows:
venv\\Scripts\\activate
# Linux/Mac:
source venv/bin/activate

# Run the server
python app.py
```

**Expected output:**

```
============================================================
  DRONE GCS SERVER STARTING
  Open http://localhost:5000 in your browser
============================================================
 \* Running on http://0.0.0.0:5000
```

### Open the Dashboard

Open your browser and go to:

```
http://localhost:5000
```

> Use \*\*Google Chrome\*\* or \*\*Mozilla Firefox\*\* for best results.
> Do NOT use Internet Explorer.

### Access from Another Device (same WiFi)

Find your laptop's IP:

```bash
# Windows
ipconfig  →  IPv4 Address (e.g. 192.168.1.100)

# Linux/Mac
ifconfig  →  inet addr
```

Then open: `http://192.168.1.100:5000` on any phone/tablet on same network.

\---

## 7\. SWITCHING FROM SIMULATION TO REAL HARDWARE

The app starts in **Simulation Mode** by default.

### To connect real Pixhawk hardware:

1. Connect Telemetry Radio USB dongle to laptop (or USB cable to Pixhawk)
2. Find the COM port (see Section 3)
3. In the GCS top bar, type the port in the **COM3 / /dev/ttyUSB0** field
4. Click **⊕ CONNECT HW**
5. Status badge changes from `SIMULATION` to `MAVLINK LIVE` (amber → blue)
6. All telemetry now streams from real drone

### To switch back to simulation:

* Click **⊘ DISCONNECT**

\---

## 8\. UNDERSTANDING THE DASHBOARD

### Top Header Bar

|Indicator|Meaning|
|-|-|
|🟢 SIMULATION / MAVLINK LIVE|Connection status|
|🟢 GPS 3D FIX|GPS lock quality|
|🟢 EKF OK|Kalman filter health|
|Clock|Real-time system time|

### Mission Control Bar (Top)

|Button|Function|
|-|-|
|▶ ARM|Arms or disarms the drone|
|◈ START MISSION|Begins autonomous waypoint flight|
|⤴ RTL|Return to Launch|
|⊗ ABORT|Abort mission, enter LOITER|
|MODE selector|Change flight mode|
|📊 EXPORT EXCEL|Download full mission report|
|⊕ CONNECT HW|Connect real Pixhawk|

### Left Panel

* Arm status badge, flight mode, altitude tiles
* GPS coordinates, satellites, HDOP
* Artificial Horizon (roll + pitch visualization)
* Compass (heading)
* Vibration analysis per axis

### Center Map

* 🔵 Rotating icon = drone position
* 🟡 H marker = home/launch point
* 🟣 Human icon = detected victim
* Dashed blue line = numbered waypoints
* Solid blue line = actual flight path taken
* Click **🗺 LAYER** to switch satellite/street view

### Right Panel

* Battery: visual meter, voltage, current, consumed mAh, time remaining
* Component health grid (GPS/IMU/Baro/Compass/Battery/Motors/RC/Datalink)
* Motor PWM % per motor (FL/FR/RL/RR)
* Mission progress bar + current waypoint
* Victim detections log with thermal + AI confidence bars
* System event log (timestamped, color-coded by severity)

### Bottom Charts Strip

Real-time scrolling charts:

* Altitude (m) over time
* Ground speed (m/s) over time
* Battery remaining (%) over time

\---

## 9\. EXCEL EXPORT EXPLAINED

Click **📊 EXPORT EXCEL** → downloads `drone\_mission\_YYYYMMDD\_HHMMSS.xlsx`

|Sheet|Contents|
|-|-|
|**Mission Summary**|Date, mode, arm status, flight time, max altitude, victims, firmware, etc.|
|**Telemetry Timeline**|Time-series: altitude, speed, battery%, voltage, current, roll, pitch, climb rate|
|**System Events Log**|All timestamped events with GPS location, mode, battery at each event|
|**GPS Flight Path**|All recorded lat/lon/alt points with timestamps|
|**Victims Detected**|Each victim: coordinates, thermal confidence, AI confidence, timestamp|
|**Waypoints**|All waypoint definitions + whether each was reached|
|**Component Health**|Final health status of each component|
|**Failure Analysis**|Failure mode, component, location, time, battery %, last status text|

### Failure Analysis Sheet

This sheet records:

* **Failure Mode**: e.g. `AUTO\_RTL` (battery triggered), `MISSION\_ABORT`, etc.
* **Failure Component**: e.g. `Battery`, `GPS`, `Motor`
* **Failure Location**: Exact GPS coordinates when failure occurred
* **Battery at Failure**: % remaining when failure triggered
* **Altitude at Failure**: Height when failure occurred
* **Last Status Text**: Final ArduPilot status message before failure

\---

## 10\. TROUBLESHOOTING

### "Port not found" / Cannot connect

```
✅ Check: Is the USB dongle/cable actually plugged in?
✅ Check: Correct port name? (use Device Manager on Windows)
✅ Check: Is another app using the port? (close Mission Planner, QGroundControl)
✅ Linux: Did you run `sudo usermod -a -G dialout $USER`?
```

### Map not loading (blank gray screen)

```
✅ Check internet connection — map tiles load from OpenStreetMap
✅ Try refreshing with Ctrl+F5
✅ Try satellite layer (click 🗺 LAYER)
```

### Charts not updating

```
✅ WebSocket might be disconnected — refresh the browser page
✅ Check server terminal for error messages
```

### `ModuleNotFoundError: No module named 'flask\_socketio'`

```bash
# Make sure venv is active, then:
pip install flask-socketio eventlet
```

### `pymavlink` warning (harmless)

```
If pymavlink is not installed, app works fine in simulation mode.
To enable real hardware: pip install pymavlink
```

### High CPU usage

```
✅ Normal at startup — chart rendering is GPU-accelerated
✅ Close other browser tabs
✅ The 10Hz telemetry loop is by design — reduce if needed in app.py
```

\---

## 11\. SAFETY CHECKLIST

**Before arming the drone:**

* \[ ] Props are **OFF** during bench testing
* \[ ] Battery is charged and checked
* \[ ] All 4 motors spin freely (no obstructions)
* \[ ] GPS fix obtained (14+ satellites, HDOP < 1.5)
* \[ ] EKF status shows GREEN
* \[ ] Component health grid shows all NOMINAL
* \[ ] Battery voltage > 15.0V (4S full = 16.8V)
* \[ ] RC transmitter powered ON and bound
* \[ ] Home location set (drone moved outdoors with GPS lock)
* \[ ] Vibration values < 0.4 on all axes
* \[ ] Wind speed < 8 m/s recommended

**During flight:**

* \[ ] Keep drone in line of sight at all times
* \[ ] Battery warning at 30%, auto-RTL at 15%
* \[ ] Monitor signal strength (should be > 70%)
* \[ ] Always have ABORT button ready

\---

## QUICK START SUMMARY

```bash
# 1. Navigate to project folder
cd DroneGCS

# 2. Activate virtual environment
# Windows:  venv\\Scripts\\activate
# Linux/Mac: source venv/bin/activate

# 3. Start the GCS server
python app.py

# 4. Open browser
# Go to: http://localhost:5000

# 5. (Optional) Connect real hardware
# Plug in telemetry radio → type COM port → click CONNECT HW

# 6. Arm → Start Mission → Monitor → Export Excel after flight
```

\---

*Drone GCS v1.0 | Built with Flask + Socket.IO + Leaflet.js + Chart.js
Compatible with Pixhawk 2.4.8, ArduCopter 4.x, MAVLink 2.0*

