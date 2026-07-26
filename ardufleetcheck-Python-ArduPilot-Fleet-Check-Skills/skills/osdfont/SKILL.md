---
name: osdfont
description: Switch the OSD font on a connected Betaflight OR ArduPilot FC. Autodetects firmware MSP-FIRST (per feedback_msp_first_detection.md — ~0.5s; MSP variant 'BTFL'=Betaflight, 'ARDU'=ArduPilot; MAVLink heartbeat fallback for AP without MSP DisplayPort). BF path uploads the .mcm via MSP_OSD_CHAR_WRITE (cmd 87, 256 chars × 54 bytes) into MAX7456 NVM. AP path FIRST tries the built-in ROMFS fonts — clarity=0, clarity_medium=1, bfstyle/betaflight=2, bold=3, digital=4 — by just setting OSD_FONT (no MAVFTP needed, works on every AP board). Falls back to MAVFTP upload for non-built-in fonts on boards with writable storage (SD card root or LittleFS); .bin format is 256×54=13824 bytes per AP_OSD_MAX7456 NVM_RAM_SIZE. Default font is clarity for both families. Use when the user types /osdfont, says "upload font X", "change OSD font to Y", "set the OSD font to Clarity", etc.
---

# /osdfont — Upload an OSD font to a BF or AP FC

## Trigger

User types `/osdfont`, `/osdfont <name>`, or asks "upload the Clarity font", "change OSD font to Bold", "set the font to digital". With no name the skill defaults to `clarity`. The skill handles fetch + upload end-to-end for either Betaflight or ArduPilot.

## Supported fonts (case-insensitive)

Sourced from `github.com/betaflight/betaflight-configurator/resources/osd/{1,2}/<name>.mcm`:

`betaflight`, `bold`, `clarity` (default), `default`, `digital`, `extra_large` (alias `xl`), `impact`, `impact_mini` (alias `mini`), `large`, `vision`

## Scripts

- `osdfont.py` — single orchestrator. Usage: `osdfont.py [name] [--page 1|2] [--dry-run] [--probe] [--port PATH] [--family bf|ap] [--list]`. Defaults to `clarity` if no name. Autodetects FC family.

## Autonomous flow

1. Resolve font name (case-insensitive + prefix match). Default = `clarity` if omitted. If ambiguous or unknown, list options and stop.
2. Download `resources/osd/1/<name>.mcm` from the betaflight-configurator GitHub repo into `~/.cache/osdfont/`. Cache hit → skip fetch.
3. Scan `/dev/cu.usbmodem*` for an FC. **MAVLink-first detection** (see `feedback_ap_mavlink_first_detection.md` — MSP-first locks AP's USB into MSP mode and kills the heartbeat stream): open pymavlink at 115200 with `source_system=255, source_component=190`; send 4× `HEARTBEAT(MAV_TYPE_GCS)` spaced 200 ms; `wait_heartbeat(timeout=4)`; retry up to 3× total. If any heartbeat → AP path. Else MSP probe `MSP_FC_VARIANT` — if `BTFL` → BF path. (BF doesn't speak MAVLink; the MAVLink probe times out harmlessly on BF.) The AP run path also sends GCS heartbeats on connect to keep the channel in MAVLink mode through the whole session.
4. **Pre-flight (always print before upload — see `feedback_show_state_before_mutating_fc.md`):**
   - BF: `MSP_BOARD_INFO` (board id), `MSP_OSD_CONFIG` (hardware type, `device_detected` = video signal, video system AUTO/PAL/NTSC/HD), local marker (last font/page/family).
   - AP: `OSD_TYPE`, `OSD_TYPE2`, `OSD_FONT` current values, warn if neither type is MAX7456 (=1), local marker.
5. Run the family-specific upload (see below).
6. Write `~/.cache/osdfont/last_uploaded.json` keyed by port basename (USB serial; unique per FC) — tracks `{font, page, family, ts}`.

## Betaflight path

- Parse .mcm: 256 chars × 64 bytes/char; keep first 54 bytes per char (visible pixel data), drop the 10 trailing NVM metadata bytes.
- Upload all 256 chars sequentially via `MSP_OSD_CHAR_WRITE` (cmd 87), payload = `[addr] + 54_bytes`. ~15 ms sleep between chars (MAX7456 NVM write spec — 12 ms + margin). Total ≈ 5–8 s. Progress bar.
- No `MSP_EEPROM_WRITE`, no reboot — MAX7456 has its own NVM and BF firmware sets `fontHasBeenUpdated` to refresh the OSD on the next draw.
- BF firmware has **no** `MSP_OSD_CHAR_READ`, so the previous font is only known if a prior `/osdfont` run wrote the marker.

## ArduPilot fast path (built-in fonts)

AP ships 5 fonts baked into ROMFS (`libraries/AP_OSD/fonts/font0..font4.bin`). If the requested font matches one, skip MAVFTP entirely and just set `OSD_FONT`:

- `clarity` → OSD_FONT 0 (AP default)
- `clarity_medium` → 1
- `bfstyle` / `betaflight` → 2
- `bold` → 3
- `digital` → 4

This works on **every** AP board, including those without an SD card. Proven on board 344064000 (2026-05-20): `OSD_FONT 1 → 0` switches from Clarity Medium to Clarity in ~2 s.

## ArduPilot custom-font path (MAVFTP)

