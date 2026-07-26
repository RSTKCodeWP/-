# MAVLink Parameter Protocol Audit

Audited Argus GCS parameter protocol against ArduPilot reference implementation.

Files audited:
- `backend/param_manager.py`
- `backend/commands/_setup.py`
- `backend/mavlink_handlers.py`
- `backend/pllink_proto.py`

ArduPilot reference:
- `libraries/GCS_MAVLink/GCS_Param.cpp`
- `libraries/GCS_MAVLink/GCS_MAVLink.cpp` (`mav_param_type`)
- `libraries/AP_Param/AP_Param.cpp` (`cast_to_float`, `set_float`)
- `modules/mavlink/message_definitions/v1.0/common.xml`

Wire definitions (from generated headers at `build/sitl/.../mavlink_msg_param_*.h`):

| Msg | ID | Length | CRC_EXTRA | Wire layout (LE) |
|-----|----|--------|-----------|------------------|
| PARAM_REQUEST_READ | 20 | 20 | 214 | int16 idx @0, u8 sys @2, u8 comp @3, char[16] id @4 |
| PARAM_REQUEST_LIST | 21 | 2 | 159 | u8 sys @0, u8 comp @1 |
| PARAM_VALUE | 22 | 25 | 220 | float val @0, u16 count @4, u16 index @6, char[16] id @8, u8 type @24 |
| PARAM_SET | 23 | 23 | 168 | float val @0, u8 sys @4, u8 comp @5, char[16] id @6, u8 type @22 |

MAV_PARAM_TYPE enum (1..10): UINT8=1, INT8=2, UINT16=3, INT16=4, UINT32=5, INT32=6, UINT64=7, INT64=8, REAL32=9, REAL64=10.

ArduPilot only ever sends INT8/INT16/INT32/REAL32 (`GCS_MAVLink.cpp:105-118` — "treat any others as float"). PX4 may send unsigned types.

---

## Section 1 — Field-level (offsets, encoding)

### 1.1 PARAM_VALUE decode — CORRECT
`param_manager.py:38-45` — `handle_param_value`:
- offset 0: `<f` → param_value (FLOAT) — matches wire
- offset 4: `<H` → param_count (uint16) — matches wire
- offset 6: `<H` → param_index (uint16) — matches wire
- offset 8..24: `param_id` (16 bytes, null-trimmed) — matches wire
- offset 24: `param_type` (uint8) — matches wire
- Min payload check `pl < 25` — correct (full length = 25, no extension fields).

All offsets line up with `mavlink_msg_param_value.h` field info table:
`{ "param_value", 0 }, { "param_count", 4 }, { "param_index", 6 }, { "param_id", 8 }, { "param_type", 24 }`.

### 1.2 PARAM_REQUEST_LIST encode — CORRECT
`param_manager.py:35-36`:
```python
payload = struct.pack('<BB', self._link.vehicle.sysid, 1)  # 2 bytes
self._link.send(bm(21, payload, self._link.sq, 159))
```
2 bytes total. CRC_EXTRA 159 matches. Target component hard-coded to 1 (autopilot).

### 1.3 PARAM_SET encode — CORRECT
`param_manager.py:77-83`:
```python
name_bytes = name.encode('ascii')[:16].ljust(16, b'\x00')
payload = (struct.pack('<f', value) +        # 4 bytes @0
           struct.pack('<BB', sysid, 1) +    # 2 bytes @4,5
           name_bytes +                      # 16 bytes @6..21
           struct.pack('<B', ptype))         # 1 byte @22
# total 23 bytes, CRC_EXTRA 168
```
Layout matches `mavlink_msg_param_set.h`. The `.encode('ascii')[:16].ljust(16, b'\x00')` correctly handles both <16 chars (null-padded) and exactly 16 chars (no terminator) — matches ArduPilot's `strncpy(key, packet.param_id, AP_MAX_NAME_SIZE); key[AP_MAX_NAME_SIZE] = 0;` (`GCS_Param.cpp:276-277`) where `AP_MAX_NAME_SIZE = 16`.

