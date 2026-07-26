# MAVLink Mission Protocol Audit — Argus GCS vs ArduPilot

Scope: Argus backend `_mission.py`, `_helpers.py`, `mavlink_handlers.py` audited against ArduPilot `AP_Mission.cpp`, `GCS_Common.cpp`, `MissionItemProtocol*.cpp`. Field-level byte correctness was already confirmed in a prior round; this audit focuses on the stateful protocol.

---

## Section 1 — Field-level findings (per function)

### Outbound (send_*) helpers

| Function | File:line | Result |
|---|---|---|
| `send_mission_count` (mission, type=0) | `_helpers.py:25-26` | OK — packs `<HBB`+type byte → 5 bytes; CRC 221, msg 44; matches `mavlink_mission_count_t` (LEN=5, MIN=4). |
| `send_fence_count` (type=1) | `_helpers.py:29-30` | OK — identical to mission count with mission_type=1. |
| `send_mission_item_int` | `_helpers.py:45-56` | PARTIAL — wire format is right, but frame-selection logic is incorrect for several commands; see Sec 3. |
| `send_fence_item_int` | `_helpers.py:33-42` | OK — packs `<ffffiifHHBBBBBB` (38 bytes), CRC 38, msg 73, mission_type=1 in last byte. |
| `cmd_mission_clear` MISSION_CLEAR_ALL | `_mission.py:41` | PARTIAL — packs 3 bytes (sysid,1,0); msg 45, CRC 232. Correct wire format but only clears mission_type=0; cannot clear fence (type=1) or rally (type=2). |
| `cmd_mission_download` MISSION_REQUEST_LIST | `_mission.py:90` | PARTIAL — packs 3 bytes (sysid,1,0); msg 43, CRC 132. Only downloads mission_type=0; no API to download fence/rally. |
| `_request_dl_item` MISSION_REQUEST_INT | `mavlink_handlers.py:434-436` | OK — packs `<HBBB`; msg 51, CRC 196. |
| GCS-side MISSION_ACK (after DL complete) | `mavlink_handlers.py:431` | PARTIAL — packs 3 bytes (sysid, 1, type=0). Relies on mavlink2 zero-trim of extension `mission_type` byte. Works only if type=0 (mission). Cannot ack fence/rally downloads. |
| `_upload_rally` MISSION_COUNT + items | `_mission.py:192-203` | WRONG — see Sec 4, bug #1. Sends MISSION_COUNT with mission_type=2 then blasts every MISSION_ITEM_INT without waiting for MISSION_REQUEST. Violates the request/response state machine. |
| `send_cmd` MISSION_START (cmd 300) | `_flight.py + _helpers.py:14-17` | OK — COMMAND_LONG payload `<fffffffHBBB`, CRC 152, msg 76. |

### Inbound handlers

| Function | File:line | Result |
|---|---|---|
| `handle_mission_count` | `mavlink_handlers.py:377-390` | PARTIAL — extracts count u16 at offset 0; works. **Does not read or store mission_type** (offset 4 extension). If AP responds to a fence request_list (not currently sent by Argus, but defensive concern) the type info is lost. Also no defensive bound on count — a malformed count=65535 would allocate a 65535-entry None list. |
| `handle_mission_item_int` | `mavlink_handlers.py:393-431` | PARTIAL — reads p1, p2 only. **Loses p3, p4, frame, current, autocontinue, mission_type** during download. Re-uploading a downloaded mission silently zeroes p3/p4 (e.g. CONDITION_YAW direction in p3) and forces frame back to whatever `send_mission_item_int` picks based on cmd id. |
| `handle_mission_request` (msg 40 & 51) | `mavlink_handlers.py:439-452` | PARTIAL — correct seq decode, but: (a) routes only on `_fence_pending` / `_mission_pending`; cannot handle rally (mission_type=2); (b) on concurrent pendings both branches are tested with elif so an ack/request can be misrouted; (c) no acknowledgement that seq is the expected `request_i`; we always answer with whatever the FC asks. |
| `handle_mission_ack` | `mavlink_handlers.py:455-471` | PARTIAL — type/mission_type offsets correct. Routes fence vs mission by mission_type, **but does not distinguish rally**. If `_fence_pending` and `_mission_pending` are both true (concurrent uploads possible) and the ACK arrives with trimmed extension (mission_type=0 by zero-fill), only `_mission_pending` is cleared — the fence side is orphaned. |
| `handle_mission_item_reached` (msg 46) | `mavlink_handlers.py:158-162` | OK — seq u16 at 0. |
| `handle_mission_current` (msg 42) | `mavlink_handlers.py:142-145` | PARTIAL — reads seq only. Does not capture total / mission_state / mission_mode extension fields. Minor; no protocol break. |

