# walksnail_osd

Export **Walksnail Avatar** goggle `.osd` recordings to plain text for analysis.

Inspired by [pymsposd](https://github.com/sbvualo/pymsposd), which does the same
job for the msp-osd / DJI format. This tool reuses its idea of extracting
telemetry by locating OSD glyphs, adapted to the Walksnail Avatar container.

## Why not pymsposd?

[pymsposd](https://github.com/sbvualo/pymsposd) targets the **msp-osd / DJI**
`.osd` format (magic `MSPOSD\x00`). Walksnail Avatar files use a different
container (magic `BTFL`), so pymsposd fails on the header magic check. This tool
handles the Walksnail format.

## Format

- 40-byte header starting with `BTFL`; grid size at offsets 36/38 (here 53×20).
- Frames of `4 + width*height*2` bytes: a `uint32` LE timestamp in **milliseconds**
  followed by `width*height` `uint16` LE glyph codes (row-major).
- Codes `0x20..0x7E` are ASCII; `0` is blank; other codes are font icon glyphs
  (satellite, units, home, …) rendered as `·`.

## Usage

### Raw text grid (one screen per changed frame)

```sh
python3 walksnail_osd.py AvatarG0252.osd        # -> AvatarG0252.txt
python3 walksnail_osd.py *.osd                  # each -> <name>.txt
python3 walksnail_osd.py --all-frames file.osd  # do not collapse unchanged screens
```

### Labelled telemetry CSV (recommended for analysis)

Pass a Betaflight CLI backup with `--config`. The tool reads every
`set osd_<element>_pos` line, decodes each element's grid position, and extracts
the value at that position for every frame into a named column.

```sh
python3 walksnail_osd.py --config BTFL_cli_backup.txt *.osd   # each -> <name>.csv
```

### Try it with the bundled sample

`examples/` contains one short recording, its `.srt`, a Betaflight config, and
the exports they produce:

```sh
python3 walksnail_osd.py --config examples/betaflight_config.txt examples/AvatarG0273.osd
```

Columns are the OSD elements actually enabled in that config, e.g. `cell_V`,
`current_A`, `mah`, `throttle`, `rssi_dbm`, `core_temp_C`, `timer2`,
`flight_mode`. Only elements with an OSD profile bit set are exported, so a
disabled GPS/satellites element is correctly omitted.

## Position encoding (Betaflight 4.5, HD)

```
column  = (v & 0x1F) | ((v & 0x400) >> 5)   # 6-bit column, bit10 is the HD high bit
row     = (v >> 5) & 0x1F
visible = (v & 0x3800) != 0                  # OSD profile bits 11/12/13
```

Glyphs are decoded by their low byte (`code & 0xFF`) so values drawn in an
alternate font page (bold/large digits, codes > 0xFF) still resolve to ASCII.

Run tests: `python3 test_walksnail_osd.py`
