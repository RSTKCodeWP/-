# claude-mgrsosd

A Claude Code plugin that pushes a Betaflight OSD layout (`.rtf` exported from TextEdit) directly to an attached flight controller over MSP/CLI.

Minimal by design: enter CLI, ensure `feature OSD` is on, paste the file line-by-line, stop after `save`. No `dump master`, no reset, no readback verification — earlier "smart" versions kept wedging the FC mid-flash.

## Install

```
/plugin install mgrsosd@paulnurkkala/claude-mgrsosd
```

## Usage

In Claude Code, type:

```
/mgrsosd
```

or ask "push the OSD layout" / "apply the OSD file".

By default it looks for `./diff_bf_osd.rtf` in the current working directory. Override with:

```
/mgrsosd --file path/to/layout.rtf
```

## Requirements

- macOS or Linux with a Betaflight FC enumerated as `/dev/cu.usbmodem*` (or pass `--port`)
- Python 3 with `pyserial` installed (`pip install pyserial`)
- An OSD `.rtf` exported from TextEdit (Cocoa RTF — uses `\cf0 ` content marker and `\<newline>` line terminators)

## What it does

1. Probes the port with `MSP_FC_VARIANT` — bails if not `BTFL`.
2. Enters CLI with a bare `#` (no newline — `#\n` is flaky after a Configurator disconnect).
3. Runs `feature`; if `OSD` isn't active, sends `feature OSD`.
4. Parses the `.rtf` (strips Cocoa preamble and RTF control words), then pastes each CLI line.
5. Stops when it sees `save`. The FC reboots; the script exits without polling — give it ≥8 s of quiet before re-probing.

## License

MIT