### CRC and msg-id summary (verified against generated MAVLink headers)

| Msg | id | CRC | Argus uses | Status |
|---|---|---|---|---|
| MISSION_REQUEST | 40 | 230 | n/a (only receives) | OK |
| MISSION_CURRENT | 42 | 28 | n/a (receives) | OK |
| MISSION_REQUEST_LIST | 43 | 132 | 132 | OK |
| MISSION_COUNT | 44 | 221 | 221 | OK |
| MISSION_CLEAR_ALL | 45 | 232 | 232 | OK |
| MISSION_ITEM_REACHED | 46 | n/a | n/a (receives) | OK |
| MISSION_ACK | 47 | 153 | 153 | OK |
| MISSION_REQUEST_INT | 51 | 196 | 196 | OK |
| MISSION_ITEM_INT | 73 | 38 | 38 | OK |
| COMMAND_LONG | 76 | 152 | 152 | OK |
| SET_MODE | 11 | 89 | 89 | OK |

---

## Section 2 — State-machine findings

### 2.1 No upload watchdog / timeout

`_mission.py` initialises `_mission_pending=True` and `_fence_pending=True` but never starts a timer. By contrast `cmd_mission_download` does set `_dl_start_time` and `check_mission_dl_timeout` (called from the main loop) eventually clears `_dl_pending`. There is no analogous `_mission_pending_start_time` / `_fence_pending_start_time`.

Consequence: if AP times out (its `upload_timeout_ms = 8000`; see `MissionItemProtocol.cpp:95`) and sends `MAV_MISSION_OPERATION_CANCELLED`, that ACK clears the flag — fine in the happy path. But if the link drops mid-upload (e.g., briefly disconnected), the ACK is never received and `_mission_pending` stays true indefinitely. The next upload attempt does not re-arm anything — `_upload_mission` just overwrites `_mission_items` and sends a fresh `MISSION_COUNT`. AP cancels the first transfer (per `MissionItemProtocol.cpp:61-80 cancel_upload`) and the new one proceeds, so this usually self-heals. But `_fence_pending` never gets cleared from the first run, so the next time AP sends MISSION_REQUEST with `mission_type=1`, Argus may still serve from the stale fence items list. Add explicit timeout + reset for `_mission_pending` and `_fence_pending`.

### 2.2 Disconnect cleans `_mission_pending` but not `_fence_pending`/`_dl_pending`

In `drone_link.py:207` only `self.mission._mission_pending = False` is reset on disconnect. `_fence_pending`, `_dl_pending`, `_dl_start_time`, `_dl_items`, `_dl_total` survive a disconnect/reconnect. On reconnect, a stray spontaneous MISSION_REQUEST from the new vehicle could trip the lingering fence branch, or a stale download could carry over.

### 2.3 Concurrent mission + fence uploads share a single dispatch in `handle_mission_request` / `handle_mission_ack`

```python
if mission_type == 1 and m._fence_pending:
    ...
elif m._mission_pending:
    ...
```

If both pendings are set (the UI can plausibly fire both quickly back-to-back), the **elif** means we evaluate only one branch. For ACK, if the ack's `mission_type` extension is zero-trimmed (always interpreted as 0), the fence-pending ACK is delivered to the mission branch — clearing the wrong flag. AP itself sends ACK with mission_type set per `MissionItemProtocol::send_mission_ack` (line 347-357), but mavlink-2 zero-trimming can drop the last byte if it's zero. Mission_type=0 is exactly zero, so the trim is common. The `_pad` in `handle_mission_ack` does pad to 4, so `p[3]` becomes 0, which then matches mission. We can NEVER reliably distinguish a mission ACK from a zero-trimmed fence ACK whose true mission_type byte was unfortunately trimmed — except that AP_Mission does send mission_type=1 explicitly in `send_mission_ack`. The trimmer only drops trailing zero bytes, so when mission_type=1 the byte is preserved, and when mission_type=0 the byte may be trimmed. In practice this means fence ACKs always have mission_type=1 visible; mission ACKs may or may not. So the actual misroute scenario is narrower — but it still exists if both pendings are concurrently set AND AP gets confused about which to ack.

### 2.4 `MissionState._dl_pending` doubles as "are we receiving items?"