### 1.4 PARAM_REQUEST_READ — NOT IMPLEMENTED
`PARAM_REQUEST_READ` (msg 20, CRC 214) is only listed in the frontend CRC table (`src/lib/mavlink/crc.ts:34`) but is **never sent** by the backend. There is no way to request a single missing parameter — see Section 2.4 (gap detection).

### 1.5 param_id encoding — CORRECT
Both decode and encode follow the MAVLink convention "null-terminated if <16, no terminator if exactly 16". `bytes(p[8:24]).split(b'\x00')[0]` correctly stops at the first NUL. `.ljust(16, b'\x00')` zero-pads short names.

ASCII case-sensitivity: ArduPilot params are case-sensitive (e.g., `BATT_CAPACITY` vs `batt_capacity`). Argus does no normalization, and `set_param` looks up `self.params.get(name)` — if the user types lowercase, the lookup fails and falls back to `ptype = 9` (REAL32), which could corrupt an INT param's value (see Section 3.1).

### 1.6 Type punning (INT params) — CORRECT
ArduPilot `AP_Param::set_float` (`AP_Param.cpp:2225-2255`) casts the float back to int with `value + rounding_addition` (sign-aware 0.01 epsilon), then constrain-clamps to type bounds. Argus packs the user-supplied `float(value)` directly — this is the correct CAST (not bit-reinterpret) and matches AP's expectations.

`AP_Param::cast_to_float` (`AP_Param.cpp:1946-1960`) just casts the int to float — values like 5 arrive as `5.0`. Argus's float decode is correct.

---

## Section 2 — State machine (retry, race conditions, ordering)

### 2.1 No retry on PARAM_SET — PARTIAL (per MAVLink spec)
The MAVLink spec for PARAM_SET says: *"The receiving component should acknowledge the new parameter value by broadcasting a PARAM_VALUE message... If the sending GCS did not receive a PARAM_VALUE within its timeout time, it should re-send the PARAM_SET message."*

Argus `set_param` (`param_manager.py:74-84`) sends the PARAM_SET once and returns. There is no:
- Tracking of in-flight sets
- Timeout for the echo
- Retry on missing echo
- Detection of out-of-range rejections (ArduPilot logs `Param write denied (%s)` via STATUSTEXT but echoes back the OLD value — argus would silently update its cache to a wrong "applied" value if it trusted the echo path naively, but in practice the echo carries the old value so the cache becomes correct on echo; the problem is the user thinks they wrote a new value).

### 2.2 PARAM_SET race during initial download — PARTIAL
If the user clicks a slider during initial download, `set_param` is sent. AP processes it and emits a PARAM_VALUE echo with `param_count=N` and `param_index=65535` (`-1` cast to uint16 — see Section 3.2). This echo arrives mixed into the streaming params:

- Line 50-51 (`if name not in self.params: self.received_count += 1`): if the echoed param is NEW (not yet streamed), `received_count` is incremented prematurely. When AP later streams that param in sequence, `name in self.params` and `received_count` is NOT incremented again — count stays accurate by coincidence.
- Line 47-48 (`if self.total_count < 0: self.total_count = count`): if the echo arrives first, `total_count` is set from the echo's count — that's correct as AP uses the same `count_parameters()`.
- Line 64 (`if self.received_count >= self.total_count > 0`): the async echo's `param_index=65535` does NOT corrupt the index counter logic, but the SET echo may trigger early `params_complete` if it arrives near the end (because count is by-name, and the echo IS a unique name).

The `_messages` queue is shared, so frontend sees a `param_value` for `THR_MAX=5.0` mid-stream then again later when sequential streaming reaches it. The second value (sequential) overwrites the cached set value but matches the SET echo, so eventual state is consistent. **However the frontend's `param_value` count may exceed `total_count`** if any echo precedes the matching sequential stream (since `received` in the message is what's set at line 61, and may briefly read higher than expected).

