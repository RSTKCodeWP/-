# 🎯 RunCam Divinus — FPV Streamer for RunCam WiFiLink 2

> **Maximum video quality at ≤700 KB/s** on SSC338Q (Sigmastar Infinity6E)

[![Platform](https://img.shields.io/badge/Platform-SSC338Q-blue)]()
[![Codec](https://img.shields.io/badge/Codec-H.265%20AVBR-green)]()
[![Bitrate](https://img.shields.io/badge/Bitrate-≤700KB/s-orange)]()
[![Resolution](https://img.shields.io/badge/Resolution-1024×576-yellow)]()

## Overview

This project replaces the stock **Majestic** streamer on RunCam WiFiLink 2 with **[Divinus](https://github.com/OpenIPC/divinus)** — a lightweight, open-source video streamer optimized for FPV applications.

### Why Divinus over Majestic?

| Feature | Majestic | Divinus |
|---|---|---|
| Source code | Closed | Open (GPLv2) |
| Binary size | ~2.5 MB | ~300 KB |
| Memory usage | Higher | Lower |
| Encoder tuning | Limited YAML | Full SDK access |
| Community patches | Not possible | Fork and modify |

### Encoding Strategy

At **700 KB/s (5600 kbps)** budget with **30 FPS**, every bit counts:

```
Resolution    Pixels/frame  Bits/pixel   Quality
──────────────────────────────────────────────────
1024×576      589,824       9.49 bpp     ★★★★★ Excellent
1152×648      746,496       7.50 bpp     ★★★★☆ Good
1280×720      921,600       6.07 bpp     ★★★☆☆ Acceptable
```

We use **H.265 AVBR** (Adaptive VBR) with **High Profile**:
- Static scenes → QP ~28, low bitrate, pristine quality
- Fast motion → QP rises to ~42, uses full 5600 kbps budget
- CABAC entropy coding → ~15% better compression than CAVLC
- 8x8 transform → sharper textures at same bitrate

## Quick Start (SD Card Install)

### 1. Build Divinus

```bash
git clone https://github.com/OpenIPC/divinus.git
cd divinus
./build.sh star6e
# Output: ./divinus (~300KB ARM binary)
```

### 2. Prepare SD Card

Format SD card as **FAT32**, then copy all files from `sdcard/` directory:

```
SD Card (FAT32):
├── autorun.sh
├── install_divinus.sh
├── restore_majestic.sh
├── divinus                  ← compiled binary (you build this)
├── divinus.yaml
├── S95divinus
└── user.ini
```

### 3. Flash

1. Insert SD card into RunCam WiFiLink 2
2. Power on the camera
3. Wait ~30 seconds for automatic installation
4. Camera reboots with Divinus running

### 4. Verify

```bash
ssh root@192.168.1.10    # password: 12345
ps | grep divinus
```

### 5. Emergency Restore

If anything goes wrong:

```bash
ssh root@192.168.1.10
sh /mnt/sdcard/restore_majestic.sh
```

## Project Structure

```
runcam-divinus/
├── README.md
├── LICENSE
├── sdcard/                    ← Copy contents to SD card
│   ├── autorun.sh             ← SD auto-execute entry point
│   ├── install_divinus.sh     ← Main installer script
│   ├── restore_majestic.sh    ← Emergency rollback
│   ├── divinus.yaml           ← Optimized encoder config
│   ├── S95divinus             ← init.d service script
│   └── user.ini               ← Minimal RunCam override
├── patches/                   ← Divinus source patches
│   └── 001-encoder-tuning.patch
├── src/                       ← Modified Divinus source files
│   └── hal/
│       ├── types.h
│       └── star/
│           └── i6c_hal.c
├── build.sh                   ← Cross-compile helper
└── docs/
    ├── INSTALL.md
    ├── ENCODING-THEORY.md
    └── TROUBLESHOOTING.md
```

## Hardware

- **Camera:** RunCam WiFiLink 2
- **SoC:** SSC338Q (Sigmastar Infinity6E, ARM Cortex-A7)
- **Sensor:** IMX335 / IMX415 (check with `fw_printenv sensor`)
- **WiFi:** RTL8812AU / RTL88X2EU via wfb-ng
- **Flash:** 16MB NOR
- **RAM:** 128MB DDR

## Configuration Presets

### FPV Low Latency (Default)
```yaml
mp4:
  codec: H.265
  mode: AVBR
  width: 1024
  height: 576
  fps: 30
  gop: 30
  profile: HP
  bitrate: 5600
```

### FPV Higher Resolution
```yaml
mp4:
  codec: H.265
  mode: AVBR
  width: 1280
  height: 720
  fps: 30
  gop: 60
  profile: HP
  bitrate: 5600
```

## Credits

- [OpenIPC](https://github.com/OpenIPC) — Divinus streamer and firmware
- [wfb-ng](https://github.com/svpcom/wfb-ng) — WiFi Broadcast
- RunCam — WiFiLink 2 hardware

## License

GPLv2 — See [LICENSE](LICENSE)