`handle_mission_count` and `handle_mission_item_int` both gate on `_dl_pending`. If `cmd_mission_download` is called twice in quick succession, the second call resets `_dl_total=0`, `_dl_items=[]`, `_dl_start_time=time.time()` while the first is mid-transfer. AP, upon receiving the second MISSION_REQUEST_LIST, ignores it (sends `MAV_MISSION_DENIED` per `MissionItemProtocol.cpp:129-134 handle_mission_request_list` because `receiving` is from a different stream — actually `receiving` only applies to uploads; downloads can be re-initiated freely). AP will start a fresh count send. The old in-flight item would now collide with the new state — `_dl_items` was cleared so storing the in-flight seq is in bounds, but the resulting download is corrupt.

### 2.5 `_upload_mission` does not lock against concurrent commits

If two clients submit different missions simultaneously, both reach `_upload_mission` and both write `m._mission_items` / `m._mission_pending = True`. The second write wins. AP receives two MISSION_COUNT messages and only the latest sticks; AP cancels the prior upload. Argus serves items from whichever `_mission_items` won — could be inconsistent. Add a mutex around the upload sequence or reject when `_mission_pending` is already true.

### 2.6 No cancel API for mid-upload

The frontend has no "cancel upload" endpoint. If the user navigates away mid-upload, Argus keeps responding to AP's MISSION_REQUEST until AP times out. There is no `cmd_mission_cancel` that sends a MISSION_ACK with a non-zero error code to tell AP to abort.

### 2.7 MISSION_REQUEST is the legacy form (MAV deprecated) but AP still issues msg 40 to mavlink1 GCSs

Argus handles both msg 40 (MISSION_REQUEST) and msg 51 (MISSION_REQUEST_INT) with the same function — this is fine. But Argus always replies with MISSION_ITEM_INT (msg 73). AP's MissionItemProtocol::handle_mission_request expects a MISSION_ITEM (msg 39) in the legacy flow, but Argus only sends 73. Since Argus is mavlink-2 native (the `bm()` wrapper builds mavlink-2 frames per `pllink_proto.py:57-60`), AP's `mavlink2_requirement_met` check passes and the item_int path is used; AP simply prefers item_int. OK, but check the warning: AP emits `"got MISSION_REQUEST; use MISSION_REQUEST_INT!"` (`MissionItemProtocol.cpp:217`) when it sees a legacy GCS pull. That suggests AP sends MISSION_REQUEST (msg 40) only when it's the legacy path or non-int item flow. Argus correctly registers a handler for both. Non-issue.

### 2.8 Pending state has no per-transfer ID

Both `_mission_pending` and `_fence_pending` are booleans. Cannot distinguish a stale ACK from a current one. If we send two consecutive mission uploads and the first one's MAV_MISSION_OPERATION_CANCELLED arrives after the second's start, the cancel ACK clears `_mission_pending` for the wrong transfer, and the second one is left dangling.

### 2.9 `wp_seq` updates from MISSION_CURRENT without checking ownership

`handle_mission_current` (msg 42) updates `link.mission.wp_seq = p[0] | (p[1] << 8)` unconditionally. If a stale message arrives during a mid-upload (AP keeps reporting current=0), we overwrite our state. The download `dl_items` index is separate, but UI may use `wp_seq` to highlight current waypoint. During an upload, this remains stuck at 0 — minor cosmetic.

---

## Section 3 — Critical edge cases

### 3.1 Frame value selection in `send_mission_item_int`

```python
frame = 3 if wp['cmd'] in (16, 18, 19, 21, 22, 82) else 2
```

- **frame=3 (`MAV_FRAME_GLOBAL_RELATIVE_ALT`)** for: NAV_WAYPOINT(16), NAV_LOITER_TURNS(18), NAV_LOITER_TIME(19), NAV_LAND(21), NAV_TAKEOFF(22), NAV_SPLINE_WAYPOINT(82). Correct — these are nav cmds with `stored_in_location=true` (AP_Mission.cpp:889) and alt is interpreted as above-home.

- **frame=2 (`MAV_FRAME_MISSION`)** for everything else — e.g. DO_SET_ROI(201), DO_CHANGE_SPEED(178), DO_SET_SERVO(183), DO_SET_RELAY(181), CONDITION_YAW(115), DO_VTOL_TRANSITION(3000), and so on.

  Problem: `MAV_FRAME_MISSION` is only meaningful for non-location commands. For DO_SET_ROI(201), `stored_in_location(201)` is **true** (AP_Mission.cpp:907). AP's frame switch (AP_Mission.cpp:1465-1491) accepts MISSION (line 1467) but maps it to `relative_alt=0` (absolute). The ROI altitude (m, from MSL) becomes absolute MSL — but the user almost certainly meant relative altitude. **Bug:** ROI items get the wrong altitude frame.

  For the non-location DO commands (178, 181, 183, 115, etc.) the frame is irrelevant because AP's switch in `mavlink_int_to_mission_cmd` only enters the frame branch if `stored_in_location` is true. So frame=2 is harmless for them.

  Recommendation: use frame=3 for cmd in `stored_in_location` set ∪ ROI(201)/ROI_LOCATION(195), frame=2 otherwise.

