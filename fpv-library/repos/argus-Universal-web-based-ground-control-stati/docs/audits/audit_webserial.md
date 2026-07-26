# WebSerial MAVLink Codec Audit

Frontend MAVLink stack (`src/lib/mavlink/*`, `src/lib/fc/*`) audited against
backend (`backend/mavlink_handlers.py`, `backend/drone_link.py`, `backend/pllink_proto.py`)
with pymavlink v20 ardupilotmega dialect as the authoritative source.

CRC-extra table check: every entry in `src/lib/mavlink/crc.ts CRC_EXTRA` matches
pymavlink exactly. Every entry in `backend/drone_link.py _CRC_EXTRA` also matches.
The frontend is missing entries for `158 MOUNT_STATUS (=134)`, `191 MAG_CAL_PROGRESS (=92)`,
and `192 MAG_CAL_REPORT (=36)` — these messages cannot be CRC-validated by the
frontend parser (it silently accepts them without checking the CRC; see section 3).

---

## Section 1 — Decoder field-offset discrepancies

### 1.1 BUG: `decodeServoOutput` misaligned for servos 9..16

File: `src/lib/mavlink/messages.ts:210-216`

```ts
export function decodeServoOutput(p: DataView): ServoOutput {
  const outputs: number[] = [];
  for (let i = 0; i < 16 && (4 + i * 2 + 1) < p.byteLength; i++) {
    outputs.push(p.getUint16(4 + i * 2, true));
  }
  return { outputs };
}
```

Authoritative wire layout for `SERVO_OUTPUT_RAW` (msg id 36):

| ofs | field        |
|-----|--------------|
|  0  | time_usec u32 |
|  4  | servo1_raw u16 |
|  6  | servo2_raw u16 |
|  8  | servo3_raw u16 |
| 10  | servo4_raw u16 |
| 12  | servo5_raw u16 |
| 14  | servo6_raw u16 |
| 16  | servo7_raw u16 |
| 18  | servo8_raw u16 |
| **20** | **port u8 (1B gap)** |
| 21  | servo9_raw u16 |
| 23  | servo10_raw u16 |
| 25  | servo11_raw u16 |
| 27  | servo12_raw u16 |
| 29  | servo13_raw u16 |
| 31  | servo14_raw u16 |
| 33  | servo15_raw u16 |
| 35  | servo16_raw u16 |

The TS decoder reads channels at offsets `4 + i*2` for `i=0..15`, i.e.
`4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34`. Servos 1..8
land on the correct offsets, but starting at outputs[8] the read is shifted
1 byte left because the TS code does not skip the `port` byte at offset 20.

Result for a payload `04 00 00 00 / a0 0f a1 0f a2 0f a3 0f a4 0f a5 0f a6 0f a7 0f / 01 / a8 0f a9 0f aa 0f ab 0f ac 0f ad 0f ae 0f af 0f`:

| TS output    | TS reads from | Value           | Correct wire field | Correct value |
|--------------|--------------:|-----------------|--------------------|---------------|
| outputs[0..7] | ofs 4..18    | `0fa0..0fa7`    | servo1..8          | matches OK    |
| outputs[8]   | ofs 20       | `0f01` (port + servo9 lo) | port byte (not a servo) | bogus |
| outputs[9]   | ofs 22       | `0fa8` (servo9 hi + servo10 lo) | servo10            | bogus |
| outputs[15]  | ofs 34       | `0fad` (servo14 hi + servo15 lo) | servo16             | bogus |

Backend reads correctly (`backend/mavlink_handlers.py:249-260`):

```python
rc.servo_out = [struct.unpack_from('<H', p, 4 + i * 2)[0] for i in range(8)]
if pl >= 37:
    rc.servo_out += [struct.unpack_from('<H', p, 21 + i * 2)[0] for i in range(8)]
```

Fix: replace the single loop with two loops, mirroring the backend (use base
4 for `i in 0..7` and base 21 for `i in 0..7`), and skip output `port`.

### 1.2 Other decoders — clean

