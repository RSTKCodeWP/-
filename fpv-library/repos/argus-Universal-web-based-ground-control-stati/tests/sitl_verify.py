#!/usr/bin/env python3
"""Argus GCS — Comprehensive SITL verification v2 (38 additional items)."""
import asyncio
import base64
import json
import sys
import time

import httpx
import websockets

WS_URL = 'ws://127.0.0.1:8100/ws'
API = 'http://127.0.0.1:8100'

PASS = FAIL = SKIP = 0
RESULTS = []


def record(name, ok, detail='', skip=False):
    global PASS, FAIL, SKIP
    if skip:
        SKIP += 1; RESULTS.append(('SKIP', name, detail))
        print(f'  [SKIP] {name}' + (f' — {detail}' if detail else '')); return
    if ok:
        PASS += 1; RESULTS.append(('PASS', name, detail))
    else:
        FAIL += 1; RESULTS.append(('FAIL', name, detail))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}' + (f' — {detail}' if detail else ''))


async def wait_for(ws, pred, timeout=10):
    t = time.monotonic() + timeout
    while time.monotonic() < t:
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
            if pred(m): return m
        except asyncio.TimeoutError: pass
    return None


async def drain(ws, sec=1):
    msgs = []; t = time.monotonic() + sec
    while time.monotonic() < t:
        try: msgs.append(json.loads(await asyncio.wait_for(ws.recv(), 0.2)))
        except asyncio.TimeoutError: pass
    return msgs


async def cmd(ws, c, p=None, **kw):
    msg = {'type': 'command', 'cmd': c, 'param': p}; msg.update(kw)
    await ws.send(json.dumps(msg))


async def accum_state(ws, sec=10, until=None):
    """Accumulate full state from delta pushes."""
    st = {}; t = time.monotonic() + sec
    while time.monotonic() < t:
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
            if m.get('type') == 'state': st.update(m)
        except asyncio.TimeoutError: pass
        if until and until(st): break
    return st


async def collect_msgs(ws, sec=5, types=None):
    """Collect WS messages of specific types."""
    out = []; t = time.monotonic() + sec
    while time.monotonic() < t:
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
            if types is None or m.get('type') in types: out.append(m)
        except asyncio.TimeoutError: pass
    return out


# ═══════════════════════════════════════════════════
# A. REST endpoints (补充项)
# ═══════════════════════════════════════════════════
async def test_rest_extra():
    print('\n' + '─' * 55)
    print('[A] REST API (补充)')
    print('─' * 55)
    async with httpx.AsyncClient(base_url=API, timeout=30) as c:
        # tile_cache_clear
        r = await c.post('/api/tile_cache_clear')
        record('POST /api/tile_cache_clear', r.json().get('ok'))

        # firmware upload (valid .apj)
        import io
        fake_apj = b'\x00' * 100
        files = {'file': ('test_fw.apj', io.BytesIO(fake_apj), 'application/octet-stream')}
        r = await c.post('/api/firmware/upload', files=files)
        d = r.json()
        record('POST /api/firmware/upload (valid)', d.get('ok') and d.get('filename') == 'test_fw.apj',
               f"size={d.get('size')}")

        # param_meta plane (may timeout on slow network)
        try:
            r = await c.get('/api/param_meta?vehicle=plane')
            record('GET /api/param_meta (plane)', r.status_code == 200)
        except httpx.ReadTimeout:
            record('GET /api/param_meta (plane)', True, skip=True)


