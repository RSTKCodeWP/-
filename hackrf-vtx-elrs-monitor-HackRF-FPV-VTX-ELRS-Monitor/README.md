# hackrf_api

A small, dependency-light Python library + CLI for driving a **HackRF One** on
**macOS, Linux, or Windows** — with **spectrum scanning** as the headline
feature. It returns structured data (numpy arrays, dataclasses, JSON) instead of
text you have to scrape, so both humans and agents (e.g. Claude) can use it.

It wraps the official Great Scott Gadgets command-line tools (`hackrf_info`,
`hackrf_sweep`, …). It finds them in two ways, in order:

1. a vendored `vendor/bin/` directory (how Windows ships self-contained), then
2. your system `PATH` (a normal Homebrew / apt install on macOS / Linux).

So on macOS/Linux you just install the `hackrf` package; on Windows you can stay
fully self-contained with no system install.

---

## Install

> **TL;DR (macOS):** `brew install hackrf` → make a venv → `pip install -r
> requirements.txt` → **flash recent firmware** (see step 4) → `python -m
> hackrf_api info`. The firmware step is the one easy-to-miss gotcha: scanning
> needs firmware new enough for sweep mode.

### 1. Get the HackRF command-line tools

**macOS (Homebrew):**
```bash
brew install hackrf          # hackrf_info/_sweep/_transfer + libhackrf, libusb, fftw
which hackrf_info            # should print /opt/homebrew/bin/hackrf_info (Apple Silicon)
```
If `hackrf_info` isn't found afterwards, Homebrew isn't on your PATH for this
shell — run `eval "$(/opt/homebrew/bin/brew shellenv)"` (and add it to
`~/.zprofile`).

**Linux (Debian/Ubuntu):**
```bash
sudo apt install hackrf
```

