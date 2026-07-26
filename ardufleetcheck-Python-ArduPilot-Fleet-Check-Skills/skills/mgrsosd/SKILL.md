---
name: mgrsosd
description: Push the standard MGRS OSD layout to a connected FC. Autodetects Betaflight (MSP) vs ArduPilot (MAVLink) and applies the right file — BF gets `$TTFLEET_ROOT/mgrs update/diff_bf_osd.rtf` pasted into CLI (with stale-element clear), AP gets `$TTFLEET_ROOT/mgrsosd ardupilot elements.param` pushed via PARAM_SET. The AP .param file is a full OSD-namespace dump, so EN=0 lines double as the "clear unwanted elements" step. Use when user types /mgrsosd or asks to "push OSD layout", "apply MGRS OSD", "load OSD file".
---

# /mgrsosd — push the MGRS OSD layout to BF or AP

## Trigger

`/mgrsosd`, "push the OSD layout", "apply the MGRS OSD", "load the OSD file".

## Script

`mgrsosd.py` — single orchestrator that autodetects firmware family. CLI:

```
mgrsosd.py [--file PATH] [--port /dev/...]
```

Default files (selected after detection; both under `$TTFLEET_ROOT`):
- BF: `$TTFLEET_ROOT/mgrs update/diff_bf_osd.rtf`
- AP: `$TTFLEET_ROOT/mgrsosd ardupilot elements.param`

## Detection

1. MSP probe (`MSP_FC_VARIANT`) on the first `/dev/cu.usbmodem*`.
2. If returns `BTFL` → Betaflight path.
3. Otherwise → ArduPilot path (open MAVLink at 115200, wait for heartbeat).

## Betaflight flow (unchanged from v3)

1. Enter CLI with bare `#` (per `feedback_bf_cli_entry.md`).
2. `feature` — if `OSD` not in active list, send `feature OSD`.
3. Scan currently-set OSD elements via `diff` and remember every key with a nonzero position.
4. Inject `set osd_<key>_pos = 0` lines right after `batch start` so stale elements are zeroed before the new layout is applied.
5. Paste each `.rtf` line. Wait for the next `# ` prompt between lines (5 s timeout).
6. Stop after `save` (FC reboots). **No further probes, no verification, no /wiggle.**
7. If `save` is refused due to per-line errors, re-enter CLI and re-paste with rejected lines filtered out.

## ArduPilot flow

1. Connect via pymavlink at 115200 and wait for heartbeat.
2. Fetch the full param list (cached for the run; refreshed each pass).
3. Print the **currently-enabled OSD elements** as a state snapshot before mutating (per `feedback_show_state_before_mutating_fc.md`).
4. For every `OSD*` line in the `.param` file:
   - Skip if the FC's current value already matches.
   - Otherwise `PARAM_SET` and verify via the echoed `PARAM_VALUE`.
5. **Multi-pass (2)** — `OSD2_ENABLE=1`/`OSD_TYPE` and similar gating params may need a second pass to surface dependent params.
6. Print a summary: already-matching / newly-set / missing-on-FC / failed-to-set, with samples.

The .param file is a full OSD-namespace dump (236 params), so it includes `OSD1_*_EN = 0` lines for every element the standard layout does NOT want enabled. Pushing the whole file is the "clear stale + push new" operation in a single transaction — no separate clear step needed.

AP params persist immediately on `PARAM_SET`. **No reboot is performed.** If the user wants a clean visual confirmation, they can power-cycle manually.

## What this skill deliberately does NOT do

- BF: no `dump master` (crashed FC on May-15 build — see `feedback_bf_silent_serial_revert.md`). No re-enumeration polling, no verify readback, no `/wiggle` chain.
- AP: no reboot, no verify-after-reboot, no save (AP saves on PARAM_SET automatically).

## Updating the "AP standard layout"

The AP master file lives at `$TTFLEET_ROOT/mgrsosd ardupilot elements.param`. To regenerate from a known-good FC:

```
python3 "$TTFLEET_ROOT/clone_scripts/01_dump_fc.py" --port /dev/cu.usbmodem1101 --out /tmp/ref/
# then extract the OSD* subset and save as `mgrsosd ardupilot elements.param`
```

## Don't-ask rules

- Don't ask which firmware — autodetect.
- Don't ask which file unless the user specifies one.
- Don't ask whether to push — just push (per `feedback_push_tweaks_autonomously.md`).

## Known gotchas

- **CLI entry is bare `#`** (BF, no newline) per `feedback_bf_cli_entry.md`.
- **BF `save` reboots the FC.** Script exits immediately after — the caller (or next skill) waits through the boot cycle (8 s, per `feedback_bf_boot_cycle_quiet.md`).
- **The .rtf is Cocoa format** — TextEdit-generated. Parser assumes `\cf0 ` content marker and `\<newline>` line terminators.
- **AP param types** are read from the FC (`param_type` field of `PARAM_VALUE`). Don't try to infer types from the .param file — only 2 float params exist (`OSD_W_ACRVOLT`, `OSD_W_AVGCELLV`).
- **`param_request_read_send` can drop silently** on AP — the multi-pass loop in this skill uses `param_request_list_send` (whole list) instead, which is more reliable.
