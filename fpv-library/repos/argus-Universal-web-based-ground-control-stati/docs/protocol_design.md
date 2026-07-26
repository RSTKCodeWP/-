# Protocol-Layer Design Notes

This is the "**don't refactor this, here's why**" document. Each entry
documents a piece of code that looks wrong to a reader who hasn't gone
through the 2026-05-23 audit cycle — and explains the upstream constraint
that forces the current shape.

Pairs with:
- `CLAUDE.md ## Protocol Code Discipline` (the rule)
- `docs/audits/README.md` (the receipts)
- Individual commit messages (the per-fix justification)

---

## Load-bearing oddities

### 1. `cmd_cal_accel_next` sends `command=0, result=1`

**Looks wrong because:** Every MAVLink reference shows COMMAND_ACK fields as
`command = a MAV_CMD value, result = a MAV_RESULT value`. The natural code
would be `command=MAV_CMD_ACCELCAL_VEHICLE_POS (42429), result=ACCEPTED (0)`.

**Why it's correct:** ArduPilot's `AP_AccelCal::handle_command_ack`
(`libraries/AP_AccelCal/AP_AccelCal.cpp:367-398`) reinterprets the fields
entirely for its private "advance accel calibration" protocol:
```cpp
if (packet.command > 6) { return; }
if (packet.result != MAV_RESULT_TEMPORARILY_REJECTED) { return; }
```
So `command` is a 0-6 index (0=any/QGC, 1-6=specific pose), and `result`
must be `MAV_RESULT_TEMPORARILY_REJECTED = 1`. QGroundControl and
MissionPlanner do the same thing. See `backend/commands/_setup.py`.

**Frontend mirror:** WebSerial direct mode bypasses the Python backend and
needs the same wire bytes — implemented at `src/lib/transport.ts:serialCalAccelNext`
via the `encodeCommandAck(0, 1)` helper in `src/lib/mavlink/messages.ts`.
Both call sites carry the citation comment; both call sites must stay in
sync if the AP handler ever changes.

**Cited:** Commit `2f93a6d`, `6a42c47`, and the Phase F WebSerial accel
calibration commit that added the frontend mirror.

---

### 2. Every receive handler calls `_pad(p, n)` before `struct.unpack_from`

**Looks wrong because:** It's boilerplate. Every handler has a 1-line
"pad to N bytes" call that seems like it should be factored into a
decorator or into the dispatch layer.

**Why it's correct:** MAVLink 2 senders may zero-trim trailing zero bytes
from a payload. The receiver MUST treat the missing bytes as zero. We
tried centralizing the pad in `_process` and the dispatch layer; that
broke many tests because they call handlers directly. Self-padding in
each handler is the contract that works regardless of caller.

The strict `if pl < N: return` checks were also wrong-by-default — they
rejected legitimate trimmed frames. Each handler's check is now the
*minimum* `pl` for which any work is meaningful (e.g., `if pl < 1` rather
than `if pl < 25` for PARAM_VALUE).

**Cited:** Commit `102a05e`.

---

### 3. `_events_emitted_total` monotonic counter instead of `len(events)`

**Looks wrong because:** A monotonic counter that grows without bound
duplicates information already available in `len(self.events)`. Standard
"just use the length" advice.

**Why it's correct:** `events` is a ring buffer trimmed from 100 to 50 on
overflow. `ws_manager._push_loop` uses the counter as its cursor; if it
used `len(events)`, then after a trim the cursor would point into the
freshly-rotated array and either replay or drop events for connected
clients. The monotonic counter survives the trim — when the next push
runs, `events_emitted_total > cursor` correctly identifies new events
and we look them up by `seq` field, not by index.

**Cited:** Commit `7d50700`. The bug it fixes: drone_link audit C5.

---

### 4. `cmd_param_load` runs the load in a background thread

**Looks wrong because:** Inlining the loop would be simpler and avoid the
thread.

