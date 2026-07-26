# Argus Backend / Simulator Sweep — FC-Protocol Correctness Audit

Scope: modules not deeply audited in prior rounds. Citations are `file:line`.

Severity: 🔴 Critical · 🟡 Medium · 🟢 Low

---

## 1. `backend/connection.py`

🟡 **UDP wrapper buffers an unbounded `_remote` from any source** — `UdpWrapper.read()` (`connection.py:36-39`) latches `self._remote` to the address of the FIRST datagram it ever receives, with no host filter. If the FC is on a NAT and an attacker sends a single UDP packet to the same listening port before the FC's first datagram arrives, all subsequent `write()` calls (heartbeats, arm/disarm, mode change) go to the attacker. Fix: only update `_remote` when the source matches a pre-configured peer, or always reply to the source of the most recent datagram instead of latching.

🟡 **TCP/UDP/serial wrappers swallow all `OSError` silently in read** — `TcpWrapper.read`/`UdpWrapper.read` (`connection.py:14-17, 34-41`) return `b''` for any `OSError` (including `ECONNRESET`, `EBADF`). The caller (`drone_link._loop`) just treats no-data as idle and never logs the underlying error. A broken serial cable or dropped TCP looks identical to a momentary stall. Fix: log the exception at debug level so the issue is visible in the inspector.

🟢 **`UdpWrapper.bind` lacks `SO_REUSEPORT`** (`connection.py:29`). Only `SO_REUSEADDR` set, so a stale process holding the port can be EADDRINUSE on Linux >=3.9. Cosmetic.

🟢 **TCP wrapper has no half-open-detection** — once `connect()` returns, the wrapper never checks heartbeat liveness from its side; only `drone_link._loop` tracks `last_frame_time`. Acceptable.

---

## 2. `backend/ws_manager.py`

🔴 **Roles are advisory only — `command` dispatch never checks role** (`ws_manager.py:132-137`). The `set_role` handler stores `'pilot'`/`'observer'` in `_roles[id(ws)]`, but the `command` branch on line 132 invokes `commands.execute(...)` for any connected client regardless of role. Any observer (or any client at all) can arm, switch modes, disarm-in-flight, upload mission, etc. Fix: in the `command` branch, gate non-read-only commands on `self._roles.get(id(ws)) == 'pilot'` and `ws is self._pilot_ws`.

🔴 **`_pilot_ws` is never cleared on pilot disconnect** (`ws_manager.py:54-72`). `handle_client`'s `finally` only discards from `_clients`; `_pilot_ws` and the `_roles[id(ws)]` entry persist with a dead websocket reference. Then `request_handoff` checks `self._pilot_ws in self._clients` (line 116): since the dead ws is no longer in `_clients`, the next observer to call `request_handoff` becomes pilot automatically without a real handoff. Fix: in the `finally`, if `ws is self._pilot_ws` set `self._pilot_ws = None`, and `self._roles.pop(id(ws), None)`.

🔴 **`broadcast()` does not catch `WebSocketDisconnect`** (`ws_manager.py:46-52`). `WebSocketDisconnect` is a plain `Exception`, not `ConnectionError`/`RuntimeError`. If any single client disconnects mid-broadcast, the exception escapes and is caught by the outer `_receive_loop`'s `except (ConnectionError, RuntimeError)` at line 140 — which won't match — so it propagates further up and terminates the receiver of the **calling** client, kicking the wrong user. Fix: add `WebSocketDisconnect` to the broadcast except clause, or catch `Exception`.