### 3.2 Waypoint command param semantics — verified mappings

For Argus-generated items:

| Argus cmd | AP semantics (AP_Mission.cpp) | p1 | p2 | p3 | p4 | Argus value | Verdict |
|---|---|---|---|---|---|---|---|
| 16 NAV_WAYPOINT | Copter: p1=delay sec | `p1_val` (delay or loiter) | 0 | 0 | 0 | OK for Copter | OK |
| 16 NAV_WAYPOINT | Plane: p1=(passby<<8)\|acceptance, p2=acceptance, p3=passby | sends only p1 (delay) — Plane will pack the delay value into the low byte of acceptance | 0 | 0 | 0 | **subtle bug for Plane** | PARTIAL |
| 18 NAV_LOITER_TURNS | p1=turns(low)\|radius(high8), p3=radius signed for CCW, p4>0 = xtrack tangent | sends only `loiter_param` to p1 | 0 | 0 | 0 | If user sets >1 turn, radius defaults to 0m | PARTIAL |
| 19 NAV_LOITER_TIME | p1=time(s), p3=radius (sign=CCW), p4 xtrack | sends only loiter_param to p1 | 0 | 0 | 0 | OK time only | PARTIAL |
| 20 NAV_RETURN_TO_LAUNCH | none | 0 | 0 | 0 | 0 | OK | OK |
| 22 NAV_TAKEOFF | p1=min_pitch (plane only) | 0 | 0 | 0 | 0 | OK | OK |
| 82 NAV_SPLINE_WAYPOINT | p1=delay sec (Copter), Plane refuses | `delay` | 0 | 0 | 0 | OK Copter; Plane will reject (MAV_MISSION_UNSUPPORTED) | PARTIAL (no plane guard) |
| 115 CONDITION_YAW | p1=angle, p2=rate, p3=dir, p4=relative | yaw deg | 0 | dir | 0 | OK | OK |
| 178 DO_CHANGE_SPEED | p1=speed_type, p2=target_ms, p3=throttle_pct | 1 (groundspeed) | spd | 0 | 0 | OK | OK |
| 181 DO_SET_RELAY | p1=num, p2=state | 0 | 0 | 0 | 0 | OK only for relay 0 OFF | OK (matches `cmd_drop` design) |
| 183 DO_SET_SERVO | p1=channel, p2=PWM | servo num | pwm | 0 | 0 | OK | OK |
| 201 DO_SET_ROI | p1=mode (0..4) | 0 | 0 | 0 | 0 | sends mode=0 ("no ROI"); user's lat/lon stored but ignored | **subtle bug** (p1=0 means clear ROI, so the lat/lon are never used by AP) — see #3.4 |
| 206 DO_SET_CAM_TRIGG_DIST | p1=distance, p3=trigger immediate | dist | 0 | 0 | 0 | OK | OK |
| 3000 DO_VTOL_TRANSITION | p1=target_state | mode | 0 | 0 | 0 | OK | OK |

### 3.3 SEQ wrapping at 65535

Argus's frontend cap is 500 waypoints (`cmd_mission_upload:50`) which generates at most ~3500 items including extras. seq u16 fits up to 65535. No wrap risk in practice.

### 3.4 Empty mission upload

`cmd_mission_upload` returns early if `wps` is empty. Cannot send `count=0`. If you want to clear the mission, you must call `cmd_mission_clear` instead. AP would accept count=0 (`MissionItemProtocol.cpp:110-113`: it calls `transfer_is_complete` immediately).

But `_upload_mission` always prepends a home item (seq 0, cmd 16) and a takeoff (seq 1, cmd 22) and appends an RTL (cmd 20). So the smallest payload is 3 items even with zero user waypoints — never zero.

### 3.5 Download with empty mission

`handle_mission_count` with `count=0` properly sets `_dl_pending = False`. But it does NOT send a MISSION_ACK back to AP, even though AP would prefer one. Looking at AP's code (`MissionItemProtocol.cpp:120-144 handle_mission_request_list`), AP just emits MISSION_COUNT and waits for the GCS to request items. With count=0, no further interaction is required. So omitting the ACK is fine per spec.

### 3.6 Spurious MISSION_COUNT or MISSION_ITEM_INT from FC

When `_dl_pending` is False, both handlers early-return. Good.

