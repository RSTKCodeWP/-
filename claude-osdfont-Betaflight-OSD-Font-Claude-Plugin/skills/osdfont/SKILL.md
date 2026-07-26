---
name: osdfont
description: Upload an OSD .mcm font (Clarity, Bold, Default, Betaflight, Digital, Impact, Large, Vision, etc.) to a Betaflight FC over MSP. Pulls the .mcm from betaflight-configurator/resources/osd/ on GitHub, parses 256 chars × 54 bytes, and writes one char per MSP_OSD_CHAR_WRITE (cmd 87). Analog SD (MAX7456) only. Use when the user types /osdfont, says "upload font X", "change OSD font to Y", "set the OSD font to Clarity", etc.
---

# /osdfont — Upload an OSD font to a Betaflight FC

## Trigger

User types `/osdfont <name>` or asks "upload the Clarity font", "change OSD font to Bold", "set the font to digital". The skill handles fetch + upload end-to-end.

## Supported fonts (case-insensitive)

Sourced from `github.com/betaflight/betaflight-configurator/resources/osd/{1,2}/<name>.mcm`:

`betaflight`, `bold`, `clarity`, `default`, `digital`, `extra_large` (alias `xl`), `impact`, `impact_mini` (alias `mini`), `large`, `vision`

## Scripts

- `osdfont.py` — single orchestrator. Usage: `osdfont.py <name> [--page 1|2] [--dry-run] [--port PATH] [--list]`. Downloads `.mcm`, caches in `~/.cache/osdfont/`, parses, uploads via MSP.

## Autonomous flow

1. Resolve font name (case-insensitive + prefix match). If ambiguous or unknown, list options and stop.
2. Download `resources/osd/1/<name>.mcm` from the betaflight-configurator GitHub repo into `~/.cache/osdfont/`. If already cached, skip the fetch.
3. Parse the .mcm: first line must be `MAX7456`; then 256 chars × 64 ASCII-binary lines per char. Each line is 8 chars of `'0'`/`'1'` representing 1 byte. Keep the first 54 bytes per char (visible pixel data); drop the trailing 10 metadata bytes.
4. Scan `/dev/cu.usbmodem*` for an FC. Probe each with MSP `MSP_FC_VARIANT` (cmd 2). The port that returns `BTFL` is the target. If no `BTFL` responder → fail with a clear message.
5. **Pre-flight (always print before upload)**:
   - `MSP_BOARD_INFO` (cmd 4) → board id (e.g. `H743`)
   - `MSP_OSD_CONFIG` (cmd 84) → OSD hardware type (`max7456` / `frskyosd` / `msp_displayport`), `device_detected` bit (= video signal present), `video_system` (AUTO/PAL/NTSC/HD)
   - Previous font name from `~/.cache/osdfont/last_uploaded.json` keyed by port basename (the USB serial in the port name uniquely identifies the FC; board id like `H743` is too generic for a multi-board fleet)
   - If `MSP_OSD_CHAR_READ` ever existed: BF firmware **does not** implement it (the protocol header defines cmd 86, but `msp.c` has zero references). So the previous font is only known if a prior `/osdfont` run wrote the marker.
6. Upload all 256 chars sequentially via `MSP_OSD_CHAR_WRITE` (cmd 87), payload = `[addr_byte] + 54_bytes`. ~15 ms sleep between chars (MAX7456 NVM write spec). Total ≈ 5–8 s. Show a progress bar.
7. Write `~/.cache/osdfont/last_uploaded.json` so the next run can report the previous font.
8. No `MSP_EEPROM_WRITE`, no reboot — MAX7456 has its own NVM and BF firmware sets `fontHasBeenUpdated` to refresh the OSD on the next draw.

## Flags

- `--list` — print supported font names
- `--probe` — preflight only (camera/OSD status + last-known font), no upload
- `--dry-run` — download + parse only, no FC contact
- `--page {1,2}` — page 1 (chars 0–255, default) or page 2 (chars 256–511, 2-byte addr)
- `--port PATH` — override port autodetect

## Page-2 (extended) characters

`--page 2` uploads chars 256–511. Some BF builds support a second font page (AT7456E or HD-capable analog). Payload uses 2-byte address (little-endian `uint16`) — BF firmware accepts both 1-byte and 2-byte addresses based on payload length. Default to page 1 unless the user asks for "page 2" or the extended set.

## Don't-ask rules

- Don't ask which port — autodetect by probing `MSP_FC_VARIANT == 'BTFL'`.
- Don't ask whether to save — MAX7456 NVM is persistent; nothing to EEPROM-write.
- Don't ask whether to reboot — not required.
- If the FC reports as ArduPilot (MAVLink heartbeat) instead of BTFL, **stop** with a clear error. AP's OSD font upload path is different and untested here.

## Known facts / gotchas

- **.mcm header is exactly `MAX7456`.** Anything else → reject.
- **Bytes per char in .mcm = 64; bytes uploaded = 54.** The last 10 bytes of each 64-byte block in the .mcm are MAX7456 metadata (`MAX_NVM_FONT_CHAR_FIELD_SIZE - MAX_NVM_FONT_CHAR_SIZE`) and are intentionally not sent.
- **One-byte address for page 1 (0–255), two-byte for page 2.** BF dispatches on payload size: 55 bytes = 1B-addr + 54B-data; 56 bytes = 2B-addr + 54B-data.
- **NVM write timing**: MAX7456 datasheet says ~12 ms per char NVM write. 15 ms sleep gives margin. Without the delay, BF can NACK or drop writes silently.
- **Font cache**: `~/.cache/osdfont/<page>_<name>.mcm`. Delete if betaflight-configurator publishes an updated .mcm and you need to re-pull.
- **HD fonts NOT supported** (HDZero/Walksnail/DJI). They use a different upload path (`MSP2_FONT_WRITE_HD`-style commands, 512+ chars, different file format). This skill is analog/SD-only by design.
- **Verification**: there's no readback after each char (`MSP_OSD_CHAR_READ` is slow and rarely used). Trust the firmware's per-char ACK. If a char ACK is missing, abort and report which index failed.
