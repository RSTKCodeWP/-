# AeroStab

GPS-free optical navigation for **ArduPilot** multicopters.

**Target:** Raspberry Pi Zero 2W + Frank-S01-V1.0 (OV5647) → **PosHold hover without GPS**.

## Product journey

```
Flash SD → install → reboot → http://aerostab.local:8080
  → wizard green (FLIGHT OK) → arm PosHold → hover
```

If tracking is lost mid-flight: **HOLD LAST** (freeze odometry, keep last pose to EKF).

## Install (Pi)

**Quick:** `sudo bash deploy/install_pi.sh && sudo reboot`

**SD bundle (flash-ready):** see [image/README.md](image/README.md) and [docs/FLASH.md](docs/FLASH.md)

```bash
bash image/build_sd_bundle.sh
# extract dist/aerostab-sd-bundle.tar.gz to boot partition
```

1. Open **http://aerostab.local:8080** → tab **Політ** / **Інструкція**
2. Wire UART: Pi TX→FC RX, Pi RX→FC TX, GND, 5V
3. Load `deploy/ardupilot_aerostab.param` (SERIAL2 TELEM2 @ 230400 — change if needed)
4. Arm **PosHold** only when UI shows **FLIGHT OK**

## Web UI

| Tab | Purpose |
|-----|---------|
| **Політ** | First-flight wizard, FLIGHT OK gate |
| **Налаштування** | Full config (camera, MAVLink, altitude, quality, …) |
| **Інструкція** | Built-in docs (`docs/*.md`) |
| **Маска** | ROI mask editor |
| **Перевірки** | Preflight health |

Modular backend: `aerostab/web/` (Flask routes, schema-driven config API).

## Documentation

- [docs/FLASH.md](docs/FLASH.md) — SD card + Pi Imager
- [docs/INSTALL.md](docs/INSTALL.md) — install on Pi
- [docs/WIRE.md](docs/WIRE.md) — UART wiring + ArduPilot params
- [docs/SETTINGS.md](docs/SETTINGS.md) — settings reference
- [FLIGHT.md](FLIGHT.md) — flight card (UA)

## Flight rules

| UI | Meaning |
|----|---------|
| **FLIGHT OK** | Safe to arm PosHold |
| **NAV WAIT** | Waiting for stable track / warmup |
| **HOLD LAST** | Texture lost — position frozen, stay calm / switch AltHold if needed |
| **НЕ АРМИТИ** | Banner — do not arm |

## Features

- Lucas–Kanade optical flow + optional PMW3901 blend
- MAVLink ExternalNav (`VISION_POSITION_ESTIMATE` + `VISION_SPEED_ESTIMATE`)
- Hold-last on quality drop · FOV live update · metric 1 m grid
- Camera mask editor · RTL path · preflight health gate
- SITL mock FC · GitHub CI · flight log analyzer

## Development / CI

```bash
pip install -e .
python3 -m pytest -q
python3 scripts/sitl_hil.py --seconds 5
python3 scripts/sitl_scenarios.py
python3 scripts/simulate.py
python3 scripts/analyze_log.py -d logs
```

## Config highlights

```yaml
altitude:
  source: auto   # rangefinder → baro_relative → relative_alt
quality:
  hold_last_on_drop: true
  nav_valid_warmup_s: 2.0
estimator:
  use_visual_yaw: false   # compass yaw from FC
```

## License

MIT — experimental, not flight-certified. Soft ground, low altitude first.