When `_dl_pending` is True, `handle_mission_count` overwrites `_dl_total` and `_dl_items`. AP cannot legitimately re-send MISSION_COUNT mid-transfer (it sends once per RequestList), but a stale duplicate could clobber state. Mostly safe.

### 3.7 Concurrent fence + mission uploads

Already covered in 2.3. Argus would set both `_mission_pending` and `_fence_pending` if user clicks both quickly. AP cancels the first when the second MISSION_COUNT arrives (`MissionItemProtocol::cancel_upload` line 61-80) and only one will succeed. Argus state is corrupted — both pending flags remain true, only one ACK clears one. The other becomes a permanent orphan until disconnect or a fresh upload of that type.

### 3.8 Rally upload completely broken

The rally upload (`_upload_rally`) sends MISSION_COUNT with mission_type=2 then immediately blasts every MISSION_ITEM_INT (with seq=0,1,2,...) without waiting. AP rejects the items with `MAV_MISSION_INVALID_SEQUENCE` (`MissionItemProtocol.cpp:278-280`) because `request_i` is still 0 and the second item's `cmd.seq=1 != request_i=0`. AP also has no rally pending state in Argus, so it can't fulfill the request even if AP does request item 0. The rally upload silently fails.

### 3.9 NAV_LAND missing from `_upload_mission`

`send_mission_item_int` includes cmd=21 in the frame-3 group, but `_upload_mission` never adds a NAV_LAND. The mission always ends with NAV_RETURN_TO_LAUNCH (cmd 20). For ArduCopter, RTL is equivalent. For ArduPlane on auto mission, RTL works too. Acceptable.

### 3.10 `seq_to_wp` mapping drift

`_seq_to_wp` is computed in a parallel loop (lines 168-185) that mirrors the item-build loop (lines 112-164). Any divergence between the two loops would corrupt the seq→wp index mapping (used elsewhere to map FC reports back to original waypoints). Currently they appear consistent. Maintenance risk only.

### 3.11 Mission_type extension byte not always set on outbound MISSION_ITEM_INT

In `send_mission_item_int` (line 49), the final 6 bytes packed by `<BBBBBB>` are: sysid, 1, frame, current, autocontinue, **0**. The last byte = mission_type = 0 (mission). For mission items this is correct. But `send_fence_item_int` (line 41) packs final 6 as `sysid, 1, 3, 0, 1, 1` — mission_type = 1 (fence). Correct.

For rally `_upload_rally` (line 200): final 6 = `sysid, 1, 3, 0, 1, 2` — mission_type=2. Correct on the field level, but the surrounding protocol violation makes this moot.

### 3.12 No range check on downloaded `count`

`handle_mission_count` allocates `_dl_items = [None] * count` with no upper bound. A malformed (or adversarial) FC could send count=65535 → ~520 KB allocation. Not catastrophic but worth bounding to ~1000.

### 3.13 `handle_mission_item_int` drops p3, p4, frame, current

When downloading, the handler only stores p1, p2, lat, lon, alt, seq, cmd. Lost data:
- p3 (e.g. CONDITION_YAW direction, DO_CHANGE_SPEED throttle, NAV_LOITER radius)
- p4 (e.g. CONDITION_YAW relative flag, DO_SET_SERVO not used)
- frame (MAV_FRAME_GLOBAL_RELATIVE_ALT vs MAV_FRAME_GLOBAL vs MAV_FRAME_GLOBAL_TERRAIN_ALT) — relative_alt vs absolute vs terrain context is lost

Re-uploading a downloaded mission is therefore lossy.

---

## Section 4 — Concrete bug list (ranked by severity)

### CRITICAL

**Bug 1: Rally point upload violates MAVLink mission protocol — items are blasted without waiting for MISSION_REQUEST**

- Location: `backend/commands/_mission.py:192-203 _upload_rally`
- Expected (per `ardupilot/libraries/GCS_MAVLink/MissionItemProtocol.cpp:82-118 handle_mission_count` + `:13-34 init_send_requests` + `:270-327 handle_mission_item`):
  1. GCS sends MISSION_COUNT.
  2. AP allocates buffer, sets `request_i = 0`, sends MISSION_REQUEST(seq=0).
  3. GCS sends MISSION_ITEM_INT(seq=0) **only in response**.
  4. AP increments `request_i`, sends MISSION_REQUEST(seq=1). Repeat.
  5. After last item, AP sends MISSION_ACK.
  AP rejects items whose `seq != request_i` with `MAV_MISSION_INVALID_SEQUENCE` (`MissionItemProtocol.cpp:278-280`).
