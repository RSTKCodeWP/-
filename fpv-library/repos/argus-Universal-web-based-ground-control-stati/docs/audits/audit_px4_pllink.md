# Argus GCS — PX4 & PL-Link Protocol Audit

Repo: `github.com/L-X-Yao/argus`, branch `main` @ commit `41b03b0`

---

## Section 1 — PX4 Support

### What's claimed

- `README.md:Argus aims to be the first truly universal web GCS — one interface that works with any MAVLink vehicle (ArduPilot, PX4)`
- `README.md:| Protocols | ArduPilot + PX4 (auto-detect via FC adapter layer) |`
- `README.md:| src/lib/fc/ | Flight controller adapter (ArduPilot + PX4 mode/command mapping) |`
- `CLAUDE.md:Protocol: MAVLink v2 (standard + PL-Link wrapper), ArduPilot + PX4`

### What's actually implemented

`src/lib/fc/` defines an `FcAdapter` abstraction (`interface.ts:17-46`) with `ardupilotAdapter` (`ardupilot.ts:32-77`) and `px4Adapter` (`px4.ts:60-100`). It includes a `detectAdapter(autopilot)` helper (`index.ts:15-20`) that switches on the HEARTBEAT `autopilot` field (3 = ArduPilot, 12 = PX4).

The PX4 adapter handles:
- 24-bit custom_mode decoding `(main << 16) | (sub << 24)` (`px4.ts:8-9, 28-30`)
- Mode names for 14 modes (manual/altctl/posctl/auto sub-modes) (`px4.ts:32-47`)
- Mode buttons (`px4.ts:49-58`)
- RTL / hold / auto / arm-base-mode helpers (`px4.ts:87-90`)

### Gaps

#### G1. The FC adapter is unwired dead code

Nothing outside `src/lib/fc/` ever imports it. Verified by grep across the entire `src/` tree:
- No production file imports `ardupilotAdapter`, `px4Adapter`, `detectAdapter`, or `FcAdapter`.
- Only `src/lib/fc/fc.test.ts` references it (unit test isolated from production).
- `src/lib/types.ts:32` declares `mode_btns: [number, string][]` which is populated **server-side** in `backend/drone_link.py:281,315` via `_get_vehicle_info()`.
- UI components (`ControlPanel.svelte:71,100,133,154`, `MapControls.svelte:42`, `CommandPalette.svelte:171-172`, `App.svelte:202`) read `app.drone.mode_btns` directly from the backend payload.

Result: the `px4Adapter` mode tables, buttons, RTL/HOLD/AUTO IDs are never seen by the running UI.

#### G2. Backend never reads the autopilot field from HEARTBEAT

`backend/mavlink_handlers.py:30-64` (`handle_heartbeat`) reads `p[0..3]` (custom_mode), `p[4]` (type), `p[6]` (base_mode), `p[7]` (system_status), but **never reads `p[5]` (autopilot)**. The vehicle state `backend/state.py:56` only stores `vtype_raw`. There is no field or branch anywhere in the backend that distinguishes ArduPilot from PX4.

#### G3. Backend mode tables are ArduPilot-only

`backend/constants.py:1-7` ("Verified against ArduCopter/mode.h, ArduPlane/mode.h, …") defines COPTER_MODES, PLANE_MODES, ROVER_MODES, SUB_MODES — all using ArduPilot custom_mode integer enumerations.

`backend/drone_link.py:253-274` (`_get_vehicle_info`) selects one of these tables based on `vtype_raw` (MAV_TYPE) alone — never based on autopilot.

If a PX4 vehicle connects, the backend will look up PX4's custom_mode (a packed 32-bit `(sub<<24)|(main<<16)`) in a flat ArduPilot table:
- PX4 POSCTL = `0x00030000` (196608) → falls through to `MODE%d` fallback (`drone_link.py:288`)
- PX4 AUTO/MISSION = `0x04040000` (67371008) → same fallback.

Every PX4 mode appears as `MODE197120` style garbage in the UI.

#### G4. Mode-set commands assume ArduPilot integers