### 2.3 `request_all` during in-progress fetch — BUG
`param_manager.py:27-36`: `request_all()` blindly resets `params`, `total_count`, `received_count`, sets `fetching = True`, and sends another PARAM_REQUEST_LIST.

ArduPilot's `handle_param_request_list` (`GCS_Param.cpp:210-227`) **always restarts** the parameter stream:
```cpp
_queued_parameter = AP_Param::first(...);
_queued_parameter_index = 0;
_queued_parameter_count = AP_Param::count_parameters();
```

So a second request will restart streaming from index 0. But the `_messages` queue is NOT cleared — old `param_value` messages still sit there for the websocket cursor to push. The frontend's `param_cursor` keeps advancing and sees a mix of stale and new messages.

More dangerously: between the time `request_all()` clears `self.params` and the new stream arrives, **any code reading `self.params` sees an empty dict**. A concurrent `set_param('X', ...)` between these two events would see `param = None` and fall back to `ptype = 9` (REAL32) — sending an INT param as REAL32 (see Section 3.1).

### 2.4 Gap detection — BUG (missing functionality)
ArduPilot streams params sequentially (`_queued_parameter_index++`) but with bandwidth caps (30% link bw, max 5 params/cycle without flow control). UDP/serial packet loss can drop a PARAM_VALUE; the receiver is responsible for detecting gaps via the `param_index` field and re-requesting with PARAM_REQUEST_READ.

`param_manager.py:38-72` never looks at `param_index` for ordering. It only uses `name not in self.params` for dedup. If params 50-52 are lost:
- `received_count` reaches `total_count - 3` and stays there.
- The check at line 64 never triggers → `fetching` stays True.
- After 60 sec, `check_timeout` (`param_manager.py:114-118`) emits `param_timeout`, sets `fetching = False`, leaves the dict permanently incomplete.
- **No retry, no PARAM_REQUEST_READ.**

ArduPilot params often number 700-1000. With even 0.1% loss rate, multiple params will be lost per fetch on every run. Recovery requires the user to click "Refresh" → restart the full download.

### 2.5 `params_complete` re-emission — BUG
`param_manager.py:64-72`: after initial fetch completes, ANY subsequent `param_value` whose name is not in `self.params` (e.g., a newly-created param after a FRAME_CLASS change, or any async echo for a never-streamed param) increments `received_count` past `total_count`, and `received_count >= total_count > 0` is STILL true, so a new `params_complete` event is emitted.

For an existing name (typical SET echo), `received_count` does not increment but condition still holds: `params_complete` is **re-emitted on every PARAM_SET echo after the initial fetch finishes**. The frontend likely just no-ops on duplicate complete events, but it spams `_messages` with stale completion markers and triggers any UI flow tied to "fetch done".

### 2.6 `check_timeout` once-only emission — PARTIAL
`param_manager.py:114-118`: the timeout check correctly fires once because it gates on `self.fetching` and unconditionally sets `fetching = False`. But `received_count` and `total_count` are left as-is — the next state poll (`get_status`) reports `param_fetching: False, param_count: N, param_total: M` with N<M. The frontend has no UI signal that the partial state is stale-vs-still-fetching, except by inspecting count<total.

### 2.7 Component ID hard-coded — PARTIAL
All four messages (REQUEST_LIST, SET) hard-code `target_component = 1` (autopilot). ArduPilot uses component 1 for the main FC, so this is correct in practice. But camera/gimbal/companion components also have params, and you can never reach them via this code path.

`bm()` defaults source `sysid=255, compid=1` — typical GCS values. ArduPilot's `mavlink_msg_param_set_decode` doesn't validate `target_system` against its own SYSID strictly enough on some configs (it ignores msgs not addressed to it), but argus uses `self._link.vehicle.sysid` correctly.

---

## Section 3 — Edge cases (type conversion, large param counts)

### 3.1 Unknown param uses REAL32 fallback — BUG
`param_manager.py:74-76`:
```python
param = self.params.get(name)
ptype = param['type'] if param else 9
```