**Why it's correct:** The loop does `time.sleep(PARAM_LOAD_SPACING)` between
each `set_param` to avoid overrunning the FC's param queue. For a
1000-param file that's ~20s of sync blocking. `commands.execute()` is
called from inside an `async def receive_loop`, so a sync sleep freezes
the asyncio event loop for that whole window — heartbeats stop, other
clients hang, LINK_LOST_TIMEOUT trips.

**Cited:** Commit `f278b75`.

---

### 5. The accel cal cancel command sends MAG cal cancel

**Looks wrong because:** `cmd_cal_cancel` sends `MAV_CMD_DO_CANCEL_MAG_CAL`
(42426) only. If the user clicks Cancel during accel calibration, this
does nothing to the FC.

**Why it's correct:** ArduPilot has no MAVLink command to abort an accel
calibration mid-sequence (`AP_AccelCal::cancel()` is internal-only). The
cleanest behavior we can offer the user is: reset the GCS-side UI state
on cancel, and either (a) wait for the next accel-cal step ACK to advance
through and complete it, or (b) reboot the FC. Documented inline in
`backend/commands/_setup.py:cmd_cal_cancel`.

**Cited:** Commit `c69f684`.

---

### 6. Unknown MAVLink msg ids are silently dropped, not warned

**Looks wrong because:** Pre-2026-05-23 there was a "fail-loud" warning for
unknown msg ids — designed to surface the case where someone added a
handler but forgot the CRC_EXTRA entry. That was removed.

**Why it's correct:** The warning fired for legitimate unhandled messages
too (TIMESYNC, SCALED_PRESSURE2, ESC_TELEMETRY, ~20 distinct ids per
real-hardware session) and flooded the operator's log. The "handler
exists without CRC_EXTRA" bug class is now caught statically by
`tests/test_contract_handlers_crc.py`. Runtime is silent and clean.

**Cited:** Commit `f278b75`. Tried-and-reverted in `9b6276a`.

---

### 7. Auto-detect protocol scans first 256 bytes for magic, doesn't lock on byte 0

**Looks wrong because:** "Just check the first two bytes" is the obvious
implementation. The current code does a scan-and-resync.

**Why it's correct:** A hot connect can catch a partial frame mid-stream
(USB enumeration garbage, RS-485 echo, a previous half-sent MAVLink
frame). Locking on byte 0 was wrong-protocol for the lifetime of the
connection. The scan handles "leading garbage, then real magic".

**Cited:** Commit `e2bc1d5`.

---

### 8. Frontend `src/components/params/*.svelte` panels seed local state from `getParam` ONCE via a `_loaded` flag

**Looks wrong because:** Standard Svelte pattern is `let value = $derived(getParam(...))` — reactive over the param store.

**Why it's correct:** `paramState.list` grows over ~10s during the initial
PARAM_REQUEST_LIST burst (700-1000 params on a typical ArduCopter). A
derived-from-store binding would re-fire on every batch, clobbering any
edit the operator made before the fetch finished. The `_loaded` flag
seeds values once at first availability and lets the user edit freely.

**Cited:** Commit `f96b5c6`.

---

### 9. CRC_EXTRA[85]=140, CRC_EXTRA[87]=150 (verified non-obvious values)

**Looks wrong because:** These values can't be derived without running the
MAVLink XML through `mavgen` or pymavlink. They were wrong in the
codebase for a long time (143 and 5).

**Why it's correct:** These are the canonical CRC extras for
POSITION_TARGET_LOCAL_NED (85) and POSITION_TARGET_GLOBAL_INT (87) per
pymavlink. The `tests/test_contract_pymavlink.py::TestCrcExtraMatchesPymavlink`
test enforces that every entry in `_CRC_EXTRA` (backend) and `CRC_EXTRA`
(frontend `crc.ts`) matches pymavlink byte-for-byte. Do NOT "round" them.

**Cited:** Commit `bd3afb9`.

---

### 10. Mission upload watchdog timers are stored in MissionState dataclass fields, not module globals

**Looks wrong because:** Three almost-identical fields
(`_mission_ul_start_time`, `_fence_ul_start_time`, `_rally_ul_start_time`)
that could be one shared field.

