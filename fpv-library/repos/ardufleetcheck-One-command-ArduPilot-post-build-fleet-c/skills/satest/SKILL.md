---
name: satest
description: SmartAudio/Tramp sanity test on a Betaflight OR ArduPilot FC. Autodetects firmware MSP-FIRST (per feedback_msp_first_detection.md — ~0.5s; MSP variant 'BTFL'=Betaflight, 'ARDU'=ArduPilot). Falls back to MAVLink heartbeat only when MSP is silent. BF path FIRST autofixes a corrupted vtxtable by detecting via CLI `dump vtxtable` and pushing the canonical 5-band Tramp template (BOSCAM_A/B/E, FATSHARK, RACEBAND × 8 channels, 5 power levels) if any band's name/letter/freqs look broken; then reads MSP_VTX_CONFIG, inspects device_type + deviceIsReady. AP path reads VTX_ENABLE / VTX_TYPE / VTX_BAND / VTX_CHANNEL / VTX_POWER and checks ENABLE=1 + TYPE!=0. If broken, prints actionable recommendations. If healthy, prints status, then performs a visible toggle test (R1→R2→wait→R1) so the operator can confirm video changes channel. `--no-vtxtable-fix` (BF-only) skips the autofix for non-Tramp-class VTXes. Use when the user types /satest or asks to "test SmartAudio", "check VTX comms", "is SA working".
---

# /satest — SmartAudio/Tramp sanity test

## Trigger

User types `/satest`, "test SmartAudio", "check VTX comms", "is SA working", "verify VTX channel change", etc. Works on both **Betaflight** (MSP) and **ArduPilot** (MAVLink). The script autodetects which firmware the FC is running and dispatches to the right code path.

## Script

`satest.py` — single orchestrator. CLI:

```
satest.py [--port /dev/cu.usbmodem...] [--status-only] [--wait SECONDS]
          [--no-vtxtable-fix] [--force-vtxtable]
          [--firmware {auto,betaflight,ardupilot}]
```

- `--status-only`     : print health + current channel and exit; skip the toggle dance.
- `--wait`            : seconds to hold the R2 step (default 2). The pre-transition `say` cue eats ~3 s on its own, so wait≤3 is a fast back-to-back toggle; raise for longer R2 dwell.
- `--no-vtxtable-fix` : (BF only) skip the vtxtable autofix entirely (non-Tramp VTXes). Ignored on AP.
- `--force-vtxtable`  : (BF only) push the canonical 5-band Tramp template even when the existing table passes surface validation. Use when goggle OSD renders `R:1:?` for power despite `vtx_power=1` — symptom of BF 2025.12 failing to populate `vtxDevice.capability` from the stored vtxtable (so the OSD's `vtxCommonLookupPowerName` returns `"?"`). Force-push triggers a clean re-init. Ignored on AP.
- `--firmware`        : override autodetection (rarely needed — autodetect is reliable).

## Flow

1. **Detect port** — first `/dev/cu.usbmodem*`. If none, bail.
2. **Detect firmware (MAVLink-FIRST — see `feedback_ap_mavlink_first_detection.md`)**:
   - Open pymavlink with `source_system=255, source_component=190`. Send 4× `HEARTBEAT(MAV_TYPE_GCS)` over ~0.8 s. `wait_heartbeat(timeout=4)`. Up to 3 attempts. If any heartbeat → AP path.
   - Else close pymavlink and try MSP `MSP_FC_VARIANT` → if `BTFL`, BF path.
   - Else bail with "unsupported firmware".
   - Why MAVLink-first: AP's USB CDC multiplexes MAVLink and MSP. Sending an MSP frame first can lock the channel into MSP mode and stall heartbeats. Probing MAVLink first is safe on BF (BF doesn't speak MAVLink — the attempt just times out).

### BF path (when variant=BTFL)