If the param is unknown (e.g., case-mismatch, or set BEFORE the download completes, or set immediately after `request_all` cleared the dict), `ptype` defaults to 9 (REAL32). When AP receives PARAM_SET with type=REAL32 for an INT8 param like `RC1_REVERSED`:

ArduPilot's `handle_param_set` (`GCS_Param.cpp:267-320`) uses the param's REGISTERED type, not the wire `param_type` — it finds the param via `AP_Param::find(key, &var_type, ...)` and calls `vp->set_float(packet.param_value, var_type)` with the REGISTERED `var_type`. So the wire `param_type` is **ignored** by AP.

Looking at AP source more carefully (`GCS_Param.cpp:267-296`): the wire `packet.param_type` is decoded but never used — AP uses its own `var_type` from `AP_Param::find`. **So this bug is benign for ArduPilot** but may break PX4 or other autopilots that respect wire type. Worth noting as compatibility risk, not data corruption.

However the user-visible damage: argus's `params` cache shows `ptype` for the row, used by UI to render INT vs FLOAT. A param set before the cache is populated would render with `ptype=9` (FLOAT) and probably display "1.0000" for an INT8 of 1.

### 3.2 Async PARAM_VALUE with index=65535 — PARTIAL
ArduPilot's `send_parameter_value` (`GCS_Param.cpp:322-334`) sends `-1` as the param_index for async replies (PARAM_SET echo, runtime updates). The XML declares the field as **uint16_t** so `-1` is sent on the wire as `0xFFFF` = 65535.

`param_manager.py:43`: `index = struct.unpack_from('<H', p, 6)[0]` reads it as unsigned → index=65535. The code stores `'index': 65535` in `self.params[name]['index']`. The frontend may use this for sorting (`paramState.list` could be sorted by index) and 65535 sorts to the end. Not catastrophic but the cached index is wrong for async-updated params.

The condition at line 64 (`received_count >= total_count`) is unaffected because index is not used there.

### 3.3 `param_count > 65535` — STRUCTURAL LIMITATION (not a bug)
The wire field is `uint16` (max 65535). ArduPilot returns `count_parameters()` which is `uint16_t` (`AP_Param.cpp:2670`). Argus uses `<H` unpack. If a vehicle ever exceeded 65535 params, the count would wrap. Current ArduPilot max is ~1000-1500, well within range. Not a real issue at current scale.

### 3.4 NaN/Inf in PARAM_SET — PARTIAL
ArduPilot explicitly rejects NaN/Inf:
```cpp
if (vp == nullptr || isnan(packet.param_value) || isinf(packet.param_value)) {
    return;  // GCS_Param.cpp:282-284
}
```
Argus does not check. `float('inf')` or `float('nan')` would be silently sent. The user-visible effect: no echo arrives, the cache stays as it was. The MAVLink spec says GCS should retry on missing echo — argus has no retry, so the set silently disappears.

`commands/_setup.py:81`: `value = float(data.get('value', 0))` — `float('nan')` and `float('inf')` are valid Python floats, no validation here either.

### 3.5 PARAM_SET out-of-range / frozen param — PARTIAL
ArduPilot:
- If param is read-only or has `AP_PARAM_FLAG_NO_SHELL_SET` etc., `allow_set_via_mavlink` returns false. AP sends STATUSTEXT `"Param write denied (XXX)"` AND echoes the OLD value back via PARAM_VALUE (`GCS_Param.cpp:288-293`).
- If param value is out of bounds, AP `set_float` `constrain_float`s to type bounds and saves the clamped value. AP does NOT explicitly echo for this case — saves happen via `save(force_save)` which doesn't trigger an automatic echo unless something else streams it.