- Observed: `_upload_rally` sends MISSION_COUNT(mission_type=2) then immediately loops sending all MISSION_ITEM_INT(seq=0..N-1) back-to-back. There is no `_rally_pending` state, no entry in `handle_mission_request` for `mission_type=2`, and no rally branch in `handle_mission_ack`. The rally upload silently fails on every flight controller. Items 1+ are rejected; the first may or may not be accepted depending on timing.
- Fix: replicate the mission/fence pattern — set `_rally_pending=True`, store items, send count only, respond to AP's MISSION_REQUEST(mission_type=2). Add rally branches to `handle_mission_request` and `handle_mission_ack`.

**Bug 2: `_fence_pending` is not reset on disconnect**

- Location: `backend/drone_link.py:202-209` (disconnect path)
- Expected: All three pendings (`_mission_pending`, `_fence_pending`, `_dl_pending`) should be cleared on disconnect, mirroring the existing reset for `_mission_pending`.
- Observed: Only `_mission_pending` is cleared. `_fence_pending` and `_dl_pending` survive disconnect, leading to state corruption after reconnect (e.g., stale fence_items served in response to spontaneous MISSION_REQUEST after re-handshake).
- Fix: `self.mission._fence_pending = False`, `self.mission._dl_pending = False`, `self.mission._dl_start_time = 0.0`, clear `_dl_items` and `_mission_items`/`_fence_items`.

### HIGH

**Bug 3: No upload watchdog/timeout for mission or fence uploads**

- Location: `backend/commands/_mission.py:45-65 cmd_mission_upload` and `:68-81 cmd_fence_upload`
- Expected: AP times out uploads after 8s (`MissionItemProtocol.h:95 upload_timeout_ms = 8000`). If Argus loses the ACK (link blip, disconnect mid-flight), `_mission_pending` / `_fence_pending` should auto-reset via a watchdog analogous to `check_mission_dl_timeout` (`_mission.py:93-99`).
- Observed: No timeout. `_mission_pending` / `_fence_pending` can stay true forever, blocking subsequent ACKs from clearing the right flag and corrupting routing in `handle_mission_request`/`handle_mission_ack` when multiple pending operations coexist.
- Fix: Add `_mission_pending_start_time` / `_fence_pending_start_time` to `MissionState`. Extend the main-loop tick in `drone_link.py:501` to call a new `check_mission_upload_timeout` (15s) that clears flags and emits a timeout event.

**Bug 4: DO_SET_ROI(201) gets `frame=MAV_FRAME_MISSION` (=2) which makes its altitude absolute MSL, not relative**

- Location: `backend/commands/_helpers.py:46`
- Expected (per `ardupilot/libraries/AP_Mission/AP_Mission.cpp:889-921 stored_in_location`): ROI(201) is `stored_in_location`. The frame governs `cmd.content.location.relative_alt` (line 1465-1491). `MAV_FRAME_MISSION` → `relative_alt=0` (absolute MSL). `MAV_FRAME_GLOBAL_RELATIVE_ALT` → `relative_alt=1` (above home).
- Observed: `frame = 3 if wp['cmd'] in (16, 18, 19, 21, 22, 82) else 2` excludes 201 (and 195 — DO_SET_ROI_LOCATION), so ROI items go up as frame=2. AP stores ROI altitude as absolute MSL, but the GUI almost certainly sends altitudes relative to home. The drone will look at the wrong elevation.
- Fix: Either include cmd in {195, 201} in the relative-alt set, or compute frame from a `stored_in_location` whitelist matching AP_Mission.cpp:889-921 and select MAV_FRAME_GLOBAL_RELATIVE_ALT(3) for all of them.

**Bug 5: DO_SET_ROI sends p1=0 ("no ROI") instead of p1=3 ("fixed location")**

- Location: `backend/commands/_mission.py:141-144`
- Expected (per `AP_Mission.cpp:1242-1244`): `p1 = packet.param1; // 0=no roi, 1=next wp, 2=wp number, 3=fixed location`. To set ROI to a fixed coordinate, you must send `param1=3`. AP stores the lat/lon in `cmd.content.location` but the runtime command interpreter uses p1 to decide whether to read that location.
- Observed: Argus hardcodes `'p1': 0` for cmd_roi. AP receives ROI item with `p1=0` (no ROI) and ignores the lat/lon entirely. The ROI never gets set.
- Fix: Send `'p1': 3` (or expose the mode via the GUI). Also pair with bug 4.

**Bug 6: Concurrent mission + fence upload can orphan one pending flag**