3. **Vtxtable health autofix (FIRST mutation; runs before any other test logic).**
   - Enter BF CLI, send `dump vtxtable`, parse the `vtxtable band N NAME L MODE freqs...` lines.
   - For each band: validate the name is alphanumeric, letter is A-Z, frequencies are in 4900–6100 MHz (widened 2026-05-21 to cover TBS Unify's extended U-band freqs 4990 / 6013, which the old 5000–6000 check incorrectly flagged as "corruption" and overwrote with the canonical Tramp template — destroying user-set Unify tables in the process).
   - If ANY band is broken (or no lines parsed) → push the canonical 5×8×5 Tramp template, send `save`, wait 10 s, re-read.
   - The parsed bands are attached to `cfg['_cli_bands']` so the rest of /satest reads names/letters from the source of truth, not the buggy MSP2 `GET_VTXTABLE_BAND` (which returns garbage on BF 2025.12).
   - Skipped if `--no-vtxtable-fix` (use this for non-Tramp VTXes like 4-power SA or HD).
4. **Read `MSP_VTX_CONFIG` (cmd 88)** — full payload up to 15 bytes:
   - byte 0  `device_type` (0=NONE, 1=RTC6705, 3=SmartAudio, 4=Tramp, 5=MSP-VTX)
   - byte 1  band, byte 2 channel, byte 3 power, byte 4 pitmode
   - bytes 5-6 freq (LE uint16)
   - byte 7  **`deviceIsReady`** ← the key SA-talking-back flag (BF 4.2+)
   - byte 8  lowPowerDisarm, 9-10 pitModeFreq, 11 vtxTableAvailable, 12 bands, 13 channels, 14 powerLevels
4. **Discover Raceband index** via `MSP2_GET_VTXTABLE_BAND` (0x1009) iterating 1..bands_count; match by letter=='R' or name contains "RACE". Falls back to band-4 if current band reads as 4 (TBS Unify observed mapping, see memory `reference_tbs_unify_protocol.md`), else default 5.
5. **Decide health**:
   - `device_type == 0` → no VTX driver bound to a UART (feature off / serial fn 2048 not set).
   - `device_is_ready == 0` → driver up but VTX not replying (wrong protocol in VTX menu, wiring, power).
   - Either → print recommendations and exit 2 (Claude reports failure to user, does not run toggle).
6. **Print state** — Channel / Band (with name+letter from vtxtable when available) / Power (with mW label from `MSP2_GET_VTXTABLE_POWERLEVEL` 0x100A when available).
7. **Toggle test** (each set is `MSP_SET_VTX_CONFIG` (89) + `MSP_EEPROM_WRITE` (250); FC reboots ~3.5s each, port may re-enumerate):
   - If currently **on Raceband ch1** → set R2, wait `--wait` seconds, set R1.
   - If **not on R1** → set R1 first, then run the R1→R2→wait→R1 sequence.
   - Verify each step by reading back `MSP_VTX_CONFIG`.
8. **Exit 0** when the dance lands back on R1.

### AP path (when MAVLink heartbeat is seen)

3. **Read VTX params** via `PARAM_REQUEST_READ`:
   - `VTX_ENABLE`, `VTX_TYPE` (1=Tramp, 2=SmartAudio, 3=DJI HD, 4=MSP)
   - `VTX_BAND` (0-indexed: 0=Boscam A, 1=B, 2=E, 3=FatShark, 4=Raceband, 5=Low)
   - `VTX_CHANNEL` (0-indexed: 0=ch1, …, 7=ch8)
   - `VTX_POWER` (mW), `VTX_MAX_POWER` (mW)
   - `VTX_FREQ` (MHz), `VTX_OPTIONS`
4. **Health check**: `VTX_ENABLE == 0` or `VTX_TYPE == 0` → fail with recommendations (set VTX_ENABLE=1, set VTX_TYPE to your protocol, check SERIAL*_PROTOCOL=37 for SmartAudio / 36 for Tramp, SERIAL*_BAUD=4 for 4800).
5. **Print status** (decoded VTX_TYPE / band name / 1-based channel).
6. **Toggle test** via `PARAM_SET` (NO reboot — AP pushes live to the VTX over SA/Tramp):
   - If not on Raceband ch1 (band=4 ch=0) → set R1 first.
   - R1 → R2 (band=4 ch=1) → wait `--wait` seconds → R1.
   - Verify each step by re-reading `VTX_BAND`/`VTX_CHANNEL`.
7. **Force `VTX_POWER=25`** (mW) as the test post-condition. AP VTX_POWER is in mW directly (no vtxtable slot). The set has a 5-attempt verify loop because the param queue can be busy from the preceding BAND/CHANNEL sets — first readback occasionally reads back the pre-set value before the change has propagated. Retry sleeps 0.5 s between attempts.
8. **Exit 0** when the dance lands back on R1 @ 25 mW.

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

- Don't ask which firmware — the script autodetects (MAVLink heartbeat → AP, MSP BTFL → BF).
- Don't ask "should I run the test?" — the user typing `/satest` means yes, run it.
- Don't ask whether to save — BF goes through `MSP_EEPROM_WRITE` so it persists; AP `PARAM_SET` is persistent immediately.

## Known gotchas

### BF-specific
- **Each `MSP_EEPROM_WRITE` reboots the FC.** Port may re-enumerate to a different `/dev/cu.usbmodem*` serial. Script rescans after each write.
- **`device_is_ready` is BF 4.2+.** Older builds return 5-byte `MSP_VTX_CONFIG`; the script prints "<not reported>" in that case and only fails when `device_type==0`.
- **The Raceband index is vtxtable-dependent.** On default factory vtxtable Raceband=5; on the Sequre+TBS bench it's 4 (memory `reference_bf_templates.md`). The script asks the FC rather than assuming.
- **Power is forced to the 25 mW slot** on every set (2026-05-19, refined later same day). The slot index is resolved by looking up the vtxtable's `powerlabels` line for a `'25'` entry; falls back to `powervalues == 25`, then the lowest-numeric-label slot, then slot 1. Rationale: different VTXes put 25 mW at different slot numbers — Tramp tables have it at slot 1, but HD VTXes or shuffled SmartAudio tables may not. Looking up by label keeps /satest's post-condition consistent (lowest legal transmit power, valid OSD state) regardless of hardware.

### AP-specific
- **No reboot between toggles.** AP pushes band/channel live to the VTX over SA/Tramp; `PARAM_SET` returns and the next read sees the new value within a few hundred ms.
- **Channel indexing is 0-based.** R1 = `VTX_CHANNEL=0`, R8 = `VTX_CHANNEL=7`. The status print decodes the 1-based human label.
- **Raceband is fixed at band index 4** in AP. No vtxtable lookup needed.
- **No `device_is_ready` equivalent.** AP only exposes whether the *driver* is configured (VTX_ENABLE, plus VTX_TYPE/PROTOCOL on builds that have it). It does not surface whether the VTX is actually replying on the SA wire. The toggle test is the only ground-truth that the VTX is responding. If `VTX_BAND` readback after `PARAM_SET` matches the requested band but the goggle doesn't actually change, the wire is silent — check SERIAL*_PROTOCOL (37=SA, 36=Tramp), SERIAL*_BAUD=4, and the VTX's own protocol setting.
- **VTX_TYPE may not exist.** This fleet's AP build has no `VTX_TYPE` / `VTX_TYPES` / `VTX_PROTOCOL` param — the driver protocol is selected from `SERIAL*_PROTOCOL` once `VTX_ENABLE=1`. The script probes all three names and treats all-None as "modern build, trust VTX_ENABLE". See `reference_ap_vtx_no_type_param.md`.
- **VTX_POWER set has a queue-race.** After the back-to-back BAND/CHANNEL sets, the first VTX_POWER readback can be stale (returns the pre-set value). The post-condition loop retries up to 5× with 0.5 s waits — typically lands on attempt 2.

### Universal
- **Pre-flight obvious thing**: goggles must be powered on and within range during the test; otherwise the user can't tell whether SA worked.

## Related memories

- `reference_tbs_unify_protocol.md` — VTX menu protocol-mismatch is the #1 cause of `device_is_ready=0`.
- `reference_bf_templates.md` — TBS Unify vtxtable observed Raceband=4 (not the BF default 5).
- `reference_vtx_skill.md` — sibling skill for *changing* the channel persistently; `/satest` is for *verifying* the link, not configuring.
- `project_fleet_param_standards.md` — fleet default is R8 1000 mW, but `/satest` deliberately leaves the FC on R1 / power=1 as a post-flash sanity state. Set higher power via `/vtx` after `/satest` confirms the SA/Tramp link.
