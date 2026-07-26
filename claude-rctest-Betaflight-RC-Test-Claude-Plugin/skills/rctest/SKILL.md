---
name: rctest
description: Check whether a connected Betaflight FC is receiving live RC input from its receiver. Samples MSP_RC for ~3s, prints per-channel last/min/max/jitter (with switch position + throttle annotations), reads MSP_STATUS_EX arming-disable flags to surface FAILSAFE / RX_FAILSAFE / BOXFAILSAFE, and renders a verdict (LIVE vs no-input). Live signal = any jitter > 2us, any AUX switch thrown, or throttle outside the resting band. Use when user types /rctest or asks to "verify RX", "check RC input", "is the receiver working", "see if BF sees the radio", "test bind", "did the TX rebind take".
---

# /rctest — verify Betaflight is receiving RC frames

## Trigger

User types `/rctest`, "verify RX", "check receiver", "is BF getting input from the radio", "did the bind take", "test the controller", "see channel values", etc. Betaflight only — script bails on AP/INAV.

## Script

`rctest.py` — single orchestrator. CLI:

```
rctest.py [--port /dev/cu.usbmodem...] [--duration 3] [--channels 12] [--raw]
```

- `--duration` : seconds to sample MSP_RC (default 3). Longer = better jitter detection.
- `--channels` : how many channels to show in the table (default 12; FC may return more).
- `--raw`      : print every individual sample as it arrives instead of the min/max summary. Useful when the user wants to physically move a stick and watch values update.

## Flow

1. **Detect port** — first `/dev/cu.usbmodem*`. Bail if none.
2. **Confirm Betaflight** via `MSP_FC_VARIANT` (cmd 2) → expect `BTFL`. Refuse AP/INAV/EMUF.
3. **Read `MSP_STATUS_EX`** (cmd 150) — decode `armingDisableFlags` and surface RX-related bits: `FAILSAFE`, `RX_FAILSAFE`, `BAD_RX_RECOVERY`, `BOXFAILSAFE`. These are the FC's own verdict on whether it has a valid RC link.
4. **Sample `MSP_RC`** (cmd 105) as fast as MSP responds for `--duration` seconds. Each frame returns one uint16 per channel.
5. **Per-channel stats** — min / max / last / jitter (max-min). Print table with annotations:
   - throttle: `min/failsafe` (885–900us), `idle` (990–1020us), `THROTTLE UP` (>=1100us)
   - aux: `switch LOW` (<=1300), `switch HIGH` (>=1700), `switch MID/center` (1450–1550)
   - any channel: `live jitter` (jitter >=3us), `FROZEN` (jitter ==0)
6. **Verdict** — link is LIVE if ANY of:
   - jitter >= 3us on any channel (a real RX always pushes microsecond noise)
   - any AUX channel at <=1400 or >=1600 (user has a switch thrown)
   - throttle outside the resting band (`870–1020` or `1490–1510`)

   Otherwise NOT live, with possible causes listed (TX off, RX unbound, `feature RX_SERIAL` disabled, wrong UART `serial` mapping).

   Special warning: if AETR are all locked at exactly 1500us with zero jitter, that's BF's default channel-fill when no RX frames are coming in (not a real centered radio).

## Exit codes

- 0 = link looks live
- 1 = no /dev/cu.usbmodem* port
- 2 = wrong firmware (not BTFL)
- 3 = MSP_RC unresponsive
- 4 = no samples in window
- 5 = sampled OK but verdict = NOT live

Claude can read the exit code or just the printed verdict.

## Don't-ask rules

- Don't ask "should I run the test?" — `/rctest` typed by the user means yes.
- Don't ask which firmware — the script refuses non-BF.
- Don't ask the user to hold sticks first — run the default sample. If verdict is NOT live, *then* prompt them to wiggle a stick or flip a switch and offer to re-run.

## Recommended follow-up when verdict = NOT live

In order:
1. Confirm TX is on and bound (check RX status LED — solid = bound, blinking = searching).
2. Re-run `/rctest --duration 5` while the user physically flips one switch on the TX — if values now move, the bind is fine and the first run just caught a quiet moment.
3. If still frozen: check `feature` for `RX_SERIAL`, check `serialrx_provider` matches the actual RX (CRSF/ELRS/SBUS), check the UART's `serial` function bit 64 is set on the pad the RX is wired to. When reassigning a UART's serial function, assign the new function before clearing the old — BF can silently reshuffle if you clear first.
4. If FC reports `RX_FAILSAFE` or `BAD_RX_RECOVERY` but MSP_RC values look fine, the failsafe latched once and never cleared — flipping the TX on-off-on usually resets it.

## Known gotchas

- **The first sample window may catch a quiet moment.** With a real bound RX and sticks fully still, jitter can dip below 3us briefly — re-run with `--duration 5` or `--raw` if a known-good link reports NOT live.
- **`MSP_STATUS_EX` layout drifts across BF versions.** The script parses the 4.x layout up through `armingDisableFlags`; newer trailing fields (`cpuTemperature`, `averageSystemLoadPercent`) are ignored.
- **MSP_RC reports BF's *internal* channel values**, post-channel-mapping. If `rcmap` is non-default, channel order in the table may not match AETR. The annotations (throttle band, switch positions) assume the standard AETR mapping.
- **`feature RX_MSP` mode** will return MSP_RC values previously injected by some other tool, not what a real RX is receiving. If anything recently used `MSP_SET_RAW_RC` to inject fake RC values, what you see may be that residue.

## Notes

- After flashing or rebooting the FC, give it ~8 s of quiet before running `/rctest` — aggressive MSP polling during the boot cycle can disrupt Dshot init.
- The most common cause of "RX wired but BF sees nothing" is the UART serial-function mask not being set right (bit 64 = SERIAL_RX).
- `/rctest` *reads* what the FC sees from its receiver. It does not inject fake RC values — that's a different operation entirely.
