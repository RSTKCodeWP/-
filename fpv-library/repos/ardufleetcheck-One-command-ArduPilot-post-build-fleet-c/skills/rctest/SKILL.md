---
name: rctest
description: Check whether a connected Betaflight OR ArduPilot FC is receiving live RC input from its receiver. Autodetects firmware MSP-FIRST (per feedback_msp_first_detection.md — ~0.5s; MSP variant 'BTFL'=Betaflight, 'ARDU'=ArduPilot). Falls back to MAVLink heartbeat probe (2 attempts × 3s) only when MSP is silent. Samples RC channels for ~3s, prints per-channel last/min/max/jitter (with switch position + throttle annotations), and reads firmware-side failsafe state — MSP_STATUS_EX arming-disable flags (FAILSAFE / RX_FAILSAFE / BOXFAILSAFE) on BF, or SYS_STATUS RC_RECEIVER health bit on AP — then renders a verdict (LIVE vs no-input). Live signal = any jitter > 2us, any AUX switch thrown, or throttle outside the resting band. Use when user types /rctest or asks to "verify RX", "check RC input", "is the receiver working", "see if BF/AP sees the radio", "test bind", "did the TX rebind take".
---

# /rctest — verify a BF or AP FC is receiving RC frames

## Trigger

User types `/rctest`, "verify RX", "check receiver", "is the FC getting input from the radio", "did the bind take", "test the controller", "see channel values", etc. Works on Betaflight and ArduPilot; autodetected. INAV/EMUF bail out.

## Script

`rctest.py` — single orchestrator. CLI:

```
rctest.py [--port /dev/cu.usb...] [--duration 3] [--channels 12] [--raw]
          [--force-ap | --force-bf]
```

- `--duration` : seconds to sample RC frames (default 3). Longer = better jitter detection.
- `--channels` : how many channels to show in the table (default 12; FC may return more).
- `--raw`      : print every individual sample as it arrives instead of the min/max summary. Useful when the user wants to physically move a stick and watch values update.
- `--force-ap` / `--force-bf` : skip the firmware autodetect.

## Port resolution

1. `/dev/cu.usbmodem*` — direct USB to FC (BF or AP, 115200)
2. Fallback: `/dev/cu.usbserial-0001` @ 460800 — RC-MAVLink ground dongle (AP only)

Explicit `--port /dev/cu.usbserial-...` forces AP @ 460800.

## Firmware detection — MAVLink first

ArduPilot's USB CDC multiplexes MSP and MAVLink. If a client sends an MSP
frame first, AP's MSP-OSD server responds (variant string `ARDU`) and the
channel can get stuck in MSP mode with MAVLink heartbeats stalled. So we
probe MAVLink **before** MSP. BF doesn't speak MAVLink — the probe just
times out harmlessly there. See `feedback_ap_mavlink_first_detection.md`.

1. If `--force-bf` / `--force-ap` is set, or the port is a usbserial dongle, skip detection.
2. **MAVLink probe**: open pymavlink with `source_system=255, source_component=190`, send 4× `HEARTBEAT(MAV_TYPE_GCS)` over ~0.8s, then `wait_heartbeat(timeout=4)`. Up to 3 attempts. Any heartbeat → AP.
3. **MSP probe**: only if MAVLink probed empty — MSP `MSP_FC_VARIANT` (cmd 2). `BTFL` → BF.
4. `ARDU` / `INAV` / `EMUF` / no response → bail with exit 2.

The AP session path also re-sends 4× GCS heartbeats immediately after the
"real" connect (not just during the probe) so AP's USB stays in MAVLink mode
through the entire sample window.

## BF flow (MSP)

1. **Read `MSP_STATUS_EX`** (cmd 150) — decode `armingDisableFlags` and surface RX-related bits: `FAILSAFE`, `RX_FAILSAFE`, `BAD_RX_RECOVERY`, `BOXFAILSAFE`. These are the FC's own verdict on whether it has a valid RC link.
2. **Sample `MSP_RC`** (cmd 105) as fast as MSP responds for `--duration` seconds. Each frame returns one uint16 per channel.

## AP flow (MAVLink)

1. **Connect via pymavlink**, wait for heartbeat.
2. **Request `RC_CHANNELS` at 50 Hz** via `MAV_CMD_SET_MESSAGE_INTERVAL` (msg ID 65). Falls back gracefully if the FC ignores the request — default stream rate still yields enough samples for a coarse read.
3. **Read `SYS_STATUS`** — check bit 18 (`MAV_SYS_STATUS_SENSOR_RC_RECEIVER`) for present/enabled/healthy. If `healthy=0`, AP itself believes the link is bad (failsafe latched).
4. **Sample `RC_CHANNELS`** for `--duration` seconds. `chan1_raw`..`chan18_raw` are uint16 µs; `65535` = "not provided", treated as no data on that channel. `chancount` trims to the FC-reported usable count.

## Verdict (same for both firmwares)

