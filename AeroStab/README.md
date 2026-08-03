# AeroStab

GPS-free optical navigation for **ArduPilot** multicopters.

**Hardware target:** Raspberry Pi Zero 2W + **Frank-S01-V1.0** (OV5647 CSI camera, ~72.4° FOV).

AeroStab estimates ground velocity from downward optical flow, integrates position, and sends **MAVLink `VISION_POSITION_ESTIMATE`** to the flight controller for **PosHold** without GPS.

## Features

- Lucas–Kanade optical flow (Pi Zero friendly)
- MAVLink ExternalNav @ 230400 baud
- Web dashboard on port **8080** (live view + telemetry)
- Frank-S01 / OV5647 camera profile
- Simulation mode for bench testing
- systemd service + one-shot Pi installer
- ArduPilot parameter file included

## Quick start (Raspberry Pi)

### 1. Flash SD card

1. Download [Raspberry Pi OS Lite (64-bit) Bookworm](https://www.raspberrypi.com/software/)
2. Flash with Raspberry Pi Imager
3. Enable SSH, set hostname `aerostab`, user `pi`
4. Boot Pi, copy this repo to `/home/pi/AeroStab`

### 2. Install

```bash
cd AeroStab
sudo bash deploy/install_pi.sh
sudo reboot
```

### 3. Wiring

| Pi Zero 2W | Flight controller |
|------------|-------------------|
| GPIO 14 TX | UART RX |
| GPIO 15 RX | UART TX |
| GND | GND |
| 5V (strong pad) | 5V BEC |

**Camera:** Frank-S01 ribbon into CSI port (contacts toward PCB).

### 4. ArduPilot

Load `deploy/ardupilot_aerostab.param` in Mission Planner.

Set your UART port to **MAVLink2 @ 230400** (see comments in param file).

Flight modes: **PosHold** (primary), **AltHold**, **Stabilize** (fallback).

### 5. Fly

1. Power drone, wait for web UI: `http://<pi-ip>:8080`
2. Check camera view, tracking points (green dots)
3. Calibrate FOV in `/etc/aerostab/config.yaml` if needed (`fov_deg`: 72.4, 120, or 160)
4. Arm in **PosHold**

## Configuration

Main config: `/etc/aerostab/config.yaml` (copied from `config/default.yaml` on install).

```yaml
camera:
  fov_deg: 72.4    # Frank-S01 lens variant
  rotation_deg: 0  # align arrow with drone nose in web UI

mavlink:
  port: /dev/serial0
  baud: 230400
```

## Development (PC / CI)

```bash
cd AeroStab
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
python scripts/simulate.py
python -m aerostab --simulate   # web UI on :8080
```

## FOV calibration

1. Place drone 1 m above floor
2. Enable grid in web UI (or use ruler on floor)
3. Adjust `fov_deg` until 100 cm on ground matches one grid cell in view

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No camera | `libcamera-hello`, check `dtoverlay=ov5647` in config.txt |
| PosHold won't arm | Check MAVLink heartbeat, web UI mavlink=OK |
| Oscillation | Soften `PSC_POSXY_P`, lower PIDs |
| Drift | Increase `RC1_DZ`/`RC2_DZ`, verify FOV |
| No serial | `enable_uart=1`, `dtoverlay=disable-bt`, reboot |

## License

MIT

## Disclaimer

Experimental software. Not flight-certified. Test over soft ground at low altitude first.