- **Format**: 256 × 54 bytes = **13824 bytes raw binary**. `AP_OSD_MAX7456::update_font()` requires `font_size == NVM_RAM_SIZE * 256` where `NVM_RAM_SIZE = 54` — same visible-pixel layout as BF, the 10 metadata bytes per char are dropped. Verified against ROMFS `font0.bin` sizes on a live FC (each = 13824).
- Write the 13824-byte binary to a temp file.
- **Writable-FS probe (mandatory)**: try MAVFTP put of a tiny probe file to `/APM/font0.bin.probe`, `/font0.bin.probe`, then `font0.bin.probe`. If all fail with `FailErrno` (FtpError 2), the board has no writable filesystem (no SD card mounted at `/APM/`, no LittleFS in the build). Skill aborts with clear remediation steps — there's nothing to retry; ROMFS is read-only.
- If a writable path is found, drop the `.probe` suffix and upload via MAVFTP (`pymavlink.mavftp.MAVFTP.cmd_put`) to that path (typically `/APM/font0.bin`). `process_ftp_reply("CreateFile", timeout=90)` drives the whole transaction in one call — sends OP_CreateFile, then OP_WriteFile blocks (80 bytes each), handles ACKs, terminates session when `write_list` empties. ~5 s for 13824 bytes.
- Trigger reload: set `OSD_FONT = 0` (the slot we wrote). If `OSD_FONT` was already 0, toggle to 1 first, sleep 0.5 s, then set back to 0 — `AP_OSD_MAX7456` only calls `update_font()` when `last_font != get_font_num()`.
- No reboot needed.
- **HD-goggle caveat**: if `OSD_TYPE` (or `OSD_TYPE2`) is 7 (MSP_DISPLAYPORT) and neither is 1 (MAX7456), the FC-side font0.bin is loaded but never displayed — the goggle holds its own font. Skill prints a clear NOTE in that case.
- **Board variants without writable storage**: many TT-fleet AP builds (board 344064000 sample tested 2026-05-20) have no SD card and no LittleFS, so AP_Filesystem has no writable mount; `/APM/` lists empty and writes return `FailErrno`. On those boards `OSD_FONT` only selects among the ROMFS-embedded fonts (`/@ROMFS/font0..font4.bin`). Custom fonts require a custom firmware build (`Tools/ardupilotwaf/embed.py` + `libraries/AP_OSD/fonts/`) or adding writable storage.

## Flags

- `--list` — print supported font names
- `--probe` — preflight only (FC OSD status + last-known font), no upload
- `--dry-run` — download + parse only (both BF and AP parses), no FC contact
- `--page {1,2}` — BF only: page 1 (chars 0–255, default) or page 2 (chars 256–511, 2-byte addr). Ignored on AP.
- `--port PATH` — override port autodetect
- `--family {bf,ap}` — force family, skip autodetect (rarely needed)

## Page-2 (extended) characters — BF only

`--page 2` uploads chars 256–511. Some BF builds support a second font page (AT7456E or HD-capable analog). Payload uses 2-byte address (little-endian `uint16`) — BF firmware dispatches on payload size: 55 bytes = 1B-addr + 54B-data; 56 bytes = 2B-addr + 54B-data. AP does not have a page-2 concept; flag is ignored on AP.

## Don't-ask rules

- Don't ask which port — autodetect by probing MSP first, then MAVLink heartbeat.
- Don't ask whether to save — MAX7456 NVM is persistent; on AP the FTP write commits to the filesystem.
- Don't ask whether to reboot — not required on either family. BF refreshes on next draw; AP refreshes on the OSD_FONT toggle.

## Known facts / gotchas

- **.mcm header is exactly `MAX7456`.** Anything else → reject.
- **Bytes per char in .mcm = 64; bytes per char uploaded = 54.** BF and AP both keep 54 (visible pixel data). AP's `NVM_RAM_SIZE = 54` in AP_OSD_MAX7456.cpp — total expected = 54 × 256 = 13824. (Earlier doc here claimed 64/16384 — that was wrong; corrected against AP source + ROMFS-embedded font sizes on a live FC.)
- **AP font path = `/APM/font0.bin`** when an SD card is present. Some builds use LittleFS at `/font0.bin`. The skill probes both before committing. We always write slot 0 and set `OSD_FONT = 0`.
- **AP reload trigger**: `OSD_FONT` change. If it was already 0, the param-set is a no-op and the font won't reload — that's why we toggle 0→1→0.
- **HD goggle caveat (AP)**: with only MSP_DISPLAYPORT active, font0.bin doesn't affect the visible OSD; the goggle holds its own font.
- **NVM write timing (BF)**: MAX7456 datasheet says ~12 ms per char NVM write. 15 ms gives margin. Without the delay, BF can NACK or drop writes silently.
- **One-byte address for BF page 1, two-byte for page 2.** BF dispatches on payload size.
- **Font cache**: `~/.cache/osdfont/<page>_<name>.mcm`. Delete if betaflight-configurator publishes an updated .mcm.
- **HD fonts NOT supported** (HDZero/Walksnail/DJI native font slots). They use a different upload path (`MSP2_FONT_WRITE_HD`-style commands, 512+ chars, different file format).
- **Verification (BF)**: no readback after each char. Trust the firmware's per-char ACK. If a char ACK is missing, abort and report which index failed.
- **Verification (AP)**: MAVFTP ack-per-block via `write_list` set. Failure to drain the set within 120 s → reported as a put failure.