- `backend/commands/_flight.py:28`: `cmd_rtl` sends `send_set_mode(link, 21 if is_plane else 6)`. For PX4 this would set custom_mode=6 (AUTO main_mode=0/sub=0 if PX4 even honored the legacy SET_MODE) — meaningless.
- `backend/commands/_flight.py:36-39`: `cmd_mode` uses ArduPilot's COPTER_MODES / PLANE_MODES for the event-log name; the integer is passed straight through.
- `backend/commands/_hardware.py:34`: `cmd_guided_goto` uses `gm = 15 if is_plane else 4` (ArduPilot Guided mode IDs). PX4 has no equivalent "Guided" mode at id 4.
- `backend/commands/_mission.py:22`: `cmd_mission_start` uses `am = 10 if is_plane else 3` (ArduPilot Auto = 3 copter, 10 plane). For PX4 this is not the Auto/Mission mode bit pattern.

#### G5. `SET_MODE` (msg 11) is deprecated on PX4

`backend/commands/_helpers.py:20-22` (`send_set_mode`) sends MAVLink message 11 (SET_MODE) with `base_mode = 0x01` (MAV_MODE_FLAG_CUSTOM_MODE_ENABLED). PX4 documents SET_MODE as deprecated; the canonical mechanism is `MAV_CMD_DO_SET_MODE` (cmd 176, COMMAND_LONG) with `param1 = base_mode`, `param2 = main_mode`, `param3 = sub_mode`.

The deprecation is informational on recent PX4 builds — they still mostly honor SET_MODE — but the `(custom_mode = u32 enum)` semantic is fundamentally different between the two stacks, so even if PX4 accepts the message, the integer payload is wrong.

#### G6. ArduPilot-private MAVLink messages are registered as common

`backend/drone_link.py:49-57` (`_CRC_EXTRA`) and `backend/mavlink_handlers.py:634-666` (`init_handlers`) treat these messages as if they were common when they are actually in the `ardupilotmega` dialect — verified against pymavlink (these msg IDs are absent from `dialects.v20.common`):

- `158` MOUNT_STATUS — AP only; PX4 uses MOUNT_ORIENTATION (msg 265).
- `163` AHRS — AP only.
- `168` WIND — AP only; PX4 uses WIND_COV (231).
- `178` AHRS2 — AP only.
- `191` MAG_CAL_PROGRESS — AP only.
- `192` MAG_CAL_REPORT — AP only.
- `193` EKF_STATUS_REPORT — AP only; PX4 uses ESTIMATOR_STATUS (230).
- `241` VIBRATION — common (PX4 does send this).

On a PX4 vehicle, none of the AP-private streams arrive, so the Vibration / EKF / Wind / Gimbal panels show only zeros, and accel-cal / mag-cal flows are silent. The CRC_EXTRAs themselves are correct (matched against pymavlink ardupilotmega dialect), so no parsing corruption — just missing data.

#### G7. Calibration ACK semantics are AP-private

`backend/commands/_setup.py:47-58` (`cmd_cal_accel_next`) sends a COMMAND_ACK (msg 77) with `command=0, result=MAV_RESULT_TEMPORARILY_REJECTED(1)` — verbatim from `AP_AccelCal::handle_command_ack` in ArduPilot. PX4 has no equivalent — its accel calibration uses a different orientation-handshake flow (via custom STATUSTEXT / SENSOR_OFFSETS).

`backend/commands/_setup.py:19, 24, 70`: cmds 42424 / 42425 / 42426 (`DO_START_MAG_CAL`, `DO_ACCEPT_MAG_CAL`, `DO_CANCEL_MAG_CAL`) are AP MAVLink extensions; PX4 ignores them.

`backend/commands/_setup.py:29-44`: cmd 241 (`MAV_CMD_PREFLIGHT_CALIBRATION`) is common, but PX4 only honors `p1=1` (gyro) and `p3=1` (baro); PX4's accel cal flow is different.

#### G8. Force-disarm magic value is AP-only

`backend/commands/_flight.py:23-24`: `send_cmd(link, 400, p1=0, p2=21196)`. The magic 21196 is `'L'<<8|'I'` (Land Immediately), checked specifically in `AP_Arming::run_arming_checks`. PX4 ignores p2 — it uses `21196` is not interpreted, and PX4 force-disarm is `param2 = 21196` only honored on AP. To force-disarm on PX4 the command must be a regular `cmd 400, p1=0` from a system_status==CRITICAL state.

