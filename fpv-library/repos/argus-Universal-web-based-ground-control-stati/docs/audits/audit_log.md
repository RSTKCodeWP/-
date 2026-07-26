# Argus MAVLink Log Download Audit

Reference: ArduPilot 4.x AP_Logger_MAVLinkLogTransfer.cpp + GCS_Common.cpp + common.xml.

## Summary of correctness

| Item | Status |
|---|---|
| msg 117 wire layout | OK (`<HHBB` = start, end, target_system, target_component) |
| msg 119 wire layout | OK (`<IIHBB` = ofs, count, id, target_system, target_component) |
| msg 122 wire layout | OK (`<BB` = target_system, target_component) |
| msg 118 RX layout | OK (`<IIHHH` = time_utc, size, id, num_logs, last_log_num) |
| msg 120 RX layout | OK (`<IHB` = ofs, id, count, data follows at offset 7) |
| CRC extras 117/119/122 | OK (128/116/203 verified via pymavlink) |
| Min payload checks | OK (handle_log_entry pl>=14; handle_log_data pl>=7) |

The wire encoding is **correct**. Bugs are concentrated in the application-layer state machine in `handle_log_data` / `cmd_log_download` / `cmd_log_cancel`.

---

## Critical bugs (download can hang, OOM, corrupt buffer, or misbehave on FC error)

### C1. `count=0` infinite loop — DoS / hang
**Location:** `backend/mavlink_handlers.py:506-545`
**Severity:** CRITICAL

AP_Logger sends `LOG_DATA` with `count=0` when `get_log_data()` returns an error (`nbytes < 0`, line 311 in `AP_Logger_MAVLinkLogTransfer.cpp`) — this is its EOF/error signal. The MAVLink spec also documents this: `count` field comment says "Number of bytes (zero for end of log)".

`handle_log_data` does:
```python
end = ofs + count            # if count==0, end == ofs
if end <= lg._log_download_size:
    lg._log_download_data[ofs:end] = data   # writes b'' — no-op, OK
lg._log_download_ofs = end
...
if end >= lg._log_download_size:    # False whenever ofs < size
    # complete
else:
    # request next chunk starting at ofs (same offset!)
    link.send(bm(119, struct.pack('<IIHBB', end, chunk, log_id, ...), ...))
```

If the FC errors at offset 50000 of a 10MB log, FC sends `LOG_DATA(ofs=50000, count=0)` and ends its side of the transfer. Argus then sends a fresh `LOG_REQUEST_DATA(ofs=50000, count=4500)`. FC has `transfer_activity = IDLE`, so it re-opens the transfer (no link conflict because the previous link cleared `_log_sending_link` in `end_log_transfer()`). FC may again return `nbytes<0`, again sends `count=0`, → tight infinite loop until FC reboots or user cancels.

**Also for legitimate EOF on a log that is smaller than recorded size:** AP_Logger's `end_log_transfer()` fires when `nbytes < 90` even at the *very end* — and the GCS-side `_log_download_size` came from the LOG_ENTRY which is documented as "may be approximate" (common.xml). If the real log is *shorter* than the entry-reported size (which can happen with the LOG_REPLAY backend or with rotated logs), Argus never reaches `end >= size`, never marks complete, and loops forever.

**Fix:** Treat `count == 0` (or `count < 90` and `end < size`) as a transport end; mark complete, or surface an error to the UI and stop requesting.

---

### C2. Out-of-order / duplicate chunks rewind `_log_download_ofs`
**Location:** `backend/mavlink_handlers.py:517`
**Severity:** CRITICAL (causes data overwrite + infinite re-fetch)

`lg._log_download_ofs = end` is **unconditional**. If a duplicate or out-of-order LOG_DATA arrives (very real on lossy/serial links — pymavlink-style retries happen), `_log_download_ofs` walks backward.

Worse, the very next branch fires the *follow-up* request based on `end`:
```python
link.send(bm(119, struct.pack('<IIHBB', end, chunk, log_id, ...
```
…re-requesting bytes we already received, causing the FC to resend them, and (since AP_Logger streams sequentially from `packet.ofs`) we end up re-downloading the tail of the log on every duplicate. A single dropped + retransmitted packet near the end can multiply the download size by O(N).

Argus has no "is this chunk newer than what we've seen?" filter and no "received-coverage" bitmap. Compare ArduPilot's expected GCS behavior (MAVProxy): track holes, request only gaps.

**Fix:** Only kick a follow-up request when `end > previous_ofs`. Track high-water mark separately from the `end` value of the just-received packet.

---

### C3. New `log_download` while one is in-flight: silent stall + buffer churn
**Location:** `backend/commands/_setup.py:114-126`
**Severity:** HIGH