- Location: `backend/mavlink_handlers.py:455-471 handle_mission_ack`
- Expected: Each pending operation is tracked independently; the ACK's `mission_type` field is authoritative.
- Observed: The `if/elif` structure makes the two paths mutually exclusive within a single ACK. If `mission_type=0` (mission) ACK arrives while `_fence_pending=True`, only the mission branch runs — correct. But because the extension byte in MAVLink-2 can be zero-trimmed, a mission ACK and a "trimmed fence ACK" are byte-identical. AP itself always sends `mission_type` explicitly (`MissionItemProtocol::send_mission_ack` line 347-357) and `mavlink_msg_mission_ack_send` does NOT trim it when non-zero, so a fence ACK preserves the `1` byte. So the misroute risk is asymmetric and limited to the case where AP sends mission_type=0 and the `_fence_pending` is still set from an earlier orphaned transfer. Combined with Bug 2 (no disconnect reset) and Bug 3 (no timeout), this is reachable in practice.
- Fix: After fixing Bug 2 + Bug 3, also add an assertion-style log when ACK arrives and the matching pending is not set, so dangling pendings surface.

**Bug 7: Downloaded mission loses p3, p4, frame, current**

- Location: `backend/mavlink_handlers.py:393-431 handle_mission_item_int`
- Expected: Downloaded items carry full payload (p1-p4, frame, current, autocontinue, mission_type) per `MISSION_ITEM_INT` schema and per AP's `mission_cmd_to_mavlink_int` (AP_Mission.cpp:1584).
- Observed: Only p1, p2, lat, lon, alt, seq, cmd are stored in `_dl_items`. The frontend mission-downloaded summary that gets emitted by line 411-425 collapses items to a wp/loiter/spline/drop minimal schema; p3 (e.g. yaw direction, loiter radius) and p4 are silently dropped. Re-uploading a downloaded mission also forces `current=1 if seq==0 else 0` and `autocontinue=1`, throwing away whatever AP returned.
- Fix: Read p3/p4/frame/current/autocontinue from the wire (offsets 8, 12, 34, 35, 36) and stash them in `_dl_items` for accurate round-trip.

### MEDIUM

**Bug 8: `cmd_mission_clear` only clears `mission_type=0` (mission), not fence or rally**

- Location: `backend/commands/_mission.py:40-42`
- Expected: ArduPilot supports clearing each mission type independently via `MISSION_CLEAR_ALL` with `mission_type` set (per `mavlink_mission_clear_all_t`).
- Observed: Argus hardcodes the third byte to `0`. No way to clear fence or rally points from the GCS. Operators must manually delete fence via parameter `FENCE_TOTAL=0` or similar.
- Fix: Accept a `mission_type` arg (default 0) and pass it through.

**Bug 9: `cmd_mission_download` only supports `mission_type=0`**

- Location: `backend/commands/_mission.py:84-90`
- Expected: Same as bug 8 — protocol supports type=1 (fence) and type=2 (rally) downloads.
- Observed: Hardcoded `mission_type=0` byte in MISSION_REQUEST_LIST. `handle_mission_count` likewise assumes type=0 and never inspects the extension byte.
- Fix: Take mission_type as parameter; thread it through `_dl_pending` state and the request_int loop.

**Bug 10: Second simultaneous upload trashes the first's state without rejection**

- Location: `backend/commands/_mission.py:108-189 _upload_mission`
- Expected: Either serialize uploads (block until previous finishes) or reject ("upload in progress"). AP would itself cancel the previous upload (`MissionItemProtocol::cancel_upload`) but Argus's local state should track only one transfer at a time.
- Observed: No check — the second call overwrites `_mission_items` and re-sets `_mission_pending=True`. If AP's MISSION_REQUEST for the previous transfer is in flight, the response uses the new `_mission_items`, producing a Frankenstein upload.
- Fix: At top of `_upload_mission`, if `_mission_pending` is True (and within timeout), reject with `{'ok': False, 'error': 'mission upload already in progress'}`.

**Bug 11: NAV_LOITER_TURNS / NAV_LOITER_TIME ignore radius**

- Location: `backend/commands/_mission.py:118-130`
- Expected (per `AP_Mission.cpp:1093-1124`): loiter turns radius lives in `packet.param3` (signed: negative = CCW). loiter time radius also in p3. Currently Argus only sends `p1=loiter_param` and zero everywhere else.
- Observed: Radius defaults to 0 → AP uses the global default (`WP_LOITER_RAD`). User has no way to override per-waypoint.
- Fix: Accept `loiter_radius` from the wp dict and route to p3.

**Bug 12: `handle_mission_count` should validate `mission_type` matches the in-flight download**