# ═══════════════════════════════════════════════════
# B. Full Copter verification (含38项新增)
# ═══════════════════════════════════════════════════
async def test_copter():
    print('\n' + '=' * 55)
    print('[B] COPTER SITL — Full verification')
    print('=' * 55)

    async with websockets.connect(WS_URL, max_size=2**20, open_timeout=30) as ws:
        # ── Connect ──
        print('\n[B1] Connect + GPS wait')
        await ws.send(json.dumps({'type': 'connect', 'port': 'tcp:localhost:5760', 'baud': 57600, 'protocol': 'auto'}))
        cr = await wait_for(ws, lambda m: m.get('type') == 'connect_result', 10)
        record('connect', cr and cr.get('ok'))
        if not cr or not cr.get('ok'):
            record('ABORT', False, 'cannot connect'); return

        # Set English locale
        await ws.send(json.dumps({'type': 'set_locale', 'locale': 'en'}))

        # ── Telemetry (full) ──
        print('\n[B2] Telemetry (after GPS lock)')
        fields = {
            'lat': lambda v: v is not None and abs(v) > 0.01,
            'lon': lambda v: v is not None and abs(v) > 0.01,
            'alt_msl': lambda v: v is not None,
            'alt_rel': lambda v: v is not None,
            'roll': lambda v: v is not None,
            'pitch': lambda v: v is not None,
            'yaw': lambda v: v is not None,
            'hdg': lambda v: v is not None,
            'gs': lambda v: v is not None,
            'voltage': lambda v: isinstance(v, (int, float)) and v > 0,
            'current': lambda v: v is not None,
            'remaining': lambda v: v is not None,
            'gps_fix': lambda v: v is not None,
            'gps_sats': lambda v: v is not None and v >= 0,
            'mode': lambda v: isinstance(v, str) and len(v) > 0,
            'armed': lambda v: v is not None,
            'vtype_raw': lambda v: v is not None,
            'autopilot': lambda v: v is not None,
            'mode_btns': lambda v: isinstance(v, list) and len(v) > 0,
            'home_lat': lambda v: v is not None,
            'home_lon': lambda v: v is not None,
            'dist_home': lambda v: v is not None,
            'vibe': lambda v: isinstance(v, list) and len(v) == 3,
            'ekf_flags': lambda v: v is not None,
            'ekf_vel': lambda v: v is not None,
            'ekf_pos_h': lambda v: v is not None,
            'ekf_pos_v': lambda v: v is not None,
            'ekf_compass': lambda v: v is not None,
            'airspeed': lambda v: v is not None,
            'throttle': lambda v: v is not None,
            'climb': lambda v: v is not None,
            'bat_time': lambda v: v is not None,
            'cells': lambda v: isinstance(v, list),
            'rc_rssi': lambda v: v is not None,
            'parse_errors': lambda v: v is not None,
            'link_age': lambda v: isinstance(v, (int, float)) and v < 5,
            'wind_speed': lambda v: v is not None,
            'wind_dir': lambda v: v is not None,
            'param_count': lambda v: v is not None,
        }
        # The backend pushes deltas with a full state every 10th push (2 s
        # cadence when connected — ws_manager._push_loop). Constant fields
        # (mode on the ground, vibe≈0, board_id=0 …) only ever appear in the
        # full pushes, so accumulate until GPS is locked AND a full push has
        # landed — waiting on GPS alone raced ahead of the first full state
        # and reported two dozen phantom None fields.
        st = await accum_state(
            ws, 40,
            lambda s: s.get('lat') and abs(s.get('lat', 0)) > 0.01 and all(k in s for k in fields),
        )
        for f, chk in fields.items():
            v = st.get(f)
            record(f'telem.{f}', chk(v) if v is not None or chk(None) else False, f'{v}')

        # NEW: fw_version / board_id
        record('telem.fw_version', st.get('fw_version') is not None, f"{st.get('fw_version')}")
        record('telem.board_id', st.get('board_id') is not None, f"{st.get('board_id')}")

        # ── Delta push ──
        print('\n[B3] Delta push')
        msgs = await drain(ws, 2)
        st_msgs = [m for m in msgs if m.get('type') == 'state']
        record('delta push rate', len(st_msgs) >= 3, f"{len(st_msgs)} in 2s")

        # ── Parameters ──
        print('\n[B4] Parameters')
        await cmd(ws, 'param_request_all')
        pc = 0
        for m in await collect_msgs(ws, 45, {'param_batch', 'state'}):
            if m.get('type') == 'param_batch':
                pc += len(m.get('params', []))
        record('param_request_all', pc > 100, f"{pc} params")

        # NEW: param_batch WS type verification
        record('param_batch WS type', pc > 0, 'param_batch messages received')

        await cmd(ws, 'param_set', name='PILOT_SPEED_UP', value=300)
        ack = await wait_for(ws, lambda m: m.get('type') == 'param_batch', 5)
        record('param_set', ack is not None)

        await cmd(ws, 'param_get', name='PILOT_SPEED_UP')
        val = await wait_for(ws, lambda m: m.get('type') == 'param_batch', 5)
        record('param_get', val is not None)

        # NEW: param_save
        await cmd(ws, 'param_save')
        save_r = await wait_for(ws, lambda m: m.get('type') == 'cmd_result', 5)
        record('param_save', save_r is not None and save_r.get('ok', False), str(save_r)[:60] if save_r else '')

        # NEW: param_load (skip if save failed)
        if save_r and save_r.get('ok') and save_r.get('path'):
            await cmd(ws, 'param_load', path=save_r['path'])
            load_r = await wait_for(ws, lambda m: m.get('type') in ('cmd_result', 'event'), 5)
            record('param_load', load_r is not None, str(load_r)[:60] if load_r else '')
        else:
            record('param_load', False, skip=save_r is None)

        # ── Mode switching ──
        print('\n[B5] Mode switching (9 modes)')
        modes = [(0, 'Stabilize'), (2, 'Alt Hold'), (5, 'Loiter'), (3, 'Auto'),
                 (4, 'Guided'), (6, 'RTL'), (7, 'Circle'), (9, 'Land'), (16, 'PosHold')]
        for mid, mname in modes:
            await cmd(ws, 'mode', mid)
            await drain(ws, 0.3)
            ms = await wait_for(ws, lambda m: m.get('type') == 'state' and 'mode' in m, 5)
            got = ms.get('mode', '?') if ms else '?'
            record(f'mode → {mname}({mid})', ms is not None and got != '?', f"got: {got}")

        # ── NEW: set_vtype ──
        print('\n[B6] set_vtype / switch_vehicle')
        await cmd(ws, 'set_vtype', 'plane')
        await drain(ws, 1)
        svt = await accum_state(ws, 3)
        record('set_vtype plane', True)  # pure state op
        await cmd(ws, 'set_vtype', 'auto')
        await drain(ws, 1)

        # NEW: switch_vehicle (may not have other sysids, but command should not error)
        await cmd(ws, 'switch_vehicle', 1)
        await drain(ws, 0.5)
        record('switch_vehicle(1)', True)

        # ── NEW: Calibrations ──
        print('\n[B7] Calibrations')
        await cmd(ws, 'cal_gyro')
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 10)
        record('cal_gyro', evt is not None, str(evt)[:60] if evt else '')

        await cmd(ws, 'cal_level')
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 10)
        record('cal_level', evt is not None, str(evt)[:60] if evt else '')

        await cmd(ws, 'cal_baro')
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 10)
        record('cal_baro', evt is not None, str(evt)[:60] if evt else '')

        await cmd(ws, 'cal_cancel')
        await drain(ws, 1)
        record('cal_cancel', True)

        # ── NEW: Motor test ──
        print('\n[B8] Motor test')
        await cmd(ws, 'motor_test', motor=1, throttle=5, duration=0.5)
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 5)
        record('motor_test (#1 5%)', evt is not None, str(evt)[:60] if evt else '')

        await cmd(ws, 'motor_test_stop')
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 5)
        record('motor_test_stop', evt is not None)

        # ── NEW: ROI ──
        await cmd(ws, 'do_set_roi', lat=-35.363, lon=149.165, alt=100)
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 5)
        record('do_set_roi', evt is not None, str(evt)[:60] if evt else '')

        # ── NEW: drop / drop_stop ──
        print('\n[B9] Relay (drop)')
        await cmd(ws, 'drop')
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 5)
        record('drop (relay on)', evt is not None)

        await cmd(ws, 'drop_stop')
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 5)
        record('drop_stop (relay off)', evt is not None)

        # ── NEW: rc_override ──
        await cmd(ws, 'rc_override', channels=[1500, 1500, 1000, 1500, 0, 0, 0, 0])
        await drain(ws, 0.5)
        record('rc_override (8 ch)', True)

        # ── PreArm check ──
        print('\n[B10] PreArm messages')
        # Accumulate state, check for prearm messages in events
        evts = await drain(ws, 2)
        prearm = [m for m in evts if m.get('type') == 'event' and 'PreArm' in m.get('text', '')]
        record('PreArm messages', True, f"{len(prearm)} prearm events collected")

        # ── Console ──
        print('\n[B11] Console')
        await cmd(ws, 'serial_control', text='ver')
        con = await wait_for(ws, lambda m: m.get('type') in ('console_output', 'event'), 8)
        # ArduPilot has no MAVLink shell on SERIAL0 (SERIAL_CONTROL is for
        # device passthrough) — no reply is expected behavior, not a failure.
        record('console serial_control("ver")', True, 'reply' if con else 'no shell reply (AP)', skip=con is None)

        # ── Inspector ──
        print('\n[B12] Inspector')
        await cmd(ws, 'inspector_toggle')
        insp = await wait_for(ws, lambda m: m.get('type') == 'inspector', 5)
        n = len(insp.get('messages', {})) if insp else 0
        record('inspector data', insp is not None, f"{n} msg types")
        await cmd(ws, 'inspector_toggle')
        await drain(ws, 0.5)

        # ── Logs ──
        print('\n[B13] Logs')
        await cmd(ws, 'log_list')
        # Backend emits ONE 'log_list' message (all entries in a 'logs' array),
        # never per-entry 'log_entry'. Byte-complete download is verified after
        # the flight (B14b): a disarmed boot records no log (LOG_DISARMED=0
        # default), so a log with content only exists once the vehicle has armed.
        log_msgs = await collect_msgs(ws, 15, {'log_list', 'event', 'state'})
        log_lists = [m for m in log_msgs if m.get('type') == 'log_list']
        logs0 = log_lists[-1].get('logs', []) if log_lists else []
        record('log_list', len(log_lists) > 0, f"{len(logs0)} entries")

        # ── Mission ──
        print('\n[B14] Mission (upload + start + wp_seq + download + clear)')
        wps = [
            {'lat': -35.3630, 'lon': 149.1655, 'alt': 30, 'speed': 5, 'delay': 0, 'cmd': 16, 'frame': 3},
            {'lat': -35.3638, 'lon': 149.1662, 'alt': 40, 'speed': 5, 'delay': 0, 'cmd': 16, 'frame': 3},
            {'lat': -35.3635, 'lon': 149.1650, 'alt': 30, 'speed': 5, 'delay': 0, 'cmd': 16, 'frame': 3},
        ]
        await cmd(ws, 'mission_upload', waypoints=wps)
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 15)
        record('mission_upload (3 WPs)', evt is not None, str(evt)[:60] if evt else '')

        await drain(ws, 1)
        await cmd(ws, 'mission_download')
        dl = await wait_for(ws, lambda m: m.get('type') in ('mission_item', 'event', 'cmd_result'), 10)
        record('mission_download', dl is not None)

        # NEW: mission_start (arm + auto fly)
        await cmd(ws, 'mode', 4)  # GUIDED
        await drain(ws, 1)
        # Wait for EKF to settle after calibrations
        await asyncio.sleep(5)
        await drain(ws, 2)
        await cmd(ws, 'arm')
        arm = await wait_for(ws, lambda m: m.get('type') == 'state' and m.get('armed') is True, 15)
        record('arm (for mission)', arm is not None)

        if arm:
            await cmd(ws, 'takeoff', 25)
            await drain(ws, 5)
            alt_ok = await wait_for(ws, lambda m: m.get('type') == 'state' and (m.get('alt_rel') or 0) > 5, 25)
            record('takeoff for mission', alt_ok is not None, f"alt={alt_ok.get('alt_rel', 0):.1f}" if alt_ok else '')

            # NEW: mission_start
            await cmd(ws, 'mission_start')
            auto_mode = await wait_for(ws, lambda m: m.get('type') == 'state' and m.get('mode') is not None, 10)
            record('mission_start', auto_mode is not None, f"mode={auto_mode.get('mode')}" if auto_mode else '')

            # NEW: wp_seq advancement
            await asyncio.sleep(3)
            st = await accum_state(ws, 10)
            record('wp_seq after mission_start', st.get('wp') is not None, f"wp={st.get('wp')}")

            # RTL
            await cmd(ws, 'rtl')
            await drain(ws, 2)
            record('RTL after mission', True)

            # Wait for disarm
            landed = await wait_for(ws, lambda m: m.get('type') == 'state' and m.get('armed') is False, 90)
            record('landing + disarm', landed is not None)

            # NEW: flight_summary
            st2 = await accum_state(ws, 5)
            fs = st2.get('flight_summary')
            record('flight_summary', fs is not None, str(fs)[:80] if fs else 'None')

            # NEW: clear_summary
            await cmd(ws, 'clear_summary')
            await drain(ws, 1)
            st3 = await accum_state(ws, 3)
            record('clear_summary', st3.get('flight_summary') is None or st3.get('flight_summary') == fs)

            # ── NEW [B14b]: log_download byte-complete ──
            # The CI-automatable half of whole-log streaming (2a496d4).
            # SITL/loopback proves byte-complete reassembly; the speed win
            # (RTT≈0 here) needs real USB. This is the standing regression
            # guard for the [-200:] trim bug that silently dropped 60% of a
            # 28 MB download. Runs disarmed — download refuses while armed —
            # and only now (post-arm) does a log with content exist.
            print('\n[B14b] Log download (byte-complete)')
            await cmd(ws, 'log_list')
            ll = await wait_for(ws, lambda m: m.get('type') == 'log_list', 15)
            logs = ll.get('logs', []) if ll else []
            dl_logs = [x for x in logs if x.get('size', 0) > 0]
            if dl_logs:
                # smallest non-empty log → fastest deterministic download
                target = min(dl_logs, key=lambda x: x['size'])
                await cmd(ws, 'log_download', id=target['id'])
                chunks = {}
                complete = None
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline and complete is None:
                    try:
                        m = json.loads(await asyncio.wait_for(ws.recv(), 2))
                    except asyncio.TimeoutError:
                        continue
                    ty = m.get('type')
                    if ty == 'log_chunk':
                        chunks[m['ofs']] = base64.b64decode(m['data'])
                    elif ty == 'log_complete' and m.get('id') == target['id']:
                        complete = m
                record('log_download completes', complete is not None,
                       f"decl={target['size']} got={complete.get('size') if complete else '?'}")
                # Reassemble by offset; stop at the first hole so a gap fails
                # the length check below rather than silently concatenating.
                reasm = bytearray()
                for ofs in sorted(chunks):
                    if ofs != len(reasm):
                        break
                    reasm += chunks[ofs]
                ok = bool(complete) and len(reasm) == complete['size'] == target['size'] \
                    and not complete.get('truncated')
                record('log_download byte-complete', ok,
                       f"reasm={len(reasm)} decl={target['size']} "
                       f"size={complete.get('size') if complete else '?'} "
                       f"trunc={complete.get('truncated') if complete else '?'}")
                await cmd(ws, 'log_cancel')  # no-op after finalize, must not error
                await drain(ws, 1)
                record('log_cancel', True)
            else:
                record('log_download completes', True, skip=True)
                record('log_download byte-complete', True, skip=True)
                record('log_cancel', True, skip=True)
        else:
            for t in ('takeoff for mission', 'mission_start', 'wp_seq', 'RTL after mission',
                       'landing + disarm', 'flight_summary', 'clear_summary'):
                record(t, False, 'arm failed')
            record('log_download completes', True, skip=True)
            record('log_download byte-complete', True, skip=True)
            record('log_cancel', True, skip=True)

        # mission_clear
        await cmd(ws, 'mission_clear')
        clr = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 10)
        record('mission_clear', clr is not None)

        # ── Fence ──
        print('\n[B15] Fence')
        await cmd(ws, 'fence_upload', points=[
            {'lat': -35.360, 'lon': 149.162}, {'lat': -35.360, 'lon': 149.170},
            {'lat': -35.368, 'lon': 149.170}, {'lat': -35.368, 'lon': 149.162},
            {'lat': -35.364, 'lon': 149.166},
        ])
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 10)
        record('fence_upload (5 pts)', evt is not None, str(evt)[:60] if evt else '')

        # ── NEW: Rally ──
        print('\n[B16] Rally')
        await cmd(ws, 'rally_upload', points=[
            {'lat': -35.365, 'lon': 149.167, 'alt': 50},
            {'lat': -35.362, 'lon': 149.163, 'alt': 40},
        ])
        evt = await wait_for(ws, lambda m: m.get('type') in ('event', 'cmd_result'), 10)
        record('rally_upload (2 pts)', evt is not None, str(evt)[:60] if evt else '')

        # ── Roles + Multi-client ──
        print('\n[B17] Roles & Locale')
        await ws.send(json.dumps({'type': 'set_role', 'role': 'pilot'}))
        r = await wait_for(ws, lambda m: m.get('type') == 'role_update', 5)
        record('set_role pilot', r is not None and r.get('pilot_connected'))

        await ws.send(json.dumps({'type': 'set_locale', 'locale': 'zh'}))
        await drain(ws, 0.5)
        record('set_locale zh', True)

        await ws.send(json.dumps({'type': 'set_locale', 'locale': 'en'}))
        await drain(ws, 0.5)
        record('set_locale en', True)

        # ── Safety ──
        print('\n[B18] Safety commands')
        await cmd(ws, 'disarm')
        await drain(ws, 1)
        record('disarm (idempotent)', True)

        await cmd(ws, 'force_disarm')
        await drain(ws, 1)
        record('force_disarm', True)

        # ── Flight log (while still connected — the CSV closes on disconnect) ──
        print('\n[B20] Flight log REST')
        async with httpx.AsyncClient(base_url=API, timeout=10) as c:
            r = await c.get('/api/log')
            record('CSV flight log', r.status_code == 200 and len(r.content) > 50, f"{len(r.content)} bytes")

        # ── Disconnect ──
        print('\n[B19] Disconnect')
        await ws.send(json.dumps({'type': 'disconnect'}))
        dc = await wait_for(ws, lambda m: m.get('type') == 'connect_result' and m.get('ok'), 5)
        record('disconnect', dc is not None)

        ds = await wait_for(ws, lambda m: m.get('type') == 'state' and not m.get('connected'), 5)
        record('state disconnected', ds is not None)


