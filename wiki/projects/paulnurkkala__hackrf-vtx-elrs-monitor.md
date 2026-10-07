# hackrf_api

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [paulnurkkala/hackrf-vtx-elrs-monitor](https://github.com/paulnurkkala/hackrf-vtx-elrs-monitor) |
| Локальна тека | `hackrf-vtx-elrs-monitor-HackRF-FPV-VTX-ELRS-Monitor` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `elrs` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-26 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A small, dependency-light Python library + CLI for driving a **HackRF One** on **macOS, Linux, or Windows** — with **spectrum scanning** as the headline feature. It returns structured data (numpy arrays, dataclasses, JSON) instead of text you have to scrape, so both humans and agents (e.g. Claude) can use it.

It wraps the official Great Scott Gadgets command-line tools (`hackrf_info`, `hackrf_sweep`, …). It finds them in two ways, in order:

1. a vendored `vendor/bin/` directory (how Windows ships self-contained), then 2. your system `PATH` (a normal Homebrew / apt install on macOS / Linux).

So on macOS/Linux you just install the `hackrf` package; on Windows you can stay fully self-contained with no system install.

_З README.md, без переказу._

## Для чого

HackRF multi-band FPV VTX + ELRS link monitor (Claude-built)

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «vtx».
- Інженер радіолінка — у тексті є «elrs».


## Функція

Список із розділу features / можливості в README:

- **Frequency range:** 1 MHz – 6 GHz (usable), 7.25 GHz absolute.
- **Sweep resolution:** `bin_width_hz` 2,445 Hz – 5 MHz.
- **Sample rate (record):** up to 20 Msps (this board shares a busy USB bus —
- **IQ format:** signed 8-bit, interleaved I,Q.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `bootstrap_vendor.py`
- `calib/`
- `CLAUDE_PORTING_GUIDE.md`
- `CLAUDE_SETUP.md`
- `elrs_calibrate.py`
- `hackrf_api/`
- `INSTALL.md`
- `INTEGRATION_PROMPT.md`
- `monitor_app.py`
- `monitor_launcher.ps1`
- `monitor_launcher.sh`
- `NEXT_CLAUDE.md`
- `packaging/`
- `README.md`
- `requirements.txt`
- `SETUP_NOTES.md`
- `start_monitor.ps1`
- `start_monitor.sh`

Типи файлів за вибіркою (42 файлів, глибина до 3): Python (14), JSON (10), Markdown (7), shell (4), .ps1 (3), .txt (1).


## Що треба

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `numpy>=1.24`, `matplotlib>=3.7`, `zstandard>=0.21`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

> **TL;DR (macOS):** `brew install hackrf` → make a venv → `pip install -r
> requirements.txt` → **flash recent firmware** (see step 4) → `python -m
> hackrf_api info`. The firmware step is the one easy-to-miss gotcha: scanning
> needs firmware new enough for sweep mode.
### Standalone executable (no Python install needed)

Prefer a double-clickable app over a Python install? There's a single-file
executable of the multi-band monitor for macOS and Windows. It **bundles the
HackRF SDK tools** (hackrf_info/hackrf_sweep + native libs), so the target
machine needs nothing installed — just a connected HackRF.

* **Download:** grab the latest `hackrf-monitor-macos` / `hackrf-monitor-windows`
  from the **Actions** tab (artifacts of the *Build standalone executables*
  workflow) or a GitHub Release.
* **Run it:** launch the file; it starts the dashboard and opens
  `http://127.0.0.1:8080/`. Set a different port with the `HACKRF_PORT` env var.
  * macOS: it's an unsigned local build — if Gatekeeper blocks it, right-click →
    **Open** once, or `xattr -dr com.apple.quarantine ./hackrf-monitor-macos`.
* **Firmware:** the executable doesn't flash firmware. If a scan reports error
  `-1005`, update the device firmware once (step 4 above).

Build them yourself:

```bash
bash packaging/build_macos.sh        # -> dist/hackrf-monitor-macos
packaging\build_windows.bat          # -> dist\hackrf-monitor-windows.exe  (on Windows)
```

Both are also built in CI by `.github/workflows/build-executables.yml`.

---

## Супутні документи в теці

- [`INSTALL.md`](../../hackrf-vtx-elrs-monitor-HackRF-FPV-VTX-ELRS-Monitor/INSTALL.md)

## З чого зібрана картка

`catalog.json`, `hackrf-vtx-elrs-monitor-HackRF-FPV-VTX-ELRS-Monitor/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/paulnurkkala__hackrf-vtx-elrs-monitor.md`.