Per-channel stats: min / max / last / jitter (max-min). Table annotations:
- throttle: `min/failsafe` (885–900us), `idle` (990–1020us), `THROTTLE UP` (>=1100us)
- aux: `switch LOW` (<=1300), `switch HIGH` (>=1700), `switch MID/center` (1450–1550)
- any channel: `live jitter` (jitter >=3us), `FROZEN` (jitter ==0)

Link is LIVE if ANY of:
- jitter >= 3us on any channel (a real RX always pushes microsecond noise)
- any AUX channel at <=1400 or >=1600 (user has a switch thrown)
- throttle outside the resting band (`870–1020` or `1490–1510` — AP's `FS_THR_VALUE` default 975 lands in this band too)

Otherwise NOT live, with firmware-specific causes listed.

Special warning: if AETR are all locked at exactly 1500us with zero jitter, that's the default channel-fill when no real RX frames are coming in.

## Channel mapping assumption

Both BF (AETR via `rcmap`) and AP (default `RCMAP_ROLL=1`, `RCMAP_PITCH=2`, `RCMAP_THROTTLE=3`, `RCMAP_YAW=4`) use the same default AETR ordering, so the table labels (`roll`, `pitch`, `throttle`, `yaw`, `aux1`…) are correct out of the box. If RCMAP is non-default on AP or `rcmap` is non-default on BF, channel-order labels may not match the physical sticks — but the verdict logic still works.

## Exit codes

- 0 = link looks live
- 1 = no port found
- 2 = unsupported firmware / no heartbeat
- 3 = RC frames unresponsive (no MSP_RC reply or no RC_CHANNELS arriving)
- 4 = no samples collected in window
- 5 = sampled OK but verdict = NOT live

Claude can read the exit code or just the printed verdict.

## Don't-ask rules

- Don't ask "should I run the test?" — `/rctest` typed by the user means yes.
- Don't ask which firmware — the script autodetects.
- Don't ask the user to hold sticks first — run the default sample. If verdict is NOT live, *then* prompt them to wiggle a stick or flip a switch and offer to re-run.

## Recommended follow-up when verdict = NOT live

In order:
1. Confirm TX is on and bound (check RX status LED — solid = bound, blinking = searching).
2. Re-run `/rctest --duration 5` while the user physically flips one switch on the TX — if values now move, the bind is fine and the first run just caught a quiet moment.
3. If still frozen:
   - **BF**: check `feature` for `RX_SERIAL`, check `serialrx_provider` matches the actual RX (CRSF/ELRS/SBUS), check the UART's `serial` function bit 64 is set on the pad the RX is wired to. See memory `feedback_bf_serial_ordering.md`.
   - **AP**: check `SERIAL*_PROTOCOL = 23` (RCIN) on the RX UART, check `RC_PROTOCOLS` bitmask includes the receiver's protocol (e.g. CRSF=8, SBUS=0, etc.), and that `BRD_ALT_CONFIG` selects the right pin if the FC uses a dedicated RCIN pin.
4. **BF only**: if FC reports `RX_FAILSAFE` or `BAD_RX_RECOVERY` but MSP_RC values look fine, the failsafe latched once and never cleared — flipping the TX on-off-on usually resets it. **AP**: same idea — if `RC_RECEIVER` healthy=0 but channel values look fine, power-cycle the TX.

## Known gotchas

- **The first sample window may catch a quiet moment.** With a real bound RX and sticks fully still, jitter can dip below 3us briefly — re-run with `--duration 5` or `--raw` if a known-good link reports NOT live.
- **`MSP_STATUS_EX` layout drifts across BF versions.** The script parses the 4.x layout up through `armingDisableFlags`; newer trailing fields (`cpuTemperature`, `averageSystemLoadPercent`) are ignored.
- **MSP_RC reports BF's *internal* channel values**, post-channel-mapping. `RC_CHANNELS` on AP reports physical RX channels pre-RCMAP. If either FC has a non-default mapping, the column labels (`roll`/`pitch`/`throttle`/`yaw`) may not match the user's stick.
- **`feature RX_MSP` mode (BF)** will return MSP_RC values that *Claude* wrote, not what an actual RX is receiving. If a chained skill recently called `/wiggle`, the values you see may be the wiggle's residue, not live RX frames.
- **RC-MAVLink dongle path is AP-only.** A BF FC can't be reached over `/dev/cu.usbserial-0001` — that route requires MAVLink.

## Related memories

- `reference_bfflash_skill.md` — after a `/bfflash` the RX needs to rebind; `/rctest` is the natural follow-up.
- `reference_arduflash_skill.md` — same for AP after `/arduflash`.
- `reference_wiggle_skill.md` — sibling skill that *injects* fake RC values via MSP_SET_RAW_RC. `/rctest` *reads* what the FC is seeing.
- `reference_rc_mavlink_connection.md` — the `/dev/cu.usbserial-0001 @ 460800` fallback path this skill uses for AP-via-dongle.
- `feedback_bf_serial_ordering.md` — most common cause of "RX wired but BF sees nothing" is the UART serial-function mask not being set right.
- `feedback_bf_boot_cycle_quiet.md` — if /rctest runs immediately after a BF reboot, give the FC its 8s boot quiet period before probing.