#### G9. Motor-test param mapping is AP-only

`backend/commands/_hardware.py:110-125`: cmd 209 `MAV_CMD_DO_MOTOR_TEST` with `p1 = 1-based motor index`. The comment explicitly cites `GCS_MAVLink_Copter.cpp:702`. PX4 uses different motor test semantics (commander module accepts `param5 = motor_id` differently). Even motor numbering differs.

#### G10. WebSerial direct path uses ArduPilot Copter RTL

`src/lib/transport.ts:172-174`: `serialSendRtl()` calls `serialSendMode(11)` with comment "RTL mode for copter". 11 is ArduPlane RTL, not Copter RTL (Copter RTL = 6). For PX4 it's neither (it'd be sub=0 main=0, undefined). This is a freestanding bug compounding the PX4 gap.

#### G11. Heartbeat/vehicle-type fallback assumes AP-style multirotor

`backend/drone_link.py:271-273`: when MAV_TYPE matches none of the explicit branches but `> 0`, the backend defaults to COPTER_MODES. For a PX4 fixed-wing with MAV_TYPE=1 (FIXED_WING) it would hit the plane branch first (`vtype_raw in (1, 19, 20, …)`) — but a PX4 hexarotor (MAV_TYPE=13) wouldn't match either, so it'd silently get ArduCopter's mode names. The fallback assumption is wrong for PX4.

#### G12. AP-specific PreArm string parsing

`backend/mavlink_handlers.py:244`: `if text.startswith('PreArm:') or text.startswith('Arm:')`. ArduPilot prefixes pre-arm failures with `PreArm:` / `Arm:`. PX4 uses different prefixes (e.g. `Preflight Fail:`). Pre-arm messages from PX4 won't be deduplicated/aggregated as designed.

#### G13. `statustext_filter` only knows AP strings

`backend/statustext_filter.py:1-38`: every leak filter is AP/APM/ArduCopter/EKF3/etc. PX4 STATUSTEXTs (e.g. `Commander: …`, `Preflight Fail: …`) get no translation, no brand suppression. (This is more cosmetic but reinforces that PX4 was never exercised.)

#### G14. Stream requests work, but not what we tell PX4 to send

`backend/commands/_helpers.py:86-99`: `request_streams()` uses `MAV_CMD_SET_MESSAGE_INTERVAL` (cmd 511) — universal MAVLink — so this works. But it requests msg 65 (RC_CHANNELS), msg 241 (VIBRATION), msg 74 (VFR_HUD), msg 33 (GLOBAL_POSITION_INT) — most are common. Then cmd 512 with p1=148 (request AUTOPILOT_VERSION) — common. So data flow works for PX4 for the messages PX4 implements.

The WebSerial path (`src/lib/transport.ts:135-150`) however uses deprecated `REQUEST_DATA_STREAM` (msg 66) with stream IDs 1, 2, 3, 6, 10, 11, 12. PX4 stopped supporting that years ago; no telemetry will flow on the WebSerial path with a PX4 vehicle.

### Summary

The PX4 story is: a frontend FC adapter pattern was scaffolded (`src/lib/fc/`) but never wired in. The backend is monolithic ArduPilot end-to-end — mode tables, custom_mode integers, calibration semantics, force-disarm magic, motor test, fence/rally protocols, PreArm parsing, statustext filtering, AP-private message IDs. PX4 connections will see a HEARTBEAT, the backend will display garbled mode names like `MODE197120`, and PX4-private telemetry (EKF, mount, mag-cal) will never reach the UI.

**14 gaps identified.**

---

## Section 2 — PL-Link Protocol

### Reconstructed protocol description (from `backend/pllink_proto.py`)

**Frame format (7-byte overhead + variable payload):**

```
+------+------+--------+--------+------+------------------+------+
| 0x50 | 0x4C | LEN_LO | LEN_HI |  SEQ |  XOR(payload)    | CRC  |
| (1)  | (1)  |  (1)   |  (1)   | (1)  |     (LEN)        | (2)  |
+------+------+--------+--------+------+------------------+------+
```

