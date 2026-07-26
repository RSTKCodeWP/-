# Ruben-FPV

Low-latency FPV video system using raw 802.11 packet injection. Bypasses WiFi protocol overhead (no handshakes, ACKs, retransmissions) for sub-100ms latency video transmission.

## Architecture

```
AIR UNIT (Pi 4)                         GROUND STATION (Pi 2)
┌─────────────────┐                     ┌─────────────────┐
│  USB Camera     │                     │  Display/HDMI   │
│       │         │                     │       ▲         │
│       ▼         │                     │       │         │
│  ffmpeg H.264   │                     │  mpv/ffplay     │
│       │         │                     │       ▲         │
│       ▼         │    Raw 802.11       │       │         │
│  ruben-tx.py    │ ─────────────────►  │  ruben-rx.py    │
│       │         │    5GHz Channel     │       ▲         │
│       ▼         │                     │       │         │
│  WiFi Adapter   │ ))))))))))))))))))) │  WiFi Adapter   │
│  (Monitor Mode) │                     │  (Monitor Mode) │
└─────────────────┘                     └─────────────────┘
```

## Quick Start - Pre-built Image (Easiest)

1. Download `ruben-fpv.img` from [Releases](https://github.com/rubenCodeforges/ruben-fpv/releases)
2. Flash to SD card (use Raspberry Pi Imager or `dd`)
3. Edit `ruben.txt` on boot partition:
   ```
   ROLE=air      # for transmitter (camera side)
   ROLE=ground   # for receiver (display side)
   ```
4. Insert SD, power on - done!

## Build Your Own Image

```bash
# On any Linux machine
git clone https://github.com/rubenCodeforges/ruben-fpv.git
cd ruben-fpv/image
sudo ./build-image.sh

# Outputs: ruben-fpv.img (ready to flash)
```

## Manual Install (on existing Pi OS)

```bash
git clone https://github.com/rubenCodeforges/ruben-fpv.git
cd ruben-fpv
sudo ./install.sh
```

Or one-liner:
```bash
curl -sSL https://raw.githubusercontent.com/rubenCodeforges/ruben-fpv/main/install.sh | sudo bash
```

## Hardware Requirements

| Component | Air Unit | Ground Station |
|-----------|----------|----------------|
| SBC | Raspberry Pi 4 | Raspberry Pi 2/3/4 |
| WiFi | T2U Plus (RTL8812AU) | T2U Plus (RTL8812AU) |
| Camera | USB Webcam | - |
| Display | - | HDMI Monitor |

**WiFi Adapter**: TP-Link Archer T2U Plus (RTL8821AU chipset) - supports monitor mode and packet injection on 5GHz.

## Driver Installation

The T2U Plus requires the RTL8812AU driver (works for both RTL8812AU and RTL8821AU chips).

**Pre-compiled driver included** for kernel `6.12.47+rpt-rpi-v8` (Raspberry Pi OS).

```bash
# Install driver (uses pre-compiled if kernel matches, otherwise builds from source)
sudo ./drivers/install-rtl8812au.sh

# Verify
iwconfig  # Should show new wlanX interface
```

If your kernel differs, the script will compile from source (takes ~10 min on Pi 4, needs cooling).

## Manual Usage

### Air Unit
```bash
# Setup monitor mode
sudo /opt/ruben-fpv/setup-monitor.sh

# Start transmission
sudo /opt/ruben-fpv/start.sh
```

### Ground Station
```bash
# Setup monitor mode
sudo /opt/ruben-fpv/setup-monitor.sh

# Start reception
sudo /opt/ruben-fpv/start.sh
```

## Configuration

Edit `/opt/ruben-fpv/config.sh`:

```bash
WIFI_INTERFACE="wlan1"    # WiFi adapter
WIFI_CHANNEL="36"         # Must match on both units!
VIDEO_WIDTH="1280"        # Air unit only
VIDEO_HEIGHT="720"
VIDEO_FPS="30"
VIDEO_BITRATE="4M"
```

## Service Management

```bash
# Enable auto-start
sudo systemctl enable ruben-fpv

# Start/stop
sudo systemctl start ruben-fpv
sudo systemctl stop ruben-fpv

# View logs
journalctl -u ruben-fpv -f
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No monitor mode | Check `iw list` for "monitor" support |
| Driver not loading | Install RTL8812AU driver (install.sh offers this) |
| No video | Check camera with `v4l2-ctl --list-devices` |
| High latency | Lower bitrate, use 5GHz, check for interference |
| Packet loss | Move closer, check antenna, try different channel |

## File Structure

```
/opt/ruben-fpv/
├── config.sh           # Configuration
├── setup-monitor.sh    # WiFi monitor mode setup
├── start.sh            # Main launcher
├── ruben-tx.py         # (air) Packet transmitter
├── ruben-video.sh      # (air) Video encoder
├── ruben-rx.py         # (ground) Packet receiver
├── ruben-display.sh    # (ground) Video display
└── common/
    └── protocol.py     # Shared protocol definitions
```

## License

MIT
