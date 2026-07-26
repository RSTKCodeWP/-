# Cross-platform setup notes (working doc)

Live notes captured while making the repo macOS/Windows-agnostic. These feed the
rewritten install instructions. Environment: Apple Silicon (arm64) macOS,
Darwin 25.4.0, system Python 3.9.6, Homebrew 6.0.5 at `/opt/homebrew`.

## Hardware
- HackRF One, connected via USB. Confirmed enumerating on macOS via:
  `ioreg -p IOUSB -l | grep -i hackrf` → "HackRF One" / "Great Scott Gadgets",
  idVendor 7504 (0x1d50). No driver step needed on macOS (unlike Windows/Zadig).

## Dependency enumeration (macOS)
| dep | why | how |
|---|---|---|
| Homebrew | package manager for the SDR tools | already present at /opt/homebrew |
| hackrf (brew) | hackrf_info/hackrf_sweep/hackrf_transfer + libhackrf | `brew install hackrf` |
| Python 3 | runtime | system python3 3.9.6 ok (venv recommended) |
| numpy, zstandard | core requirements.txt | pip |
| matplotlib | live view / PNG waterfall (optional) | pip |

## Windows path (existing, keep working)
- `bootstrap_vendor.py` downloads prebuilt Windows binaries into `vendor/bin/`.
- HackRF needs WinUSB driver bound (Zadig) unless already present.

## Code changes needed for OS-agnosticism
- `core.find_binaries()` only searches `vendor/bin/`. On macOS/Linux it should
  fall back to system PATH (`shutil.which`) when no vendored binary exists.
- Add a non-Windows launcher equivalent to `start_monitor.ps1`.

## Install / test log

### What worked
- `brew install hackrf` → hackrf_info/sweep/transfer + libhackrf 2026.01.3 in
  /opt/homebrew/bin. No sudo, no driver step.
- venv + `pip install -r requirements.txt` → numpy 2.0.2, zstandard 0.25.0.
- Cross-platform `find_binaries()` PATH fallback verified: `python -m hackrf_api
  info` ran against Homebrew binaries with NO vendor/bin present.

### FIRMWARE GOTCHA (important for docs)
- Device shipped with firmware **2018.01.1 (API 1.02)**. `info` works, but
  `hackrf_sweep` fails: `hackrf_start_rx_sweep() failed: feature not supported
  by installed firmware (-1005)`. Sweep mode needs newer firmware.
- Fix: flash the firmware bundled with brew's hackrf:
  `hackrf_spiflash -w $(brew --prefix hackrf)/share/hackrf/firmware-bin/hackrf_one_usb.bin`
  then unplug/replug. (DFU recovery exists if SPI flash is bad: hold DFU on
  power-up. `hackrf_dfu` not bundled by brew; spiflash is the normal path.)
- After flashing, `hackrf_info` should report 2026.01.3 and sweep should work.

### END-TO-END SUCCESS (macOS, after firmware flash + replug)
- `hackrf_info` → firmware 2026.01.3 (API 1.10) after replug.
- `python -m hackrf_api scan 2400 2483.5 --bin 200000 --sweeps 3 --plot` →
  noise floor ~-70.5 dBm, peak 2465.9 MHz @ -33.2 dBm (WiFi). ASCII plot OK.
- Full chain verified: brew tools → cross-platform find_binaries → sweep → render.

### PATH note
- Homebrew bin (/opt/homebrew/bin) must be on PATH so find_binaries' shutil.which
  resolves the tools. brew sets this in the user's interactive shell; a bare
  non-login shell needs `eval "$(/opt/homebrew/bin/brew shellenv)"`.

## Windows install log (end-to-end, confirmed working)

Ran from source with vendored binaries (Path B in `NEXT_CLAUDE.md`) on Windows
10. Worked nicely once the launcher gotcha below was fixed.

### LOCALHOST / IPv6 GOTCHA (important — Windows-only)
- `monitor_launcher.ps1` probed and opened `http://localhost:$Port/`. On Windows,
  `localhost` resolves to IPv6 `::1` first, but the Python webapp binds IPv4 only,
  so the readiness probe (`Invoke-WebRequest`) and the browser open both hang /
  fail to connect even though the server is up.
- Fix: use `http://127.0.0.1:$Port/` in the launcher instead of `localhost`.
  With that, the "wait until the web app answers" loop succeeds and the dashboard
  opens immediately. (macOS/Linux resolve `localhost` to IPv4 first, so they were
  never affected.)
- If you hit a hang on any other Windows launcher/helper that talks to the local
  server, check for a bare `localhost` and swap it for `127.0.0.1` for the same
  reason.