- **Magic**: `0x50 0x4C` (ASCII "PL") — `pllink_proto.py:27`
- **Length**: `u16 little-endian` of the inner (decrypted) payload length, valid range 1..280 — `pllink_proto.py:33-35`
- **Sequence**: `u8`, wraps at 256 — `pllink_proto.py:26`
- **Payload**: caller's data XORed byte-by-byte with the 8-byte key `b'KeyPL1!@'` (`bytes([0x4B, 0x65, 0x79, 0x50, 0x4C, 0x31, 0x21, 0x40])`), key repeats cyclically — `pllink_proto.py:5-12`
- **CRC**: 2-byte little-endian CRC-16/CCITT-FALSE-like (init 0xFFFF, poly 0x1021, MSB-first, no reflect, no xorout) over `LEN(2) + SEQ(1) + XOR(payload)` — `pllink_proto.py:15-21, 26-27, 41-42`

The encoded payload is always a full MAVLink v2 frame (the senders pass the output of `bm()`, never bare bytes). The PL-Link layer is therefore a transport wrapper, not a message encoder.

**Build-MAVLink helper `bm()`** (`pllink_proto.py:57-60`): assembles a standalone MAVLink v2 frame:
```
0xFD | LEN | 0x00 | 0x00 | SEQ | SYSID | COMPID | MID[3] | payload | MAVLink-CRC[2]
```
- `incompat_flags=0`, `compat_flags=0` → no signing
- MAVLink-CRC is the CRC-16/MCRF4XX (X.25 variant, reflected) over the header bytes (excluding magic) + payload + `CRC_EXTRA` — `pllink_proto.py:45-54`

The two CRCs (`c16` for PL-Link, `mc` for MAVLink) are different algorithms — `c16` does NOT reflect, `mc` reflects per byte. Both are correct for their target protocol.

### Correctness assessment

| Item | Verdict |
| --- | --- |
| Magic-byte symmetry | `ple()` writes `0x50 0x4C`; `pld()` requires `d[0]==0x50 and d[1]==0x4C`. ✓ |
| Length encoding | `<HB` little-endian for `(len, seq)`; `pld()` reads `d[2] | (d[3] << 8)`. ✓ |
| XOR key symmetry | XOR is self-inverse with the same key — verified by `test_unit_pllink_proto.py:TestXorCipher`. ✓ |
| CRC algorithm | Symmetric (`c16(h + xor_payload)` on both ends). ✓ |
| CRC coverage | Encoder includes `LEN(2) + SEQ(1) + XOR(payload)`; decoder reconstructs `struct.pack('<HB', l, d[4]) + px` — same range. ✓ |
| Roundtrip | `ple()` → `pld()` recovers original — verified by `TestPldDecode.test_roundtrip`. ✓ |
| Length bounds | `pld()` rejects `l < 1 or l > 280` — `pllink_proto.py:34-35`. Max MAVLink v2 frame is 280 bytes (1 + 9 + 255 + 2 + 13 signed). ✓ |
| MAVLink-CRC algorithm | Matches `_mavlink_crc16` in `backend/drone_link.py:399-406` and `mc()` in pllink_proto.py — same MCRF4XX. ✓ |
| MAVLink header layout | bm() lays out `LEN, incompat, compat, SEQ, sysid, compid, mid[3]` after the 0xFD magic — matches MAVLink v2 spec. ✓ |

The protocol is correctly implemented in the simple/happy case. Concerns are around edge cases and integration semantics:

### Edge cases & concerns

#### E1. Length skip on bad-magic is technically correct but oddly written

`pllink_proto.py:32`: `return None, max(1, len(d) > 0)`. `len(d) > 0` is a bool that becomes 0 or 1 when compared to integers; `max(1, 0) == max(1, 1) == 1`. So skip is always 1 when this branch fires, regardless of `len(d)`. This is what's intended (advance 1 byte and look again) but it reads like a typo. The outer loop in `drone_link.py:497` requires `len(self._buf) >= 7` before calling `_next_frame()`, so the `len(d) > 0` check is unreachable as written. Cosmetic.

#### E2. False-positive magic with bad CRC advances only 2 bytes

`pllink_proto.py:42`: when CRC fails, `pld` returns `(None, 2)` — skip past the 2-byte magic only. If the byte stream contained random bytes that happened to start `0x50 0x4C`, we lose 2 bytes (acceptable) but may then re-enter the next frame mid-payload, costing more bytes before resync. Worst case is correctness-preserving but slow recovery. No data corruption — every subsequent `pld()` call requires magic at offset 0.

