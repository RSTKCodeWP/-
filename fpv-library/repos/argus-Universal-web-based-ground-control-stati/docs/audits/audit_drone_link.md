# Audit: backend/drone_link.py

Scope: connection management, main loop, heartbeat, stream-request, frame parsing,
state-lock discipline, event ring buffer, inspector data.

Severity scale:
- **CRITICAL**: correctness break, data loss/leak, or AP-side fail-safe risk.
- **WARNING**: latent bug, UX regression, or resource growth that hasn't yet bitten.
- **NOTE**: minor smell / suggestion / inconsistency, no immediate harm.

---

## CRITICAL

### C1. In-place reconnect (in `_loop`) does not reset session state — state leaks across reconnect
**File**: `backend/drone_link.py:466-486`
**Description**: When `LINK_LOST_TIMEOUT` triggers the in-loop reconnect, only `_buf` and
`_protocol` are reset. Compare with `disconnect()` (line 191-225) which also clears
`vehicle.vtype_raw`, `vehicle.force_plane`, `attitude._prev_pos`,
`mission._mission_pending/_fence_pending/_rally_pending/_dl_pending/_dl_start_time`,
`log_dl._log_download_*`, `_prearm_messages`.
Result on in-loop reconnect: half-finished mission/fence/rally uploads remain "pending",
a partial log-download buffer (up to ~100 MB) is retained, and PreArm dedup state is
stale. After the recent "disconnect cleanup" patch the user-driven path is OK, but the
silent in-loop reconnect path still leaks.
**Fix**: extract the disconnect-state-reset block into a helper (e.g.
`_reset_session_state()`) and call it from both `disconnect()` and the in-loop
reconnect branch.

### C2. Stream re-request never fires after in-loop reconnect
**File**: `backend/drone_link.py:464,477` (in-loop reconnect leaves `frame_count` untouched)
**Description**: The "request streams once on initial connect" gate is
`if not self.connected and self.frame_count < 3` (line 464). The in-loop reconnect
clears `_buf` and `_protocol` but does NOT reset `frame_count` or `last_frame_time`.
After a TCP/UDP disconnect+reopen, AP sees a brand-new client and (for UDP) has lost
any previously-set message intervals tied to the source endpoint, yet `frame_count`
remains in the thousands so `request_streams()` is never re-issued. UI stops updating
ATTITUDE/POSITION/etc. until the user manually triggers something.
**Fix**: in the reconnect branch set `self.frame_count = 0` and `self.last_frame_time = 0.0`
inside the `_state_lock` block. (Use the same helper as C1.)

### C3. Race between user `disconnect()/reconnect()` and the loop's in-place reconnect
**File**: `backend/drone_link.py:191-226, 227-251, 472-486`
**Description**: `disconnect()` and `reconnect()` use `_thread.join(timeout=3)` to wait
for the loop to exit; the loop may itself be inside `time.sleep(cfg.RECONNECT_DELAY)`
(default 3.0 s) on line 485. The join can therefore time out, after which the calling
thread closes `_ser` and sets `_ser = None` while the orphan loop is still alive.
When the loop wakes, it either:
  (a) opens a new socket on line 480 — overwriting the `None` set by disconnect, so
      the freshly-opened port is **leaked** (never closed) when the loop finally exits;
  (b) hits `self._ser.read(1024)` on a `None` reference → `AttributeError` (not caught
      — only `OSError` is caught on line 494), terminating the loop with an uncaught
      exception in the daemon thread.
**Fix**: either (i) set `RECONNECT_DELAY < join timeout` and use a `threading.Event`
that the loop checks instead of `time.sleep`, or (ii) catch `AttributeError` next to
`OSError` on line 494 and also raise the join timeout above `RECONNECT_DELAY`. Prefer
the Event-based approach.

### C4. `_unknown_msg_ids` dict grows without bound
**File**: `backend/drone_link.py:112, 438`
**Description**: Each unknown MAVLink msg id encountered (legitimate-but-unregistered
or false-sync from noise) gets a key in `self._unknown_msg_ids`. The mid is computed
from `payload[7:10]` (24-bit), and on a bursty/noisy serial line the false-sync case
generates effectively-random mids. Nothing reads or caps this dict — pure memory
leak. The "fail-loud throttle" comment suggests it was once consumed, but the consumer
is gone.
**Fix**: either cap the dict size (e.g. discard new keys once `len > 256`) and reset
on (re)connect, or remove the counter entirely if no consumer exists.