- Location: `backend/mavlink_handlers.py:377-390`
- Expected: The download is per-type; receiving a MISSION_COUNT with a different `mission_type` than the one we requested means a foreign-initiated transfer. Should ignore.
- Observed: The extension byte at offset 4 is never read. Any MISSION_COUNT consumes the same `_dl_pending` slot.
- Fix: Read `mission_type` (after padding); ignore if it doesn't match a stored target mission_type.

### LOW

**Bug 13: `handle_mission_current` ignores `total`, `mission_state`, `mission_mode` fields**

- Location: `backend/mavlink_handlers.py:142-145`
- Cosmetic — these would enable a richer UI (showing mission state machine).

**Bug 14: GCS-side MISSION_ACK (after download) sends only 3 bytes, omitting `mission_type` extension**

- Location: `backend/mavlink_handlers.py:431`
- Observed: `struct.pack('<BBB', sysid, 1, 0)` — 3 bytes. Relies on AP zero-trimming the extension byte to interpret it as `mission_type=0` (mission). Functionally correct for mission downloads but does not generalise to fence/rally (would need byte 4 = 1 or 2). Combine with bug 9 fix.

**Bug 15: `_upload_mission` rejects valid lat=0 input**

- Location: `backend/commands/_mission.py:57`
- Observed: `if abs(lat) < 0.001 or ...`. Valid coordinates near the equator are rejected. Minor but worth noting if anyone flies in equatorial latitudes (Singapore at lat ~1.3 is OK; African coast near equator might trip it). AP itself accepts `lat=0` (`check_lat(0) = true` per `AP_Math/location.cpp:45-48`).
- Fix: Drop the absolute-value lower bound or guard only against the (0,0) pair which represents "uninitialised".

**Bug 16: No bound on `_dl_total` when receiving MISSION_COUNT**

- Location: `backend/mavlink_handlers.py:382-384`
- Observed: `m._dl_items = [None] * count`. A buggy/malicious FC sending `count=65535` triggers a 520KB allocation per transfer. Not catastrophic but defensive.
- Fix: Reject `count > 1000` (or similar) with an event log.

**Bug 17: Loop logic in `handle_mission_item_int` always requests seq+1 even on duplicate item**

- Location: `backend/mavlink_handlers.py:407-410`
- Observed: If AP retransmits an already-received item, Argus re-issues MISSION_REQUEST_INT for seq+1 (which we already received) or seq+2 (which we already requested). AP will gracefully re-send, but burns bandwidth.
- Fix: Track the next-expected seq separately from the last-received seq; ignore items where `seq < next_expected`.

**Bug 18: NAV_SPLINE_WAYPOINT (cmd 82) on ArduPlane will be rejected**

- Location: `backend/commands/_mission.py:125-127`
- Observed: AP_Mission.cpp:1153-1159 returns `MAV_MISSION_UNSUPPORTED` for cmd 82 on Plane. Argus doesn't pre-filter based on vehicle type.
- Fix: In `_upload_mission`, if `link.is_plane()` and `wp['type']=='spline'`, fall back to nav_cmd=16 (regular waypoint) or reject.

**Bug 19: Spline waypoint param semantics**

- Location: `backend/commands/_mission.py:127`
- Observed: `p1_val = float(wp.get('delay', 0))`. AP_Mission.cpp:1157 stores `cmd.p1 = packet.param1` as delay seconds. Fine — but uses `wp.get('delay')` whereas loiter uses `wp.get('loiter_param')` and waypoint uses `wp.get('delay')`. Field-naming inconsistency, minor.

**Bug 20: ArduPlane NAV_WAYPOINT acceptance radius can't be set**

- Location: `backend/commands/_mission.py:131-132` and `_helpers.py:50`
- Observed: For ArduPlane, `packet.param2`=acceptance radius, `packet.param3`=pass-by distance (AP_Mission.cpp:1071-1085). Argus always sends p2=0, p3=0. Plane will use its default `WP_RADIUS`. No per-waypoint override.
- Fix: For plane, allow per-wp `accept_radius` / `passby_distance` fields.

---

## Summary
- **Critical bugs**: 2 (rally upload protocol violation; disconnect not clearing fence/dl pending)
- **High-severity bugs**: 5 (no upload watchdog, ROI frame, ROI param1, concurrent uploads, lossy download)
- **Medium-severity bugs**: 5 (clear-all single type, download single type, no upload reject, loiter radius, mission_type unchecked on RX)
- **Low-severity bugs**: 8 (handler extension fields, ack length, equator lat, count bound, duplicate handling, plane-spline, naming, plane-accept radius)
