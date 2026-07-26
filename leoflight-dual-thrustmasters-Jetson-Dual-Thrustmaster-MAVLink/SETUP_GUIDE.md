# Leoflight Setup Guide

A Thrustmaster T.16000M FCS dual-joystick to ArduPilot MAVLink bridge, running on an NVIDIA Jetson connected to an ARK FPV flight controller.

## Table of Contents

1. [Hardware Overview](#hardware-overview)
2. [Network Setup: Mac to Jetson](#network-setup-mac-to-jetson)
3. [Jetson Software Installation](#jetson-software-installation)
4. [Deploying Leoflight to the Jetson](#deploying-leoflight-to-the-jetson)
5. [Running the Application](#running-the-application)
6. [Joystick Mapping](#joystick-mapping)
7. [Flight Controller Configuration](#flight-controller-configuration)
8. [Architecture & How It Works](#architecture--how-it-works)
9. [Troubleshooting](#troubleshooting)

---

## Hardware Overview

| Component | Details |
|-----------|---------|
| Companion computer | NVIDIA Jetson (hostname: `jetsonDoodle`), Linux 4.9.253-tegra aarch64 |
| Flight controller | ARK FPV running ArduPilot |
| Joysticks | 2x Thrustmaster T.16000M FCS |
| Connection: Mac ↔ Jetson | Direct Ethernet (IPv6 link-local) |
| Connection: Jetson ↔ FC | USB-C (shows as `/dev/ttyACM0`, `/dev/ttyACM1`) |
| Connection: Joysticks ↔ Jetson | USB (show as `/dev/input/js0`, `/dev/input/js1`) |

### Wiring Diagram

```
  [Mac] ──ethernet──> [Jetson] ──USB-C──> [ARK FPV FC]
                          │
                          ├── USB ── [T.16000M #1 (Roll/Pitch/Yaw)]
                          └── USB ── [T.16000M #2 (Throttle)]
```

---

## Network Setup: Mac to Jetson

The Jetson is connected to the Mac via a direct Ethernet cable. Communication uses IPv6 link-local addressing.

### Discovering the Jetson

The Jetson was found at IPv6 link-local address `fe80::4ab0:2dff:fed3:ef8a` on Mac interface `en16`.

Discovery method:
```bash
# Ping all IPv6 link-local hosts on the Ethernet interface
ping6 ff02::1%en16
```

### SSH Configuration

An SSH config was saved to `~/.ssh/config` on the Mac:

```
Host jetson
    HostName fe80::4ab0:2dff:fed3:ef8a%en16
    User jetson
    StrictHostKeyChecking no
```

SSH credentials: `jetson` / `test1234`

Quick SSH access:
```bash
ssh jetson
# or with sshpass for scripted access:
sshpass -p 'test1234' ssh jetson@"fe80::4ab0:2dff:fed3:ef8a%en16"
```

### Internet Sharing (Mac → Jetson)

The Jetson needs internet access (via the Mac) to install packages. The Mac acts as a NAT gateway.

**On the Mac** (requires sudo):

1. Assign an IP on the Jetson's subnet to the Mac's Ethernet interface:
   ```bash
   sudo ifconfig en16 10.223.0.1 netmask 255.255.0.0 up
   ```

2. Enable IP forwarding:
   ```bash
   sudo sysctl -w net.inet.ip.forwarding=1
   ```

3. Enable NAT via pfctl:
   ```bash
   echo 'nat on en0 from 10.223.0.0/16 to any -> (en0)' | sudo pfctl -ef -
   ```
   (Where `en0` is the Mac's internet-facing interface, e.g. Wi-Fi.)

**On the Jetson:**

1. Add the Mac as the default gateway:
   ```bash
   sudo ip route add default via 10.223.0.1
   ```

2. Set DNS:
   ```bash
   echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf
   ```

3. Verify:
   ```bash
   ping -c 2 8.8.8.8
   ping -c 2 google.com
   ```

> **Note:** The Jetson's default route and DNS are lost on reboot. Re-run the Jetson-side commands after each reboot.

---

## Jetson Software Installation

The Jetson runs Python 3.6.9. The following packages are needed.

### System dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libxml2-dev libxslt1-dev
```

### Python packages

```bash
pip3 install cython
pip3 install pygame==2.6.1 pymavlink==2.4.40 pyserial==3.5
```

Cython must be installed first because pymavlink needs it during build.

### Joystick permissions

Add the `jetson` user to the `input` group so it can read joystick devices:

```bash
sudo usermod -aG input jetson
```

Log out and back in (or reboot) for this to take effect.

---

## Deploying Leoflight to the Jetson

### Project files

The project lives at `~/leoflight/` on the Jetson. The key files are:

| File | Purpose |
|------|---------|
| `config.py` | Axis mapping, deadband, expo, serial port, button assignments |
| `input_monitor.py` | Main application: combined bridge + visual monitor + 3D drone visualization |
| `leoflight.py` | Original headless bridge (single joystick, no GUI) |
| `requirements.txt` | Python dependencies |

### Deploying from the Mac

```bash
# Copy a single file
sshpass -p 'test1234' scp -6 input_monitor.py \
    "jetson@[fe80::4ab0:2dff:fed3:ef8a%en16]:~/leoflight/"

# Copy all project files
sshpass -p 'test1234' scp -6 *.py requirements.txt \
    "jetson@[fe80::4ab0:2dff:fed3:ef8a%en16]:~/leoflight/"
```

> Note the bracket syntax `[IPv6%iface]` required for SCP with IPv6 link-local addresses.

---

## Running the Application

### Starting the monitor + bridge

The application requires a display. Launch it from SSH with `DISPLAY=:0`:

```bash
# Interactive (output visible in terminal):
DISPLAY=:0 python3 /home/jetson/leoflight/input_monitor.py

# Background (survives SSH disconnect):
DISPLAY=:0 nohup python3 -u /home/jetson/leoflight/input_monitor.py \
    >/tmp/input_monitor.log 2>&1 &
```

### Stopping the application

```bash
# From the Jetson display: press [ESC] or close the window
# From SSH:
echo 'test1234' | sudo -S killall python3
```

### Viewing logs

```bash
tail -f /tmp/input_monitor.log
```

### Running the headless bridge (no display)

For eventual headless operation:
```bash
python3 /home/jetson/leoflight/leoflight.py
python3 /home/jetson/leoflight/leoflight.py --diag  # Diagnostic: joystick only
```

---

## Joystick Mapping

### Dual joystick setup

Two T.16000M controllers are used. The pygame joystick indices determine which physical controller is which:

| Pygame Index | Role | Axes Used |
|-------------|------|-----------|
| Joystick 1 (`js_rp`) | Roll, Pitch, Yaw | Axis 0 = Roll, Axis 1 = Pitch, Axis 2 = Yaw (twist) |
| Joystick 0 (`js_ty`) | Throttle | Axis 1 (stick Y) = Throttle |

> If only one joystick is detected, it is used for all axes (fallback mode).

### Axis configuration (config.py)

```
AXIS_ROLL     = 0   # Stick X
AXIS_PITCH    = 1   # Stick Y
AXIS_YAW      = 2   # Twist Z
AXIS_THROTTLE = 3   # Throttle slider

INVERT_ROLL     = False
INVERT_PITCH    = False
INVERT_YAW      = False
INVERT_THROTTLE = True
```

### Input processing pipeline

1. **Raw axis** → value in [-1.0, +1.0] from pygame
2. **Inversion** → flips sign if configured
3. **Deadband** (0.05) → values within ±5% of center become zero; remainder is rescaled to full range
4. **Expo** (1.5) → softens response near center (`output = |input|^1.5 * sign`)
5. **MAVLink scaling** → Roll/Pitch/Yaw: [-1000, +1000], Throttle: [0, 1000]

### Coordinated turns

Roll-to-yaw mixing is enabled. When the roll stick is deflected, proportional yaw is automatically added to keep turns coordinated.

```
COORD_TURN_FACTOR = 0.5   # 0.0 = off, 1.0 = full mixing
mav_yaw = manual_yaw + (mav_roll * COORD_TURN_FACTOR)
```

This is set in `input_monitor.py` line 432 and can be changed to 0.0 to disable.

### Keyboard controls

| Key | Action |
|-----|--------|
| `A` | Toggle arm/disarm (force arm) |
| `ESC` | Quit and disarm |

---

## Flight Controller Configuration

### Parameters set at startup

The application automatically configures the FC on each launch:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `ARMING_CHECK` | 0 | Disables all pre-arm safety checks (EKF, compass, battery, etc.) |
| `BATT_FS_LOW_ACT` | 0 | Disables battery failsafe (no battery connected in bench testing) |
| Flight mode | ACRO (1) | Set before arming via `set_mode_send` |
| Arm | Force arm | Uses param2=21196 to bypass remaining checks |

### Startup sequence

1. Connect to FC via serial (`/dev/ttyACM0` auto-detected)
2. Wait for heartbeat
3. Set `ARMING_CHECK=0` and `BATT_FS_LOW_ACT=0`
4. Request all data streams at 10 Hz
5. Set ACRO mode
6. Force arm
7. Start pygame display and main loop
8. Auto-retry arming every 5 seconds if FC disarms

### MAVLink messages used

**Sent to FC:**
- `MANUAL_CONTROL` at 50 Hz (pitch, roll, throttle, yaw)
- `COMMAND_LONG` for arm/disarm and mode changes
- `PARAM_SET` for disabling pre-arm checks

**Received from FC:**
- `HEARTBEAT` — armed state, flight mode
- `SERVO_OUTPUT_RAW` — motor output values (displayed in UI)
- `NAV_CONTROLLER_OUTPUT` — FC desired roll/pitch angles (drives 3D visualization)
- `VFR_HUD` — throttle percentage

### ArduPilot flight mode numbers

| Mode | Number |
|------|--------|
| STABILIZE | 0 |
| ACRO | 1 |
| ALT_HOLD | 2 |
| LOITER | 5 |
| LAND | 9 |

---

## Architecture & How It Works

### Data flow

```
[Joystick 1] ──axis 0,1,2──┐
                             ├─→ [input_monitor.py] ─── MANUAL_CONTROL ──→ [FC]
[Joystick 2] ──axis 1──────┘         │    ↑
                                      │    │
                                      │    └── HEARTBEAT, SERVO_OUTPUT_RAW,
                                      │        NAV_CONTROLLER_OUTPUT, VFR_HUD
                                      ↓
                               [Pygame Display]
                               ┌─────────────────────────┐
                               │ Stick viz | 3D Drone | FC│
                               │  R/P  Yaw | (tilts)  |Out│
                               │  Thr      |          |   │
                               └─────────────────────────┘
```

### Display layout (1024x600)

- **Left panel:** Joystick input visualization — two stick indicators (Roll/Pitch and Yaw) plus a throttle bar
- **Center panel:** 3D drone visualization that tilts based on FC-commanded angles (from `NAV_CONTROLLER_OUTPUT`). Yaw is accumulated from the commanded yaw rate. Prop discs scale with throttle.
- **Right panel:** FC output gauges (Roll, Pitch, Yaw rate, Throttle percentage) and raw servo values (M1-M4)
- **Header:** "LEOFLIGHT" title, armed/disarmed status, flight mode, connection indicator

### 3D visualization details

The drone is rendered with perspective projection from a ~30-degree top-down viewing angle. The attitude is derived from:

- **Roll/Pitch:** `NAV_CONTROLLER_OUTPUT.nav_roll` and `nav_pitch` (FC desired angles in degrees)
- **Yaw:** Accumulated from the commanded yaw rate (`mav_yaw / 1000 * 180 deg/s`)
- **Throttle:** `VFR_HUD.throttle` (0-100%)

Values are smoothed with exponential smoothing (alpha = 0.3) for fluid animation.

### Why NAV_CONTROLLER_OUTPUT?

We tried several MAVLink message sources for the 3D visualization:

1. **SERVO_OUTPUT_RAW** — shows PID corrections from the stabilization loop, so the drone appears to move even with a neutral stick. Rejected.
2. **RC_CHANNELS** — all zeros because there's no physical RC receiver. Rejected.
3. **NAV_CONTROLLER_OUTPUT** — shows the FC's *desired* roll/pitch angles, which are near-zero with a neutral stick and respond proportionally to stick input. This is the correct source.

---

## Troubleshooting

### Jetson loses internet after reboot

Re-run on the Jetson:
```bash
sudo ip route add default via 10.223.0.1
echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf
```

And verify the Mac side is still configured:
```bash
sudo ifconfig en16 10.223.0.1 netmask 255.255.0.0 up
sudo sysctl -w net.inet.ip.forwarding=1
echo 'nat on en0 from 10.223.0.0/16 to any -> (en0)' | sudo pfctl -ef -
```

### D-Bus crash on Jetson

The Jetson's D-Bus configuration can cause pygame to crash. This is handled by:
- Setting `DBUS_FATAL_WARNINGS=0` environment variable
- Only initializing needed pygame subsystems (`pygame.display.init()`, `pygame.font.init()`, `pygame.joystick.init()`) instead of `pygame.init()`

### FC won't arm

Common causes and fixes:
- **Pre-arm checks failing** — The application sets `ARMING_CHECK=0` on startup. If it still fails, the param_set may not have taken effect. Restart the application.
- **FC in LAND mode** — Causes immediate disarm after arming. The application sets ACRO mode before arming.
- **Throttle not at minimum** — Ensure the throttle joystick/slider is at minimum before arming.
- **Force arm** — The application uses `param2=21196` to force arm past remaining checks.

### No display on Jetson

If launching from SSH, you must set `DISPLAY=:0`:
```bash
DISPLAY=:0 python3 /home/jetson/leoflight/input_monitor.py
```

If no X server is running on the Jetson, you need a monitor connected or a virtual framebuffer.

### Pitch is backwards

Toggle `INVERT_PITCH` in `config.py`. This was changed from `True` to `False` when switching to the dual joystick setup.

### Joystick controllers are swapped

The pygame indices (0 and 1) depend on USB enumeration order. If the controllers are reversed, either:
- Swap the USB cables physically
- Swap the indices in `input_monitor.py` lines 347-352 (change `Joystick(1)` ↔ `Joystick(0)`)

### FC data not showing in the UI

The application requests all data streams at startup. If the connection indicator (top-right dot) is red:
- Check the USB-C cable between Jetson and FC
- Verify the serial port: `ls /dev/ttyACM*`
- Try specifying the port: `--port /dev/ttyACM1`

---

## Quick Reference

### Full startup sequence from Mac

```bash
# 1. SSH to Jetson
ssh jetson

# 2. (If needed) Restore internet
sudo ip route add default via 10.223.0.1
echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf

# 3. Kill any existing instance
sudo killall python3 2>/dev/null

# 4. Launch the monitor + bridge
DISPLAY=:0 python3 /home/jetson/leoflight/input_monitor.py

# Or in background:
DISPLAY=:0 nohup python3 -u /home/jetson/leoflight/input_monitor.py \
    >/tmp/input_monitor.log 2>&1 &
```

### Deploy updated code from Mac

```bash
sshpass -p 'test1234' scp -6 input_monitor.py config.py \
    "jetson@[fe80::4ab0:2dff:fed3:ef8a%en16]:~/leoflight/"
```
