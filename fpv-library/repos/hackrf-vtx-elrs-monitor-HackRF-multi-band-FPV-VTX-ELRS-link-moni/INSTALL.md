# Install & test — HackRF FPV Band Monitor (human instructions)

Watch the 5.8 GHz FPV video band and the 2.4 GHz / 900 MHz ExpressLRS control
bands with a HackRF One: a live web dashboard reports which of the 48 VTX
channels are active and whether a control link is on the air.

Project page: https://talentedhobbyists.com/open/hackrf-fpv-band-monitor/

## What you need

- A HackRF One with an antenna (any wideband whip works; a 5.8 GHz antenna
  helps for the video band).
- macOS or Linux with Python 3.9+ (Windows works too — the repo can download
  self-contained HackRF tools, see step 2).
- No accounts, no network access at runtime: everything runs locally.

## 1. Get the code

    git clone git@github.com:paulnurkkala/hackrf-vtx-elrs-monitor.git
    cd hackrf-vtx-elrs-monitor

(or `git clone https://github.com/paulnurkkala/hackrf-vtx-elrs-monitor.git`)

## 2. Install the HackRF command-line tools

- macOS: `brew install hackrf`
- Debian/Ubuntu: `sudo apt install hackrf`
- Fedora: `sudo dnf install hackrf`
- Windows (or no package manager): `python bootstrap_vendor.py` downloads
  prebuilt tools into `vendor/bin/` and the repo uses them automatically.

Plug in the HackRF and confirm the tools see it:

    hackrf_info        # expect "Found HackRF" with a serial number

## 3. Python environment

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

## 4. Run the monitor

    .venv/bin/python -m hackrf_api webapp --port 8080

Open http://127.0.0.1:8080/ — you should see three panels (VTX 5.3–6 GHz,
2.4 GHz ELRS, 900 MHz ELRS) filling with waterfall data within ~10 seconds.

## 5. Check it's actually working

Things you can verify without transmitting anything:

- The 2.4 GHz panel should show your WiFi as bursty activity, and the ELRS
  card should call it **ambient** (not a control link) — that's the detector
  correctly rejecting WiFi.
- Power up an FPV drone or standalone VTX **at its lowest power setting
  (25 mW or pit mode)**: within a few seconds the matching channel tile in
  the grid lights green, the verdict card names the channel, and the voice
  announcer (if enabled in the header) calls it out. Note: keep bench-test
  power low — a high-power VTX a meter from any receiver overloads it.
- Key an ExpressLRS transmitter: the matching ELRS card should flip to
  **TX ACTIVE** within a few seconds.

Command-line equivalents (against the running webapp):

    .venv/bin/python -m hackrf_api vtx      # active VTX channels
    .venv/bin/python -m hackrf_api elrs     # ELRS verdicts
    .venv/bin/python -m hackrf_api scan 5645 5945 --plot   # one-shot sweep

## 6. Optional: on-site ELRS calibration

The ELRS detector ships with bench-recorded ambient baselines. For best
false-positive rejection at your site, record your own with everything off:

    .venv/bin/python elrs_calibrate.py baseline

then restart the webapp.

## Troubleshooting

- **"No HackRF boards found"** — cable/port issue, or another program has the
  radio open (only one process can). Close SDR software, replug, retry.
- **Dashboard loads but panels stay empty** — check the terminal for errors;
  `hackrf_info` must work from the same shell.
- **Everything looks 20–40 dB quieter than expected** — antenna not seated,
  or an RP-SMA/SMA mismatch (FPV antennas are usually RP-SMA; the HackRF is
  SMA — a mismatched pair threads on fine but makes no center-pin contact).
- The dashboard's BROADCASTING tab can transmit test signals. It is guarded
  behind an explicit confirmation because transmitting in these bands
  generally requires a license in most jurisdictions — leave it alone unless
  you know you're allowed.