🟡 **JSON encoding for the same delta is repeated per client** — `_push_loop` (line 161, 172, 183, 188, 198, 205, 215) calls `json.dumps()` once per send and the same payload is encoded N times for N clients, but the push loop is per-client and computes its own delta against `last_sent`. A `broadcast`-style fan-out would be cheaper but the current model is also correct. (Note for `broadcast`: `text = json.dumps(msg)` is computed once, then sent to N — that's fine.) Low priority.

🟡 **`_push_loop` re-emits stale delta on rotating buffers** — `event_cursor` is reset to 0 (`ws_manager.py:169`) whenever `events` shrinks (rotation at `drone_link.add_event` when len>100). On the next push, ALL current events are flushed to the client again, including ones already shown. Fix: when rotation happens (`events = events[-50:]`), broadcast an `event_reset` and have the cursor track by event timestamp/sequence rather than list index.

🟡 **`broadcast` allows TOCTOU on `_clients`** — `for ws in list(self._clients): ... self._clients.discard(ws)` (line 48-52) iterates a snapshot, but a concurrent `handle_client` finishing during the loop can leave `_pilot_ws` referring to a discarded ws. See critical bug above for the fix.

🟢 **`_VALID_LOCALES` is a frozenset hard-coded** (`ws_manager.py:16`) — must be kept in sync with `src/lib/locales/`. No runtime symmetry test exists.

🟢 **Push interval not adaptive to client count** — at 50 clients the per-client push at 0.2s = 250 JSON encodings/sec is fine, but at higher counts the loop becomes serial CPU-bound. Cosmetic for current scale.

---

## 3. `backend/config.py`

🟡 **`_env` cast is permissive — bad value crashes app at import** (`config.py:7-12`). `_env('ARGUS_PORT', 8100)` with `ARGUS_PORT=abc` raises `ValueError` at module import (when `Config` body executes). The process dies before logging is configured, so the user gets a bare traceback. Fix: catch `ValueError`/`TypeError`, log a warning, and fall back to the default.

🟡 **No port range validation** — `ARGUS_PORT=99999` is accepted by the int cast but fails later in `uvicorn.run()` with a confusing socket error. Fix: clamp/reject after cast.

🟡 **`ARGUS_CORS_ORIGINS` not whitespace-stripped** (`app.py:114-117`). `.split(',')` keeps spaces, so `"https://foo, https://bar"` produces `['https://foo', ' https://bar']` and the second origin never matches. Fix: `[s.strip() for s in env.split(',') if s.strip()]`.

🟢 **Insecure-by-default CORS** — defaults to localhost-only, which is safe. The websocket origin check (`app.py:206-209`) only fires when origin is non-empty, so non-browser clients bypass it. Acceptable for the documented "trusted LAN" deployment model.

🟢 **`VALID_PROTOCOLS` includes `'auto'`** (`config.py:65`). `sanitize_protocol` (ws_manager.py:31-32) defaults to `'auto'` for unknown inputs; this is fine since the protocol-detection logic in `_next_frame` handles it.

---

## 4. `backend/app.py`

🔴 **Path traversal in `/api/firmware/download`** (`app.py:524, 538`). `filename = body.get('filename', 'firmware.apj')` is concatenated as `FIRMWARE_DIR / filename` without sanitization. A request like `{"url": "https://...", "filename": "../../../etc/shadow"}` would write to that path. The `endswith('.apj')` check does not prevent the traversal. Compare with `api_firmware_upload` (line 457) which correctly uses `Path(file.filename).name`. Fix: `safe_name = Path(filename).name` before writing.

🔴 **SSRF in `/api/firmware/download`** (`app.py:528-540`). Accepts any HTTPS URL with a hostname. No blocklist for internal hosts, no IP-private check (unlike `video.py:21-41`). An authenticated user can fetch internal HTTPS endpoints (`https://127.0.0.1`, `https://169.254.169.254/latest/meta-data/`, etc.) and save them to the firmware directory, then potentially observe via `/api/firmware/list`. Fix: reuse `_validate_video_url`-style host blocking, or restrict to a fixed list of allowed firmware hosts.

🟡 **`/api/tile_bulk_download` divides by zero at `lat == ±90°`** (`app.py:390-391`). `1/math.cos(math.radians(90))` raises `ZeroDivisionError` (or `math.log` raises `ValueError` on tan(90)). Body `{lat_min:-90, lat_max:90, ...}` crashes the request. Fix: clamp `lat_min, lat_max` to `(-85.05, 85.05)` (Web Mercator usable range).

🟡 **`/api/firmware/download` returns raw exception text** (`app.py:540-541`). `return {'ok': False, 'error': str(e)}` leaks server paths and stack-ish info via `urllib.error.URLError.reason`. Fix: return a generic message; log the detail server-side.

🟡 **`/sw.js` and `/manifest.json` not exempted in `auth_middleware`** (`auth.py:54-55`). The exempt set is `('/health', '/', '/index.html')` + `/assets`/`/lib`/`/images` prefixes. When auth is enabled, the service worker fetch (`/sw.js`) requires `Authorization: Bearer ...`, which browsers don't send for service-worker installs → PWA install/refresh breaks. Fix: add `/sw.js`, `/manifest.json` to the exempt list.

🟡 **`api_auth_login` doesn't validate `token` type** (`app.py:182-186`). `body.get('token')` is passed directly to `verify_token`, which calls `hmac.compare_digest(provided, expected)`. If `provided` is non-`str`/`bytes` (e.g. `null`, `123`, `[]`), `compare_digest` raises `TypeError` → 500. Fix: `token = body.get('token') or ''; if not isinstance(token, str): return 401`.

🟡 **`_tile_count` TOCTOU on cache cap** (`app.py:259-275`). Two concurrent tile requests both see `_tile_count < _TILE_MAX`, both increment, total exceeds cap by N. Cosmetic but cap is not enforced.

🟢 **`urlopen(req, timeout=cfg.TILE_DOWNLOAD_TIMEOUT).read()` has no byte limit** (`app.py:269`). A malicious tile server can stream gigabytes. Operator risk only.

🟢 **`api_terrain_elevation` doesn't bound the points list size** (`app.py:300-320`). `points_str.split(';')` with a 5 MB query string produces millions of points, each triggering a synchronous SRTM lookup. Fix: cap to 200.

🟢 **`api_firmware_online` builds version URLs by string concat without URL-encoding the parsed filename** (`app.py:512`). If the upstream firmware server is hostile, `fname` could contain query-string chars, but this only affects the displayed URL — the user has to copy/click. Low impact.

🟢 **`_BOARD_MAP` is hardcoded to two boards** (`app.py:486-489`). Anything else returns "Unknown board_id". By design.

---

## 5. `backend/auth.py`

🟡 **`_token` is cached forever once loaded** (`auth.py:13-21`). If the operator edits `.gcs_token` to rotate the credential while the server is running, the in-memory `_token` keeps the old value. Fix: stat-check the file or expose `_reload_token()`.

🟡 **Token comparison uses `hmac.compare_digest` but the input isn't validated to be `str|bytes`** (`auth.py:43`). With auth enabled, a malformed request body sending `null` for token causes a 500 (see also app.py finding). Fix: coerce/reject early.

🟢 **Token file is created with `0o600`** (`auth.py:33`) — good.

🟢 **`generate_token` truncates SHA256 to 32 hex chars = 128 bits of entropy** — adequate.

🟢 **`auth_required()` returns `False` by default** (`auth.py:46-47`). This is the documented insecure-by-default model for LAN deployment. The /api/auth/generate route can only run once. Acceptable but the README/UI should make this prominent.

---

## 6. `backend/log.py`

🟢 **Module-level mutation of `logger` handlers** (`log.py:13-16`). If `log.py` is imported twice (which Python prevents via module cache), nothing happens. If anyone uses `logging.getLogger('gcs')` directly elsewhere, they see this handler. Cosmetic.

🟢 **No log file rotation** — the GCS itself doesn't write to disk via the logger (only the dataflash-style CSV does). The stream handler writes to stderr. Acceptable.

---

## 7. `backend/video.py`

🟡 **Hostname-based SSRF bypass** (`video.py:34-41`). `_validate_video_url` calls `ipaddress.ip_address(host)` which only succeeds for raw IP literals. For hostnames (`gcs-internal.lan`), it falls into `except ValueError:` and only blocks the literal strings `'localhost'` and `'localhost.localdomain'`. A DNS name that resolves to `127.0.0.1` or `169.254.169.254` is not detected. Fix: do a `socket.getaddrinfo` resolution and run the `is_private/loopback/reserved` check on the resolved IPs.

🟡 **ffmpeg `-rtsp_transport tcp` is hard-coded** (`video.py:77`). For an `http://`/`https://` URL, ffmpeg ignores the rtsp flag — fine. For `rtmp://`, ffmpeg silently ignores too. Cosmetic.

🟡 **`generate()`'s buffer can grow indefinitely** (`video.py:92-114`). If the MJPEG stream has no JPEG markers (e.g. wrong format), the inner `while True` finds no frame and `buf += chunk` accumulates the entire stream. Fix: cap `buf` to a few MB and reset on overflow.

🟢 **Process lifecycle uses a single `_active_proc` module global** (`video.py:43-44`). Concurrent `/api/video?url=...` calls kill each other's ffmpeg. Documented behavior.

🟢 **`stderr=subprocess.DEVNULL`** (`video.py:86`). ffmpeg errors are not surfaced. Operator UX concern.

---

## 8. `scripts/sim_pllink.py`

🟡 **Simulator listens for log-cancel on mid==126 (SERIAL_CONTROL), not 122 (LOG_REQUEST_END)** (`sim_pllink.py:490`). Backend's `cmd_log_cancel` (`commands/_setup.py:155`) sends MAVLink ID 122. The real ArduPilot FC honors 122 correctly, but in the simulator the cancel is a no-op — the FC continues streaming log data. This masks bugs where the GCS's log-cancel path doesn't actually free the buffer or clear the download-id locally (the only thing that visibly works is the GCS-side state reset). Fix: change `elif mid == 126:` → `elif mid == 122:`. Note the simulator also defines `_helpers.send_serial_control` which DOES send mid==126 (shell text) — those two distinct messages are being conflated.

🟡 **`msg_terrain_report` references `self.alt_rel` which doesn't exist** (`sim_pllink.py:322`). `Simulator.__init__` defines `self.alt`, never `self.alt_rel`. This would raise `AttributeError` if the method were called. Dead code today (no caller in `serve()`), but enabling it would crash.

🟡 **Simulator hard-codes `current_height=alt_rel`** in `msg_terrain_report` — once fixed to `self.alt`, that field maps to "vehicle height above ground"; combined with `terrain_msl` and the GCS-side `handle_terrain_report` reading `terrain_height` (offset 8), the test path is reasonable. Note the GCS only stores `terrain_height` (offset 8) but the docstring says it wants "ground elevation" — the simulator's `terrain_msl=400` matches.

🟡 **`msg_param_value` index field type is wrong (u16 vs documented but ArduPilot u16)** (`sim_pllink.py:384`). `struct.pack('<HH', total, index)` — total then index, packed in `<HH`. The MAVLink layout is `param_count (u16) param_index (u16)`. The order here is `(total, index)` → packed as `(count, index)`. That's correct for the spec field order. Good.

🟡 **`_handle_cmd` for `cmd == 241` accel calibration** (`sim_pllink.py:553-573`). The simulator immediately appends "Accel calibration complete" without going through the orientation sequence. Real ArduPilot sends per-position STATUSTEXTs. Acceptable for a smoke-test simulator but masks the orientation-handling path that was just fixed in commit 68d1561.

🟢 **Simulator hardcodes vehicle type as Copter mode list** (`sim_pllink.py:37-39`). Switching the GCS to "Plane" then issuing a Plane-specific RTL mode (21) would route through `_handle_cmd` ok, but the simulator's `COPTER_MODES` constant labels them as Copter modes. Cosmetic.

🟢 **`msg_log_data` builds chunks per call rather than streaming** (`sim_pllink.py:483-488`). A 2 KB log produces 23 LOG_DATA messages all sent in one `handle_mavlink` cycle without backpressure. Real FCs throttle. Cosmetic.

🟢 **`Simulator.tick(0.05)` and the outer `time.sleep(0.05)` mean simulator time runs at exactly real-time** — no fast-forward. By design.

---

## Cross-cutting Notes

- **CRC_EXTRA table in `drone_link.py:49-57` matches the authoritative ArduPilot `MAVLINK_MESSAGE_CRCS` macro** (verified against ArduPilot build output `ardupilotmega.h`). No discrepancies in the verified subset (IDs 0,1,22,24,30,33,36,42-47,51,65,70,73-77,116-126,136,147,148,158,163,168,178,191-193,233,241,242,246,253,310,311).
- **No memory leak in `_unknown_msg_ids`** is a 🟢: bounded by 2^24 IDs but realistically only a handful of unique IDs ever appear.
- **`_msg_stats` does grow per unique message ID seen, never pruned** (`drone_link.py:108`). Inspector mode only — cosmetic.

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 5 |
| 🟡 Medium | 23 |
| 🟢 Low | 20 |

### Critical findings (prioritized)
1. **`ws_manager.py:132`** — No role enforcement; any client can send arm/disarm/mode commands.
2. **`ws_manager.py:54-72`** — `_pilot_ws` and `_roles` leak on disconnect; next observer auto-becomes pilot.
3. **`ws_manager.py:46-52`** — `broadcast` doesn't catch `WebSocketDisconnect`; one client disconnect can kick another.
4. **`app.py:538`** — Path traversal in `/api/firmware/download` (`filename` not sanitized like upload route).
5. **`app.py:528`** — SSRF in `/api/firmware/download` (no host blocklist; unlike `video.py`).
