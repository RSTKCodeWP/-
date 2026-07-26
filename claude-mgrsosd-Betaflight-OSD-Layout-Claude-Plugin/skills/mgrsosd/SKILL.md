---
name: mgrsosd
description: Push the OSD CLI lines from a `.rtf` file (default `./diff_bf_osd.rtf`) directly to the attached Betaflight FC. Minimal flow — enter CLI, make sure feature OSD is on, paste the file line-by-line until `save`, done. No reset block, no diff, no readback verification. Use when user types /mgrsosd or asks to "push OSD layout", "apply MGRS OSD", "load OSD file".
---

# /mgrsosd — paste OSD .rtf to the BF FC

## Trigger

`/mgrsosd`, "push the OSD layout", "apply the MGRS OSD", "load the OSD file".

## Script

`mgrsosd.py` — single tiny orchestrator. CLI:

```
mgrsosd.py [--file PATH] [--port /dev/...]
```

Default file: `./diff_bf_osd.rtf` (resolved relative to the current working directory). Pass `--file` to point at a different `.rtf`.

## Flow

1. Find Betaflight FC on `/dev/cu.usbmodem*` (refuse non-BTFL).
2. Enter CLI with bare `#`.
3. `feature` — if `OSD` not in active list, send `feature OSD`.
4. Parse the `.rtf`:
   - strip Cocoa preamble (everything up to and including `\cf0 `)
   - split on `\` + newline (Cocoa line terminator)
   - drop `\<word>` RTF control glyphs
   - strip trailing `}`
5. Paste each line into CLI as-is. Wait for the next `# ` prompt between lines (5 s timeout).
6. Stop after `save` (FC reboots). **No further probes, no verification.**

## What this version deliberately does NOT do

- No `dump master` (has crashed some Betaflight builds mid-dump).
- No reset-then-apply (no zeroing of `osd_*_pos` keys not in the file).
- No re-enumeration polling after save.
- No verify readback.

Earlier versions did all of the above and kept wedging the FC. This version is intentionally minimal so the only thing it can do is paste the file.

## Don't-ask rules

- Don't ask which firmware. Refuses non-BTFL automatically.
- Don't ask which file unless the user specifies one.
- Don't add steps. If the user wants verification, they can run their own readback separately.

## Known gotchas

- **CLI entry is bare `#`** (no newline). `#\n` is flaky after a Configurator disconnect.
- **`save` reboots the FC.** Script exits immediately after — the caller is responsible for waiting through the boot cycle (≥8 s of pure quiet, then probe).
- **The .rtf is Cocoa format** (TextEdit-generated). Parser assumes `\cf0 ` content marker and `\<newline>` line terminators.
