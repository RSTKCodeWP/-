---
name: loadmission
description: Upload a QGroundControl .plan mission file to a connected ArduPilot drone via MAVLink. Lists .plan files from ~/Documents/QGroundControl/Missions sorted newest-first, asks the user to pick, then uploads via MISSION_COUNT + MISSION_REQUEST_INT + MISSION_ITEM_INT exchange and waits for MISSION_ACK. Clears the existing mission first. ArduPilot-only. Use when the user types /loadmission, says "load a mission", "upload mission", "send the QGC plan to the drone".
---

# /loadmission — upload a QGC .plan to ArduPilot

## Trigger

User types `/loadmission` or says "load a mission", "upload mission to the drone", "send the QGC plan".

ArduPilot-only. Betaflight doesn't run waypoint missions.

## Script

`loadmission.py` — single MAVLink uploader. CLI:

```
loadmission.py [--plan PATH] [--port /dev/...] [--baud N] [--missions-dir DIR]
```

- `--plan PATH`        : the .plan file to upload. If omitted, enumerates available plans and exits 10 (operator-pick workflow).
- `--port` / `--baud`  : MAVLink port + baud (auto-detected if omitted; usbmodem*=115200, usbserial-0001=460800).
- `--missions-dir`     : where to look for .plan files (default `~/Documents/QGroundControl/Missions`).

## Two-call workflow

1. **First call** (no `--plan`): the script lists `.plan` files in the missions dir, sorted by modification time (newest first), and exits with code 10. Output prints a numbered list with timestamps.
2. **Claude calls `AskUserQuestion`** to pick from the enumerated list.
3. **Second call** (with `--plan <chosen-path>`): the script parses the plan, connects to the FC, clears the existing mission, and uploads the new one.

## Pipeline (when --plan given)

1. **Parse** the QGC `.plan` JSON. Validates `fileType == "Plan"`. Walks `mission.items[]` — each must be `type == "SimpleItem"` with 7 params (`[p1, p2, p3, p4, lat°, lon°, alt_m]`). Complex items (survey patterns, etc.) abort.
2. **Print a brief command summary** (e.g. `TAKEOFF×1, WAYPOINT×4, RTL×1`) so the operator can sanity-check before upload.
3. **Connect via pymavlink**, wait for AP heartbeat, advertise GCS heartbeats. Abort if the autopilot isn't AP.
4. **`MISSION_CLEAR_ALL`** for `MAV_MISSION_TYPE_MISSION` — wipe existing mission before upload (avoids stale items past the new mission's end).
5. **Send `MISSION_COUNT(n)`**. AP responds with `MISSION_REQUEST_INT(seq=0)`.
6. For each `seq` AP requests, send `MISSION_ITEM_INT` with the matching item. Lat/lon are scaled from float° to int32 (`* 1e7`), altitude stays as float meters.
7. After the final item, AP sends `MISSION_ACK`. Decode the type: 0 = ACCEPTED (success), anything else = failure reason (e.g. INVALID_SEQUENCE, NO_SPACE, INVALID_PARAM5_X for bad coordinate).
8. **Re-send COUNT once** if AP doesn't respond with a request within 2 s of the initial COUNT. Time out if no request arrives in 8 s total.

## Exit codes

- 0  = mission uploaded (MISSION_ACK = ACCEPTED)
- 1  = no port found
- 2  = no heartbeat / wrong autopilot
- 3  = no .plan files, file not found, or parse error
- 4  = upload failed (timeout or AP rejected with non-zero ACK type)
- 10 = enumeration only — re-run with --plan PATH

## Don't-ask rules

- Don't ask which mission to upload — the operator-pick step is the only interactive part.
- Don't ask whether to clear the existing mission — always clear first. Without that, leftover items past the new mission's end keep "running" after RTL finishes.
- Don't ask which firmware — AP-only by design.

## Known gotchas

- **MISSION_ITEM_INT vs MISSION_ITEM**: the script always sends INT (int32-scaled lat/lon). Modern AP and QGC both prefer INT — the float-coordinate `MISSION_ITEM` form is deprecated and loses 0.1 m of precision at the equator.
- **QGC's `plannedHomePosition` is NOT uploaded.** AP sets home from the GPS lock or an explicit `SET_HOME_POSITION` command — sending it as a mission item confuses things.
- **Complex items** (survey, structure-scan, corridor-scan) get expanded to multiple SimpleItems when QGC saves. If your .plan still has `type: "ComplexItem"` entries, save it again from QGC after a small edit — newer QGC versions normalize on save. The script aborts on ComplexItem to avoid uploading a half-mission.
- **Mission item indices use `doJumpId`** from QGC as their seq number. The script uses array position instead — AP just wants 0..N-1 contiguous, which matches what QGC writes.
- **Frame matters**: QGC mostly emits frame=3 (`MAV_FRAME_GLOBAL_RELATIVE_ALT` — altitude is relative to launch). frame=10 is `MAV_FRAME_GLOBAL_RELATIVE_ALT_INT`. We pass whatever the plan has.
- **MISSION_CLEAR_ALL** also clears the rally and fence by default in older AP — we explicitly set `mission_type=MAV_MISSION_TYPE_MISSION` to scope it.

## Related memories

- `reference_drone_connection.md` — port + baud conventions
- `reference_rc_mavlink_connection.md` — usbserial-0001 fallback for the RC-MAVLink dongle
- `reference_canarm_skill.md` — sibling probe; check arm-readiness after the mission upload
