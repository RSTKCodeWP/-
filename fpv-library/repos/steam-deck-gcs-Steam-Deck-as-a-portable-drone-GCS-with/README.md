# Steam Deck Ground Control Station

Turn your Steam Deck into a portable drone ground control station using ExpressLRS MAVLink telemetry.

This guide covers setting up **QGroundControl** and **Mission Planner** on a Steam Deck with a **RadioMaster Nomad** ELRS module as a standalone MAVLink radio — no RC transmitter needed.

## What This Does

- Steam Deck runs QGroundControl (Flatpak) and Mission Planner (via Nix + Mono)
- RadioMaster Nomad connects via USB-C as a bidirectional MAVLink telemetry radio
- Nomad powered by a small LiPo via XT30
- ELRS dual-band (2.4GHz + 868/915MHz) Gemini link to the aircraft
- Full GCS telemetry, mission planning, and parameter tuning
- RC stick control via QGC joystick mapping (Steam Deck built-in controls)
- User-installed software and configuration persist across SteamOS updates; the `/etc` udev symlink must be restored afterward

## Bill of Materials

| Item | Purpose | Notes |
|------|---------|-------|
| Steam Deck (any model) | Ground control station | LCD or OLED both work |
| [RadioMaster Nomad](https://radiomasterrc.com/products/nomad-dual-1-watt-gemini-xrossband-expresslrs-module) | ELRS TX module (standalone) | Dual-band Gemini, USB-C, ESP32 |
| [RadioMaster DBR4](https://radiomasterrc.com/products/dbr4-dual-band-xross-gemini-expresslrs-receiver) | ELRS RX on the aircraft | Dual-band Gemini receiver |
| USB-C to USB-C cable | Nomad to Steam Deck | Short cable preferred |
| 2S-4S LiPo battery | Powers the Nomad via XT30 | Small 2S 300-600mAh works |
| XT30 pigtail/cable | Connects battery to Nomad | Included with most LiPos |

> **Note:** The Nomad's USB-C handles data only — RF power comes from the XT30 LiPo.

## Architecture

```
┌─────────────────┐     USB-C      ┌──────────────┐    ELRS 2.4GHz    ┌──────────────┐
│   Steam Deck    │◄──────────────►│  RadioMaster │◄─────────────────►│   Aircraft   │
│                 │   Serial/MAV    │    Nomad     │    + 868/915MHz   │              │
│  QGC / MP       │   460800 baud  │              │    Gemini Link    │  FC + ELRS   │
│  MAVProxy       │                │  XT30◄──LiPo │                   │  Receiver    │
└─────────────────┘                └──────────────┘                   └──────────────┘
```

## Quick Start

### 1. Install GCS Software

```bash
# Run the install script (does everything)
./install.sh
```

Or manually:

```bash
# QGroundControl (easy, works immediately)
flatpak install -y --user flathub org.mavlink.qgroundcontrol

# Mission Planner (requires Nix for mono)
# First: sudo chown -R $USER /nix
curl -L https://nixos.org/nix/install | bash -s -- --no-daemon
. ~/.nix-profile/etc/profile.d/nix.sh
nix-env -iA nixpkgs.mono
# Then extract Mission Planner
mkdir -p ~/.local/share/mission-planner
unzip MissionPlanner-latest.zip -d ~/.local/share/mission-planner/
```

### 2. Configure the Nomad (one-time)

Before standalone use, configure the Nomad using a radio handset + ELRS Lua script:

- Set your **binding phrase**
- Set **packet rate** (recommend F1000 for MAVLink throughput)
- Set **RF power** as needed
- These settings are stored as **Model ID 0**, which is what the Nomad uses in standalone mode

Alternatively, connect to the Nomad's WiFi AP and configure via the ELRS web UI.

### 3. Configure ArduPilot (on the aircraft)

Set these parameters on the serial port connected to your ELRS receiver:

```
SERIALx_PROTOCOL = 23    # RCIN (RC + MAVLink on same port)
SERIALx_BAUD = 460        # 460800 baud
RSSI_TYPE = 5              # RSSI via MAVLink
```

Set MAVLink stream rates (replace `x` with your stream number):

```
SRx_ADSB = 0
SRx_EXT_STAT = 1
SRx_EXTRA1 = 1
SRx_EXTRA2 = 1
SRx_EXTRA3 = 1
SRx_PARAMS = 0
SRx_POSITION = 1
SRx_RAW_CTRL = 0
SRx_RAW_SENS = 1
SRx_RC_CHAN = 1
```

### 4. Connect

1. Power the Nomad via XT30 (plug in the LiPo)
2. Connect Nomad USB-C to Steam Deck
3. Power on the aircraft
4. Open QGC or Mission Planner
5. Connect on the serial port at **460800 baud**

The Nomad auto-detects MAVLink traffic and starts the link.

### 5. Joystick Control (QGC only)

QGC supports the Steam Deck's built-in controls for RC override:

1. Connect to a vehicle (joystick menu only appears when connected)
2. Go to **Vehicle Setup** → **Joystick**
3. Select the Steam Deck controller
4. Map axes: Left stick = Roll/Pitch, Right stick = Yaw/Throttle
5. Map buttons: A = Arm, B = RTL, etc.
6. Set deadband to 5-10% (gaming sticks aren't as precise as RC gimbals)

> **Note:** Mission Planner's joystick doesn't work on Linux (DirectX dependency). Use QGC for stick control.

## What Persists Across SteamOS Updates

| Component | Location | Survives update? |
|-----------|----------|:----------------:|
| QGroundControl | Flatpak (user) | Yes |
| Mission Planner | `~/.local/share/mission-planner/` | Yes |
| Mono runtime | `/nix/store/` (Valve preserves `/nix`) | Yes |
| Launcher scripts | `~/.local/bin/` | Yes |
| Udev rules file | `~/.config/udev-rules/` | Yes |
| Udev symlink in `/etc` | `/etc/udev/rules.d/` | **No** — re-run `gcs-post-update` |

After a SteamOS update, run:
```bash
~/.local/bin/gcs-post-update
```

## Firmware Requirements

- ELRS TX + RX firmware: **3.5.0** or newer
- TX Backpack firmware: **1.5.0** or newer (if using WiFi method)
- ArduPilot: any recent version with MAVLink support

## Alternative Connection Methods

### WiFi (wireless, no USB cable)

Instead of USB serial, you can use the Nomad's WiFi backpack:

1. Enable WiFi backpack telemetry in ELRS Lua script
2. Connect Steam Deck WiFi to `ExpressLRS TX Backpack` (password: `expresslrs`)
3. In QGC/MP, connect via **UDP port 14550**

### MAVProxy (CLI GCS with working joystick)

MAVProxy is a lightweight CLI-based GCS. Unlike Mission Planner, its joystick module **works on Linux** — making it the best option for RC control from the Steam Deck's built-in sticks.

The install script sets up MAVProxy in a Python venv with a Steam Deck joystick config.

```bash
# Launch (defaults to /dev/ttyACM0 @ 460800)
mavproxy-gcs

# Custom port/baud
mavproxy-gcs /dev/ttyUSB0 115200
```

#### Steam Deck Joystick Mapping (Mode 2)

The included `steam-deck.yml` config maps:

| Control | Channel | Function |
|---------|---------|----------|
| Left stick Y | CH3 | Throttle |
| Left stick X | CH4 | Yaw |
| Right stick Y | CH2 | Pitch |
| Right stick X | CH1 | Roll |
| A / B / X / Y | CH5 | Flight modes (Stabilize/Loiter/Guided/RTL) |
| LB / RB | CH7 / CH8 | Arm / Disarm |
| Left trigger | CH9 | Aux (gimbal tilt, etc.) |
| Right trigger | CH10 | Aux |
| D-pad X | CH6 | Aux toggle |

Edit `~/.mavproxy/joysticks/steam-deck.yml` to customize.

#### Useful MAVProxy Commands

```
joystick status          # verify joystick is detected
joystick redetect        # re-scan for joysticks
mode GUIDED              # switch flight mode
arm throttle             # arm the vehicle
disarm                   # disarm
wp list                  # list waypoints
param show SERIAL*       # show serial params
```

## Known Limitations

- **Mission Planner joystick broken on Linux** — MP uses DirectX for joystick input, which doesn't work under Mono. Use QGC for stick control.
- **Steam Deck sticks are gaming-grade** — shorter throw and less precision than RC gimbals. Fine for guided/loiter modes, not ideal for aggressive manual flying.
- **MP under Mono has occasional crashes** — this is a known upstream issue. Save your work frequently.
- **Nomad needs external power** — USB-C is data only, XT30 LiPo required for RF.

## References

- [ExpressLRS MAVLink Documentation](https://www.expresslrs.org/software/mavlink/)
- [ExpressLRS Gemini Documentation](https://www.expresslrs.org/software/gemini/)
- [ArduPilot Joystick/Gamepad Docs](https://ardupilot.org/copter/docs/common-joystick.html)
- [MAVProxy Joystick Module](https://ardupilot.org/mavproxy/docs/modules/joystick.html)
- [RadioMaster Nomad Product Page](https://radiomasterrc.com/products/nomad-dual-1-watt-gemini-xrossband-expresslrs-module)
- [SkyDeck Project (archived reference)](https://github.com/TigeyJewellAlibhai/skydeck)
- [Nix on Steam Deck](https://determinate.systems/blog/nix-on-the-steam-deck/)
- [ArduPilot: Mission Planner on Steam Deck](https://discuss.ardupilot.org/t/steamdeck-install-of-mission-planner-instructions-or-package-please/115111)

## License

MIT
