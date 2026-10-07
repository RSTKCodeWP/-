# Ruben-FPV

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rubenCodeforges/ruben-fpv](https://github.com/rubenCodeforges/ruben-fpv) |
| Локальна тека | `fpv-library/repos/ruben-fpv` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-01-30 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Low-latency FPV video system using raw 802.11 packet injection. Bypasses WiFi protocol overhead (no handshakes, ACKs, retransmissions) for sub-100ms latency video transmission.

_З README.md, без переказу._

## Для чого

Low-latency FPV video system using raw 802.11 packet injection. Bypasses WiFi protocol overhead (no handshakes, ACKs, retransmissions) for sub-100ms latency video transmission.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `air/`
- `CLAUDE.md`
- `common/`
- `drivers/`
- `ground/`
- `image/`
- `install.sh`
- `README.md`

Типи файлів за вибіркою (21 файлів, глибина до 3): shell (13), Python (3), Markdown (2), JSON (1), .xz (1), .service (1).

Фрагмент README про будову:

### Architecture

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

## Що треба

### Hardware Requirements

| Component | Air Unit | Ground Station |
|-----------|----------|----------------|
| SBC | Raspberry Pi 4 | Raspberry Pi 2/3/4 |
| WiFi | T2U Plus (RTL8812AU) | T2U Plus (RTL8812AU) |
| Camera | USB Webcam | - |
| Display | - | HDMI Monitor |

**WiFi Adapter**: TP-Link Archer T2U Plus (RTL8821AU chipset) - supports monitor mode and packet injection on 5GHz.


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start - Pre-built Image (Easiest)

1. Download `ruben-fpv.img` from [Releases](https://github.com/rubenCodeforges/ruben-fpv/releases)
2. Flash to SD card (use Raspberry Pi Imager or `dd`)
3. Edit `ruben.txt` on boot partition:
   ```
   ROLE=air      # for transmitter (camera side)
   ROLE=ground   # for receiver (display side)
   ```
4. Insert SD, power on - done!
### Build Your Own Image

```bash
# On any Linux machine
git clone https://github.com/rubenCodeforges/ruben-fpv.git
cd ruben-fpv/image
sudo ./build-image.sh

# Outputs: ruben-fpv.img (ready to flash)
```
### Manual Install (on existing Pi OS)

```bash
git clone https://github.com/rubenCodeforges/ruben-fpv.git
cd ruben-fpv
sudo ./install.sh
```

Or one-liner:
```bash
curl -sSL https://raw.githubusercontent.com/rubenCodeforges/ruben-fpv/main/install.sh | sudo bash
```
### Driver Installation

The T2U Plus requires the RTL8812AU driver (works for both RTL8812AU and RTL8821AU chips).

**Pre-compiled driver included** for kernel `6.12.47+rpt-rpi-v8` (Raspberry Pi OS).

```bash
# Install driver (uses pre-compiled if kernel matches, otherwise builds from source)
sudo ./drivers/install-rtl8812au.sh

# Verify
iwconfig  # Should show new wlanX interface
```

If your kernel differs, the script will compile from source (takes ~10 min on Pi 4, needs cooling).

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ruben-fpv/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rubenCodeforges__ruben-fpv.md`.