Every other TS decoder agrees with the authoritative wire layout (verified
against pymavlink `mavlink_map[msgid].unpacker.format` and `ordered_fieldnames`):

| msg id | name                | TS decoder | Status |
|--------|---------------------|------------|--------|
| 0      | HEARTBEAT           | `decodeHeartbeat` | OK |
| 1      | SYS_STATUS          | `decodeSysStatus` | OK (voltage @14 u16 /1000, current @16 i16 /100, remaining @30 i8) |
| 24     | GPS_RAW_INT         | `decodeGpsRawInt` | OK (lat @8, lon @12, alt @16, fix_type @28, sats @29) |
| 30     | ATTITUDE            | `decodeAttitude`  | OK (roll @4, pitch @8, yaw @12 — units rad→deg) |
| 33     | GLOBAL_POSITION_INT | `decodeGlobalPositionInt` | OK |
| 65     | RC_CHANNELS         | `decodeRcChannels` | OK (channels @4+2i for i in 0..17; chancount @40; rssi @41) |
| 74     | VFR_HUD             | `decodeVfrHud`    | OK (airspeed @0, groundspeed @4, alt @8, climb @12, heading @16 i16, throttle @18 u16) |
| 22     | PARAM_VALUE         | `decodeParamValue` | OK (value @0, count @4, index @6, id @8 char[16], type @24) |
| 77     | COMMAND_ACK         | `decodeCommandAck` | OK (command @0 u16, result @2 u8) |
| 42     | MISSION_CURRENT     | `decodeMissionCurrent` | OK (seq @0 u16) |
| 44     | MISSION_COUNT       | `decodeMissionCount` | OK (count @0 u16) |
| 47     | MISSION_ACK         | `decodeMissionAck`   | OK (type @2 u8) |
| 73     | MISSION_ITEM_INT    | `decodeMissionItemInt` | OK (params @0..12 f32, x @16 i32, y @20 i32, z @24 f32, seq @28 u16, command @30 u16, frame @34, current @35, autocontinue @36) |
| 242    | HOME_POSITION       | `decodeHomePosition` | OK (lat @0 i32 /1e7, lon @4 i32 /1e7, alt @8 i32 /1000) |
| 241    | VIBRATION           | `decodeVibration`    | OK (x @8, y @12, z @16, clip0..2 @20/24/28) |
| 168    | WIND                | `decodeWind`         | OK (direction @0, speed @4) |
| 253    | STATUSTEXT          | `decodeStatusText`   | OK (severity @0, text @1..50) |

### 1.3 Field semantics — backend-vs-frontend divergences (not bugs, but inconsistent surfaces)

These are not field-offset bugs but semantic surfaces that differ between
WebSerial mode and backend-proxy mode for the same wire data:

1. `decodeWind` returns raw direction in `[-180, 180]` or `[0, 360]` exactly as
   the FC sends it. The backend does `direction % 360`
   (`backend/mavlink_handlers.py:351`), so the UI will see negative wind angles
   in WebSerial mode whenever the FC sends them — a display difference, not a
   wire-level bug.

2. `decodeAttitude` returns yaw in `[-180, 180]` (TS just does `*180/pi`).
   Backend does `if a.yaw < 0: a.yaw += 360`
   (`backend/mavlink_handlers.py:73-74`), so yaw in WebSerial mode is signed
   degrees, while in backend-proxy mode it's `[0, 360]`.

3. `decodeGpsRawInt` returns `alt / 1000` (meters). Backend leaves alt as raw
   millimeters and never exposes it through state (only fix_type and sats). The
   TS `GpsRawInt` interface declares `alt` and `lat`/`lon` but no UI consumer
   reads them — they're scaled "for free" if a future consumer wants them.

4. `decodeGlobalPositionInt` does not compute `gs = sqrt(vx^2+vy^2)` like the
   backend does (`mavlink_handlers.py:91`). UI consumers in WebSerial mode that
   want ground speed must compute it themselves.

5. The TS decoder does not derive `dist_home` / `total_dist` / `max_alt` /
   `max_speed`. The backend computes these inline during message handling.
   Consumers in WebSerial mode get raw lat/lon/alt only; flight summary fields
   on the state object will not be populated.

