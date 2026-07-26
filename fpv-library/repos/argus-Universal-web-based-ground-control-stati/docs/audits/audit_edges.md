# Argus Protocol Audit — "partial / low priority" edge cases

Date: 2026-05-23
Scope: Investigation of 8 specific items flagged in prior protocol audits.
Refs:
- Argus root: project root (`./`)
- ArduPilot root: local ArduPilot source tree

## 1. Equator-coordinate rejection (handle_global_position_int)

**Status:** real bug — **FIXED**

**Citation:** ArduPilot `libraries/GCS_MAVLink/GCS_Common.cpp:3062-3092` — `send_home_position()` returns early
if home is not set (`if (!AP::ahrs().home_is_set()) return`), so any HOME_POSITION (msg 242) we receive
necessarily has a valid home. Coupled with `libraries/AP_AHRS/AP_AHRS.h` `home_is_set()` semantics, the
FC will never spam (0,0) home positions.

**Problem in Argus:**
- `backend/mavlink_handlers.py:97` checked `a.home_lat == 0 and a.home_lon == 0 and abs(a.lat) > 0.001`
  before setting home. At lat=0 (equator), real position fixes were rejected → home never set →
  `dist_home` stuck at 0 forever.
- `backend/mavlink_handlers.py:160` also rejected HOME_POSITION messages whose `hlat ~ 0` — so even the
  authoritative FC message couldn't repair the state.

**Fix applied:** Introduced `AttitudeState._home_set: bool` flag.
- `handle_global_position_int`: only auto-infer home on first valid fix where `lat OR lon` is non-zero
  (still rejects the (0,0) startup placeholder).
- `handle_home_position`: trust the FC unconditionally; set `_home_set = True`.

Files:
- `backend/state.py` — added `_home_set: bool = False` to `AttitudeState`.
- `backend/mavlink_handlers.py:79-104` — use `_home_set` flag.
- `backend/mavlink_handlers.py:154-167` — trust HOME_POSITION unconditionally.

## 2. NAV_SPLINE_WAYPOINT on Plane

**Status:** real bug — **FIXED**

**Citation:** `libraries/AP_Mission/AP_Mission.cpp:1153-1158`:
```cpp
case MAV_CMD_NAV_SPLINE_WAYPOINT:                   // MAV ID: 82
#if APM_BUILD_TYPE(APM_BUILD_ArduPlane)
    return MAV_MISSION_UNSUPPORTED;
#else
    cmd.p1 = packet.param1;
    break;
#endif
```
Plus `ArduPlane/commands_logic.cpp:40-204` confirms `start_command` has no `case MAV_CMD_NAV_SPLINE_WAYPOINT`
even outside the AP_Mission validation. So upload returns UNSUPPORTED and the entire mission item is dropped
mid-upload, leaving a partial mission stored.

**Fix applied:** `backend/commands/_mission.py:cmd_mission_upload` now early-returns a clear error
("Spline waypoints are not supported on ArduPlane") when `link.is_plane()` and any WP has `type == 'spline'`.
The frontend will surface the error before any wire bytes are sent.

## 3. cmd_rc_override SYSID_MYGCS mismatch

**Status:** real, low-impact, **NOT FIXED** (documented).

**Citation:** `libraries/GCS_MAVLink/GCS_Common.cpp:4043-4047`:
```cpp
void GCS_MAVLINK::handle_rc_channels_override(const mavlink_message_t &msg)
{
    if(msg.sysid != sysid_my_gcs()) {
        return; // Only accept control from our gcs
    }
```
`ArduPlane/Parameters.cpp:30` and `ArduCopter/Parameters.cpp:52` both default `SYSID_MYGCS` to **255**.

**Argus behavior:** `backend/pllink_proto.py:57` — `bm(mid, p, s, ce, sysid=255, compid=1)` — we always send
with sysid=255, matching the default. Verified all callers in `_helpers.py` and `_hardware.py` use the default.

**Why not fix now:**
- Default value matches, so the common case works.
- A fix would require: reading SYSID_MYGCS at connect via PARAM_REQUEST_READ, plumbing the value through
  state, and adding a UI warning if it diverges from 255. That's >>5 lines and crosses 3 modules
  (param_manager, state, frontend).
- Misconfigured users see a silent failure but get an event-log clue ("RC override sent" with no FC
  response). Manual debugging finds it quickly.

