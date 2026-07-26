# claude-satest

A Claude Code plugin that performs an end-to-end SmartAudio sanity test on a connected Betaflight FC: reads `MSP_VTX_CONFIG`, decides whether SA is healthy, and (if it is) runs a visible Raceband 1 → Raceband 2 → wait → Raceband 1 toggle so you can confirm in your goggles that video actually changed channel.

## Install

```
/plugin install satest@paulnurkkala/claude-satest
```

## Usage

```
/satest
```

or ask "test SmartAudio", "check VTX comms", "is SA working".

Flags:

- `--status-only` — print SA health + current channel and exit; skip the toggle dance.
- `--wait SECONDS` — hold the R2 step longer (default 5).

## Requirements

- macOS/Linux with a Betaflight FC on `/dev/cu.usbmodem*`
- Python 3 with `pyserial` (`pip install pyserial`)
- Goggles powered on and roughly in range — the whole point is for you to *see* the channel change

## What it does

1. Confirms `MSP_FC_VARIANT == 'BTFL'` — refuses ArduPilot/INAV/EmuF.
2. Reads `MSP_VTX_CONFIG` (cmd 88): `device_type`, `band`, `channel`, `power`, and the BF 4.2+ `deviceIsReady` flag.
3. Discovers the Raceband table index by walking `MSP2_GET_VTXTABLE_BAND` — TBS Unify bench has Raceband at index 4 instead of the BF default 5; the script asks rather than assumes.
4. Decides health:
   - `device_type == 0` → no VTX driver bound to a UART
   - `device_is_ready == 0` → driver up but VTX not replying (usually the VTX's own menu has protocol set to CRSF instead of SmartAudio)
5. If healthy, runs `R1 → R2 → wait → R1` with `MSP_SET_VTX_CONFIG` + `MSP_EEPROM_WRITE` between each step. Each EEPROM write reboots the FC and the port may re-enumerate — the script rescans automatically.

## License

MIT