### 1.4 Missing decoders / dispatch cases

The frontend `dispatchFrame` (messages.ts:385-407) routes only 18 messages.
The backend handles 31. Messages the frontend silently ignores (or routes to
`onUnknown`) in WebSerial mode:

| msg id | name | Backend feature |
|--------|------|-----------------|
| 46     | MISSION_ITEM_REACHED | `wp_reached` event |
| 40, 51 | MISSION_REQUEST(_INT) | mission upload progress |
| 118    | LOG_ENTRY            | log list |
| 120    | LOG_DATA             | log download |
| 126    | SERIAL_CONTROL       | FC console |
| 136    | TERRAIN_REPORT       | `terrain_alt` |
| 147    | BATTERY_STATUS       | battery cell voltages |
| 148    | AUTOPILOT_VERSION    | `fw_version`, `fw_git`, `board_id` (`AutopilotVersion` interface is declared in `messages.ts:132` but there is no decoder and no dispatch case) |
| 158    | MOUNT_STATUS         | gimbal pitch/yaw |
| 191    | MAG_CAL_PROGRESS     | compass cal progress |
| 192    | MAG_CAL_REPORT       | compass cal result |
| 193    | EKF_STATUS_REPORT    | `ekf_vel`, `ekf_pos_h`, `ekf_pos_v`, `ekf_compass`, `ekf_flags` |
| 246    | ADSB_VEHICLE         | nearby traffic |

In WebSerial mode all these features are silently unavailable.

---

## Section 2 — Encoder byte-identity verification

For identical inputs (sysid=255, compid=190, same payload bytes, same seq),
TS `encodeFrame(msgId, payload, sysId, compId, seq)` produces **byte-identical
wire frames** to backend `pllink_proto.bm(mid, p, s, ce, sysid=255, compid=190)`.
Verified for HEARTBEAT (msg 0) and COMMAND_LONG (msg 76):

```
HEARTBEAT (sysid=255,compid=190,seq=13):
  backend bm():    fd0900000dffbe000000000000000608000003eadd
  ts encodeFrame: fd0900000dffbe000000000000000608000003eadd
  Identical: True

COMMAND_LONG ARM (sysid=255,compid=190,seq=0):
  backend bm():    fd21000000ffbe4c00000000803f0000000000000000…21dd
  ts encodeFrame: fd21000000ffbe4c00000000803f0000000000000000…21dd
  Identical: True
```

CRC algorithm and seed location verified identical:
- Frontend `crc16` and backend `_mavlink_crc16` produce same CRC for any input.
- Frontend `encodeFrame` accumulates CRC over `buf[1..10+payload_len)` then
  appends `crc_extra`.
- Backend `bm()` does the same.

### 2.1 Behavior difference (not byte-level): default compid

- Frontend `transport.ts:131` calls `encodeFrame(msgId, payload, 255, 190, seq++)`
  — sysid 255 ("GCS"), compid 190 (`MAV_COMP_ID_MISSIONPLANNER`).
- Backend `pllink_proto.bm()` defaults to `sysid=255, compid=1`. Callsites in
  `backend/commands/` use the default unless overridden.

When the same wire frame is generated from either side, the FC sees a different
component id (190 vs 1). This is not a parse error but does mean things like
ack routing / target_component comparisons can behave differently. Most ArduPilot
FCs ignore compid for command routing, so in practice both work.

### 2.2 Encoder: no zero-trim

Neither side applies MAVLink 2 zero-trim on send (the spec permits omitting
trailing zero bytes from the payload to save bandwidth). Both always send the
full nominal payload length. This is legal — receivers must accept both forms.

---

## Section 3 — Edge case handling

### 3.1 MAVLink 2 zero-trim — DECODER GAP

The MAVLink 2 spec allows the SENDER to truncate trailing zero bytes from the
payload. The receiver must treat any byte past `payload_len` as zero. ArduPilot
*does* zero-trim on send for many messages.

