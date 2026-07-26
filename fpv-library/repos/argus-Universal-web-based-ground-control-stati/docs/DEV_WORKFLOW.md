# Argus + ArduPilot — Development Workflow

Two-environment split. **Each task runs in the environment where it is most natural; cross-environment trips are minimized to git pulls and the occasional firmware APJ copy.**

## TL;DR — Where each task lives

| Task | Where | Why |
| - | - | - |
| Write Argus code, run lint/tests | **WSL2** | CI is Ubuntu; ruff / pytest / vitest / svelte-check are all native; same toolchain as everyone else |
| Run Argus against ArduPilot SITL | **WSL2** | SITL is Linux; one host, zero glue |
| Run Argus against the **real FC** | **Windows** | `COM6/COM8` directly accessible; WebSerial and backend share the same host; no usbipd dance |
| Real-sensor calibration (compass/gyro/accel/level/baro) | **Windows** | Same as above |
| Flash FC firmware | **Windows** | FC uploader / Mission Planner are Windows tools |
| End-user demo / acceptance | **Windows** | Matches the deployment environment |
| Edit ArduPilot fork (C++) | **WSL2** | waf, SITL build, fork maintenance — Linux-first ecosystem |
| Build ArduPilot SITL or firmware APJ | **WSL2** | Same |

Single rule: **never test the real FC in WSL via usbipd in the steady state.** It works (proven by the 2026-05-24 A.0 baseline), but Windows-native is materially simpler and matches the user environment. Keep usbipd as an emergency fallback only.

## WSL2 — main development environment

Already set up. See `docs/MIGRATION_TO_WSL.md` for the bootstrap.

**Daily commands**:

```bash
cd ~/project/argus

# Run against SITL
python run.py --sim                          # backend + simulator on :8100

# Pre-commit gate
ruff check backend/ scripts/ tests/
~/argus-venv/bin/python -m pytest tests/test_unit_*.py tests/test_contract_*.py -v
npx vitest run
npx svelte-check
npm run build                                # only when shipping
```

**Retire usbipd in the steady state**. From Windows admin PowerShell, when you are sure you are done validating in WSL:

```powershell
usbipd detach --busid=2-1                    # release back to Windows
usbipd unbind --busid=2-1                    # remove the share
```

(Re-bind only if you ever need a one-off WSL-side hardware test again.)

## Session record / replay — hardware sessions as offline assets

Every live connection automatically records every **validated** MAVLink frame
(both directions) to `logs/argus_*.tlog` alongside the telemetry CSV. The
format is standard tlog (8-byte big-endian µs timestamp per message) —
readable by pymavlink `mavlogdump.py` and Mission Planner. Frames that fail
CRC or carry unknown msg ids are dropped before recording (they surface in
`parse_errors` / the unknown-id log instead) — the tlog captures exactly what
drove state, not the raw wire noise.

This shrinks the code→hardware→observe loop: an FC quirk captured once on the
Windows box replays forever in WSL, no hardware attached.

**Replay into the running UI** — connect with a `replay:` port (optional
`@speed` suffix); commands are discarded, the session loops at end-of-log:

```
replay:logs/argus_20260712_213300.tlog@10
```

**Replay into tests** — drive the real parse→dispatch→state path offline:

```python
from backend.replay import replay_into
link = DroneLink()
replay_into(link, "tests/fixtures/that_weird_calibration.tlog")
assert link.get_state()["..."] == ...
```

When a hardware session exposes a bug, copy its tlog into `tests/fixtures/`
and pin the fixed behavior with a replay test. Frame builders for synthetic
sessions live in `tests/frame_builders.py`.

### Calibration fixtures — recorded from real-firmware SITL

`tests/fixtures/{magcal,accelcal}_sitl.tlog` are full calibration handshakes
(onboard compass cal incl. accept; 6-position accel cal) recorded against the
prebuilt ArduPilot SITL using its special `calibration` vehicle model, driven
end-to-end through the backend's own command path.
`tests/test_contract_calibration_replay.py` replays them every CI run — the
offline regression for the calibration protocol, no hardware or SITL needed.

Regenerate after changing anything FC-coupled in the calibration flow:

```bash
python tests/sitl_calibrate.py   # self-contained: boots SITL + backend, ~3 min
```