If the user clicks a second log while a first is downloading:
1. Argus overwrites `_log_download_id`, `_log_download_size`, `_log_download_data = bytearray(new_size)` (old buffer GC'd, possibly large).
2. Argus sends a fresh `LOG_REQUEST_DATA` for the new log.
3. FC side: `handle_log_request_data` checks `_log_sending_link != nullptr` and rejects with a statustext "Log download in progress" (line 113-118 of `AP_Logger_MAVLinkLogTransfer.cpp`). FC continues sending data for the **previous** log.
4. Argus sees incoming LOG_DATA, `log_id != _log_download_id` (the new one), returns silently.
5. **Stuck:** new buffer never fills; old transfer can't progress (Argus stopped echoing requests for the old id); UI shows new download stuck at 0%.

**Fix:** `cmd_log_download` should first send `LOG_REQUEST_END` to reset FC state, then issue the new request (after a short delay to let FC's `end_log_transfer()` fire), OR reject the new download client-side until cancel completes.

---

### C4. `cmd_log_list` while download is in flight
**Location:** `backend/commands/_setup.py:108-111`
**Severity:** HIGH

Similar to C3: `cmd_log_list` clears `_log_list` but does **not** stop the in-flight download. It sends LOG_REQUEST_LIST. FC will reject with "Log download in progress" (line 73 of MAVLinkLogTransfer.cpp) — but only as a statustext. Meanwhile incoming LOG_DATA for the still-active download continues to fill `_log_download_data` and emits a `log_complete` message that's no longer expected by the UI.

**Fix:** Auto-cancel any in-progress download when log_list is requested, or block the request until idle.

---

### C5. Disconnect / reconnect leaves stale download state
**Location:** `backend/drone_link.py` reconnect path (lines 221-235, 444-470)
**Severity:** HIGH

On reconnect (port drop or vehicle swap), `log_dl` state is **not** reset:
- `_log_download_id`, `_log_download_size`, `_log_download_data`, `_log_download_ofs` all persist.
- If we reconnect to a *different* vehicle whose next-allocated log_id collides (totally plausible: small monotonic IDs), incoming LOG_DATA for that vehicle's logs will be written into the leftover buffer.
- Even on same vehicle, FC has reset its `transfer_activity = IDLE` (the reconnect implies it lost us); Argus's `_log_download_id` is still set, so any new request from the user will mis-interpret the state.

**Fix:** Reset `link.log_dl = LogState()` (or call a `reset_log_state()` helper) on reconnect and on initial connect.

---

### C6. `cmd_log_cancel` does not free the buffer
**Location:** `backend/commands/_setup.py:129-132`
**Severity:** MEDIUM

After cancel:
```python
link.log_dl._log_download_id = -1
```
…but `_log_download_data` (the bytearray) is not cleared. For a cancelled 100 MB download, this holds 100 MB in Python's heap until the next download (which reassigns) or process exit. Not strictly a leak, but a footprint anomaly.

Also `_log_download_size`, `_log_download_ofs`, and `link._log_progress_counter` are not reset. If a stale `LOG_DATA` with the old log_id arrives between the cancel send and FC's `end_log_transfer()` (race window — could be 100s of ms), it slides past `if log_id != lg._log_download_id` (because `_log_download_id == -1` now, mismatch, return). Safe by accident.

**Fix:** Reset all five fields on cancel.

---

## Partial / latent issues

### P1. Large logs: bytearray is correctly pre-allocated, but base64 doubles memory
**Location:** `backend/mavlink_handlers.py:531-538`
**Severity:** MEDIUM

`_log_download_data = bytearray(log_entry['size'])` is pre-allocated, so no realloc growth — good. But on completion:
```python
b64 = base64.b64encode(bytes(lg._log_download_data)).decode('ascii')
```
1. `bytes(bytearray)` copies the entire buffer (peak = 2× size).
2. `base64.b64encode` produces a string ~1.33× the input (peak = 3.33× size).
3. `.decode('ascii')` again copies.

A 100 MB log briefly requires ~500 MB working memory in Python. On a 1 GB log this is fatal.

Worse: the entire base64'd payload is then put in `_log_messages.append({'data': b64, ...})` and serialized through `json.dumps(...)` in `ws_manager._push_loop` (line 189) — another full copy as a JSON string sent over the websocket in a single `send_text` call. The browser must then hold the entire base64 payload in a single message, decode it, and process it.

**Fix:** Stream the log to disk on the backend and let the UI download it via a separate HTTP endpoint, OR chunk the websocket transmission (multiple `log_chunk` messages then `log_complete` with a manifest).

---

### P2. Armed-state precondition is not surfaced to the UI as a typed error
**Location:** `backend/commands/_setup.py:108-111` and frontend `LogPanel.svelte`
**Severity:** MEDIUM

ArduPilot rejects log access when armed (line 40-46 of MAVLinkLogTransfer.cpp) and emits a one-shot statustext `"Disarm for log download"` (no continuation until disarm-rearm cycle resets `_warned_log_disarm`). The user does see "FC: Disarm for log download" in the EventLog (via `handle_statustext`), but:
- The LogPanel UI doesn't know the request failed — it shows "no logs returned" (empty list) which looks like a connection issue.
- There is no pre-check in `cmd_log_list` or `cmd_log_download` for `link.vehicle.armed`.
- If user disarms, no auto-retry hint, no clear UI state.

**Fix:** Add a vehicle.armed check in `cmd_log_list`/`cmd_log_download`; return a typed error like `err_log_armed`. Frontend should display it as a banner. (A locale string `err_log_armed` does not exist yet — only `err_log_not_found` is defined in locale_text.py:70.)

---

### P3. Inefficient request-pacing on high-latency links
**Location:** `backend/mavlink_handlers.py:544`
**Severity:** LOW (perf, not correctness)

Argus requests in 4500-byte windows (`chunk = min(90 * 50, ...)`) and waits for AP_Logger to finish each window before sending the next LOG_REQUEST_DATA. On a 100 ms RTT link the round-trip per 50 packets is dead air ≈ 10% of throughput.

ArduPilot is designed to handle a single very large LOG_REQUEST_DATA (count = 0xFFFFFFFF) and stream the whole log; the GCS only re-requests if it detects gaps. Argus's design is simpler but slower.

**Fix:** Increase initial `count` to `min(0xFFFFFFFF, log_size - ofs)`, then handle gap-fill on the GCS side using a coverage bitmap (which fixes C2 simultaneously).

---

### P4. `_log_progress_counter` leaks across downloads
**Location:** `backend/mavlink_handlers.py:518-522`
**Severity:** LOW

`link._log_progress_counter` is dynamically attached via `hasattr` and never reset on cancel or new download. It is reset to 0 *after* hitting 10 inside the loop, but if a download finishes at counter=7 the next download starts at 7, emitting first progress event after only 3 chunks instead of 10. Cosmetic.

**Fix:** Move into `LogState` dataclass; reset in `cmd_log_download` and `cmd_log_cancel`.

---

### P5. Simulator `sim_pllink.py` checks wrong cancel message ID
**Location:** `scripts/sim_pllink.py:490`
**Severity:** LOW (sim only — masks C3 / C4 / C6 testing)

```python
elif mid == 126:        # SHOULD be 122 (LOG_REQUEST_END). 126 is SERIAL_CONTROL.
    self._log_send_active = False
```

This means the simulator never sees real cancel messages from the backend (which sends 122), so cancel/restart races are not exercised in `test_integration.test_log_download`. The integration test passes because the sim doesn't actually need to stop sending — it sends the requested range and stops naturally.

**Fix:** Change `mid == 126` → `mid == 122`.

---

### P6. `cmd_log_download` size==0 edge case
**Location:** `backend/commands/_setup.py:122-126`
**Severity:** LOW

If `log_entry['size'] == 0` (FC reports a 0-byte log — possible on a freshly-created log entry), Argus:
- `_log_download_data = bytearray(0)`,
- `chunk = min(4500, 0) = 0`,
- sends LOG_REQUEST_DATA with count=0.

FC's `handle_log_request_data` sets `_log_data_remaining = 0`, immediately calls `end_log_transfer()` — no LOG_DATA reply. Argus is stuck with `_log_download_id == 0` and never gets `log_complete`. UI shows a 0% download forever.

**Fix:** Handle size==0 in `cmd_log_download` by emitting `log_complete` immediately with empty data, or refusing the request.

---

### P7. Backend processes LOG_DATA when `_log_download_id == -1` is the active sentinel
**Location:** `backend/mavlink_handlers.py:511`
**Severity:** LOW

`if log_id != lg._log_download_id: return` — when no download is active, `_log_download_id == -1`. Any genuine LOG_DATA arriving (e.g., a delayed packet after cancel) has `log_id >= 0`, so it's correctly ignored. **However**, if the user uploaded a log_id==-1 (impossible, log_id is uint16), nothing weird. Edge case noted only — fine.

---

## Recommended priority order

1. **C1** — count==0 infinite loop (could brick a session permanently).
2. **C2** — out-of-order rewind + re-request (multiplies download size).
3. **C5** — reconnect leaves stale state (silent data corruption).
4. **C3/C4** — concurrent operations deadlock the UI.
5. **P1** — large-log memory blowup (limits practical use to <50 MB logs).
6. **P2** — armed precondition UX.
7. **C6/P4/P5/P6/P7** — cleanup, sim fix, edge cases.

## Files audited

- `backend/commands/_setup.py` (lines 106-132)
- `backend/mavlink_handlers.py` (lines 450-458, 506-545)
- `backend/state.py` (LogState, lines 106-113)
- `backend/ws_manager.py` (log_messages push, lines 147, 166, 185-190)
- `scripts/sim_pllink.py` (lines 467-493 — sim bug P5)
- `src/components/tools/LogPanel.svelte` (no armed-check UI)
- ArduPilot reference: `libraries/AP_Logger/AP_Logger_MAVLinkLogTransfer.cpp` (all 336 lines)
- ArduPilot reference: `libraries/GCS_MAVLink/GCS_Common.cpp` lines 4258-4266
- `modules/mavlink/message_definitions/v1.0/common.xml` — wire layouts confirmed
- pymavlink verification — CRC extras 128/56/116/134/203 confirmed