The backend handles this with the `_pad(p, n)` helper in `mavlink_handlers.py:16-27`
which zero-pads the payload before unpacking:

```python
def _pad(p: bytes, n: int) -> bytes:
    return p if len(p) >= n else p + b'\x00' * (n - len(p))
```

It is called explicitly in `handle_servo_output`, `handle_vibration`,
`handle_vfr_hud`, `handle_mission_current`, `handle_mission_ack`, `handle_wind`,
`handle_command_ack`, `handle_mag_cal_report`.

**The frontend never zero-pads.** The TS decoders read at fixed offsets via
`DataView.getXxx(offset)`. If the FC ships a trimmed payload, every offset past
`payload_len` will throw `RangeError`. Specifically at risk:

| Decoder | TS reads up to offset | Trims to (if nominal-zero fields) |
|---------|----------------------:|-----------------------------------|
| `decodeSysStatus`        | 30 (Int8 remaining) | drops error_count4 (28-29) + remaining (30) when all zero — wire len 18 |
| `decodeVfrHud`           | 18 (u16 throttle) | drops heading+throttle (16-19) when zero — wire len 16 |
| `decodeVibration`        | 28 (u32 clip2)     | drops clip1+clip2 (24-31) when zero — wire len 24 |
| `decodeRcChannels`       | 41 (u8 rssi)       | drops chan13..18 + chancount + rssi when zero — wire len 4 |
| `decodeServoOutput`      | 34 (u16 servo15-16 if hit) | drops servo9..16 + port when zero — wire len 20 |
| `decodeGpsRawInt`        | 29 (with guard) | guard at line 165: `p.byteLength > 29` — handles trim gracefully |
| `decodeStatusText`       | 1..51 (with `Math.min`) | safe |
| `decodeParamValue`       | 24 (u8 type) | drops type when zero — wire len 24; reading offset 24 throws RangeError on a 24-byte buffer (off-by-one risk) |
| `decodeMissionCurrent`   | 0..2 (u16 seq)  | seq is rarely zero in practice |
| `decodeMissionCount`     | 0..2 (u16 count) | count rarely zero |
| `decodeMissionAck`       | 2 (u8 type) | safe — type 0 = ACCEPTED so trim drops byte 2; **TS reads offset 2 directly, RangeError if pl < 3** |
| `decodeMissionItemInt`   | 36 (u8 autocontinue) | autocontinue often = 1, low trim risk |
| `decodeHomePosition`     | 8..12 (i32 alt)  | rare |
| `decodeWind`             | 4..8 (f32 speed) | rare; if wind reported as exactly zero, full payload would trim to 1B → RangeError |
| `decodeCommandAck`       | 2 (u8 result)   | result=0 (ACCEPTED) frequent — trim drops bytes 2..9 → wire len 2; **TS reads offset 2, RangeError if pl < 3** |

The most concrete bug: any `COMMAND_ACK` that pymavlink-encoded-and-trimmed
would land as 2 bytes (command u16 only) — TS would `RangeError` reading offset
2. ArduPilot's own MAVLink stack *does* zero-trim (`mavlink_helpers.h:_mav_finalize_message_chan_send`),
so this is a real runtime risk, not a hypothetical.

The 18 dispatch cases catch `RangeError` nowhere — it propagates out of
`dispatchFrame`. In `transport.ts` it is propagated from the read-loop and only
caught by the outer `serialReadLoop` callback in transport.ts (which does
`console.error(...)`). The frame is lost but the loop should keep running.

**Recommended fix**: copy the backend's `_pad` strategy. Either (a) wrap each
decoder in a "view a zero-padded array" helper, or (b) have `dispatchFrame`
extend the underlying buffer with zeros before constructing the DataView.

### 3.2 MAVLink 1 (0xFE magic) — no fallback (parity)

Neither frontend nor backend handles MAVLink 1 frames. Both parsers look for
`0xFD` only:
- Frontend `codec.ts:42`: `buf.indexOf(STX, offset)` with `STX = 0xFD`.
- Backend `drone_link.py:394`: `buf.find(b'\xfd')`.