### C5. Event ring-buffer trim corrupts ws_manager cursor → duplicated or dropped events
**File**: `backend/drone_link.py:138-141`, `backend/ws_manager.py:144,168-178`
**Description**: `add_event()` appends to `self.events`; when length crosses 100 the
list is replaced with the last 50 entries. The `_push_loop` cursor (`event_cursor`)
is an absolute index into the pre-trim list. After the trim, two failure modes:
  (a) cursor was caught up (e.g. == 100). After trim, len == 50, cursor (100) > len,
      ws_manager resets cursor to 0 and re-sends all 50 entries — the **client receives
      duplicate events**.
  (b) cursor was at 50 (client had seen the first half, which now got dropped). After
      trim, len == 50 and cursor (50) is NOT > len, so neither branch fires; the
      "new" events that were originally events[50..99] (now at index 0..49) are
      silently **skipped**.
The calibration UI already uses timestamp-filter (CalibrationPanel.svelte:68) to avoid
this, but the general EventLog consumer goes through `event_cursor` and is exposed.
**Fix**: keep events as a deque with a stable monotonic id, or change the trim policy
so that `len(events)` is **never less than `event_cursor`** for any active client.
Simplest patch: replace ring-buffer with `collections.deque(maxlen=200)` and track a
monotonic "events ever produced" counter per client; ws_manager indexes by that
counter, not by the live list length.

### C6. `_msg_stats` mutated from loop thread, read from asyncio thread, no lock
**File**: `backend/drone_link.py:524-537 (read), 549-559 (write under _state_lock)`
**Description**: `_process` writes to `_msg_stats` while holding `_state_lock`
(line 546). But `get_inspector_data()` (line 524) iterates `self._msg_stats.items()`,
reads/replaces each entry's `times` list, **without acquiring `_state_lock`**, and is
called from the asyncio push loop (ws_manager line 207). Concurrent
`st['times'].append(now)` (writer) with `times = [t for t in times ...]` followed by
`st['times'] = times` (reader) → either lost appends or `RuntimeError: dictionary
changed size during iteration` if a new mid is added mid-iter.
**Fix**: wrap the `for mid, st in sorted(self._msg_stats.items()):` body in
`with self._state_lock:` (the RLock makes this cheap; ws_manager already does similar
on line 163).

---

## WARNING

### W1. Infinite-spin reconnect with no backoff or attempt-cap
**File**: `backend/drone_link.py:470-486`
**Description**: When `_reconnect_enabled=True` and the port is permanently bad
(unplugged USB, blocked port), the loop sleeps `RECONNECT_DELAY` (3 s) and tries again
forever. There is no exponential backoff, no max-attempts, no surface to the UI other
than the `reconnect_fail` event spam (which will themselves trigger event ring
trim → C5 duplicates). The user has no way to abort other than disconnect from UI.
**Fix**: introduce attempt counter + exponential backoff (cap at e.g. 30 s), and
either auto-disable reconnect after N consecutive failures or expose a UI signal.

### W2. param_mgr state survives disconnect with stale `_fetch_start`
**File**: `backend/drone_link.py:191-225` (no `param_mgr` reset) + `param_manager.py:166-192`
**Description**: If a PARAM_REQUEST_LIST is in flight when disconnect happens,
`param_mgr.fetching` stays True and `_fetch_start` retains the old timestamp. On the
next connect the loop runs `param_mgr.check_timeout()` immediately; since
`now - _fetch_start` already exceeds `PARAM_FETCH_TIMEOUT`, a bogus `param_timeout`
event is emitted on the new session.
**Fix**: in disconnect(), call something like
```python
self.param_mgr.fetching = False
self.param_mgr._messages.clear()
self.param_mgr._fetch_start = 0.0
```
or add a `ParamManager.reset()` method and call it from disconnect.

### W3. `_parse_errors` counter doesn't actually track parse errors
**File**: `backend/drone_link.py:320, 493, 505`
**Description**: The UI shows `parse_errors` (state.py output, `_build_state` line
320). The counter is incremented in only two places:
  1. line 493 — when the receive buffer overflows 64 KB (a backpressure signal, not a
     parse error).
  2. line 505 — when `_process` raises `struct.error/ValueError/IndexError` (a
     downstream-handler error, after parse already succeeded).
True parse errors (CRC mismatch on line 442, unknown msg id on line 438-439) are
silently dropped without incrementing the counter. End-user-visible "parse_errors"
therefore misrepresents the link quality.
**Fix**: increment `_parse_errors` on the CRC-mismatch path (line 441-442) and
optionally on unknown-mid (line 438-439). Buffer-overflow should be its own counter
(`_buffer_overflows` or similar), since it's a different failure mode.