**Proposed fix (not applied):** In `param_manager.py:handle_param_value` (or a new tracker), keep
`SYSID_MYGCS` value; in `cmd_rc_override`, before sending, compare to `link.vehicle.sysid_mygcs` (or similar
attribute) and surface a `cmd_ack_fail` event if mismatched. Approximate scope: ~15 LOC + UI string.

## 4. cmd_serial_control SHELL device gate

**Status:** real bug, **NOT FIXED** (documented). The FC silently drops the frame; user sees nothing.

**Citation:** `libraries/GCS_MAVLink/GCS_serial_control.cpp:33-95`:
```cpp
switch (packet.device) {
case SERIAL_CONTROL_DEV_TELEM1: ...
case SERIAL_CONTROL_DEV_TELEM2: ...
case SERIAL_CONTROL_DEV_GPS1: ...
case SERIAL_CONTROL_DEV_GPS2: ...
case SERIAL_CONTROL_SERIAL0 ... SERIAL_CONTROL_SERIAL9: ...
default:
    // not supported yet
    return;
}
```
**There is no `case SERIAL_CONTROL_DEV_SHELL`** in current ArduPilot. Even when shell was historically
available behind `AP_SERIALMANAGER_SHELL_ENABLED`, the symbol no longer exists in the current handler tree
(grep confirmed: `grep -rn "AP_SERIALMANAGER_SHELL_ENABLED" libraries/` returns 0 hits in current source).
Sending `packet.device = 10` (SHELL) falls through to `default: return` — silently swallowed.

**Argus behavior:** `backend/commands/_helpers.py:73-78` `send_serial_control` hardcodes `device=10`. The
console panel will appear to send keystrokes that never produce a response.

**Why not fix in one < 5-line patch:** The right fix is to make device configurable and default to one of
`SERIAL_CONTROL_DEV_TELEM1/2` or a `SERIAL0..9` port, requiring frontend UI changes (which port to
connect to, exclusivity flag warnings). Console panel is currently advertised in CLAUDE.md as a tool;
making it functional requires choosing the port. That's a feature scope, not an edge-case patch.

**Proposed fix (not applied):**
1. Add `port` data field in `cmd_serial_control` (default to SERIAL0 = 100).
2. Add UI dropdown in ConsolePanel.svelte.
3. Document caveat: AP must have the corresponding SERIALn_PROTOCOL set to something the user types to.
4. Optionally: add an event-log warning whenever `device == 10` is used.

## 5. VTOL takeoff via NAV_TAKEOFF (cmd 22) without GUIDED mode

**Status:** real bug — **FIXED**

**Citation:**
- `ArduPlane/GCS_Mavlink.cpp:1194-1211` — `handle_command_MAV_CMD_NAV_TAKEOFF` calls
  `plane.quadplane.do_user_takeoff(takeoff_alt)` and returns `MAV_RESULT_FAILED` if it fails.
- `ArduPlane/quadplane.cpp:3948-3953` — `do_user_takeoff` strictly requires GUIDED:
  ```cpp
  if (plane.control_mode != &plane.mode_guided) {
      gcs().send_text(MAV_SEVERITY_INFO, "User Takeoff only in GUIDED mode");
      return false;
  }
  ```
So sending cmd 22 from QSTABILIZE / QHOVER / QLOITER / any non-GUIDED mode fails with a STATUSTEXT
("User Takeoff only in GUIDED mode") and a FAILED command ack.

**Fix applied:** `backend/commands/_flight.py:cmd_takeoff` now switches to GUIDED (mode 15) before sending
cmd 22, but only for Plane. Mirrors the pattern already in `cmd_guided_goto` (`_hardware.py:34-36`).

Note: For Copter, several modes support user takeoff (`ArduCopter/mode.h:488+`), so we don't force a mode
switch and preserve previous behavior.

## 6. NAV_WAYPOINT p1 semantics for Plane

**Status:** **NOT a bug** (verified harmless).

**Citation:** `libraries/AP_Mission/AP_Mission.cpp:1065-1086`:
```cpp
case MAV_CMD_NAV_WAYPOINT: {                        // MAV ID: 16
#if APM_BUILD_TYPE(APM_BUILD_ArduPlane)
    uint16_t acp = packet.param2;     // acceptance radius
    uint16_t passby = packet.param3;  // pass by distance
    ...
    cmd.p1 = (passby << 8) | (acp & 0x00FF);
#else
    cmd.p1 = packet.param1;           // delay (copter)
#endif
```
And `ArduPlane/commands_logic.cpp:397-400` (`do_nav_wp`) **never reads cmd.p1**; only `verify_nav_wp`
reads p1 as the post-encoded `(passby<<8)|acceptance` — i.e. the field is populated from packet.param2/3
on the FC side, not from packet.param1.