ArduPilot 4.x and PX4 1.13+ default to v2, but legacy FCs may still ship v1.
Both sides silently skip those bytes. This is consistent behavior — not a
divergence, just a shared limitation.

### 3.3 Signed v2 frames (incompat_flags bit 0) — parity, no validation

Both frontend (`codec.ts:50-51`) and backend (`drone_link.py:402-403`) recognize
the signing flag and skip the 13-byte signature trailer in the frame length
calculation. Neither validates the signature. Consistent behavior.

### 3.4 CRC for full header — verified correct

Both implementations accumulate CRC over the full header (excluding STX):

```
crc_data = payload_len(1B) || incompat_flags(1B) || compat_flags(1B) ||
           seq(1B) || sysid(1B) || compid(1B) || msgid(3B) || payload(NB)
crc = crc16(crc_data ++ crc_extra)
```

This includes `incompat_flags`, `compat_flags`, `seq`, `sysid`, `compid`, all
3 msgid bytes, and the payload. Confirmed by reading frontend `codec.ts:60`
and backend `drone_link.py:409`. CRC algorithm (CRC-16/MCRF4XX, X.25 variant)
is bit-identical between the two.

### 3.5 Unknown msg id handling — DIVERGENCE

Frontend `codec.ts:58-68`:
```ts
const crcExtra = CRC_EXTRA[msgId];
if (crcExtra !== undefined) {
  // validate CRC, skip frame if invalid
}
// else: silently accept frame without CRC check
```

Backend `drone_link.py:411-423`:
```python
crc_extra = _CRC_EXTRA.get(mid)
if crc_extra is None:
    self._unknown_msg_ids[mid] = self._unknown_msg_ids.get(mid, 0) + 1
    return None, 1   # drop the frame
```

**Frontend accepts unknown-msgid frames** (including potential parse-sync
artifacts where 0xFD lands mid-payload) and dispatches them to `onUnknown`.
Backend rejects them. Since the frontend's missing-CRC-EXTRA list is much
larger (no 158/191/192 + the 13 messages it never decodes), a parse-sync error
in the middle of e.g. a real `EKF_STATUS_REPORT` payload could surface as a
spurious `onUnknown` callback with garbage data.

The frontend also lacks `decodeFooBar` for those msg ids, so the practical
risk is just one spurious `onUnknown` call rather than corrupted state. Still,
the parity gap is worth noting: backend is strict; frontend is permissive.

### 3.6 Mission download / upload — not implemented in WebSerial

The frontend has decoders for `MISSION_COUNT`, `MISSION_ITEM_INT`, `MISSION_ACK`
but no dispatch logic that *initiates* a download (no analogue of backend's
`_request_dl_item` and `_dl_pending` flow in `mavlink_handlers.py:371-413`).
WebSerial mode cannot download or upload missions even though the decoders
exist.

---

## Section 4 — `src/lib/fc/` adapter discrepancies

### 4.1 ArduPilot adapter (`src/lib/fc/ardupilot.ts`)

#### Copter mode table — superset of backend

Frontend `COPTER_MODES` defines 27 entries (0..27). Backend `COPTER_MODES`
(`backend/constants.py:1-4`) defines 11 entries (0..21). Authoritative ArduPilot
source (`ArduCopter/mode.h`) defines 0..28:

