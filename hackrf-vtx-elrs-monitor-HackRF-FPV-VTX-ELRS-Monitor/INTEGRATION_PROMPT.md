# Kickoff prompt — integrate the HackRF VTX/ELRS monitor into a website

> Paste everything below the line into the other Claude (in the target project).

---

You are integrating an existing, working HackRF SDR monitoring system into our
application's website. The system is a separate, self-contained project that
drives a HackRF One to detect, in real time:

- **FPV VTX activity** (analog 5.8 GHz video): which of the 40-channel L/A/B/E/F/R
  plan is transmitting, analog vs digital, one clean label per transmitter, plus
  the loudest channel and a "multiple VTX on similar power" warning.
- **ELRS control-link activity** on 2.4 GHz and 900 MHz: whether a control
  transmitter is keyed up, distinguished from ambient WiFi/BT.

**Source repo (private):** `https://github.com/paulnurkkala/hackrf-vtx-elrs-monitor`
**Read first:** `CLAUDE_PORTING_GUIDE.md` (the full spec — RF domain knowledge,
algorithms, calibrated constants, data contracts) and `README.md`.

## Integration model — consume it as a service, do NOT copy the algorithms

The monitor already exposes a clean JSON HTTP API. **Treat it as a local sensor
microservice** and have our website consume its endpoints. Do not fork or
re-implement `vtx.py` / `elrs.py` into our codebase — that loses upstream fixes
and the hardware calibration. Keep the monitor as its own process/repo (see
"Maintaining it separately" below) and talk to it over HTTP.

### Run the monitor (on the machine physically connected to the HackRF)
```bash
pip install -r requirements.txt
python bootstrap_vendor.py            # fetch HackRF binaries locally (no install)
python -m hackrf_api webapp --port 8080
```
It serves a dashboard at `/` and a JSON API. Only ONE process can own the HackRF
at a time.

### The API our website calls
- `GET /api/elrs` → `{ elrs: { elrs24: {...}, elrs900: {...} } }`. Each band:
  `verdict` ∈ `tx_active | ambient | weak | quiet`, plus `confidence`,
  `confidence_smoothed`, `n_hops`, `intermittency_db`, `peak_dbm`,
  `above_ambient_db`, `note`.
- `GET /api/channels` → VTX `{ active: ["R1", ...], signals: [...], floor_dbm }`.
  Each signal: `freq_mhz`, `candidates` (single representative channel name),
  `kind` ("analog"|"digital"), `power_dbm`, `occupancy`, `on_time_s`.
- `GET /api/meta` → per-band config + `freqs_mhz[]` (call once to set up axes /
  channel table).
- `GET /api/band?id=<vtx|elrs24|elrs900>&since=<n>` → incremental waterfall:
  `{ count, rows[][] (new dBm rows since n), maxhold[], avg[], analysis, age_s }`.
  Poll with the last `count` as `since` to stream only new rows.

### What to build on the website
1. **Status strip** (the high-value, low-effort piece): three indicators —
   - VTX: loudest active channel (name + freq + dBm); if `signals` has ≥2 within
     6 dB of the loudest, show a **yellow "MULTIPLE VTX"** warning listing each
     channel and its frequency.
   - 2.4 GHz ELRS and 900 MHz ELRS: green when `verdict == "tx_active"`, yellow
     for `"ambient"` (WiFi/BT), grey for `weak`/`quiet`. Show `confidence` as the
     headline % (so strong WiFi still reads 100%, just labelled "WiFi/ambient").
2. **Waterfalls** (optional): three `<canvas>` elements; on a ~600 ms poll of
   `/api/band`, append `rows` to a scrolling image (map dBm→colour with a turbo
   colormap), draw `avg`/`maxhold` as the spectrum line above. Bands update in
   bursts because the radio is time-shared.

Implementation choices:
- **Simplest:** have the browser `fetch()` the monitor's endpoints directly (it's
  same-machine localhost). If our site is served from another origin, **proxy**
  `/hackrf/*` → `http://127.0.0.1:8080/*` through our web server to avoid CORS.
- The reference dashboard `hackrf_api/webui.py` is a single self-contained HTML/JS
  file — read it for exact rendering logic (turbo colormap, waterfall scroll,
  status cards) and adapt the markup to our design system. Don't embed it raw.

### Semantics you MUST preserve (honesty matters here)
- ELRS detection **cannot confirm a "bound" link** from RF — a controller that's
  merely powered on looks identical to a bound one. Report **"TX active (bound or
  searching)"**, never "bound". Receiver-only is the only state you can rule out
  (`weak`/`quiet`).
- **900 MHz is the trustworthy ELRS indicator.** 2.4 GHz is shared with WiFi/BT
  and is gated against a recorded ambient baseline; surface its `verdict` as
  WiFi/ambient when it isn't ≥10 dB over baseline.
- VTX channels overlap; the API already collapses to one label per transmitter —
  display `candidates[0]`, not raw channel lists.

### One-time per-site setup the monitor needs
ELRS WiFi rejection relies on a recorded ambient baseline. On the deployment
machine, with all RC gear **off**, run:
```bash
python elrs_calibrate.py ambient
```
This writes `calib/ambient__*.json`; the monitor loads it on start. Re-run if the
local WiFi environment changes a lot. (Other thresholds transfer across sites.)

## Maintaining it as a separate directory/repo

Keep the monitor isolated from our app so upstream updates stay easy:
- **Preferred — separate service + git submodule/clone.** Add it as a git
  submodule (or a sibling clone) at e.g. `services/hackrf-monitor`, pinned to a
  commit. Update with `git -C services/hackrf-monitor pull` (or
  `git submodule update --remote`). Our app only depends on its HTTP API, never
  its Python internals, so upstream refactors don't break us.
- **Or run it as a standalone background service** (systemd unit / Windows
  service / `start_monitor.ps1`) and point our site at its URL via config
  (`HACKRF_MONITOR_URL`, default `http://127.0.0.1:8080`).
- **Do not** copy `hackrf_api/*.py` into our repo. If you must run it in-process
  (we already drive the HackRF in Python), import `hackrf_api` as a dependency
  from the pinned checkout rather than vendoring source.
- `vendor/` (the HackRF binaries) is git-ignored and regenerated by
  `bootstrap_vendor.py` — never commit it; run that script on each new machine.
- Treat `CLAUDE_PORTING_GUIDE.md` as the contract. If you need a behaviour change,
  prefer contributing it upstream (PR to the monitor repo) over patching locally.

## Gotchas
- One process owns the HackRF — don't run the monitor and any other sweep tool
  at once.
- Bands update in bursts (time-shared); VTX is pinged ~2× per rotation, ELRS
  bands ~1×. Don't treat a stale `age_s` as "signal lost" — check it.
- Windows console is cp1252; keep any CLI output ASCII. The HTML/JSON is UTF-8.
- Frequencies: VTX scan ranges are MHz; IQ record APIs are Hz.

Deliverable: wire our website to the monitor's API, build the status strip first
(VTX loudest + multiple-warning, 2.4/900 ELRS verdicts), then optionally the
waterfalls, keeping the monitor as a separately-maintained service. Start by
reading `CLAUDE_PORTING_GUIDE.md`.