#### E3. One-shot auto-detect can mis-lock the protocol

`backend/drone_link.py:445-455` (`_next_frame`): the first time `len(self._buf) >= 2`, the code locks `_protocol` to either `'pllink'` or `'standard'` based on bytes [0..1], with no fallback. If the very first 2 bytes of stream are garbage that happens to be `0x50 0x4C`, the link permanently believes it's PL-Link and never parses any real MAVLink. Probability is low (1/65536) but the failure mode is silent — heartbeats keep going out, no frames come in, the user sees a "connected" toast that's actually broken.

#### E4. No way to switch protocol after lock-in

Once `_protocol` is `'pllink'` or `'standard'`, the only way back to `'auto'` is `reconnect()` (`drone_link.py:240`) or a link-loss-driven re-open (`drone_link.py:478`). Manual protocol changes via UI aren't possible after connect.

#### E5. PL-Link sequence number is decoupled from MAVLink sequence

The inner MAVLink frame already contains a SEQ byte at offset 4. The outer PL-Link header also has a SEQ byte. `backend/drone_link.py:148` uses the same `self.sq` for both — fine — but on the receive side `pld()` (`pllink_proto.py:30-42`) returns the decoded MAVLink frame and **silently drops** the PL-Link seq. It's never checked for gaps, never compared to the inner MAVLink seq.