The recorder is also a live integration test — it dies loudly if any step of
either handshake stalls (that is how the missing MAG_CAL_PROGRESS stream
subscription was found).

## Windows — hardware + demo station

### First-time setup (~15 minutes)

```powershell
# 1. Toolchains (or use python.org / nodejs.org installers)
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install Git.Git

# 2. Independent clone — do NOT use \\wsl.localhost\... paths
git clone https://github.com/L-X-Yao/argus.git C:\argus
cd C:\argus

# 3. Python deps (use a Windows-native venv, separate from WSL's)
python -m venv C:\argus-venv-win
C:\argus-venv-win\Scripts\Activate.ps1
pip install -e ".[dev]"

# 4. Node deps + build (also separate from WSL's node_modules)
npm install
npm run build
```

**Why separate venv + node_modules**: WSL's `~/argus-venv` is a Linux ELF binary tree and its `node_modules/` has Linux-compiled native modules (vite/rolldown). Reusing them on Windows fails immediately; installing Windows versions on top corrupts the WSL ones. Two independent trees, synced through git, is the only clean shape.

### Daily flow

```powershell
cd C:\argus
git pull                                     # always pull first
C:\argus-venv-win\Scripts\Activate.ps1
python run.py                                # backend on :8100, no sim — connect real FC from the UI
```

Then in Chrome (or Edge): `http://localhost:8100` → click **USB** (WebSerial) or the normal **连接** button (backend pyserial mode on `COM6`).

### What lives on Windows

- `C:\argus` — independent git clone
- `C:\argus-venv-win` — Windows Python venv
- That's it. No ArduPilot source; no SITL binaries; no toolchain.

## ArduPilot fork — WSL only

```bash
# One-time
git clone --recursive https://github.com/ArduPilot/ardupilot.git ~/ardupilot
cd ~/ardupilot
git checkout master                          # or checkout your target branch/commit
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile

# Build SITL (for Argus protocol-layer development)
./waf configure --board sitl
./waf copter
# → build/sitl/bin/arducopter

# Build flashable firmware
./waf configure --board <your-board-name>
./waf copter
# → build/<your-board>/bin/arducopter.apj
```

**Flashing the FC**: build the APJ in WSL, copy it to Windows, flash from Windows:

```
# In Windows Explorer
\\wsl.localhost\Ubuntu\home\administrator\ardupilot\build\<your-board>\bin\arducopter.apj
→ copy to C:\firmware\
→ flash with FC uploader / Mission Planner over COM6
```

Cross-boundary file copy is acceptable here because it is low-frequency (a flash, not a build).

## Synchronization discipline

The only two-environment failure mode is **forgetting to push before switching sides**. The recovery is annoying (uncommitted work on the wrong side, manual transfer) but not catastrophic.

Habit: every time you finish a chunk on one side, `git push` before opening the other terminal. If WSL is `git status` clean and Windows is `git pull` clean, you cannot trip yourself.

## When you really must use the other environment

- **Need Linux-only tool on Windows**: open WSL ad-hoc, don't try to install Linux things on Windows
- **Need a one-off real-FC test in WSL** (e.g. reproducing a hardware-coupled bug that only shows on the WSL pyserial path): re-bind + attach via usbipd per `docs/MIGRATION_TO_WSL.md` Phase 4. Detach when done.
- **Need to run Argus against SITL on Windows**: don't. SITL goes in WSL with `python run.py --sim`. If Windows really must drive SITL, it can connect to the WSL SITL TCP port at `tcp:<wsl-ip>:5760` — but this is a workaround, not the path.

## Why this is the shape

- **CI is Ubuntu** — main dev environment matching CI catches Linux-only regressions in the dev loop, not at PR time
- **End users are on Windows** — running real hardware integration on Windows matches their environment; nothing is "works on my machine" only
- **ArduPilot maintainers are on Linux** — fork patches and SITL stay in the most-supported toolchain
- **WSL+usbipd works but is not free** — every hardware test session pays attach/detach + the WebSerial detach-back tax. Windows-native pays nothing
- **Two clean trees beat one shared tree** — every attempt to share venv or node_modules across the WSL ↔ Windows boundary fails on native binary differences. Git as the single source of truth removes the failure mode entirely
