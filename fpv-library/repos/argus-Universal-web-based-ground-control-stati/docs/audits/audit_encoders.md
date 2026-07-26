# Frontend MAVLink Encoder Audit

Authority: pymavlink.dialects.v20.ardupilotmega

## Scope

Audited functions in `src/lib/mavlink/messages.ts`:

- `encodeHeartbeat` (msg 0)
- `encodeCommandLong` (msg 76)
- `encodeSetMode` (msg 11)
- `encodeParamRequestList` (msg 21)
- `encodeParamSet` (msg 23)
- `encodeRequestDataStream` (msg 66)

These are the only `^export function encode*` functions in the file (verified by
grep). Also audited: `src/lib/mavlink/crc.ts` (CRC algorithm + CRC_EXTRA table)
and `src/lib/mavlink/codec.ts` (`encodeFrame`).

## Top-level verdict

- **0 encoder bugs**: every payload byte produced by every `encodeXxx` matches
  pymavlink's `MAVLink_xxx_message.pack()` byte-for-byte for the same field
  values.
- **0 CRC bugs**: `crc16()` matches `pymavlink.mavutil.x25crc` on all test
  vectors. All 60 CRC_EXTRA constants match the pymavlink class attributes.
- **0 frame builder bugs**: `encodeFrame` produces a frame whose CRC is
  self-consistent and whose bytes are accepted and decoded correctly by
  pymavlink. The only difference vs. pymavlink output is that the TS encoder
  does not strip trailing-zero bytes (see "Interpretation" section below).
  This is a minor bandwidth pessimization, not a correctness bug.

## Encoder results

### [PASS] encodeHeartbeat(sysType=6, autopilot=8)

```
  payload (9): 00 00 00 00 06 08 00 00 03
```

### [PASS] encodeHeartbeat(sysType=2, autopilot=3) -- quad/APM-style

```
  payload (9): 00 00 00 00 02 03 00 00 03
```

### [PASS] encodeCommandLong(MAV_CMD_COMPONENT_ARM_DISARM=400)

```
  payload (33): 00 00 80 3f 00 98 a5 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 90 01 01 01 00
```

### [PASS] encodeCommandLong(NAV_TAKEOFF=22, varied params)

```
  payload (33): 00 00 c0 bf 00 00 00 00 00 00 00 00 00 00 00 00 1f 85 45 41 79 e9 f6 c2 00 00 c9 42 16 00 01 01 00
```

### [PASS] encodeSetMode(targetSys=1, baseMode=81, customMode=3)

```
  payload (6): 03 00 00 00 01 51
```

### [PASS] encodeSetMode(targetSys=1, baseMode=0, customMode=0)

```
  payload (6): 00 00 00 00 01 00
```

### [PASS] encodeParamRequestList(1, 1)

```
  payload (2): 01 01
```

### [PASS] encodeParamSet(1, 1, "RC1_TRIM", 1500.0, 9)

```
  payload (23): 00 80 bb 44 01 01 52 43 31 5f 54 52 49 4d 00 00 00 00 00 00 00 00 09
```

### [PASS] encodeParamSet(1, 1, "SHORT", -3.14, 6)

```
  payload (23): c3 f5 48 c0 01 01 53 48 4f 52 54 00 00 00 00 00 00 00 00 00 00 00 06
```

### [PASS] encodeParamSet(1, 1, 16-byte name, 1.0, 9)

```
  payload (23): 00 00 80 3f 01 01 41 42 43 44 45 46 47 48 49 4a 4b 4c 4d 4e 4f 50 09
```

### [PASS] encodeRequestDataStream(1, 1, streamId=1, rate=4, start)

```
  payload (6): 04 00 01 01 01 01
```

### [PASS] encodeRequestDataStream(1, 1, streamId=10, rate=2, stop)

```
  payload (6): 02 00 01 01 0a 00
```

## CRC algorithm (crc.ts crc16 vs pymavlink x25crc)

- [PASS] input (4 bytes): ts=0xc66e pym=0xc66e
- [PASS] input (9 bytes): ts=0x6f91 pym=0x6f91
- [PASS] input (256 bytes): ts=0xcfc3 pym=0xcfc3
- [PASS] input (1 bytes): ts=0x0f87 pym=0x0f87
- [PASS] input (32 bytes): ts=0x1fae pym=0x1fae
- [PASS] input (19 bytes): ts=0xe36b pym=0xe36b

## Frame builder (codec.ts encodeFrame)

### HEARTBEAT full frame

Untrimmed (TS emits full-length payload):
```
  TS  : fd 09 00 00 2a 01 01 00 00 00 00 00 00 00 06 08 00 00 03 9f ec
  PYM : fd 09 00 00 2a 01 01 00 00 00 00 00 00 00 06 08 00 00 03 9f ec
  match: True
```

Trimmed (matching pymavlink v2 trailing-zero truncation):
```
  TS  : fd 09 00 00 2a 01 01 00 00 00 00 00 00 00 06 08 00 00 03 9f ec
  PYM : fd 09 00 00 2a 01 01 00 00 00 00 00 00 00 06 08 00 00 03 9f ec
  match: True
```

### COMMAND_LONG full frame

Untrimmed:
```
  TS  : fd 21 00 00 63 01 01 4c 00 00 00 00 80 3f 00 98 a5 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 90 01 01 01 00 45 02
  PYM : fd 20 00 00 63 01 01 4c 00 00 00 00 80 3f 00 98 a5 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 90 01 01 01 d7 ef
  match: False
```

Trimmed:
```
  TS  : fd 20 00 00 63 01 01 4c 00 00 00 00 80 3f 00 98 a5 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 90 01 01 01 d7 ef
  PYM : fd 20 00 00 63 01 01 4c 00 00 00 00 80 3f 00 98 a5 46 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 90 01 01 01 d7 ef
  match: True
```

## Interpretation: COMMAND_LONG "untrimmed" mismatch

pymavlink emits MAVLink v2 frames with **trailing-zero truncation**: trailing
zero bytes in the payload are stripped before transmission, and the
`payload_len` byte is reduced accordingly. The receiver pads back to the full
expected length with zeros.

The TS `encodeFrame` does NOT zero-trim — it always sends the full-length
payload. For COMMAND_LONG with `confirmation=0` (the last byte of the
payload), the TS frame is **1 byte longer** than pymavlink's.

**This is NOT a bug**:
- The TS frame's CRC is computed over its own declared `payload_len=33`, so
  the CRC is self-consistent.
- I verified that pymavlink itself parses the untrimmed TS frame correctly
  (`Parsed: COMMAND_LONG confirmation=0`), and all compliant v2 receivers
  including ArduPilot must do the same.
- Zero-trim is a sender optimization for bandwidth, not a correctness
  requirement.

Cost: 1 extra byte per COMMAND_LONG with `confirmation=0`. Same situation
applies to PARAM_SET (last byte is `param_type` — non-zero in practice),
SET_MODE (last byte is `base_mode` — can be 0), etc. Worst case overhead is
a handful of bytes per frame.

Verdict: **OK as-is** (compatible) but **could be optimized** by adding a
trim-trailing-zeros step in `encodeFrame` before computing the length and CRC.

## Summary

- Encoder payload tests: **12 / 12 passed**
- CRC algorithm tests: **6 / 6 passed**
- HEARTBEAT full-frame: **match byte-for-byte** with pymavlink
- COMMAND_LONG full-frame: matches after pymavlink's zero-trim is applied
  (the TS code does not zero-trim — see Interpretation above)

## CRC_EXTRA table validation

- **60 / 60 entries match pymavlink** — no mismatches, no missing entries.