| Mode | Authoritative name | Frontend `COPTER_MODES` | Backend `COPTER_MODES` |
|------|--------------------|-------------------------|------------------------|
| 0    | STABILIZE          | Stabilize               | 自稳/Stabilize         |
| 1    | ACRO               | Acro                    | 特技/Acro              |
| 2    | ALT_HOLD           | AltHold                 | 定高/Alt Hold          |
| 3    | AUTO               | Auto                    | 自动/Auto              |
| 4    | GUIDED             | Guided                  | 引导/Guided            |
| 5    | LOITER             | Loiter                  | 悬停/Loiter            |
| 6    | RTL                | RTL                     | 返航/RTL               |
| 7    | CIRCLE             | Circle                  | 绕圈/Circle            |
| 9    | LAND               | Land                    | 降落/Land              |
| 11   | DRIFT              | Drift                   | (missing)              |
| 13   | SPORT              | Sport                   | (missing)              |
| 14   | FLIP               | Flip                    | (missing)              |
| 15   | AUTOTUNE           | AutoTune                | (missing)              |
| 16   | POSHOLD            | PosHold                 | 定点/PosHold           |
| 17   | BRAKE              | Brake                   | (missing)              |
| 18   | THROW              | Throw                   | (missing)              |
| 19   | AVOID_ADSB         | Avoid_ADSB              | (missing)              |
| 20   | GUIDED_NOGPS       | Guided_NoGPS            | (missing)              |
| 21   | SMART_RTL          | SmartRTL                | 智能返航/Smart RTL     |
| 22   | FLOWHOLD           | FlowHold                | (missing)              |
| 23   | FOLLOW             | Follow                  | (missing)              |
| 24   | ZIGZAG             | ZigZag                  | (missing)              |
| 25   | SYSTEMID           | SystemID                | (missing)              |
| 26   | AUTOROTATE         | Heli_Autorotate         | (missing)              |
| 27   | AUTO_RTL           | Auto RTL                | (missing)              |
| 28   | TURTLE             | (missing — bug)         | (missing)              |

