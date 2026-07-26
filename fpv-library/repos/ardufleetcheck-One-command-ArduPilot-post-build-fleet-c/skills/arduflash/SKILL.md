---
name: arduflash
description: ArduPilot fleet-flash skill — dump all params from the connected AP FC via pymavlink, prompt user to pick an .apj firmware file, validate board_id match, reboot to bootloader, flash via ArduPilot's uploader.py, wait for AP firmware to come back, then re-apply the dumped params in 3 passes (the multi-pass loop catches feature-gated params that only become visible after parent params are set). Heavy visual progress (stage banners, [OK]/[..]/[FAIL] checkmarks). Reuses ttfleet/clone_scripts/01_dump_fc.py + 02_flash_fc.py + 03_push_params.py via subprocess. Per-run output dir at ttfleet/ardupilot dumps/<timestamp>-board<id>/. Use when the user types /arduflash, "flash this ardupilot drone", "ardupilot fleet flash", "ap flash with param preservation", or similar.
---

# /arduflash — ArduPilot fleet-flash with param preservation

## Trigger

User types `/arduflash` or says "flash this ardupilot drone", "AP fleet flash", "clone params + flash AP".

## Pipeline (8 stages)

```
[1/8]  Detect FC + confirm AP    → heartbeat + AUTOPILOT_VERSION
[2/8]  Dump current params       → ttfleet/ardupilot dumps/<ts>-board<id>/full_dump.json
[3/8]  Pick firmware             → enumerates .apj files; Claude calls AskUserQuestion
[4/8]  Reboot FC to bootloader   → MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN param1=3
[5/8]  Flash via uploader.py     → 02_flash_fc.py wraps ardupilot/Tools/scripts/uploader.py
[6/8]  Wait for AP to come back  → 8 s boot quiet, then poll heartbeat (30 s timeout)
[7/8]  Restore params (3-pass)   → 03_push_params.py; auto-exits when a pass yields 0 changes
[8/8]  Verify calibration        → focused per-group check on cal-critical params
```

Stage 8 isolates the params that, if mismatched, would force a bench recalibration:
compass cal (`COMPASS_OFS*`, `COMPASS_DIA*`, `COMPASS_ODI*`, `COMPASS_MOT*`, `COMPASS_DEV_ID*`,
`COMPASS_USE*`, `COMPASS_PRIO*_ID`, `COMPASS_ORIENT*`), accel/gyro cal (`INS_ACC*_OFFS_*`,
`INS_ACC*_SCAL_*`, `INS_GYR*_OFFS_*`, `INS_*_ID`), board orientation (`AHRS_ORIENTATION`,
`AHRS_TRIM_*`), ESC/motor cal (`MOT_PWM_MIN/MAX`, `MOT_SPIN_MIN/MAX/ARM`, `MOT_THST_HOVER`),
battery cal (`BATT*_VOLT_MULT`, `BATT*_AMP_PERVLT`, `BATT*_AMP_OFFSET`), RC cal
(`RC*_MIN/MAX/TRIM/REVERSED/DZ`), baro cal (`BARO*_GND_TEMP`, `BARO*_DEVID`).

`BARO*_GND_PRESS` is in the expected-differ list (live atmospheric reading; doesn't fail
the check). End-of-run summary prints headline numbers from `push_report.json` plus the
calibration-group results.

## Script

`arduflash.py` — single orchestrator. CLI:

```
arduflash.py [--port /dev/...] [--baud N] [--apj PATH]
```

- `--port` / `--baud` : override port autodetect (defaults: `/dev/cu.usbmodem*` @ 115200; fallback `/dev/cu.usbserial-0001` @ 460800).
- `--apj PATH`        : skip the interactive picker; flash this `.apj` directly.

## Two-call workflow (the only Claude-side coordination needed)

The script can't run `AskUserQuestion` itself. So:

