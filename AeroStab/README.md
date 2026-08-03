# AeroStab

GPS-free optical navigation for **ArduPilot** multicopters.

**Hardware target:** Raspberry Pi Zero 2W + **Frank-S01-V1.0** (OV5647 CSI camera, ~72.4° FOV).

AeroStab estimates ground velocity from downward optical flow, integrates position, and sends **MAVLink `VISION_POSITION_ESTIMATE`** to the flight controller for **PosHold** without GPS.

## Features

- Lucas–Kanade optical flow (Pi Zero friendly, ~20 FPS @ 640×480)
- MAVLink ExternalNav @ 230400 baud (`VISION_POSITION_ESTIMATE` + `OPTICAL_FLOW_RAD`)
- **Production web UI** on port **8080** — live view, telemetry, mask editor, settings, preflight health
- **Camera masking** — grid-based ROI editor (hide legs, cables, props from flow)
- **GPS fusion** — optional drift correction when GPS is available at takeoff
- **Quality gating** — MAVLink odometry only when tracking is reliable
- **RTL path recording** — trajectory while armed, saved on disarm, web map
- **PMW3901 / PAA5100** optional SPI flow sensor (blended with camera LK)
- **Flight log analyzer** — CSV → `.aerostab.json` reports
- Visual yaw estimation + FC yaw fusion
- Frank-S01 / OV5647 camera profile
- Simulation mode for bench testing
- systemd service + one-shot Pi installer (Avahi `aerostab.local`)
- ArduPilot parameter files included

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

After reboot open **http://aerostab.local:8080** (or `http://<pi-ip>:8080`).

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

For RTL/failsafe with optical nav, also review `deploy/ardupilot_rtl_failsafe.param`.

Flight modes: **PosHold** (primary), **AltHold**, **Stabilize** (fallback).

### 5. Preflight (web UI)

1. Open **Перевірки** tab — all checks should be green
2. **Маска** tab — click cells covering drone parts visible in camera (legs, arms)
3. **Налаштування** — set FOV (`72.4`, `120`, or `160` for your Frank-S01 lens)
4. Verify live view shows green tracking points on ground texture
5. Arm in **PosHold** only when status shows **NAV OK**

## Web UI

| Tab | Purpose |
|-----|---------|
| Панель | Live MJPEG, FPS, position, velocity, quality, MAVLink status |
| Маска | 16×12 grid mask editor — red cells excluded from optical flow |
| Налаштування | FOV, rotation, FPS, grid overlay, GPS fusion, min quality |
| Перевірки | Preflight health checks (camera, MAVLink, tracking, mask fill) |

## Configuration

Main config: `/etc/aerostab/config.yaml` (copied from `config/default.yaml` on install).

```yaml
camera:
  fov_deg: 72.4    # Frank-S01 lens variant
  rotation_deg: 0  # align arrow with drone nose in web UI

gps_fusion:
  enabled: false     # set true to correct drift when GPS available at arm

mask:
  enabled: true
  path: /etc/aerostab/mask.json

mavlink:
  port: /dev/serial0
  baud: 230400

quality:
  min_quality: 0.25
  min_points_to_send: 8
```

Environment variable `AEROSTAB_CONFIG` overrides config path.

## Development (PC / CI)

```bash
cd AeroStab
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m pytest -q
python3 scripts/simulate.py
python3 -m aerostab --simulate   # web UI on :8080
```

### SITL / HIL testing (no hardware)

Mock MAVLink flight controller over TCP (no ArduPilot build required):

```bash
python3 scripts/sitl_hil.py --seconds 8   # integration self-test
python3 scripts/sitl_scenarios.py         # arm/disarm + RTL scenarios
python3 scripts/start_sitl_bench.sh       # mock FC + AeroStab with web UI
python3 -m aerostab --sitl                # same config via CLI flag
```

Full ArduPilot SITL (optional, requires build):

```bash
bash scripts/ardupilot_sitl.sh
```

Config: `config/sitl.yaml` — synthetic camera + `tcp:127.0.0.1:5760` MAVLink.

CI runs on push (`.github/workflows/aerostab-ci.yml`): pytest, SITL HIL, scenarios, simulate.

### Flight log analysis

```bash
python3 scripts/analyze_log.py logs/20260803_002240.csv
# or latest:
python3 -m aerostab.log_analyzer -d logs
```

### Optional PMW3901 sensor

Enable in `/etc/aerostab/config.yaml`:

```yaml
pmw3901:
  enabled: true
  chip: pmw3901   # or paa5100
  blend_weight: 0.35
```

Wire SPI (Pi Zero 2W): MOSI/MISO/SCK/CS, 3.3V. Install: `pip install pmw3901`.
Patterns adapted from [Pimoroni pmw3901-python](https://github.com/pimoroni/pmw3901-python).

## FOV calibration

1. Place drone 1 m above floor
2. Enable grid in web UI (Налаштування → Сітка FOV)
3. Adjust `fov_deg` until 100 cm on ground matches one grid cell in view

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No camera | `libcamera-hello`, check `dtoverlay=ov5647` in config.txt |
| PosHold won't arm | Check MAVLink heartbeat, web UI mavlink=OK, all health checks green |
| NAV WAIT | Improve ground texture, reduce altitude oscillation, tune mask |
| Oscillation | Soften `PSC_POSXY_P`, lower PIDs |
| Drift | Enable GPS fusion, increase `RC1_DZ`/`RC2_DZ`, verify FOV |
| No serial | `enable_uart=1`, `dtoverlay=disable-bt`, reboot |

## Architecture

```
Camera → Optical Flow → Odometry → [GPS Fusion] → MAVLink → ArduPilot EKF
              ↑
         Camera Mask (ignore drone parts)
```

## License

MIT

## Disclaimer

Experimental software. Not flight-certified. Test over soft ground at low altitude first.