### W4. Heartbeat rate is 2 Hz but configured via `HEARTBEAT_INTERVAL=0.5` — fine for AP, doc mismatch with prompt
**File**: `backend/config.py:26`, `backend/drone_link.py:461-463`
**Description**: AP accepts heartbeats at any rate ≥ ~0.5 Hz; 2 Hz is well above the
fail-safe threshold and harmless. **No code bug here**, but note: the audit prompt's
"typically 1 Hz" assumption is conservative — 2 Hz is wasteful on serial UART but fine.
The heartbeat continues to send during in-loop reconnect (good — line 461 runs before
the link-lost check).
**Fix**: optional — change `HEARTBEAT_INTERVAL` to 1.0 to halve heartbeat bandwidth.
No correctness issue.

### W5. Heartbeats stall during long synchronous handler/`time.sleep`
**File**: `backend/drone_link.py:457-518`, also `commands/_helpers.py:93-99`,
`backend/param_manager.py:162`
**Description**: The loop is single-threaded: frame parsing, dispatch, heartbeat
send, and stream-request all run on the same thread. `request_streams` does
`time.sleep(STREAM_REQUEST_SPACING)` per stream (~9 × 10 ms = 90 ms) — fine.
`ParamManager.load_from_file` does `time.sleep(PARAM_LOAD_SPACING)` per changed param
(20 ms each). For a 200-param load (rare but possible) that's 4 s of blocked main
loop, during which **no heartbeats are emitted and no frames are read** → AP's
`SR_*_GCS_FAILSAFE` could fire if the link param `FS_GCS_ENABLE=1`.
Worse, `param_load` is invoked from `commands/_setup.py:cmd_param_load` which is
called from the asyncio thread, NOT the loop thread — so heartbeats are unaffected.
Confirm: yes, `cmd_param_load` runs sync inside asyncio task; loop thread continues.
So this only matters if `load_from_file` is ever called from the loop thread. It is
not today, but a future refactor could regress this.
**Fix**: add a comment in `param_manager.load_from_file` that it must not be called
from the link loop thread, OR convert the per-param spacing into a queue serviced by
the loop.

### W6. Stream-request rates are slower than typical GCS (4 Hz ATTITUDE vs 10 Hz)
**File**: `backend/commands/_helpers.py:86-99`
**Description**: ATTITUDE (msg 30) and GLOBAL_POSITION_INT (msg 33) are requested at
250 000 µs = 4 Hz. Mission Planner / QGC typically use 10 Hz for ATTITUDE so that the
attitude indicator looks smooth in turbulence. The UI ws_push rate is
`WS_PUSH_INTERVAL_CONNECTED=0.2` s = 5 Hz, so 10 Hz upstream would feed it nicely; 4 Hz
upstream means the UI sometimes redraws the same attitude twice. Not a correctness
bug but a polish issue.
**Fix**: change `(30, 250000)` to `(30, 100000)` and `(33, 200000)` for parity with
ws push rate.

### W7. Auto-protocol detection is one-shot, no recovery from misdetection
**File**: `backend/drone_link.py:445-455`
**Description**: On first byte, if `_buf[0..1] != 0x50,0x4C`, protocol locks to
`standard` and never re-detects. If the link is PL-Link but the first incoming bytes
are noise/junk, the protocol detection latches wrong and all subsequent frames are
parsed by `_parse_mavlink_frame`, which will reject everything (CRC mismatch). No
auto-recovery; user must disconnect+reconnect.
**Fix**: keep `_protocol = 'auto'` until the first **valid** frame (i.e. one that
returned a non-None payload), not just the first non-empty buffer.

### W8. `vehicle.vtype_raw` left at zero during in-loop reconnect, but `_get_vehicle_info` defaults to copter
**File**: `backend/drone_link.py:271-274` (fall-through) and the in-loop reconnect path
**Description**: After in-loop reconnect, `vtype_raw` is whatever it was before
(could be 1=plane). UI keeps showing "plane" mode list even though FC may have rebooted
as a different vehicle type. Combined with C1 (state leak), `force_plane` may also
linger. Minor — the next HEARTBEAT corrects it within 0.5 s.
**Fix**: same as C1, reset `vtype_raw` and `force_plane` on in-loop reconnect.

