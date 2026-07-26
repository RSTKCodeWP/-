---
name: satest
description: SmartAudio sanity test on a Betaflight FC. Reads MSP_VTX_CONFIG, inspects device_type + deviceIsReady to decide if SA is healthy. If broken, prints actionable recommendations. If healthy, prints Band/Channel/Power, then performs a visible toggle test (R1→R2→wait 5s→R1) so the operator can confirm video changes channel. After the test, asks the user whether video actually changed and offers retry / confirm / troubleshoot. Use when the user types /satest or asks to "test SmartAudio", "check VTX comms", "is SA working".
---

# /satest — SmartAudio sanity test

## Trigger

User types `/satest`, "test SmartAudio", "check VTX comms", "is SA working", "verify VTX channel change", etc. Betaflight only — the script bails out fast on ArduPilot or unknown FCs.

## Script

`satest.py` — single orchestrator. CLI:

```
satest.py [--port /dev/cu.usbmodem...] [--status-only] [--wait SECONDS]
```

- `--status-only` : print SA health + current channel and exit; skip the toggle dance.
- `--wait`        : seconds to hold the R2 step (default 5).

## Flow

1. **Detect port** — first `/dev/cu.usbmodem*`. If none, bail.
2. **Confirm Betaflight** via `MSP_FC_VARIANT` (cmd 2) → expect `BTFL`. Refuse other firmwares (AP/INAV/EMUF).
3. **Read `MSP_VTX_CONFIG` (cmd 88)** — full payload up to 15 bytes:
   - byte 0  `device_type` (0=NONE, 1=RTC6705, 3=SmartAudio, 4=Tramp, 5=MSP-VTX)
   - byte 1  band, byte 2 channel, byte 3 power, byte 4 pitmode
   - bytes 5-6 freq (LE uint16)
   - byte 7  **`deviceIsReady`** ← the key SA-talking-back flag (BF 4.2+)
   - byte 8  lowPowerDisarm, 9-10 pitModeFreq, 11 vtxTableAvailable, 12 bands, 13 channels, 14 powerLevels
4. **Discover Raceband index** via `MSP2_GET_VTXTABLE_BAND` (0x1009) iterating 1..bands_count; match by letter=='R' or name contains "RACE". Falls back to band-4 if current band reads as 4 (TBS Unify observed mapping), else default 5.
5. **Decide health**:
   - `device_type == 0` → no VTX driver bound to a UART (feature off / serial fn 2048 not set).
   - `device_is_ready == 0` → driver up but VTX not replying (wrong protocol in VTX menu, wiring, power).
   - Either → print recommendations and exit 2 (Claude reports failure to user, does not run toggle).
6. **Print state** — Channel / Band (with name+letter from vtxtable when available) / Power (with mW label from `MSP2_GET_VTXTABLE_POWERLEVEL` 0x100A when available).
7. **Toggle test** (Betaflight only — each set is `MSP_SET_VTX_CONFIG` (89) + `MSP_EEPROM_WRITE` (250); FC reboots ~3.5s each, port may re-enumerate):
   - If currently **on Raceband ch1** → set R2, wait `--wait` seconds, set R1.
   - If **not on R1** → set R1 first, then run the R1→R2→wait→R1 sequence.
   - Verify each step by reading back `MSP_VTX_CONFIG`.
8. **Exit 0** when the dance lands back on R1.

## After the script returns

Claude must prompt the user (use `AskUserQuestion`):

> "Did the video actually change channel during the test?"
>
> Options:
>   - **Worked** — video switched. Done.
>   - **Try again** — re-run `/satest`.
>   - **Didn't change** — start troubleshooting.

On "Didn't change" go through, in order:
1. Verify the goggles were on Raceband 2 momentarily and Raceband 1 before/after. If the goggles were never on the right band, the VTX may *actually* be transmitting on R1↔R2 fine but the operator wasn't tuned to it.
2. Re-read with `satest.py --status-only`; if `device_is_ready` flipped to 0 mid-test, the VTX dropped the SA link — likely brownout on the VTX rail.
3. Suggest checking VTX menu (protocol = SmartAudio not CRSF — single most common cause).
4. Suggest `set vtx_smartaudio_unify=ON` / OFF and reboot.
5. Suggest pulling `serial` from CLI and confirming the UART with function bit 2048 matches the wired pad.

## Don't-ask rules

- Don't ask which firmware. The script refuses non-BF.
- Don't ask "should I run the test?" — the user typing `/satest` means yes, run it.
- Don't ask whether to save — every set goes through `MSP_EEPROM_WRITE` so it persists.

## Known gotchas

- **Each `MSP_EEPROM_WRITE` reboots the FC.** Port may re-enumerate to a different `/dev/cu.usbmodem*` serial. Script rescans after each write.
- **`device_is_ready` is BF 4.2+.** Older builds return 5-byte `MSP_VTX_CONFIG`; the script prints "<not reported>" in that case and only fails when `device_type==0`.
- **The Raceband index is vtxtable-dependent.** On default factory vtxtable Raceband=5; on TBS Unify factory builds it's been observed at 4. The script asks the FC rather than assuming.
- **Pre-flight obvious thing**: goggles must be powered on and within range during the test; otherwise the user can't tell whether SA worked.
- **Power level is preserved** through every set; the script never silently changes power.

## Notes

- VTX menu protocol-mismatch (SmartAudio vs CRSF) is the #1 cause of `device_is_ready=0`.
- `/satest` is for *verifying* the SA link, not for *configuring* the channel persistently.
