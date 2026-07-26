# For the Next Claude — Setup & Windows Transition

Short orientation for whoever (human or agent) picks this repo up next,
**especially on a fresh Windows machine.** Read this first, then `README.md`
for the full detail.

## What this is

A HackRF One SDR monitor for FPV RF: 5.8 GHz analog/digital **VTX** channel
detection, plus **ELRS** control-link activity on 2.4 GHz and 900 MHz. Core is
dependency-light Python (`numpy` + stdlib `http.server`); there's a browser
dashboard and a JSON API. It shells out to the Great Scott Gadgets CLI tools
(`hackrf_info`, `hackrf_sweep`).

## Current state (as merged to `main`)

- **`main` is the source of truth** and has everything: the emit/broadcasting
  feature, the branded dashboard, the digital-VTX channel latch, the
  analog/digital voice callouts, **and** the standalone-executable build.
- The `standalone-executables` branch has been merged into `main` — you don't
  need it anymore. `feat/emit-broadcasting` was merged long ago (PR #1).
- Build outputs (`build/`, `dist/`, `*.spec`, `packaging/hackrf_tools_*`) are
  **gitignored** — they're generated, never commit them.

## How the tools get found (the one concept to understand)

`hackrf_api` locates the SDK binaries in this order:
1. `HACKRF_BIN_DIR` env var, if set (this is how the standalone exe injects its
   bundled tools — see `monitor_app.py`),
2. a vendored `vendor/bin/` directory (how Windows ships self-contained),
3. your system `PATH` (a normal `brew`/`apt` install on macOS/Linux).

So on Windows you never need a system install — you either vendor the binaries
or run the prebuilt `.exe`.

---

## Windows setup — three paths, easiest first

### Path A — just run the prebuilt `.exe` (no Python, no install)

The GitHub Actions workflow (`.github/workflows/build-executables.yml`) builds
`hackrf-monitor-windows.exe` on every push and on each release, and uploads it
as an artifact. To get one:
- Push to GitHub → open the run under **Actions → Build standalone executables**
  → download the `hackrf-monitor-windows` artifact, **or** cut a Release and
  grab it there.
- Double-click the `.exe`. It bundles the HackRF tools + DLLs, sets
  `HACKRF_BIN_DIR` internally, starts the dashboard, and opens a browser.

**USB driver gotcha (Windows-only):** the HackRF needs the **WinUSB** driver
bound to it. If `hackrf_info` (or the exe) can't open the device, run
[Zadig](https://zadig.akeo.ie/) once and bind WinUSB to the HackRF. If WinUSB is
already bound, skip Zadig.

### Path B — run from source with vendored binaries

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bootstrap_vendor.py            # downloads hackrf_*.exe + DLLs -> vendor\bin
python bootstrap_vendor.py --verify   # sanity check
python -m hackrf_api info             # should print "Found HackRF" + serial
.\start_monitor.ps1                   # launches dashboard on http://localhost:8080
```

`bootstrap_vendor.py` pulls prebuilt binaries from conda-forge and unpacks the
`.conda` archives directly — **no conda needed**, and it's idempotent.

**Windows launcher gotcha (fixed, but worth knowing):** the launchers open the
dashboard at `127.0.0.1`, **not** `localhost`. On Windows `localhost` resolves to
IPv6 `::1` first, but the webapp binds IPv4 only, so a `localhost` probe/open
hangs. If you add a new Windows helper that hits the local server, use
`127.0.0.1`. (See `SETUP_NOTES.md` → "Windows install log".)

Optional: `powershell -File packaging\install_desktop_icon.ps1` puts a
"HackRF Monitor" shortcut on the Desktop — each click (re)starts the monitor
and opens the dashboard. (Written on macOS, not yet tested on Windows.)

### Path C — build the `.exe` yourself locally

```bat
packaging\build_windows.bat
```

Requires Python 3 on `PATH`. It installs deps + PyInstaller, runs
`bootstrap_vendor.py`, and emits `dist\hackrf-monitor-windows.exe`.

---

## macOS / Linux (reference — this is where it was developed)

```bash
brew install hackrf                   # macOS; Linux: sudo apt install hackrf
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m hackrf_api info
./start_monitor.sh                    # or:  packaging/build_macos.sh  to build the app
./packaging/install_desktop_icon.sh   # optional: desktop icon that (re)starts + opens dashboard
```

If `hackrf_info` isn't found after `brew install`, Homebrew isn't on this
shell's PATH: `eval "$(/opt/homebrew/bin/brew shellenv)"`.

## The firmware gotcha (all platforms — easy to miss)

Scanning uses **sweep mode** (`hackrf_start_rx_sweep`), which older firmware
lacks. If a scan fails with `feature not supported by installed firmware
(-1005)`, flash the firmware that ships with the modern tools, then **physically
unplug and replug** the HackRF (a power-cycle is required). See `README.md`
step 4 for the exact commands.

## Where things live

- `hackrf_api/` — the library + CLI + dashboard (`vtx.py`, `webui.py`, …).
- `monitor_app.py` — PyInstaller entry point for the standalone exe.
- `packaging/` — `build_macos.sh`, `build_windows.bat`.
- `bootstrap_vendor.py` — fetches vendored HackRF binaries for Windows.
- `start_monitor.ps1` / `start_monitor.sh` — launch the dashboard.
- `README.md` — full setup. `CLAUDE_PORTING_GUIDE.md` — RF domain knowledge +
  algorithms if you're reimplementing detection elsewhere. `SETUP_NOTES.md` —
  additional notes.

## Handy commands

```
python -m hackrf_api info      # device check
python -m hackrf_api vtx       # one-shot 5.8 GHz VTX scan
python -m hackrf_api elrs      # one-shot ELRS scan
python -m hackrf_api webapp --port 8080   # dashboard (what the launchers run)
```
