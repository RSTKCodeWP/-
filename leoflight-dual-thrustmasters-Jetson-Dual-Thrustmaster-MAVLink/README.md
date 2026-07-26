# Leoflight

Dual Thrustmaster T.16000M FCS joystick-to-ArduPilot MAVLink bridge with real-time 3D visualization, running on an NVIDIA Jetson.

```
  [T.16000M #1] ──Roll/Pitch/Yaw──┐
                                    ├──→ [Jetson] ──MAVLink──→ [Flight Controller]
  [T.16000M #2] ──Throttle────────┘         │
                                             ↓
                                      [Live Display]
```

## What It Does

Leoflight reads two USB joysticks on an NVIDIA Jetson, maps the inputs through deadband and expo curves, and streams MAVLink `MANUAL_CONTROL` messages at 50 Hz to an ArduPilot flight controller (ARK FPV). A pygame window shows:

- **Joystick inputs** — stick position indicators and throttle bar
- **3D drone model** — tilts in real-time based on FC-commanded attitude
- **FC telemetry** — roll/pitch angles, yaw rate, throttle %, servo outputs, armed state, and flight mode

## Joystick Layout

| Controller | Axes | Role |
|-----------|------|------|
| T.16000M #1 | Stick X, Stick Y, Twist | Roll, Pitch, Yaw |
| T.16000M #2 | Stick Y | Throttle |

**Coordinated turns** are built in — roll input automatically mixes proportional yaw (configurable via `COORD_TURN_FACTOR`).

## Input Processing

```
Raw axis → Invert → Deadband (±5%) → Expo (x^1.5) → Scale to MAVLink range
```

All parameters are tunable in [`config.py`](config.py):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEADBAND` | 0.05 | Dead zone around stick center |
| `EXPO_FACTOR` | 1.5 | Expo curve (1.0 = linear, 2.0 = quadratic) |
| `INVERT_*` | varies | Flip axis direction |
| `SEND_RATE_HZ` | 50 | MAVLink send rate |

## Quick Start

### Prerequisites

- NVIDIA Jetson (tested on Jetson Nano, Linux 4.9.253-tegra)
- ArduPilot flight controller connected via USB-C
- Two Thrustmaster T.16000M FCS joysticks connected via USB
- Python 3.6+ with pygame, pymavlink, pyserial

### Install

```bash
# System dependencies
sudo apt-get install -y python3-pip \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libxml2-dev libxslt1-dev

# Python packages
pip3 install cython
pip3 install -r requirements.txt

# Joystick permissions
sudo usermod -aG input $USER
```

### Run

```bash
# Main application (monitor + bridge + visualization)
DISPLAY=:0 python3 input_monitor.py

# Headless bridge only (no display needed)
python3 leoflight.py

# Diagnostic mode (joystick values only, no FC connection)
python3 leoflight.py --diag
```

### Controls

| Key | Action |
|-----|--------|
| `A` | Toggle arm / disarm |
| `ESC` | Quit (auto-disarms) |

## Files

| File | Description |
|------|-------------|
| [`input_monitor.py`](input_monitor.py) | Main application — bridge + display + 3D visualization |
| [`leoflight.py`](leoflight.py) | Headless bridge (single joystick, no GUI) |
| [`config.py`](config.py) | All tunable parameters |
| [`requirements.txt`](requirements.txt) | Python dependencies |
| [`SETUP_GUIDE.md`](SETUP_GUIDE.md) | Detailed setup guide — network config, Jetson setup, troubleshooting |

## Hardware

| Component | Details |
|-----------|---------|
| Companion computer | NVIDIA Jetson (aarch64) |
| Flight controller | ARK FPV (ArduPilot) |
| Joysticks | 2x Thrustmaster T.16000M FCS |
| FC connection | USB-C (`/dev/ttyACM0`) |

## Flight Controller Setup

The application automatically configures the FC on startup:

1. Disables pre-arm checks (`ARMING_CHECK=0`)
2. Disables battery failsafe (`BATT_FS_LOW_ACT=0`)
3. Sets ACRO flight mode
4. Force arms the vehicle

See [`SETUP_GUIDE.md`](SETUP_GUIDE.md) for the full setup guide including network configuration, SSH setup, deployment from a Mac, and troubleshooting.

## License

MIT