### W9. `_check_mission_dl_timeout` only runs at MAIN_LOOP_SLEEP cadence (50 Hz max) — fine, but check the import
**File**: `backend/drone_link.py:520-522`
**Description**: `_check_mission_dl_timeout` does a deferred `from .commands._mission
import check_mission_dl_timeout` on every loop iteration (~50 Hz). The import is
cached after first call, but the module-attribute lookup runs each time. Trivial CPU.
**Fix**: hoist the import to module-level (move the `from .commands._mission import …`
to the top of drone_link.py) or cache the function reference on the class.

---

## NOTE

### N1. `system_status=0 (MAV_STATE_UNINIT)` in GCS heartbeat
**File**: `backend/commands/_helpers.py:81-83`
**Description**: The heartbeat sends `system_status=0` (UNINIT). Mission Planner and
QGroundControl conventionally send `MAV_STATE_ACTIVE=4`. AP doesn't enforce, but
some companion-computer code paths check `MAV_STATE_ACTIVE` on the GCS heartbeat.
**Fix**: change the 5th field in `struct.pack('<IBBBBB', 0, 6, 8, 0, 0, 3)` from
`0` to `4`. Validated against `minimal.xml`: 4 = `MAV_STATE_ACTIVE`.

### N2. `bytes(buf[1:N])` is a no-op copy on a bytes object
**File**: `backend/drone_link.py:425`
**Description**: `self._buf` is already `bytes`; `bytes(buf[...])` performs an extra
copy. Cosmetic; `buf[1:...]` is equivalent.
**Fix**: drop the `bytes(...)` wrapper.

### N3. `_msg_stats` keys accumulate entries with empty `times` lists forever
**File**: `backend/drone_link.py:108, 549-559`
**Description**: Once a mid is seen, its entry in `_msg_stats` is never removed even
if it stops being seen. For e.g. one-shot AUTOPILOT_VERSION (148), the entry stays
forever with an empty `times` list. Very small leak; bounded by ~40 distinct mids
(only mids in `_CRC_EXTRA` pass CRC validation).
**Fix**: in `get_inspector_data`, drop entries whose `times` is empty AND `count`
hasn't changed in N seconds; or just reset `_msg_stats = {}` on disconnect.

### N4. `_parse_mavlink_frame` advances 1 byte after unknown-mid frame
**File**: `backend/drone_link.py:439`
**Description**: On unknown mid, advance by 1 byte (looking for next 0xFD). If the
unknown-mid was a real, intact MAVLink-2 frame, the next 0xFD is most likely inside
its payload (false sync), causing further parse errors before we find the next real
frame. Wasted CPU, no correctness issue (CRC eventually rejects garbage).
**Fix**: still advance by `frame_len` (the full unknown frame) so we resync to the
next likely boundary.

### N5. Param manager `_received_indices` never resets on disconnect
**File**: `backend/drone_link.py:191-225`, `backend/param_manager.py:35`
**Description**: Similar to W2 — `_received_indices` is reset only in `request_all()`
when a new fetch starts. If user reconnects to a DIFFERENT vehicle with a different
param set, the leftover indices from the first vehicle could feed into a subsequent
fetch's gap-fill logic for the first ~few hundred ms (until `request_all` actually
fires).
**Fix**: tied to W2 fix — reset param_mgr on disconnect.

### N6. `_console_buf` not cleared on disconnect
**File**: `backend/drone_link.py:191-225`, `mavlink_handlers.py:561-570`
**Description**: `_console_buf` retains data across disconnect. If the user opens the
console after reconnect they'll see leftover output from the previous vehicle.
**Fix**: clear `_console_buf` in disconnect() and in_loop_reconnect.

---

## Summary

- **CRITICAL**: 6 (state leak on in-loop reconnect, missing stream re-request,
  disconnect/loop race, unbounded `_unknown_msg_ids`, event cursor corruption on trim,
  `_msg_stats` lock-violation race).
- **WARNING**: 9 (no backoff/cap on reconnect, stale param_mgr after disconnect,
  misleading `parse_errors` counter, heartbeat rate doc, sync handler blocks heartbeat
  in worst-case, low stream rates, one-shot protocol detection, stale vtype,
  per-iter import).
- **NOTE**: 6 (system_status, bytes copy, msg_stats key residue, advance-1 strategy,
  param indices reset, console buf reset).

The single most impactful fix is **C1 + C2** combined: refactor the in-loop reconnect
path to share the disconnect state-reset (including `frame_count` + `last_frame_time`),
which simultaneously fixes the streams-not-re-requested bug. **C5 (events cursor)**
and **C6 (msg_stats race)** are the second-highest priority.