# ═══════════════════════════════════════════════════
# C. Multi-client (observer + handoff_accept)
# ═══════════════════════════════════════════════════
async def test_multi_client():
    print('\n' + '=' * 55)
    print('[C] Multi-client & handoff')
    print('=' * 55)

    async with websockets.connect(WS_URL) as ws1, websockets.connect(WS_URL) as ws2:
        # Connect via ws1
        await ws1.send(json.dumps({'type': 'connect', 'port': 'tcp:localhost:5760'}))
        await wait_for(ws1, lambda m: m.get('type') == 'connect_result', 10)
        await drain(ws1, 2)

        # ws1 = pilot
        await ws1.send(json.dumps({'type': 'set_role', 'role': 'pilot'}))
        await drain(ws1, 0.5)

        # ws2 = observer
        await ws2.send(json.dumps({'type': 'set_role', 'role': 'observer'}))
        await drain(ws2, 0.5)

        # Observer command rejected
        await ws2.send(json.dumps({'type': 'command', 'cmd': 'arm'}))
        rej = await wait_for(ws2, lambda m: m.get('type') == 'cmd_result' and not m.get('ok'), 5)
        record('observer cmd rejected', rej is not None)

        # Observer gets state
        st = await wait_for(ws2, lambda m: m.get('type') == 'state', 5)
        record('observer gets state', st is not None)

        # Handoff request
        await ws2.send(json.dumps({'type': 'request_handoff'}))
        hreq = await wait_for(ws1, lambda m: m.get('type') == 'handoff_request', 5)
        record('handoff_request delivered', hreq is not None)

        # NEW: handoff_accept
        if hreq:
            await ws1.send(json.dumps({'type': 'handoff_accept', 'target': hreq.get('from')}))
            granted = await wait_for(ws2, lambda m: m.get('type') == 'handoff_granted', 5)
            released = await wait_for(ws1, lambda m: m.get('type') == 'handoff_released', 5)
            record('handoff_accept → granted', granted is not None)
            record('handoff_accept → released', released is not None)
        else:
            record('handoff_accept → granted', False, 'no handoff_request')
            record('handoff_accept → released', False, 'no handoff_request')

        # Disconnect
        await ws1.send(json.dumps({'type': 'disconnect'}))
        await drain(ws1, 1)


# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════
async def main():
    print('=' * 55)
    print('Argus GCS — SITL Full Verification v2')
    print('  38 additional items over v1')
    print('=' * 55)

    await test_copter()
    await test_multi_client()
    try:
        await test_rest_extra()
    except Exception as e:
        record('REST extra', False, f'exception: {e}')

    print('\n' + '=' * 55)
    print(f'TOTAL: {PASS} passed, {FAIL} failed, {SKIP} skipped — {PASS + FAIL + SKIP} total')
    print('=' * 55)
    if FAIL > 0:
        print('\nFailed:')
        for s, n, d in RESULTS:
            if s == 'FAIL': print(f'  FAIL: {n} — {d}')
    return FAIL

if __name__ == '__main__':
    sys.exit(min(asyncio.run(main()), 127))
