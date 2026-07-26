# Ruben-FPV Project

## Overview
Low-latency FPV video system using raw 802.11 packet injection. Bypasses WiFi protocol overhead for sub-100ms latency.

## Architecture

```
USB Webcam → ffmpeg (H.264) → UDP → ruben-tx.py → Monitor Mode WiFi → Air
                                                                      ↓
Display ← mpv/ffplay ← UDP ← ruben-rx.py ← Monitor Mode WiFi ← Ground
```

## Hardware

| Role | Device | WiFi Adapter |
|------|--------|--------------|
| Air Unit | Raspberry Pi 4 | TP-Link T2U Plus (RTL8821AU) |
| Ground Station | Raspberry Pi 2 | TP-Link T2U Plus (RTL8821AU) |

## Project Structure

```
ruben-fpv/
├── air/                    # Air unit (transmitter)
│   ├── config.sh
│   ├── ruben-tx.py         # Raw packet injection
│   ├── ruben-video.sh      # ffmpeg video capture
│   ├── setup-monitor.sh
│   └── start.sh
├── ground/                 # Ground station (receiver)
│   ├── config.sh
│   ├── ruben-rx.py         # Raw packet capture
│   ├── ruben-display.sh    # Video playback
│   ├── setup-monitor.sh
│   └── start.sh
├── common/
│   ├── config.sh
│   └── protocol.py         # Packet format definitions
├── drivers/
│   ├── install-rtl8812au.sh
│   └── rtl8812au/88XXau.ko.xz  # Pre-compiled driver
├── image/
│   ├── build-image.sh      # Creates flashable .img
│   ├── firstboot.sh        # First boot configuration
│   └── ruben-firstboot.service
├── .github/workflows/
│   └── build-image.yml     # GitHub Actions for image builds
├── install.sh              # Interactive installer
└── README.md
```

## Key Commands

```bash
# Test monitor mode
sudo ip link set wlan2 down
sudo iw wlan2 set monitor control
sudo ip link set wlan2 up
sudo iw wlan2 set channel 36

# Run air unit manually
sudo /opt/ruben-fpv/start.sh

# Check service
systemctl status ruben-fpv
journalctl -u ruben-fpv -f

# Build image (on Linux)
sudo ./image/build-image.sh
```

## Configuration

Edit `/opt/ruben-fpv/config.sh` or boot partition `ruben.txt`:
- `WIFI_INTERFACE` - WiFi adapter (wlan1, wlan2, etc.)
- `WIFI_CHANNEL` - Must match on air and ground (default: 36)
- `ROLE` - air or ground (in ruben.txt)

## Current Status

- [x] Air unit TX code complete
- [x] Ground station RX code complete
- [x] Pre-compiled RTL8812AU driver (kernel 6.12.47)
- [x] Image builder
- [x] GitHub Actions workflow
- [ ] End-to-end testing
- [ ] FEC (forward error correction)

## Notes

- T2U Plus shows as `wlan2` when Edimax is also connected
- Driver compilation needs cooling (Pi gets hot)
- 5GHz channel 36 is DFS-free