1. **First call** (no `--apj`): runs stages 1, 2, 3. Stage 3 enumerates `.apj` candidates under `ttfleet/` and exits with code 10 + an "RE-RUN with --apj <path>" banner.
2. Claude reads the candidates from the script's stdout, calls `AskUserQuestion` to let the user pick.
3. **Second call** (with `--apj <chosen>`): runs stages 1+3 again briefly (dump is already on disk; just re-detects + validates board_id), then proceeds through stages 4-7.

This keeps the script self-contained and interactive without needing to embed Claude tooling.

## Reuses (don't rewrite these — call them as subprocess)

- `ttfleet/clone_scripts/01_dump_fc.py` — pymavlink param dump (PARAM_REQUEST_LIST → collect PARAM_VALUE)
- `ttfleet/clone_scripts/02_flash_fc.py` — wraps ardupilot uploader.py (downloads it from GH if missing)
- `ttfleet/clone_scripts/03_push_params.py` — multi-pass restore with skip set + FP tolerance

## Don't-ask rules

- Don't ask whether to back up params — every run dumps.
- Don't ask whether to restore — every run restores.
- Don't ask which port — autodetect.
- Don't ask about pass count — 3 passes is the default; `03_push_params.py` exits early on convergence.
- **DO ask** the user to pick the `.apj` (only explicit Claude-side interaction).

## Pre-flight checks

- `lsof /dev/cu.usbmodem*` to confirm no Configurator/MAVProxy is holding the port (per `feedback_configurator_port_grab`).
- Validate `.apj` board_id against the connected FC's `AUTOPILOT_VERSION.board_version`. Mismatch → abort before reboot.

## Known gotchas

- **AP bootloader is NOT STM32 DFU.** uploader.py talks to ArduPilot's own bootloader over USB serial (the same `/dev/cu.usbmodem*` path). No `dfu-util`, no `0483:df11` device. After REBOOT_SHUTDOWN param1=3, the FC stays at the same USB CDC path; uploader.py does the handshake.
- **Post-flash 8 s boot quiet** is mandatory before probing heartbeat (per `feedback_bf_boot_cycle_quiet`).
- **Post-flash USB serial may change.** The script's `find_port()` re-scans after stage 5.
- **Remaining diffs after pass 3 are normal:** `BARO1_GND_PRESS` is a live atmospheric reading and will never match a stale dump. `COMPASS_DEV_ID` / `INS_*_ID` only stick when the matching physical sensor is present.
- **Pass count = 3** because some params are feature-gated. E.g. setting `SERIAL5_PROTOCOL=10` (DroneCAN) unlocks `CAN_P*_*` params that weren't visible on pass 1. Multi-pass is the proven pattern in `03_push_params.py`.

## Exit codes

- 0  : full success (all stages PASS including cal verify)
- 1  : no FC port found
- 2  : stage 1 failed (heartbeat or AUTOPILOT_VERSION)
- 3  : stage 2 failed (dump)
- 4  : stage 3 — no .apj candidates
- 5  : stage 3 — board_id mismatch
- 6  : stage 4 — reboot failed
- 7  : stage 5 — flash failed
- 8  : stage 6 — AP did not come back
- 9  : stage 7 — restore failed
- 10 : interactive prompt needed (re-run with `--apj`)
- 11 : stages 1-7 OK but stage 8 found calibration mismatches (FC is flashed and operable; user should recalibrate the flagged subsystem)

## Related memories

- `reference_fc_clone_workflow.md` — the 5-script clone workflow this skill orchestrates
- `reference_drone_connection.md` — port + baud conventions
- `reference_rc_mavlink_connection.md` — usbserial-0001 fallback
- `feedback_configurator_port_grab.md` — port-grab pre-flight check
- `feedback_bf_boot_cycle_quiet.md` — 8 s post-reboot quiet (applies to AP too)
- `feedback_bfflash_battery_unplug.md` — BF-only; AP uploader.py uses USB serial not DFU, so battery state is less critical
- `reference_betafleetcheck_skill.md / project_ap_fleetcheck_pinned.md (shipped as /ardufleetcheck)` — this is step 1 of a longer AP-fleetcheck buildout
