---
name: canarm
description: Probe an ArduPilot drone's arm-readiness via MAVLink. Sends MAV_CMD_RUN_PREARM_CHECKS (cmd 401), then listens ~3 s for STATUSTEXT "PreArm:" messages, the SYS_STATUS PREARM_CHECK sensor bit (0x2000), and HEARTBEAT system_status. Reports READY (AP would accept an arm command), NOT READY (with the human-readable PreArm failure reasons), or ARMED (FC is already armed). Read-only — does not actually arm. Use when user types /canarm or asks "would this arm?", "is the drone ready to fly", "what's blocking arming", "check prearm".
---

# /canarm — ArduPilot arm-readiness probe

## Trigger

User types `/canarm` or says "would this arm?", "is the drone ready", "check prearm", "what's blocking arming", "can it fly".

ArduPilot-only. Betaflight uses MSP_STATUS_EX armingDisableFlags which is already surfaced by /rctest — no need for a separate skill there.

## Script

`canarm.py` — single MAVLink probe. CLI:

```
canarm.py [--port /dev/...] [--baud N] [--duration SECONDS]
```

- `--port` : MAVLink port (auto if omitted; usbmodem* preferred, usbserial-0001 dongle fallback)
- `--baud` : auto-selected by port name (115200 for usbmodem*, 460800 for usbserial-0001) if omitted
- `--duration` : seconds to collect STATUSTEXT/SYS_STATUS after the RUN_PREARM_CHECKS command (default 3)

## Pipeline

1. **Detect port** — first `/dev/cu.usbmodem*`, fall back to `/dev/cu.usbserial-0001` (RC-MAVLink dongle).
2. **Connect via pymavlink**, advertise GCS heartbeats, wait for AP heartbeat (5 s timeout).
3. **Read current arm state** from `HEARTBEAT.base_mode` — if `MAV_MODE_FLAG_SAFETY_ARMED` (0x80) is set, the FC is already armed → print "ARMED" and exit 0.
4. **Send `MAV_CMD_RUN_PREARM_CHECKS`** (command 401) — explicit "re-run pre-arm now" trigger. AP responds by emitting fresh STATUSTEXT messages for any failing check.
5. **Collect for `--duration` seconds**:
   - **STATUSTEXT** — filter for lines starting with `PreArm:` or `Arm:` (the human-readable failure reasons). Also retain "interesting" other STATUSTEXTs (anything that isn't boot/banner noise).
   - **SYS_STATUS.onboard_control_sensors_health** — bit 13 (`MAV_SYS_STATUS_PREARM_CHECK = 0x2000`) is the aggregate pre-arm pass/fail bit AP sets when its arming checker has finished a pass.
   - **HEARTBEAT.system_status** — `MAV_STATE_STANDBY` (3) = ready to arm, `CRITICAL` (5)/`EMERGENCY` (6) = won't arm.
6. **Decode unhealthy enabled sensors** from `onboard_control_sensors_enabled & ~onboard_control_sensors_health` — useful when no PreArm STATUSTEXT was emitted (e.g. waiting for next pre-arm pass).
7. **Verdict**:
   - **READY TO ARM** — PREARM_CHECK bit set + system_status==STANDBY + no PreArm: messages
   - **NOT READY** — list PreArm reasons; if reasons list is empty but PREARM_CHECK bit is clear, note that and suggest `--duration 6`

## Exit codes

- 0 = ready to arm (or already armed — both states mean the arm command works)
- 1 = no port found
- 2 = pymavlink missing or no heartbeat
- 5 = not ready (with reasons printed)

## Don't-ask rules

- Don't ask which firmware — AP-only by design.
- Don't ask the user to power on the TX — we're checking FC-side arming readiness, not just RX presence. The lack of RC frames is one of many reasons AP might refuse to arm; that should be surfaced by the probe, not pre-empted by the operator.

## Known gotchas

- **AP runs pre-arm in a periodic loop** (10 Hz). The `RUN_PREARM_CHECKS` command we send just nudges the next cycle to emit STATUSTEXT for failures. If duration is too short (<2 s) you may miss the STATUSTEXT but still get the PREARM_CHECK sensor bit.
- **The PREARM_CHECK bit is ground truth for "AP's pre-arm currently passes."** A drone with the bit set will accept an arm command. STATUSTEXT messages are the friendly version of *why* it doesn't.
- **GPS-required checks** depend on `ARMING_CHECK` bitmask. A drone with GPS arming disabled can be READY without a 3D fix.
- **`safety switch`** state — if AP's hardware safety switch is OFF (most fleet builds disable this via BRD_SAFETYOPTION) you'll see "PreArm: Hardware safety switch" until it's pressed. Skip on builds where the safety switch is permanently disarmed.
- **Currently-armed FC**: we report "ARMED" and exit 0 without sending RUN_PREARM_CHECKS — AP ignores the command while armed anyway, and we don't want any state changes.

## Related memories

- `reference_drone_connection.md` — port + baud conventions
- `reference_rc_mavlink_connection.md` — usbserial-0001 fallback
- `reference_rctest_skill.md` — sibling skill; /rctest answers "is RC working" (one input to prearm). /canarm answers "would the FC arm right now overall."