Wait — re-reading: `AP_Param::set_float` calls `((AP_Int8 *)this)->set(v)` etc., but `set()` (in AP_ParamT.h) doesn't trigger PARAM_VALUE emission. The echo only happens if the read-only path is hit (`GCS_Param.cpp:288-293`). So for a normal allowed set, **AP does NOT echo** unless the value is logged via `Write_Parameter` and consumed elsewhere... actually it doesn't echo at all in the standard path.

Wait, let me re-check this. The MAVLink spec ("The receiving component should acknowledge the new parameter value by broadcasting a PARAM_VALUE message") implies an echo should happen, but I don't see it in `handle_param_set` for the success path. Let me re-read:

Looking at `GCS_Param.cpp:296-320` — after `vp->set_float(...)` and `vp->save(force_save)`, there's no `send_parameter_value` call. The logging via `logger->Write_Parameter` writes to dataflash, not to MAVLink.

**However**, ArduPilot has an `AP_Param::notify()` mechanism that fires whenever a param's `set_and_save()` is called with a changed value. This triggers `GCS::send_parameter_value` (`GCS_Param.cpp:339-359`) broadcasting the new value to all active channels. So for a SUCCESSFUL set with a value that's actually changed, AP DOES echo via the notify path.

For a no-op set (value matches current), `set_and_save_ifchanged` short-circuits and no notify fires → no echo. Argus would wait forever for an echo it'll never get. But argus has no waiting/retry logic anyway, so the user just sees "no confirmation arrived".

### 3.6 `time.sleep` in `load_from_file` blocks asyncio — BUG
`param_manager.py:97-112`: `load_from_file` iterates the JSON file and for each changed param calls `set_param` followed by `time.sleep(cfg.PARAM_LOAD_SPACING)` (default 0.02s).

This function is invoked from `commands.execute` (`commands/__init__.py:122-...`), which is called inline from the websocket receive coroutine (`ws_manager.py:135`). `time.sleep` is a **synchronous** blocking call inside an async handler — it blocks the entire asyncio event loop. With 1000 changed params:
- 1000 × 0.02s = 20 seconds of frozen UI for ALL connected clients
- No heartbeat sends during freeze (could trigger LINK_LOST_TIMEOUT)
- No telemetry pushes
- New WebSocket clients can't connect

Should use `asyncio.sleep` after refactoring `cmd_param_load` to be async, or push to a worker thread.

### 3.7 `params_dir` prefix check is bypassable — BUG (security)
`commands/_setup.py:98`: `if not str(p).startswith(str(params_dir))`.

If `params_dir = /argus/params` (no trailing slash) and a user-supplied path resolves to `/argus/params_evil/foo.json`, the check passes (string prefix matches). Could be exploited if there's any user-controlled directory creation near the params dir, or if the deployment has sibling dirs like `/argus/params-backup` and the user wants to load from them.

Use `p.is_relative_to(params_dir)` (Python 3.9+) or compare with `str(params_dir) + os.sep` prefix.

### 3.8 `save_to_file` loses param TYPE information — PARTIAL
`param_manager.py:91`: `data = {name: p['value'] for name, p in sorted(self.params.items())}`. Only saves name→value, drops `type` and `index`. When loaded back, `set_param` looks up `self.params[name]['type']` from the current vehicle's cache. This is fine when re-loading the same firmware/vehicle, but loading a saved file onto a different vehicle (with different param type metadata) would use wrong types — though as Section 3.1 notes, AP ignores wire type anyway.

The saved JSON only stores raw `value` (float). For INT params with large values close to float32 precision limits (~16M for 32-bit integer precision), a round-trip could lose precision. ArduPilot's `BATT_CAPACITY` (INT32, mAh, can be 50000+) is fine; LOG_BITMASK or similar bitmasks fit in 24 mantissa bits. Probably not a real issue.

### 3.9 `_messages` cap only fires at completion — PARTIAL
`param_manager.py:71-72`: `if len(self._messages) > 2000: self._messages = self._messages[-1000:]` is inside the `if self.received_count >= self.total_count > 0:` branch. If `total_count` is never reached (gap-loss scenario, Section 2.4), `_messages` grows unbounded for the whole 60s timeout window plus all subsequent SET events forever after.