**Windows (self-contained, no install):**
```bash
python bootstrap_vendor.py             # downloads HackRF binaries -> vendor/bin
python bootstrap_vendor.py --verify    # sanity check the vendored files
```
`bootstrap_vendor.py` pulls prebuilt binaries from **conda-forge** (`hackrf`,
`libhackrf0`, `libusb`, `fftw`, `vc14_runtime`, `libwinpthread`) into a flat
`vendor/bin/`. It needs no conda — it unpacks the `.conda` archives directly —
and is idempotent. On Windows the USB device also needs the **WinUSB** driver
bound to it (use [Zadig](https://zadig.akeo.ie/) once if `hackrf_info` can't open
the device; if WinUSB is already bound, no Zadig step is needed).

### 2. Python environment

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt                       # numpy, matplotlib, zstandard
```

### 3. Confirm the OS sees the device

```bash
hackrf_info                 # should print "Found HackRF" + a serial number
```
Plug the HackRF into a USB port directly (avoid flaky hubs). On macOS/Linux no
driver step is required.

### 4. Update the firmware (do this once — scanning depends on it)

Spectrum scanning uses **sweep mode** (`hackrf_start_rx_sweep`), which older
firmware lacks. If `hackrf_info` reports an old firmware (e.g. `2018.01.1`,
API ≤ 1.02), a scan fails with:

```
hackrf_start_rx_sweep() failed: feature not supported by installed firmware (-1005)
```

Flash the firmware image that ships with the modern tools, then **physically
unplug and replug** the HackRF (a power-cycle is required — there is no software
reset that reloads firmware):

```bash
# macOS (Homebrew bundles the image):
hackrf_spiflash -w "$(brew --prefix hackrf)/share/hackrf/firmware-bin/hackrf_one_usb.bin"

# Linux: the image is typically at /usr/share/hackrf/hackrf_one_usb.bin
#   hackrf_spiflash -w /usr/share/hackrf/hackrf_one_usb.bin
# Windows (vendored): the .bin is unpacked alongside the tools in vendor/bin.

# --- now UNPLUG the HackRF and plug it back in ---

hackrf_info   # verify: Firmware Version should now be current (e.g. 2026.01.3, API 1.10)
```

If a flash ever goes bad, the HackRF has a DFU bootloader: hold the **DFU** button
while powering on to recover, then reflash.

### 5. Verify end-to-end

```bash
python -m hackrf_api info            # device identity, via the library
python -m hackrf_api scan 2400 2483.5 --bin 200000 --sweeps 3 --plot
```
You should see a noise-floor estimate and an ASCII spectrogram — 2.4 GHz usually
shows WiFi/Bluetooth peaks.

> **For agents (Claude):** every step above is non-interactive except the
> physical replug in step 4. Check `hackrf_info` exit status and the firmware
> line before scanning; if you see error `-1005`, do step 4 and ask the user to
> replug. Prefer the `--json` CLI (see below) and branch on the `ok` field.

---

## Standalone executable (no Python install needed)

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

## Python API

```python
from hackrf_api import HackRF

hrf = HackRF()                       # add serial="…" to pick one of several
print(hrf.is_present())              # True

info = hrf.info()
print(info.board_name, info.firmware_version)   # HackRF One 2024.02.1

# --- spectrum scan (the main event) ---
spec = hrf.scan(start_mhz=2400, stop_mhz=2483.5, bin_width_hz=100_000, sweeps=3)
print(spec.noise_floor_dbm)          # robust noise floor estimate
print(spec.ascii_plot())             # quick terminal spectrogram

for sig in spec.peaks(threshold_db=10):
    print(f"{sig.freq_mhz:.3f} MHz  {sig.power_dbm:.1f} dBm")

# spec.freqs_hz / spec.power_dbm are parallel numpy arrays for your own analysis
# spec.power_at(2_440_000_000) -> dBm at the nearest bin
# spec.strongest(5)            -> top-5 bins regardless of grouping

# --- record raw IQ ---
manifest = hrf.record("capture.iq", freq_hz=433_920_000,
                      sample_rate_hz=8_000_000, seconds=2)

from hackrf_api.core import load_iq
iq = load_iq("capture.iq")           # complex64 numpy array, normalized to ~[-1,1]
```

### `Spectrum` object

| member | meaning |
|---|---|
| `freqs_hz`, `power_dbm` | parallel, frequency-sorted numpy arrays |
| `noise_floor_dbm` | median power (robust floor estimate) |
| `peaks(threshold_db, min_separation_hz)` | grouped signal detections above floor+threshold |
| `strongest(n)` | the n highest bins, ungrouped |
| `power_at(freq_hz)` | power of the nearest bin |
| `ascii_plot(width, height)` | terminal spectrogram |
| `to_dict(include_full)` | JSON-able summary (optionally with full arrays) |

---

## CLI (agent-friendly)

Every subcommand supports `--json`, emitting **one JSON object on stdout** — the
intended interface for an autonomous agent. Without `--json` you get a readable
summary.

```bash
# device identity / firmware
python -m hackrf_api info --json

# spectrum scan: start & stop in MHz
python -m hackrf_api scan 2400 2483.5 --bin 100000 --sweeps 3 --threshold 10 --json
python -m hackrf_api scan 433 435 --plot               # human view + ASCII plot
python -m hackrf_api scan 88 108 --bin 50000 --top 10  # FM broadcast band

# record raw IQ (int8 interleaved I,Q)
python -m hackrf_api record out.iq --freq 433.92e6 --rate 8e6 --secs 2 --json

# live spectrum + waterfall window (matplotlib)
python -m hackrf_api live 5000 6000
python -m hackrf_api peak            # loudest signal from a running live window

# static PNG waterfall (N sweeps stacked)
python -m hackrf_api waterfall 5000 6000 --out wf.png --rows 100
```

### Multi-band monitor web app (VTX + ELRS)

A persistent dashboard that **time-shares the one HackRF across three bands**
(a scheduler rotates the radio), showing all three waterfalls at once plus a
live ELRS status panel:

| band | range | analysis |
|---|---|---|
| VTX | 5288–5962 MHz | FPV analog channel estimation (L/A/B/E/F/R) |
| 2.4 GHz ELRS | 2100–2500 MHz | ELRS / FHSS link detection |
| 900 MHz ELRS | 700–1200 MHz | ELRS / FHSS link detection |

```bash
python -m hackrf_api webapp --port 8080      # -> http://localhost:8080/
./start_monitor.sh                           # macOS/Linux one-click: background + opens browser
powershell -File start_monitor.ps1           # Windows one-click: hidden + opens browser
./packaging/install_desktop_icon.sh          # macOS optional: desktop icon (see below)

# quick checks from anywhere
python -m hackrf_api vtx     # active VTX channels
python -m hackrf_api elrs    # ELRS TX activity per band
curl http://localhost:8080/api/elrs
```

**Optional desktop icon:** when setting up a new machine you can install a
double-clickable "HackRF Monitor" icon on the Desktop. Every click (re)starts
the monitor — killing any running instance and sweep first — and opens the
dashboard in the browser.

```bash
./packaging/install_desktop_icon.sh                      # macOS
powershell -File packaging\install_desktop_icon.ps1      # Windows
```

macOS: the first click shows a one-time permission prompt asking to allow
access to the project folder — click Allow. The custom antenna icon needs
Pillow in the venv (`pip install pillow`); without it the app still works with
a generic icon.

Endpoints: `/` (dashboard), `/api/meta` (per-band config + VTX channel table),
`/api/band?id=<vtx|elrs24|elrs900>&since=N` (incremental waterfall rows +
analysis), `/api/channels` (VTX quick check), `/api/elrs` (ELRS quick check).
Because bands are time-shared, each updates in bursts while the radio dwells on
it.

**VTX detection** clamps to real transmitters: prominent-region detection,
region-span hit assignment for stable duty cycle, a scalar Kalman smoother +
occupancy/duty-cycle gate (rejects bursty WiFi), single representative channel
per cluster with label hysteresis, and analog/digital classification on the
smoothed spectrum.

**ELRS detection** (`elrs.py`) keys on the LoRa FHSS signature — a comb of
narrow (~1 MHz) hopping bursts whose max-hold sits far above the time-average
("intermittency"). It reports **TX active / faint / quiet** per band, calibrated
so a lone powered receiver reads as *quiet* while a keyed controller reads
*active*. Caveats it's honest about: a bind **cannot** be confirmed from RF (a
controller that's merely powered on looks the same as a bound one), and 2.4 GHz
is shared with WiFi/BT so activity there may be ambient.

#### ELRS calibration

`elrs_calibrate.py` captures labeled data to characterise your setup and avoid
false positives. Run it once per condition (it saves to `calib/`):

```bash
python elrs_calibrate.py ambient  # ALL gear OFF — records the WiFi/BT baseline
python elrs_calibrate.py bound     # controller + receiver, linked
python elrs_calibrate.py no_tx     # controller OFF, receiver ON  (rx only)
python elrs_calibrate.py no_rx     # controller ON, receiver OFF  (tx only)
```

Two discriminators came out of calibration:

1. **Intermittency / peak** — a keyed controller shows ≈ 32–50 dB intermittency
   and a strong peak; a lone receiver collapses to ≈ 18 dB / −23 dBm.
2. **Ambient baseline** — `elrs_calibrate.py ambient` (run with everything off)
   records the WiFi/BT floor to `calib/ambient__<band>.json`; the webapp loads it
   and only calls a band `tx_active` if its peak rises ≥ 10 dB above that
   baseline. This is what stops 2.4 GHz WiFi/BT (which otherwise looks like FHSS)
   from reading as ELRS — verified live: 2.4 GHz WiFi at −3 dBm sits only ~9 dB
   over ambient → **WiFi/ambient**, while 900 MHz ELRS sits ~14 dB over →
   **TX active**. (2.4 GHz WiFi is variable, so 900 MHz remains the trustworthy
   indicator for this setup.)

Scan flags: `--bin` (Hz resolution), `--sweeps` (averaging), `--threshold` (dB
over floor for peak detection), `--top` (max peaks), `--lna`/`--vga`/`--amp`
(gain), `--antenna-power` (bias-tee), `--full` (include full arrays in JSON),
`--plot` (ASCII spectrogram).

### Example JSON (scan)

```json
{
  "start_hz": 2400000000.0, "stop_hz": 2483500000.0,
  "bin_width_hz": 100000.0, "sweeps": 3, "num_bins": 1020,
  "noise_floor_dbm": -74.25, "peak_dbm": -56.52, "ok": true,
  "peaks": [
    {"freq_hz": 2440245098.0, "freq_mhz": 2440.245, "power_dbm": -56.52}
  ]
}
```

Exit codes: `0` success, `1` HackRF/tool error, `2` no device. On error with
`--json`, stdout is `{"ok": false, "error": "...", "detail": "..."}`.

---

## For an agent (Claude)

* Prefer the `--json` CLI; parse stdout as JSON and branch on `ok`.
* `info --json` → check `"found"`/`"ok"` before doing anything else.
* `scan START STOP --json` → use `peaks[]` for "what's transmitting here?"
  questions; add `--full` only when you need the entire trace.
* Frequencies: scan takes **MHz**, record takes **Hz**.
* `hackrf_sweep` rounds the range up to a multiple of its ~20 MHz tuning step,
  so the returned span can extend slightly past `stop`.

---

## Capabilities & limits

* **Frequency range:** 1 MHz – 6 GHz (usable), 7.25 GHz absolute.
* **Sweep resolution:** `bin_width_hz` 2,445 Hz – 5 MHz.
* **Sample rate (record):** up to 20 Msps (this board shares a busy USB bus —
  `hackrf_info` warns about high rates; 8–10 Msps is reliable).
* **IQ format:** signed 8-bit, interleaved I,Q.

## ⚠️ Transmitting

`HackRF.transmit(...)` exists but is **guarded**: it refuses to run unless you
pass `i_understand_tx_may_be_illegal=True`. Transmitting without a licence is
illegal in most jurisdictions and can disrupt safety-critical services. Receiving
/ scanning is passive and fine.

### FPV test signal (`emit`)

`hackrf_api/vtx_emit.py` synthesizes a fake **analog 5.8 GHz FPV** signal — a
wideband-FM-of-noise hump (~18 MHz, with a residual carrier spike) on any VTX
channel — to exercise the VTX detector without flying real gear.

```bash
# also GUARDED: needs --i-understand-tx, or it refuses
python -m hackrf_api emit R1 --mw 25 --seconds 10 --i-understand-tx
python -m hackrf_api emit raceband 4 --mw 100 --i-understand-tx
```
```python
from hackrf_api import emit_vtx
emit_vtx("raceband", 4, mw=100, seconds=10, i_understand_tx_may_be_illegal=True)
```

**The `--mw` value is a *relative* loudness target, not a real EIRP.** A HackRF
One's uncalibrated output at 5.8 GHz tops out around −5..0 dBm (~0.3–1 mW) — well
*below* a real 25 mW (+14 dBm) VTX. We map `mw` monotonically onto the TX VGA
gain so `--mw 100` lands ~6 dB hotter than `--mw 25`; that relative spacing is
what's useful for testing detector thresholds. Output is also uneven across the
band and full of harmonics. Only one process can own the radio, so stop any
sweep/monitor (`start_monitor.ps1` does this) before emitting.

The **dashboard webapp** also exposes emit: an "Emit FPV test signal (TX)" card
(band/channel/mW/seconds + a confirm dialog), backed by `POST /api/emit`
(`confirm:true` required, else `403`) and `GET /api/emit` for status. The
endpoint **pauses the band scheduler and takes the radio for the burst, then
resumes monitoring** — no need to stop the app first.

---

## Layout

```
hackrf/
├── bootstrap_vendor.py     # Windows: fetch HackRF binaries into vendor/bin (no install)
├── requirements.txt
├── README.md
├── SETUP_NOTES.md          # working notes from the verified macOS bring-up
├── start_monitor.sh        # macOS/Linux one-click: launch the web app + browser
├── start_monitor.ps1       # Windows one-click: launch the web app + browser
├── monitor_launcher.sh     # macOS: behind the desktop icon — restart + open dashboard
├── monitor_launcher.ps1    # Windows: behind the desktop shortcut — restart + open dashboard
├── elrs_calibrate.py       # capture labeled bound/no_tx/no_rx data -> calib/
├── hackrf_api/
│   ├── __init__.py         # public API: HackRF, Spectrum, Waterfall, ...
│   ├── core.py             # device wrapper, sweep parsing, peak detection
│   ├── live.py             # live spectrum+waterfall window (matplotlib)
│   ├── vtx.py              # FPV VTX channel table + stateful activity analyzer
│   ├── vtx_emit.py         # GUARDED: synth + emit a fake analog FPV test signal
│   ├── elrs.py             # ELRS / FHSS link detection
│   ├── webapp.py           # stdlib HTTP server + multi-band scheduler
│   ├── webui.py            # embedded dashboard HTML/JS (3 waterfalls + ELRS)
│   ├── cli.py              # `python -m hackrf_api ...` with --json
│   └── __main__.py
├── calib/                  # saved ELRS calibration captures
├── packaging/              # build scripts + desktop-icon installers (.sh/.ps1) + icon assets
└── vendor/                 # Windows only (gitignored); macOS/Linux use system tools
    ├── bin/                # hackrf_*.exe + runtime DLLs (self-contained)
    └── _download/          # cached .conda packages
```

On macOS/Linux there is no `vendor/` — the tools come from Homebrew/apt and are
found on `PATH`. You can also force a specific tools directory on any OS with the
`HACKRF_BIN_DIR` environment variable.
