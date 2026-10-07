# VueOSD — Digital FPV OSD Tool

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [wkumik/Digital-FPV-OSD-Tool](https://github.com/wkumik/Digital-FPV-OSD-Tool) |
| Локальна тека | `fpv-library/repos/Digital-FPV-OSD-Tool-MSP-OSD-overlay-tool-for-FPV-DVR-video-B` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 24 |
| Оновлено upstream | 2026-07-12 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Overlay MSP-OSD data onto FPV DVR video footage. Supports Betaflight, INAV, ArduPilot, and BetaFPV P1. Compatible with [Ruby FPV](https://rubyfpv.com/) and [Onyx FPV](https://onyxfpv.com/) via standard MSP-OSD format.

Reads `.osd` and `.srt` files recorded alongside your DVR video and renders the HUD elements directly onto the footage — frame-accurate, GPU-accelerated.

_З README.md, без переказу._

## Для чого

MSP-OSD overlay tool for FPV DVR video — Betaflight / INAV / Ardupilot

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Список із розділу features / можливості в README:

- Frame-accurate OSD overlay
- Betaflight, INAV & ArduPilot font support (SneakyFPV HD fonts included)
- Firmware auto-detected from OSD file header
- WTFOS / DJI O3 support (auto-detected 60×22 grid)
- BetaFPV P1 embedded OSD support
- Compatible with [Ruby FPV](https://rubyfpv.com/) and [Onyx FPV](https://onyxfpv.com/) (standard MSP-OSD format)
- SRT telemetry bar (speed, altitude, satellites, signal)
- GPU-accelerated encoding (NVIDIA NVENC, AMD AMF, Intel QSV, VAAPI, VideoToolbox) with automatic CPU fallback
- ColorTrans color correction with LUT preview
- Transparent overlay export (VP9 alpha)
- Trim, scale, offset, opacity controls
- Built-in video player with scrubbing, frame stepping and shuttle playback

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `_widget_draw.py`
- `_widget_map.py`
- `_widget_map_tiles.py`
- `_widget_primitives.py`
- `assets/`
- `bootstrap.py`
- `build.bat`
- `build.sh`
- `CLAUDE.md`
- `colortrans_dx9.hlsl`
- `Create Shortcut.bat`
- `docs/`
- `font_loader.py`
- `fonts/`
- `icons/`
- `main.py`
- `osd_decoder.py`
- `osd_parser.py`
- `osd_renderer.py`
- `p1_osd_parser.py`
- `player.py`
- `presets/`
- `README.md`
- `requirements.txt`

Типи файлів за вибіркою (213 файлів, глибина до 3): .png (169), Python (21), Markdown (5), .bat (3), JSON (3), (без суфікса) (3).


## Що треба

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `PyQt6>=6.6.0`, `Pillow>=10.0.0`, `numpy>=1.24.0`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start — Windows

Double-click **`VueOSD.bat`**

On first run it will:
1. Install Python dependencies automatically
2. Install FFmpeg automatically (via winget)
3. Launch the app

No manual setup required.

---
### Quick Start — Linux / macOS

```bash
chmod +x run.sh
./run.sh
```

Install FFmpeg separately:
```bash
sudo apt install ffmpeg        # Ubuntu/Debian
sudo dnf install ffmpeg        # Fedora
sudo pacman -S ffmpeg          # Arch
brew install ffmpeg            # macOS
```

---
### Build Standalone Executable

**Windows** — run `build.bat` after first launch (produces `dist\VueOSD.exe`)
**Linux/macOS** — run `./build.sh` (produces `dist/VueOSD`)

The resulting binary needs no Python installation on the target machine.
Bundle it with `ffmpeg.exe` (Windows) or ensure `ffmpeg` is on PATH.

---
### Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Супутні документи в теці

- [`docs/CREDITS.md`](../../fpv-library/repos/Digital-FPV-OSD-Tool-MSP-OSD-overlay-tool-for-FPV-DVR-video-B/docs/CREDITS.md)
- [`docs/LICENSE.md`](../../fpv-library/repos/Digital-FPV-OSD-Tool-MSP-OSD-overlay-tool-for-FPV-DVR-video-B/docs/LICENSE.md)
- [`docs/RELEASE.md`](../../fpv-library/repos/Digital-FPV-OSD-Tool-MSP-OSD-overlay-tool-for-FPV-DVR-video-B/docs/RELEASE.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Digital-FPV-OSD-Tool-MSP-OSD-overlay-tool-for-FPV-DVR-video-B/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/wkumik__Digital-FPV-OSD-Tool.md`.