Consequences: a dropped PL-Link frame is invisible (you'd only see it via the inner MAVLink seq gap, if anyone tracked that — nobody does in this codebase). Probably fine if the inner MAVLink layer is the authoritative one.

#### E6. `bm()` crashes with a `ValueError` on payloads >= 256 bytes

`pllink_proto.py:58`: `bytes([len(p), 0, 0, …])`. `len(p)` can exceed 255, and `bytes([N, ...])` requires `0 <= N <= 255`. MAVLink v2 max payload IS 255, so this won't crash in correctly-formed callers — but if any caller miscomputes a payload (e.g., a fence with too many bytes packed inline), the crash is a hard `ValueError` propagating out of `link.send()` rather than a clean MAVLink-level error.

`backend/drone_link.py:152-153` catches `OSError` only — `ValueError` from `bm()` would propagate up through the call site, killing the WebSocket handler.

#### E7. No payload-length validation in `ple()`

`pllink_proto.py:24-27`: `ple()` packs the caller-provided payload length into a `<HB` struct. Anything that fits in a u16 is accepted (up to 65535). But `pld()` rejects `l > 280`. So a sender could create a frame `ple()` would emit but `pld()` would always reject — a one-way DoS only on the receive side. Not a real-world bug because callers always pass MAVLink frames bounded to 280 bytes.

#### E8. No protection against the inner payload starting with `0x50 0x4C`

The inner MAVLink frame is XORed with `KeyPL1!@`, so its first byte (always `0xFD`) becomes `0xFD ^ 0x4B = 0xB6`. The encoded payload therefore cannot start `0x50 0x4C` (the magic) — that's good. But this is a side-effect of the XOR key choice; nothing enforces it. If the key were changed to one where `key[0] = 0xAD`, the first XORed byte would be `0x50` and frames could be mis-synced at scan time. (Low risk because XOR key is hardcoded, but worth documenting.)

#### E9. `_buf` truncation policy is lossy and can split a frame

`backend/drone_link.py:491-493`: when `len(self._buf) > 65536`, the buffer is truncated to its last 32768 bytes. If a partial PL-Link frame straddled the cutoff (e.g., we'd received the magic+length bytes but not the payload+CRC and the buffer hit the cap), the lead bytes are dropped and the remaining payload+CRC bytes become garbage. The next call to `pld()` sees garbage starting with the middle of a frame. Recovery is slow byte-by-byte resync.

The cap is large (64KB) and the FC won't normally backlog that much, but on slow read loops or a stuck consumer this could trigger and silently corrupt a frame boundary. Adding `_parse_errors += 1` (which is done) at least reports it.

#### E10. Threading model: `send()` uses `self._lock`, reads `self.sq` outside it

`backend/drone_link.py:143-153`: the write itself is protected, but `self.sq & 0xFF` is read inside the lock. Increment is also inside (`self.sq += 1` line 151). So that's fine. Multiple threads (param loader thread, NTRIP injector thread, websocket cmd handler) calling `link.send()` concurrently will serialize correctly. ✓

#### E11. The `c16` CRC choice is not the standard MAVLink CRC

`pllink_proto.py:15-21` (`c16`): MSB-first, non-reflecting, init 0xFFFF, poly 0x1021. This is CRC-16/CCITT-FALSE (also called "XMODEM" variant). MAVLink uses CRC-16/MCRF4XX (CCITT with reflection). Two distinct algorithms, both correctly implemented; just worth noting that `c16` is the PL-Link envelope CRC and `mc` is the MAVLink CRC — they cannot be reused for each other.

#### E12. `c16` does not include any framing-stable salt

There's no per-key randomization or HMAC. If an attacker captures a valid frame, they can replay it forever, or flip bits inside the XOR-encrypted region and the inner MAVLink CRC (with its CRC_EXTRA salt) becomes the only real integrity check. The PL-Link layer is obfuscation, not authentication. (This is consistent with comments in the file but not stated explicitly.)

### Summary

The PL-Link protocol is **a correct, minimal XOR-obfuscating envelope around MAVLink v2**. It is symmetric, deterministic, well-bounded, and round-trips cleanly. The encoder/decoder match. Frame sync recovery is slow but correct. The only practical issues are around (a) one-shot auto-detect with no fallback, (b) the lossy buffer truncation policy, and (c) `bm()` crashing rather than erroring on oversized payloads.

**12 edge-case concerns identified, 0 critical correctness bugs.**

---

## Section 3 — Concrete Bug List

### PX4 bugs (in order of severity)

| # | Severity | File:Line | Description |
| - | - | - | - |
| P1 | **Critical** | `src/lib/fc/index.ts:15-20` & all UI | The FC adapter (`px4Adapter`, `ardupilotAdapter`, `detectAdapter`) is **never imported** by any production code. All mode/button data is delivered by the backend in `mode_btns`/`mode` fields. README's "auto-detect via FC adapter layer" is false. |
| P2 | **Critical** | `backend/mavlink_handlers.py:30-64` | `handle_heartbeat` never reads `p[5]` (autopilot field). Backend has no way to detect PX4. |
| P3 | **Critical** | `backend/drone_link.py:253-274`, `backend/constants.py:10-44` | Mode tables are 100% ArduPilot. PX4's packed `(sub<<24)|(main<<16)` custom_mode lookup will always miss → "MODE197120" garbage in UI. |
| P4 | High | `backend/commands/_flight.py:28`, `backend/commands/_hardware.py:34`, `backend/commands/_mission.py:22` | RTL/Guided/Auto mode IDs are hardcoded to ArduPilot integers. Sending these to a PX4 vehicle is meaningless. |
| P5 | High | `backend/commands/_helpers.py:20-22` | `send_set_mode` uses deprecated MAVLink msg 11 (SET_MODE) with ArduPilot custom_mode semantics. PX4 expects `MAV_CMD_DO_SET_MODE` (cmd 176) with `(base_mode, main_mode, sub_mode)` triplet. |
| P6 | High | `backend/commands/_setup.py:23-24, 47-58, 70` | Compass cal (42424/42425/42426) and accel-cal ACK (msg 77 with cmd=0,result=1) are ArduPilot extensions. PX4 ignores them. Calibration flow will silently no-op on PX4. |
| P7 | High | `backend/commands/_flight.py:23-24` | Force-disarm magic `p2=21196` is ArduPilot-only. PX4 force-disarm uses a different mechanism. |
| P8 | Medium | `src/lib/transport.ts:135-150` | WebSerial path uses `REQUEST_DATA_STREAM` (msg 66) which PX4 dropped support for. PX4 vehicles connected via WebSerial direct will receive no telemetry. |
| P9 | Medium | `src/lib/transport.ts:172-174` | `serialSendRtl()` sends mode=11 with comment "RTL mode for copter". Copter RTL = 6, not 11. This is a freestanding bug (independent of PX4) that suggests the WebSerial path is rarely exercised. |
| P10 | Medium | `backend/commands/_hardware.py:110-125` | Motor test uses ArduPilot's 1-based motor index convention. PX4 motor test semantics differ. |
| P11 | Medium | `backend/mavlink_handlers.py:244` | PreArm/Arm prefix matching is ArduPilot-only. PX4 uses different statustext prefixes — dedup/aggregation won't trigger. |
| P12 | Low | `backend/statustext_filter.py:1-38` | All leak filters are ArduPilot strings. PX4's statustext goes through unfiltered. |
| P13 | Low | `backend/drone_link.py:49-57`, registered handlers at `mavlink_handlers.py:634-666` | Handlers registered for AP-only msgs (158 MOUNT_STATUS, 163 AHRS, 168 WIND, 178 AHRS2, 191-192 MAG_CAL_*, 193 EKF_STATUS_REPORT) will never fire on PX4 — but no PX4-equivalent handlers exist (MOUNT_ORIENTATION 265, ESTIMATOR_STATUS 230, WIND_COV 231). UI fields for these are zero-default. |
| P14 | Low | `backend/drone_link.py:271-273` | When `vtype_raw > 0` but not a known plane/rover/sub type, code defaults to COPTER_MODES. For PX4 hexarotor (MAV_TYPE=13) you'd get ArduCopter mode names — correct by accident for some IDs, wrong for most. |

### PL-Link bugs (in order of severity)

| # | Severity | File:Line | Description |
| - | - | - | - |
| L1 | Medium | `backend/drone_link.py:445-455` (`_next_frame`) | One-shot auto-detect locks in on the first 2 bytes with no fallback. Garbage that starts with `0x50 0x4C` permanently mis-locks the link to PL-Link. Probability low (~1/65536) but failure is silent. |
| L2 | Medium | `backend/pllink_proto.py:58` (`bm()`) | Crashes with `ValueError: bytes must be in range(0, 256)` if a caller passes a payload of 256+ bytes. `link.send()` only catches `OSError`, so the exception propagates up the websocket handler. Add `assert len(p) < 256` or clamp explicitly. |
| L3 | Low | `backend/drone_link.py:491-493` | Buffer truncation on overflow (`len(_buf) > 65536` → keep last 32768) can split a partial PL-Link frame. Resync is correct but lossy. |
| L4 | Low | `backend/pllink_proto.py:32` | `return None, max(1, len(d) > 0)` is obscure — `len(d) > 0` is a bool, `max(1, True)` is `1`. Always returns 1 in practice. Refactor to `return None, 1`. |
| L5 | Low | `backend/pllink_proto.py:24-27` (`ple()`) | No payload-length validation. `ple()` will silently encode a frame too large for `pld()` to ever decode (`l > 280`). Add `if len(p) > 280: raise ValueError`. |
| L6 | Low | `backend/drone_link.py:240-251` (`reconnect`) | Manual protocol switching (force std vs pllink) isn't possible after first connect — auto-detect lock-in persists across `reconnect()` (which resets to `'auto'`) but not across `disconnect()` → `connect(protocol=…)`. Minor UX. |
| L7 | Info | `backend/pllink_proto.py:5` | XOR key `b'KeyPL1!@'` is hardcoded — readable from the binary. The PL-Link envelope is obfuscation, not authentication. If anyone treats it as a security layer, they're mistaken. |

---

## Verdict

- **PX4**: The "ArduPilot + PX4" claim is not delivered. The frontend has scaffolding (a clean `FcAdapter` interface with a working PX4 adapter and unit tests) but it is **dead code** — no UI component or transport layer ever calls it. The backend has no PX4 awareness anywhere, and mode tables, calibration semantics, and mode-set commands are all ArduPilot-specific. A PX4 vehicle would connect (HEARTBEAT decodes fine), then 95% of the UI would be broken (modes garbled, calibration no-ops, EKF/wind/gimbal fields stuck at zero, mode buttons send AP integers PX4 doesn't recognize).
- **PL-Link**: Correctly implemented. The XOR/CRC/framing is symmetric and bounded; round-trips work; sync recovery is correct if slow. Real issues are minor: auto-detect lock-in, `bm()` crashing on oversized payloads, lossy buffer truncation. No data-integrity bugs.
