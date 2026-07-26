# claude-rctest

A Claude Code plugin that verifies a connected Betaflight FC is actually receiving live RC frames from its receiver. Samples `MSP_RC` for a few seconds, decodes `MSP_STATUS_EX` failsafe flags, and renders a LIVE / NOT-LIVE verdict with per-channel jitter, switch positions, and throttle annotations.

## Install

```
/plugin install rctest@paulnurkkala/claude-rctest
```

## Usage

```
/rctest
```

or ask "verify RX", "check the receiver", "is BF getting input from the radio", "did the bind take", "test the controller".

Flags:

- `--duration SECONDS` — sample longer (default 3). Longer windows catch slower switch movements.
- `--channels N` — how many channels to show in the table (default 12).
- `--raw` — print every individual sample as it arrives instead of the min/max summary. Useful when physically wiggling a stick to watch values update.
- `--port PATH` — override port autodetect.

## Requirements

- macOS/Linux with a Betaflight FC on `/dev/cu.usbmodem*`
- Python 3 with `pyserial` (`pip install pyserial`)

## What it does

1. Confirms `MSP_FC_VARIANT == 'BTFL'` — refuses ArduPilot/INAV/EmuF.
2. Reads `MSP_STATUS_EX` (cmd 150) and decodes `armingDisableFlags`, surfacing `FAILSAFE`, `RX_FAILSAFE`, `BAD_RX_RECOVERY`, `BOXFAILSAFE` — the FC's own verdict on whether the link is healthy.
3. Samples `MSP_RC` (cmd 105) as fast as MSP responds for `--duration` seconds.
4. Per-channel stats: min / max / last / jitter. Annotates throttle bands (failsafe / idle / up), AUX positions (LOW / MID / HIGH), and flags any frozen channel (jitter = 0).
5. **Verdict** — link is LIVE if jitter ≥ 3µs on any channel, or any AUX is thrown, or throttle is outside the resting band. Special warning when AETR are all locked at exactly 1500µs with zero jitter — that's BF's default channel-fill when no RX frames are arriving, not a real centered radio.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Link looks live |
| 1 | No `/dev/cu.usbmodem*` port found |
| 2 | Wrong firmware (not BTFL) |
| 3 | `MSP_RC` unresponsive |
| 4 | No samples in window |
| 5 | Sampled OK but verdict = NOT live |

## License

MIT