The frontend table is missing **mode 28 TURTLE** (added in ArduPilot 4.3).
A drone in TURTLE mode will display as `MODE28` in WebSerial mode but as
`MODE28` in backend mode too (backend's fallback is `'MODE%d' % v.mode`).
Behavior is consistent (both fail-soft), but neither has TURTLE.

#### Plane mode table — missing modes 3, 8, 13, 16

Frontend `PLANE_MODES` is missing:
- Mode 3 TRAINING
- Mode 8 AUTOTUNE
- Mode 13 TAKEOFF
- Mode 16 INITIALISING

Backend's `PLANE_MODES` is also missing these. Both fall through to `MODE%d`.

#### Mode `armBaseMode() returns 209`

Both frontend (`ardupilot.ts:63`) and px4 (`px4.ts:87`) return `209 = 0xD1 =
MAV_MODE_FLAG_CUSTOM_MODE_ENABLED (0x01) | MAV_MODE_FLAG_DECODE_POSITION_AUTO_ENABLED (...) | MAV_MODE_FLAG_SAFETY_ARMED (0x80)`.

Backend never explicitly uses `armBaseMode()`; instead it sends `MAV_CMD_COMPONENT_ARM_DISARM`
(command 400). The WebSerial transport (`transport.ts:154-166`) also uses
`COMMAND_LONG / 400` to arm, so `armBaseMode()` is currently dead code. No
divergence in practice, but the value `209` is non-standard for an arm
operation — it would only be relevant if a user invoked `serialSendMode`
with the arm-flag pattern.

#### `is_plane` heuristic — partial parity

Backend `drone_link.py:127-131`:
```python
def is_plane(self) -> bool:
    if v.force_plane is not None:
        return v.force_plane
    return v.vtype_raw in (1, 19, 20, 21, 22, 23, 24, 25)
```

Frontend has no equivalent in the adapter. The `modeName(customMode, isPlane)`
takes `isPlane` as a parameter; the caller must determine it. There is no
helper that maps `mav_type → isPlane`. UI code that needs this must replicate
the backend's tuple `(1, 19, 20, 21, 22, 23, 24, 25)` inline. Worth noting:
the frontend currently has no documented place that does this; it likely
falls back to displaying copter modes by default.

`vehicleTypeName` is exposed (`ardupilot.ts:68`) and covers the same vtype IDs
the backend recognizes — but as plain strings, with no "is this a plane"
signal extracted from them.

#### Mode buttons — different selection than backend

Frontend `COPTER_BTNS` order (`ardupilot.ts:22-25`):
`[AltHold, Loiter, Auto, RTL, Stabilize, PosHold, Guided, Land]`

Backend `COPTER_BTNS` (`backend/constants.py:18`):
`[Stabilize, AltHold, Loiter, Auto, RTL, Land]`

Different button sets and orderings. UI will display different quick-switch
buttons in WebSerial vs backend mode for the same vehicle. Not a bug — a
product decision — but inconsistent.

### 4.2 PX4 adapter (`src/lib/fc/px4.ts`)

#### custom_mode encoding — correct

PX4's `px4_custom_mode` union packs `main_mode` into bits 16..23 and
`sub_mode` into bits 24..31 (PX4 source `Firmware/src/modules/commander/px4_custom_mode.h`).
The frontend correctly extracts:

```ts
function mainMode(customMode: number): number { return (customMode >> 16) & 0xFF; }
function subMode(customMode: number): number  { return (customMode >> 24) & 0xFF; }
```

#### Mode constants — verified

`PX4_MAIN_MANUAL = 1`, `PX4_MAIN_ALTCTL = 2`, ... `PX4_MAIN_RATTITUDE = 8`
match `commander_state.h:CUSTOM_MAIN_MODE_*`.

`PX4_AUTO_TAKEOFF = 2`, `PX4_AUTO_LOITER = 3`, `PX4_AUTO_MISSION = 4`,
`PX4_AUTO_RTL = 5`, `PX4_AUTO_LAND = 6`, `PX4_AUTO_FOLLOW = 8`,
`PX4_AUTO_PRECLAND = 9` match `PX4_CUSTOM_SUB_MODE_AUTO_*`.

(Backend has no PX4 support at all, so there is nothing to compare for PX4.
The frontend is the only adapter for PX4 in either layer.)

#### vehicleTypeName — minor differences

PX4 adapter has `22: 'VTOL Standard'`; ArduPilot adapter has `22: 'VTOL Fixedrotor'`
for the same MAV_TYPE_VTOL_FIXEDROTOR enum. Both are descriptive names, not bug.
PX4 adapter also omits MAV_TYPE 23/24/25 (Tailsitter/Tilt) which ArduPilot has.

---

## Summary of findings

### Field-offset bugs: 1

1. `decodeServoOutput` misreads servos 9..16 by 1 byte (does not skip the
   `port` byte at offset 20). UI displays bogus values for servos 9..16 in
   WebSerial mode.

### Edge-case gaps: 4

1. **No zero-pad in decoders.** TS decoders use `DataView.getXxx(fixedOffset)`
   without bounds checks. If the FC trims trailing-zero bytes (per MAVLink 2
   spec, which ArduPilot does), `RangeError` is thrown. At highest risk:
   `decodeCommandAck`, `decodeMissionAck`, `decodeParamValue` (RangeError if
   pl=24), `decodeVfrHud`, `decodeVibration`, and `decodeSysStatus`.

2. **Unknown msg id frames are accepted without CRC validation.** Frontend
   permits them; backend rejects. Frontend may surface garbage `onUnknown`
   callbacks from parse-sync drift.

3. **No MAVLink 1 (0xFE) fallback.** Consistent with backend, but a parity
   limitation worth documenting.

4. **No mission upload/download flow.** Frontend has the decoders but no
   state machine to drive a download (no `_request_dl_item` analogue).

### Missing decoders / dispatch: 13 messages

`AutopilotVersion` interface declared with no decoder; messages 40, 46, 51,
118, 120, 126, 136, 147, 148, 158, 191, 192, 193, 246 are not dispatched.
WebSerial mode silently loses gimbal status, EKF status, battery cells,
terrain alt, ADSB traffic, mag cal progress, FW version, mission progress,
console, and log download.

### FC adapter discrepancies: 1 functional gap

The frontend has no `isPlane(vtype)` helper. Callers must replicate the
backend's tuple `(1, 19, 20, 21, 22, 23, 24, 25)` inline, or they will
default to copter modes when displaying a plane.

### Encoder: byte-identical

`encodeFrame` produces wire output byte-identical to backend `pllink_proto.bm()`
for the same `sysid`/`compid`/`seq`/`payload`/`crc_extra` inputs. CRC algorithm,
header layout, and field ordering all match. Default `compid` differs (190
vs 1) but this is a behavioral choice, not a wire-format defect.