**Why it's correct:** Mission/fence/rally uploads can overlap in principle
(the FC tracks them as separate `mission_type` slots). A unified timer
would incorrectly abort one when a sibling protocol's REQUEST arrived.

**Cited:** Commit `689d636`.

---

## Contract test catalog

These tests enforce protocol invariants. They are NOT redundant with unit
tests — each prevents a specific bug class that has actually occurred:

| Test file | What it catches | Origin bug |
|---|---|---|
| `test_contract_commands.py` | Frontend `sendCommand('foo')` literal with no backend dispatch entry. The reverse: backend handler with no frontend caller (dead code). | NTRIP commands wired in UI but no backend handler |
| `test_contract_state.py` | Field-shape drift between `DroneLink._build_state()` output and the frontend `DroneState` TS interface. | Caught preemptively during the audit |
| `test_contract_handlers_crc.py` | Static: every msg id registered in `init_handlers` must have an entry in `_CRC_EXTRA`. Catches the silent failure of "handler exists but parser drops the frame on the floor". | MAG_CAL_PROGRESS (191) and MAG_CAL_REPORT (192) were missing from CRC_EXTRA |
| `test_contract_pymavlink.py` | Byte-level: backend `bm()` output decodes correctly under pymavlink for every command we send; pymavlink-encoded incoming frames decode correctly under our handlers; CRC_EXTRA tables on both ends match pymavlink. 60+ tests. | Multiple wrong CRC entries, wrong handler offsets, MAVLink 2 trim handling |
| `test_contract_locale.py` | Every `t('xxx')` call in Svelte source has a key in zh/en. Orphan keys in locale files (known-orphan allowlist exists for staged-but-removed features). | `telem.battery` was used but undefined |

If one of these fails:
1. Trust the test — every contract assertion was added because the bug it
   catches *actually happened*.
2. Don't loosen the assertion. Either fix the production code, or update
   the explicit `KNOWN_*_ORPHANS` allowlist with a comment explaining the
   exception.

---

## Patterns that worked

The 2026-05-23 audit cycle established three meta-patterns. Re-use them:

### Parallel audit agents with source-of-truth citation

5+ independent agents at a time, each scoped to one protocol area (mission,
log, param, etc.) and instructed to cite ArduPilot source file:line or
pymavlink class for every finding. Reports landed in `docs/audits/`. This
worked because:
- Independent scopes = no merge conflicts
- Source citations = findings are auditable, not "agent says so"
- Per-agent severity tags = easy to triage afterwards

### pymavlink as the wire-format oracle

For any "is our struct.pack right" / "is this CRC right" question, the
answer is whatever pymavlink produces for the equivalent logical message.
`tests/test_contract_pymavlink.py` is the institutional memory of this.

### Static contract tests over runtime warnings

When tempted to add a runtime log_warning for "this shouldn't happen",
prefer a startup-time contract test instead. Runtime warnings either
spam the operator log (and get ignored) or are silent in the happy path
(and don't actually catch the bug class they're meant to). Contract
tests fail loud in CI exactly when they should.

---

## Current feature & verification status

See **`docs/FEATURE_CHECKLIST.md`** for the canonical per-feature status
(✅ real-hardware verified / ✅ᵗ test-verified / ⚠️ partial / 🔒 blocked /
❌ broken or not-implemented). It tracks ~500 numbered features and
gets updated as the codebase changes. Don't duplicate that table here —
this document is for **design rationale**, not status.

The orphan / deferred items also live in test allowlists with explanatory
comments:
- Frontend → backend command orphans (NTRIP etc.): `tests/test_contract_commands.py::KNOWN_FRONTEND_ORPHANS`
- Backend dispatch entries with no frontend caller: `tests/test_contract_commands.py::KNOWN_BACKEND_ORPHANS`
- Locale keys defined but unreferenced: `tests/test_contract_locale.py::KNOWN_ORPHAN_LOCALE_KEYS`

## Maintenance rule for this document

When you legitimately remove a load-bearing oddity (i.e., the upstream
constraint no longer applies), delete its section here **in the same
commit**. Otherwise this file rots into "looks wrong, here's why we
*used to* keep it that way" — actively misleading.
