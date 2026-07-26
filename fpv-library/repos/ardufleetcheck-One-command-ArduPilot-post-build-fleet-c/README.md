# ardufleetcheck

A one-command **post-build bring-up pipeline for ArduPilot multirotors**, packaged as a
set of [Claude Code](https://claude.com/claude-code) skills. Plug a freshly-built
drone into USB, type `/ardufleetcheck`, and it will flash firmware, restore the
config, push the OSD layout + font, sanity-check the VTX and RC link, and probe
arm-readiness — finishing with a single PASS/FAIL summary.

It talks to the flight controller over **MAVLink** (and **MSP** for the Betaflight
code paths) via `pymavlink` + `pyserial`. No Mission Planner / QGroundControl
required for the check itself.

---

## What it does

`/ardufleetcheck` is an **orchestrator** that runs seven sub-skills in order:

| # | Stage          | What it does                                                              | ~Time |
|---|----------------|---------------------------------------------------------------------------|-------|
| 1 | `/arduflash`   | Dump all params → pick `.apj` → reboot to bootloader → flash → re-apply params (3-pass) → verify cal | 4–6 min |
| 2 | `/mgrsosd`     | Push the standard MGRS OSD element layout (`PARAM_SET` burst)              | 10–20 s |
| 3 | `/osdfont`     | Set the OSD font to **clarity** (built-in AP ROMFS font, no upload needed) | ~2 s |
| 4 | `/satest`      | VTX SmartAudio/Tramp sanity test; visible R1→R2→R1 channel toggle          | ~10 s |
| 5 | `/rctest`      | Confirm the FC is receiving live RC from the receiver                      | ~5 s |
| 6 | `/canarm`      | Arm-readiness probe (`RUN_PREARM_CHECKS`); reports what's blocking arming  | ~5 s |
| 7 | `/loadmission` | *(opt-in)* Upload a QGroundControl `.plan` mission                         | ~5 s |

**Total ≈ 5–7 minutes end-to-end.** Stages 1 and 7 are optional via flags (see
[Usage](#usage)).

Each sub-skill **auto-detects ArduPilot vs Betaflight**, so the same bundle works
on BF drones too — but the orchestrator is tuned for the ArduPilot post-build flow.

---

## Requirements

- **macOS** (paths and `/dev/cu.usbmodem*` device naming assume macOS; Linux works
  if you adjust the serial device globs in the scripts).
- **Claude Code** installed and signed in.
- **Python 3** at `/usr/bin/python3` (override with `TTFLEET_PYTHON`), with:
  - `pymavlink`
  - `pyserial`
  ```bash
  /usr/bin/python3 -m pip install pymavlink pyserial
  ```
- A flight controller connected by **USB** (enumerates as `/dev/cu.usbmodem*`),
  speaking MAVLink at 115200 baud (the default for ArduPilot's USB interface).
- `lsof` (ships with macOS) — used to detect other apps holding the serial port.

> The `install.sh` script checks the Python deps for you and prints the exact
> `pip install` line if anything is missing.

---

## Install

```bash
# from the unpacked package directory:
./install.sh
```

This:
1. Copies each skill from `skills/` into `~/.claude/skills/` (where Claude Code
   discovers them).
2. Copies the data files (`clone_scripts/`, OSD layout files) from `data/` into
   the **data directory** — `~/Documents/ttfleet` by default.
3. Checks Python dependencies and prints any missing-package install command.

### Installing the data dir somewhere else

The skills find their data files (flash helper scripts, OSD layouts) under
`$TTFLEET_ROOT`. The default is `~/Documents/ttfleet`. To use a different folder:

```bash
TTFLEET_ROOT=~/drones/fleetcheck-data ./install.sh
```

…then add the export to your shell profile so it sticks (the installer reminds
you of the exact line):

```bash
echo 'export TTFLEET_ROOT="$HOME/drones/fleetcheck-data"' >> ~/.zshrc
source ~/.zshrc
```

> If you keep the default `~/Documents/ttfleet`, **no env var is needed** — that's
> the path baked in as the fallback.

### Manual install (no script)

```bash
cp -R skills/*  ~/.claude/skills/
cp -R data/.    ~/Documents/ttfleet/      # or your chosen $TTFLEET_ROOT
```

---

## Configuration (environment variables)

All optional. The defaults reproduce the original author's layout, so on a clean
macOS box you typically only set `TTFLEET_FIRMWARE_DIR` (and `TTFLEET_ROOT` if you
moved the data dir).

| Variable               | Default                          | Purpose                                                            |
|------------------------|----------------------------------|--------------------------------------------------------------------|
| `TTFLEET_ROOT`         | `~/Documents/ttfleet`            | Where the bundled `clone_scripts/` + OSD layout files live.        |
| `TTFLEET_FIRMWARE_DIR` | `$TTFLEET_ROOT`                  | Folder searched **recursively** for `.apj` firmware in stage 1.    |
| `TTFLEET_DUMP_ROOT`    | `$TTFLEET_ROOT/ardupilot dumps`  | Where each run writes its per-run param dump / restore artifacts.  |
| `TTFLEET_PYTHON`       | `/usr/bin/python3`               | Python interpreter used to run the helper scripts.                 |

### Firmware (`.apj`) files

`/arduflash` does **not** ship firmware — drop your ArduPilot `.apj` build(s) into a
folder and point the picker at it:

```bash
mkdir -p ~/Documents/ttfleet/firmware
cp ~/Downloads/arducopter-TBS_LUCID_H7.apj ~/Documents/ttfleet/firmware/
export TTFLEET_FIRMWARE_DIR=~/Documents/ttfleet/firmware
```

The package includes an empty `data/firmware/` dir as a convenient default drop
spot. The picker validates the board against the bootloader's `board_id` at flash
time (ArduPilot's `uploader.py` does the authoritative check), so dropping several
`.apj` files in is fine — you'll choose the right one per drone.

---

## Usage

### In Claude Code (the intended way)

Connect the drone and type:

```
/ardufleetcheck
```

Because firmware is drone-specific, the flow is **two calls**:

1. **First call** enumerates the `.apj` candidates it found under
   `TTFLEET_FIRMWARE_DIR` and stops (exit code 10).
2. Claude shows you the list and **asks which `.apj`** to flash.
3. **Second call** runs the full pipeline end-to-end with your choice.

That `.apj` pick is the *only* interactive prompt — everything else is automatic
(font = clarity, OSD = the bundled MGRS layout, etc.).

#### Skipping stages

If the FC is **already on the right firmware** and you just want the OSD / VTX /
RC / arm checks:

```
/ardufleetcheck --skip arduflash
```

Other useful flags (passed through to the orchestrator):

| Flag                     | Effect                                                                  |
|--------------------------|-------------------------------------------------------------------------|
| `--apj <path>`           | Skip the picker, flash this exact firmware.                             |
| `--skip a,b,c`           | Skip named stages. Valid: `arduflash,mgrsosd,osdfont,satest,rctest,canarm,loadmission` |
| `--font <name>`          | OSD font for stage 3 (default `clarity`; also `clarity_medium`, `bfstyle`, `bold`, `digital`). |
| `--mission-plan <path>`  | Upload this QGC `.plan` in stage 7 (otherwise that stage auto-skips).   |

### Running a single sub-skill

Each is also a standalone Claude Code skill — handy for spot checks:

```
/arduflash        # flash + param restore only
/mgrsosd          # just push the OSD layout
/osdfont clarity  # just set the font
/satest           # just test the VTX
/rctest           # just check RC input
/canarm           # "would this arm? what's blocking it?"
/loadmission      # upload a QGC .plan
```

### Running the scripts directly (no Claude)

The skills are plain Python and can be run from a shell:

```bash
/usr/bin/python3 ~/.claude/skills/ardufleetcheck/ardufleetcheck.py --skip arduflash
/usr/bin/python3 ~/.claude/skills/rctest/rctest.py
```

---

## Connection conventions

- **Port:** first `/dev/cu.usbmodem*` (USB direct to FC). `rctest` also accepts a
  `/dev/cu.usbserial-0001` RC-MAVLink dongle @ 460800 as a fallback.
- **Baud:** 115200 for the FC's USB MAVLink interface.
- **Port conflicts:** the orchestrator runs `lsof` first and **aborts** if Mission
  Planner / QGroundControl / DJI Pilot 2 / Betaflight Configurator is holding the
  port. Close those apps before running.

---

## What's in the box

```
ardufleetcheck/
├── README.md
├── install.sh
├── skills/                         # → installed into ~/.claude/skills/
│   ├── ardufleetcheck/             # the orchestrator
│   ├── arduflash/                  # flash + param-preserving restore
│   ├── mgrsosd/                    # push MGRS OSD layout
│   ├── osdfont/                    # set/upload OSD font
│   ├── satest/                     # VTX SmartAudio/Tramp test
│   ├── rctest/                     # RC input check
│   ├── canarm/                     # arm-readiness probe
│   ├── loadmission/                # upload QGC .plan
│   └── _helpers/                   # shared helper (closes BF Configurator)
└── data/                           # → installed into $TTFLEET_ROOT
    ├── clone_scripts/              # the flash/dump/restore workers arduflash wraps
    │   ├── 01_dump_fc.py           #   dump all params from the FC
    │   ├── 02_flash_fc.py          #   flash an .apj via ArduPilot's uploader.py
    │   └── 03_push_params.py       #   re-apply the dumped params (multi-pass)
    ├── mgrsosd ardupilot elements.param   # AP MGRS OSD layout (full OSD-namespace dump)
    ├── mgrs update/
    │   └── diff_bf_osd.rtf          # Betaflight OSD layout (for the BF code path)
    └── firmware/                   # drop your .apj builds here (empty by default)
```

`02_flash_fc.py` downloads ArduPilot's `uploader.py` to `/tmp` on first use (needs
internet once), then flashes over USB.

---

## How `/arduflash` preserves your config

The valuable trick: a flash wipes params, so `/arduflash`:

1. **Dumps** all params from the running FC to a timestamped folder.
2. Reboots to the bootloader and **flashes** the chosen `.apj`.
3. Waits for the firmware to come back, then **re-applies** the dumped params in
   **3 passes** — the repeat passes catch feature-gated params that only become
   *visible* after their parent param is set (e.g. a serial protocol that unlocks
   sub-params). 
4. Verifies the compass/accel **calibration** params survived.

Per-run artifacts land in `$TTFLEET_DUMP_ROOT/<timestamp>-board<id>/`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ABORT: no /dev/cu.usbmodem* enumerated` | Drone not plugged in / not powered / bad USB cable. |
| `ABORT: <port> is held by 'MissionPlanner'` | Close Mission Planner / QGC / Pilot 2 / BF Configurator and retry. |
| `no .apj files found` | Set `TTFLEET_FIRMWARE_DIR` to the folder with your `.apj`, or pass `--apj <path>`. |
| `ModuleNotFoundError: pymavlink` / `serial` | `"$TTFLEET_PYTHON" -m pip install pymavlink pyserial` (default python is `/usr/bin/python3`). |
| OSD layout / font file "not found" | The data dir isn't where the skills look. Set/export `TTFLEET_ROOT` to match where `install.sh` put `data/`. |
| A param won't read back | MAVLink `param_request_read` can silently drop — the scripts already retry 2–3×; re-run the stage if one param reports FAIL. |
| Flash fails board-id mismatch | You picked an `.apj` for a different board. `uploader.py` checks `board_id` against the bootloader — pick the matching firmware. |

---

## Notes & caveats

- **macOS-centric.** Serial device globbing (`/dev/cu.usbmodem*`,
  `/dev/cu.usbserial-*`) and `lsof` usage assume macOS. On Linux you'd point these
  at `/dev/ttyACM*` / `/dev/ttyUSB*`.
- **Betaflight paths included.** Sub-skills auto-detect firmware, so `/satest`,
  `/rctest`, `/osdfont`, `/mgrsosd` also handle Betaflight. The `_helpers` script
  and the `.rtf` OSD file support that BF path.
- **Firmware is not bundled.** Bring your own `.apj` builds.
- **No telemetry / no network** beyond the one-time `uploader.py` download in
  `02_flash_fc.py`.

---

*Built as Claude Code skills. To regenerate the standard OSD layout from a
known-good FC, see `skills/mgrsosd/SKILL.md`.*
