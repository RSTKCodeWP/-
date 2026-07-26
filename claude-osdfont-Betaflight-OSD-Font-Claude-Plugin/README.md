# claude-osdfont

A Claude Code plugin that uploads a stock Betaflight OSD font (`.mcm`) to a connected MAX7456-based analog FC over MSP. Pulls the `.mcm` straight from the `betaflight-configurator` GitHub repo, parses the 256 × 54-byte character data, and writes one character at a time via `MSP_OSD_CHAR_WRITE` (cmd 87).

## Install

```
/plugin install osdfont@paulnurkkala/claude-osdfont
```

## Usage

```
/osdfont clarity
/osdfont bold
/osdfont default
```

or ask "upload the Clarity font", "change OSD font to Bold", "set the font to digital".

Supported font names (case-insensitive, prefix-matched):

`betaflight`, `bold`, `clarity`, `default`, `digital`, `extra_large` (alias `xl`), `impact`, `impact_mini` (alias `mini`), `large`, `vision`

Flags:

- `--list` — print supported font names
- `--probe` — preflight only (camera/OSD status + last-known font), no upload
- `--dry-run` — download + parse only, no FC contact
- `--page {1,2}` — page 1 (chars 0–255, default) or page 2 (chars 256–511)
- `--port PATH` — override port autodetect

## Requirements

- macOS/Linux with a Betaflight FC on `/dev/cu.usbmodem*`
- Python 3 with `pyserial` and `requests` (`pip install pyserial requests`)
- A MAX7456-based analog OSD (this plugin is SD/analog only — HD fonts for HDZero/Walksnail/DJI use a different upload path and are NOT supported)

## What it does

1. Resolves the font name (case-insensitive + prefix match) and downloads the `.mcm` from `github.com/betaflight/betaflight-configurator/resources/osd/<page>/<name>.mcm` into `~/.cache/osdfont/`.
2. Parses the `.mcm`: first line `MAX7456`; then 256 chars × 64 ASCII-binary lines per char. Keeps the first 54 bytes per char (visible pixel data); drops the trailing 10 metadata bytes.
3. Scans `/dev/cu.usbmodem*`, picks the port that returns `BTFL` on `MSP_FC_VARIANT`.
4. **Pre-flight (always printed):** board id, OSD hardware type, `device_detected` (video signal present), video system, and the previously-uploaded font name (cached per port).
5. Uploads 256 chars sequentially via `MSP_OSD_CHAR_WRITE` (cmd 87) with ~15 ms between writes (MAX7456 NVM spec). Total upload ≈ 5–8 s.
6. Records the new font name in `~/.cache/osdfont/last_uploaded.json` so the next run can report what was previously installed (BF firmware does not implement `MSP_OSD_CHAR_READ`).

No EEPROM write, no reboot — MAX7456 has its own NVM and BF refreshes the OSD on the next draw.

## License

MIT
