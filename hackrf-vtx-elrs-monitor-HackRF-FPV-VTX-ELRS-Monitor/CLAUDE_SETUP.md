# Setup runbook for a Claude Code instance

Human: open Claude Code in an empty directory and say
"Read CLAUDE_SETUP.md from https://github.com/paulnurkkala/hackrf-vtx-elrs-monitor and follow it"
(or clone first and say "read CLAUDE_SETUP.md and set this up").

Claude: you are installing and verifying the HackRF FPV Band Monitor on this
machine. Work through the steps in order; verify each before moving on. Report
what you found at each verification point. Everything is local — no accounts,
no telemetry, and do not use the transmit features.

## Step 1 — prerequisites

1. Confirm Python 3.9+: `python3 --version`.
2. Install the HackRF CLI tools if `hackrf_info` is not on PATH:
   - macOS: `brew install hackrf` (if brew itself is missing, ask the human)
   - Debian/Ubuntu: `sudo apt install hackrf` (ask before sudo)
   - Fedora: `sudo dnf install hackrf`
   - Windows/no package manager: skip — after step 2 run
     `python bootstrap_vendor.py` inside the repo instead.

## Step 2 — clone and environment

    git clone https://github.com/paulnurkkala/hackrf-vtx-elrs-monitor.git
    cd hackrf-vtx-elrs-monitor
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Verify: `.venv/bin/python -c "import numpy"` exits 0.

## Step 3 — hardware check

Ask the human to plug in the HackRF One (with an antenna), then:

    hackrf_info

- "Found HackRF" + serial → proceed.
- "No HackRF boards found" → have the human replug / try another cable or
  port; also make sure no other SDR software is running (single-owner device).
- `hackrf_info` present but errors → report the exact output to the human.

Structured equivalent: `.venv/bin/python -m hackrf_api info --json`
(expect `"ok": true`).

## Step 4 — launch the monitor

Run as a background process so you can keep working:

    nohup .venv/bin/python -m hackrf_api webapp --port 8080 \
      > /tmp/hackrf_monitor.log 2>&1 &
    echo $! > .monitor.pid

Wait ~15 s, then verify all of the following:

1. `curl -s http://127.0.0.1:8080/api/meta` returns JSON with three bands
   (`vtx`, `elrs24`, `elrs900`).
2. `curl -s http://127.0.0.1:8080/api/channels` returns `"ok": true` and a
   numeric `floor_dbm` (typically −60…−80 once sweeping).
3. `curl -s "http://127.0.0.1:8080/api/band?id=vtx&since=0"` has a growing
   `count` between two calls ~10 s apart (proves live sweeping).
4. `/tmp/hackrf_monitor.log` contains "Multi-band monitor live at" and no
   tracebacks.

Then tell the human to open http://127.0.0.1:8080/ in a browser.

## Step 5 — functional test (with the human)

1. Ambient sanity: `.venv/bin/python -m hackrf_api elrs` — the 2.4 GHz band
   should read `ambient` or `quiet` (WiFi must NOT be called `tx_active`).
2. Ask the human to power an FPV VTX **at 25 mW / pit mode** (warn them:
   high power at close range overloads any receiver). Within ~10 s,
   `.venv/bin/python -m hackrf_api vtx` should list the matching channel as
   ACTIVE with `kind: analog` (or digital for DJI/HDZero-style systems).
3. If they have an ExpressLRS transmitter: key it; `-m hackrf_api elrs`
   should flip that band to `tx_active` and back to quiet when off.
4. Report a summary: what was detected, at what margin, and anything that
   didn't match expectations.

## Step 6 — cleanup / persistence

- Stop: `kill $(cat .monitor.pid)`.
- The ELRS detector ships with bench baselines; for the human's site, offer
  to record local ambient (everything off):
  `.venv/bin/python elrs_calibrate.py baseline`, then restart the webapp.

## Hard rules

- Do NOT call the `/api/emit/*` endpoints or `python -m hackrf_api emit` —
  those transmit RF, which generally requires a license. They are
  confirmation-guarded; do not provide that confirmation.
- Only one process may own the HackRF: stop the webapp before running any
  direct `scan`/`waterfall`/`record` CLI commands, and restart it after.
- If a step fails twice with the same error, stop and report rather than
  improvising around the hardware.
