# ClearFlow (UNBOUND)

Ultimate cross-platform DPI bypass engine combining Zapret 2, GoodbyeDPI, and intelligent auto-configuration.

## Architecture

**Provider-based design** supporting multiple bypass engines:
- **Zapret 2** (Windows: winws2.exe + WinDivert, Linux: nfqws + iptables, macOS: nfqws + pf)
- **GoodbyeDPI** (Windows: modes -1 to -9)
- **Android** (Magisk/KernelSU module with ARM64/ARM7 support)

## Features

- **Auto-Scan**: Automatically tests engines/profiles against blocked endpoints
- **Smart Profiles**: Discord Voice, YouTube QUIC, Telegram API, Ultimate Bypass
- **Zero-Zombie Shutdown**: Forceful cleanup of WinDivert/iptables/pf on exit
- **Autostart**: Silent boot integration via Task Scheduler (Windows) / systemd (Linux)
- **Cross-Platform**: Windows, Linux (Arch/SteamOS), macOS, Android

## Setup

### Windows
Binaries included. Run as Administrator.

### Linux
Download `nfqws` from [zapret releases](https://github.com/bol-van/zapret/releases):
```bash
wget https://github.com/bol-van/zapret/releases/latest/download/zapret-linux-x86_64.tar.gz
tar -xzf zapret-linux-x86_64.tar.gz
cp nfqws engine/core_bin/linux/
```

### macOS
Download `nfqws` from [zapret releases](https://github.com/bol-van/zapret/releases):
```bash
curl -L https://github.com/bol-van/zapret/releases/latest/download/zapret-macos-x86_64.tar.gz -o zapret.tar.gz
tar -xzf zapret.tar.gz
cp nfqws engine/core_bin/macos/
```

### Android
1. Install Magisk/KernelSU
2. Download ARM binaries from zapret releases
3. Place in `android/magisk/bin/`
4. Flash module via Magisk Manager

## Development

```bash
wails dev    # Live development with hot reload
wails build  # Production build
```

## Status

Phase 1-4 Complete (100%): Windows, Linux, macOS, Android implementations ready.