**Conclusion:** When Argus sends `param1 = delay_seconds` to Plane for a NAV_WAYPOINT, ArduPlane simply
ignores param1. It packs param2 and param3 (which Argus sends as 0,0) into cmd.p1. So:
- Wire-side parity: param1 ignored → no error.
- Field-side parity: Plane stores `cmd.p1 = (0<<8)|0 = 0` (acceptance/passby both zero), which makes
  Plane use the global `WP_RADIUS` parameter — exactly the desired default behavior.

No fix needed. If we ever want to expose per-WP acceptance radius for Plane, the right path is to
populate `wp['p2']` (acceptance radius) — see `send_mission_item_int` in `_helpers.py:59-70` which already
serializes p2.

## 7. Concurrent fence+mission upload ACK ambiguity

**Status:** **NOT a bug** with current ArduPilot behavior.

**Citation:** `libraries/GCS_MAVLink/MissionItemProtocol.cpp:347-357`:
```cpp
void MissionItemProtocol::send_mission_ack(const GCS_MAVLINK &_link, ...) const {
    ...
    mavlink_msg_mission_ack_send(_link.get_chan(),
                                 msg.sysid, msg.compid,
                                 result,
                                 mission_type());   // <-- explicit, always set
}
```
ArduPilot always emits MISSION_ACK with the correct `mission_type` matching the protocol (fence=1,
rally=2, mission=0). Zero-trimming only ever turns the byte to 0 when the value really is 0 (i.e. it's
a mission ACK).

**Argus dispatch (`mavlink_handlers.py:486-510`):** elif chain prefers fence(1) → rally(2) → mission(0).
- If mission_type==1 → fence
- If mission_type==2 → rally
- If mission_type==0 → mission

A spurious mission_type=0 ACK with both fence AND mission pending would close mission, which is
correct because the value 0 unambiguously identifies it as a mission ACK from AP. There is no
ambiguity in practice.

No fix needed. The existing `_pad` + elif-chain handles all real cases.

## 8. handle_mission_count mission_type validation

**Status:** **NOT a bug** in current code path.

**Citation:** `libraries/GCS_MAVLink/MissionItemProtocol.cpp:120-144` — `handle_mission_request_list`
responds with `mavlink_msg_mission_count_send(..., item_count(), mission_type())`. AP always tags the
MISSION_COUNT with its mission_type.

**Argus behavior:**
- `backend/commands/_mission.py:91` — `cmd_mission_download` sends `MISSION_REQUEST_LIST` with payload
  byte 2 = 0 (mission, not fence/rally). No fence download flow exists in the codebase.
- `backend/mavlink_handlers.py:377-390` — `handle_mission_count` checks `m._dl_pending` (mission-only)
  and processes any count. Since we never request fence/rally listing, no race exists.

**Latent concern (not actively triggered):** If we ever add a fence-download path that sets a
`_fence_dl_pending` flag without distinguishing from mission, an AP-initiated mission count for type 0
could theoretically interleave. Easy preemptive guard: read `mission_type = p[2]` at offset 2 of the
MISSION_COUNT payload and require it equal 0 before populating mission state. Single-line patch deferred
until fence download lands.

**Proposed (deferred) fix (not applied):** Add `mission_type = p[2]` check at `mavlink_handlers.py:381`:
```python
mission_type = p[2]
if mission_type != 0:
    return  # not for us; we only download mission_type=0
```

---

## Summary

| # | Case | Status | Action |
|---|------|--------|--------|
| 1 | Equator home rejection | real bug | **fixed** (3 hunks) |
| 2 | NAV_SPLINE_WAYPOINT on Plane | real bug | **fixed** (1 hunk) |
| 3 | SYSID_MYGCS mismatch | real, low impact | documented |
| 4 | SHELL device 10 silent drop | real bug, feature scope | documented |
| 5 | VTOL takeoff requires GUIDED | real bug | **fixed** (1 hunk) |
| 6 | NAV_WAYPOINT p1 semantics for Plane | not a bug | no change |
| 7 | Concurrent fence+mission ACK | not a bug | no change |
| 8 | handle_mission_count type validation | latent only | no change |

**Real bugs found:** 5
**Fixed in place:** 3 (cases 1, 2, 5)
**Documented only:** 2 (cases 3, 4)
**Not actually bugs:** 3 (cases 6, 7, 8)

All 948 unit tests pass after the changes.