For a 1500-param fleet refresh, `_messages` reaches ~1500 entries. With async PARAM_VALUE updates over a long session and multiple `request_all` calls without completion, `_messages` could grow to tens of thousands of entries, slowing down the `param_cursor` slicing on every push tick.

### 3.10 No protection against very long param IDs — PARTIAL
`param_manager.py:78`: `name.encode('ascii')[:16]` silently truncates. If a frontend sends `'BATT_MONITOR_ENABLE'` (19 chars), it becomes `BATT_MONITOR_ENA` on the wire. AP cannot find this — falls through `vp == nullptr` and silently returns. User sees no error.

Should validate length ≤16 on input and reject explicitly.

---

## Section 4 — Concrete bug list with file:line citations

### CRITICAL

1. **No gap detection / retry for missing PARAM_VALUE**
   `backend/param_manager.py:38-72`
   AP_Param streams sequentially and trusts the GCS to fill gaps via PARAM_REQUEST_READ. Argus never sends msg 20, only uses by-name dedup. Any packet loss leaves `fetching=True` forever (until the 60s `check_timeout`). Then the local cache is permanently missing N params. For a 1000-param fleet with realistic 0.5% UDP loss, ~5 params are missing every refresh.

2. **`time.sleep` inside async handler freezes the entire backend**
   `backend/param_manager.py:110` — `time.sleep(cfg.PARAM_LOAD_SPACING)`
   Called from `commands/_setup.py:102` (`cmd_param_load`) which runs inline in `ws_manager.py:135` (async receive_loop). Each `time.sleep(0.02)` blocks asyncio. 100 modified params = 2s frozen UI; 1000 = 20s, will trip LINK_LOST_TIMEOUT (5s) and disconnect every WebSocket client.

3. **Path-prefix check bypassable (security)**
   `backend/commands/_setup.py:98` — `if not str(p).startswith(str(params_dir))`
   Resolved path `/argus/params_evil/x.json` passes the check when `params_dir = /argus/params`. Replace with `p.is_relative_to(params_dir)` (Python ≥3.9) or compare with `str(params_dir) + os.sep`.

### HIGH

4. **`params_complete` re-emitted on every async PARAM_VALUE after initial fetch**
   `backend/param_manager.py:64-72`
   Condition `received_count >= total_count > 0` remains true forever after first completion. Every SET echo or runtime param update enters the branch and pushes another `params_complete` into `_messages`. Frontend sees spurious "fetch done" events.

5. **`set_param` race when called before fetch completes / between `request_all` and first PARAM_VALUE**
   `backend/param_manager.py:74-76`
   `self.params.get(name)` returns None during the window when `request_all` cleared the dict (line 28) but no PARAM_VALUE has yet arrived. `ptype` defaults to 9 (REAL32), sent on wire. AP ignores wire type (so the param value is set correctly), but the UI's cached `ptype` is wrong until the param streams back in. Also, an INT param shown briefly as REAL32 may display "5.0000" instead of "5".

6. **No NaN/Inf rejection on outgoing PARAM_SET**
   `backend/commands/_setup.py:81` (`value = float(data.get('value', 0))`)
   `backend/param_manager.py:74-84` (set_param)
   AP rejects NaN/Inf silently (`GCS_Param.cpp:282`). No echo arrives. Argus has no echo-timeout/retry logic, so the user's set vanishes with no error. Either validate at frontend boundary (`cmd_param_set`) or at protocol layer.

7. **`_messages` unbounded growth on incomplete fetch**
   `backend/param_manager.py:71-72`
   The 2000→1000 cap is only inside the `received_count >= total_count` branch. If the fetch never completes (gap loss / vehicle disconnect mid-fetch / many `request_all` retries), `_messages` grows without bound, plus all subsequent SET events.

