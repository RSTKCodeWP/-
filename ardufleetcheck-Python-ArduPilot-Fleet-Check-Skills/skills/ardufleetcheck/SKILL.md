---
name: ardufleetcheck
description: AP fleet-check orchestrator — runs the full ArduPilot post-build pipeline in one command — /arduflash (dump → flash .apj → restore params → cal verify) → /mgrsosd (push AP MGRS OSD param block) → /osdfont clarity (set AP OSD font) → /satest (VTX R1→R2→R1 via PARAM_SET) → /rctest (RC_CHANNELS + SYS_STATUS RC bit). Passes explicit firmware=ardupilot signals to /satest and /rctest where they accept it. Pre-flights with `lsof` to surface port-holders (MissionPlanner / QGC / Pilot 2). Two-call workflow: first invocation runs /arduflash without --apj which enumerates candidates and exits 10; Claude calls AskUserQuestion to pick, then re-runs with --apj <path> to complete the pipeline. Single PASS/FAIL summary at end. Use when user types /ardufleetcheck, says "run the AP fleet check", "ardupilot full fleet sequence", or "arduflash + mgrsosd + osdfont + satest + rctest on this AP drone".
---

# /ardufleetcheck — ArduPilot fleet-check orchestrator

## Trigger

User types `/ardufleetcheck` or says "run the AP fleet check", "AP fleet sequence", "full pipeline on this ArduPilot drone".

## Pipeline (7 stages, all AP)

```
[1/7]  /arduflash       — 8-stage flash + param restore + cal verify (~5 min)
[2/7]  /mgrsosd         — push AP MGRS OSD param block
[3/7]  /osdfont clarity — set OSD_FONT to clarity (AP ROMFS index 0)
[4/7]  /satest          — VTX sanity test R1→R2→R1 (no reboot per toggle on AP)
[5/7]  /rctest          — RC input check
[6/7]  /canarm          — arm-readiness probe (RUN_PREARM_CHECKS + STATUSTEXT collect)
[7/7]  /loadmission     — upload QGC .plan (opt-in via --mission-plan PATH; auto-skips if omitted)
```

No 10 s BF boot-quiet between stages — AP doesn't reboot per stage. The only reboots come from /arduflash itself (which handles its own post-flash 8 s quiet + heartbeat poll internally).

## Script

`ardufleetcheck.py` — single orchestrator. CLI:

```
ardufleetcheck.py [--apj PATH] [--font NAME] [--skip a,b,c]
```

- `--apj PATH`  : firmware to flash in stage 1. If omitted, stage 1 enumerates candidates and exits 10 (operator-pick workflow).
- `--font NAME` : OSD font for stage 3 (default `clarity`).
- `--skip a,b`  : skip listed stage names. Valid: `arduflash,mgrsosd,osdfont,satest,rctest,canarm,loadmission`. Use `--skip arduflash` when the FC is already on the right firmware and you just want the OSD/VTX/RC/arm check.
- `--mission-plan PATH` : optional QGC `.plan` file to upload via /loadmission. If omitted, the /loadmission stage auto-skips. Missions are per-deployment, not standard post-build.

## Two-call workflow

1. **First call** (no `--apj`): orchestrator runs /arduflash with no `--apj`. /arduflash does stages 1-3 (detect → dump → enumerate .apj candidates) and exits 10. /ardufleetcheck propagates that exit code with a clear "re-run with --apj <path>" message.
2. **Claude calls `AskUserQuestion`** to pick from the enumerated candidates.
3. **Second call** (with `--apj <chosen>`): full pipeline runs end-to-end.

When `/arduflash` is skipped via `--skip arduflash`, the orchestrator goes straight to /mgrsosd → /osdfont → /satest → /rctest. Same command, single call.

## Explicit AP signaling

Sub-skills autodetect AP vs BF, but where they accept an explicit firmware flag, ardufleetcheck passes it for safety:

- `/satest --firmware ardupilot`
- `/rctest --force-ap`

`/mgrsosd` and `/osdfont` autodetect-only (no firmware flag), which is reliable per their current implementations.

## Don't-ask rules

- Don't ask "should I run the test?" — typing `/ardufleetcheck` means yes.
- Don't ask which font — `clarity` unless `--font` overrides.
- Don't ask whether to skip stages — `--skip` is opt-in.
- Don't ask about board_id match — /arduflash's uploader.py does the authoritative check against the bootloader.
- **DO ask** the user to pick the `.apj` after stage 1 enumeration (only operator-interactive step).

## Pre-flight check

- `lsof /dev/cu.usbmodem*` — abort if MissionPlanner / QGC / DJI Pilot 2 / anything else holds the port.
- No battery-state check required for AP (uploader.py uses USB serial, not STM32 DFU — the BF battery-unplug constraint doesn't apply).

## Failure handling

- `/arduflash` failure (any rc != 0 and != 10) → hard-stop the pipeline. Downstream stages on a broken flash are pointless and may hang.
- `/arduflash` rc == 10 → propagate to Claude for the .apj picker.
- Any downstream stage failure → record in the summary, continue to the next stage. Operator can review at the end.

## Runtime

- /arduflash: ~4-6 min (1285-param dump + ~90 s flash + 3-pass restore + cal verify on 187 cal params)
- /mgrsosd: ~10-20 s (PARAM_SET burst for OSD params)
- /osdfont clarity: ~2 s (single param toggle if ROMFS index used)
- /satest: ~10 s (PARAM_SET dance + verify, no reboot per step)
- /rctest: ~5 s
- **Total: ~5-7 min end-to-end.**

## Related memories

- `reference_arduflash_skill.md` — stage 1 details
- `reference_satest_skill.md` — dual-firmware autodetect notes
- `reference_drone_connection.md` — port + baud conventions for AP USB
- `feedback_configurator_port_grab.md` — port-grab pre-flight check rationale (applies to MissionPlanner / QGC / Pilot 2 on AP same as Configurator on BF)
- `project_ap_fleetcheck_pinned.md` — this skill closes out the "AP fleetcheck" pin