8. **`request_all` doesn't clear `_messages` queue**
   `backend/param_manager.py:27-36`
   Calling `request_all` mid-fetch leaves stale `param_value` messages in `_messages`. The frontend's `param_cursor` advances through them as if they were part of the new fetch, leading to confusing UI state (parameter counts may briefly exceed total).

### MEDIUM

9. **No PARAM_SET echo timeout / retry**
   `backend/param_manager.py:74-84` — `set_param` is fire-and-forget.
   MAVLink spec says GCS should retry if echo doesn't arrive within timeout. If the SET is rejected (out of range, frozen param) AP either echoes the old value (read-only path) or doesn't echo at all (no-op set). User has no feedback on whether the set actually took effect; they only see the local cache update (via the SET echo if any). Without per-set tracking, a silent failure is indistinguishable from success.

10. **Async PARAM_VALUE stores index=65535**
    `backend/param_manager.py:43,54` — `index = struct.unpack_from('<H', p, 6)[0]`
    AP sends `-1` for async replies (`GCS_Param.cpp:333`), wire is uint16 → 65535. Argus stores `'index': 65535` in cache. If the frontend ever sorts/indexes by this field, async-updated params sort to the end. Should clamp to existing value if name is already in cache, or detect 65535 and don't overwrite.

11. **`request_all` not idempotent w.r.t. concurrent state**
    `backend/param_manager.py:27-32`
    Clears `self.params` synchronously. If a websocket push tick happens to read `params` between clear and first PARAM_VALUE arrival, the frontend may see an empty param table for several seconds. Worse, a concurrent `set_param` finds empty dict and falls back to REAL32 (see bug #5).

12. **No length validation on outgoing param name**
    `backend/param_manager.py:78` — silently truncates `name[:16]`.
    AP cannot find truncated name, returns silently. User sees no error.

13. **`save_to_file` strips type info**
    `backend/param_manager.py:91` — saves only `{name: value}`.
    Reloading uses current cache's type; loading onto a different vehicle could write wrong-type values (though AP ignores wire type, so cosmetic only).

### LOW / INFORMATIONAL

14. **Hard-coded target_component=1**
    `backend/param_manager.py:35, 80`
    Hard-coded to 1 (autopilot). Cannot reach camera/gimbal/companion params via this channel. Not a bug for current GCS purpose but limits future extensibility.

15. **PARAM_REQUEST_READ never sent**
    `backend/param_manager.py` (entire file) — msg 20 is in `src/lib/mavlink/crc.ts:34` table but never used.
    Without it, recovery from gap loss is impossible; the only fix is a full re-fetch (`request_all`). Implementing PARAM_REQUEST_READ would also enable single-param refresh after a set fails to echo.

16. **Wire-vs-spec param_index sign mismatch**
    XML field type for `param_index` is `uint16_t` but ArduPilot semantics treat -1 as "async / not indexed". Argus reads as uint16 → 65535. Matches AP's wire encoding, but documenting this in code would prevent confusion (e.g., a comment near `param_manager.py:43`).

17. **`PARAM_LOAD_SPACING` is unconfigurable per-link**
    `backend/config.py:54` — 20ms is too slow for fast links, too fast for some serial radios. Could be derived from link bandwidth or made adaptive.

---

## Summary

Audit complete. Found 8 critical/high bugs, 9 partial issues. /tmp/audit_param.md

Critical/High:
1. No gap detection / retry — silent param loss on UDP/serial
2. `time.sleep` blocks asyncio — freezes UI during bulk load
3. Path-prefix check bypassable — security
4. `params_complete` re-emitted forever — frontend confusion
5. `set_param` race with empty cache → wrong ptype
6. No NaN/Inf rejection — silent failures
7. `_messages` unbounded on incomplete fetch
8. `request_all` doesn't clear `_messages`

Field-level wire format (offsets, lengths, CRC_EXTRA) is **correct** for all four messages (msg 20/21/22/23). Float type punning for INT params is **correct** (cast, not bit-reinterpret). The bugs are concentrated in state-machine/edge-case handling, not in protocol parsing.
