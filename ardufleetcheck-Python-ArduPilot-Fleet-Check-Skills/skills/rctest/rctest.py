#!/usr/bin/env python3
"""/rctest — verify a Betaflight OR ArduPilot FC is receiving live RC frames.

Autodetects firmware:
  - Betaflight  : MSP_RC (cmd 105)        + MSP_STATUS_EX armingDisable flags
  - ArduPilot   : RC_CHANNELS MAVLink msg + SYS_STATUS RC_RECEIVER health bit

Same verdict logic for both: a live link shows ANY of:
  - throttle outside the typical resting band
  - any AUX channel thrown to an extreme (<= 1400 or >= 1600)
  - sample-to-sample jitter > 2us on at least one channel

A no-input link looks like: all channels frozen, no AUX thrown, throttle pinned.

Port resolution:
  - /dev/cu.usbmodem*       (preferred — direct USB to FC)
  - /dev/cu.usbserial-0001  (fallback — RC-MAVLink dongle @ 460800, AP only)

CLI:
  rctest.py                                   # default 3s sample window
  rctest.py --duration 5                      # longer window
  rctest.py --port /dev/cu.usbmodem...        # explicit port
  rctest.py --raw                             # dump every sample, not the summary
  rctest.py --force-ap | --force-bf           # skip autodetect
"""
import argparse
import glob
import struct
import sys
import time


CHAN_NAMES = ['roll', 'pitch', 'throttle', 'yaw',
              'aux1', 'aux2', 'aux3', 'aux4',
              'aux5', 'aux6', 'aux7', 'aux8',
              'aux9', 'aux10', 'aux11', 'aux12']

# BF arming-disable flag bit names, in bit order. This list matches the
# `runtimeConfig.h` enum used by BF 4.3–4.5; new bits are appended at the
# end across versions, so unknown high bits show as "BIT_N".
ARMING_DISABLE_FLAGS = [
    'NO_GYRO', 'FAILSAFE', 'RX_FAILSAFE', 'BAD_RX_RECOVERY',
    'BOXFAILSAFE', 'RUNAWAY_TAKEOFF', 'CRASH_DETECTED', 'THROTTLE',
    'ANGLE', 'BOOT_GRACE_TIME', 'NOPREARM', 'LOAD',
    'CALIBRATING', 'CLI', 'CMS_MENU', 'BST',
    'MSP', 'PARALYZE', 'GPS', 'RESC',
    'RPMFILTER', 'REBOOT_REQUIRED', 'DSHOT_BITBANG', 'ACC_CALIBRATION',
    'MOTOR_PROTOCOL', 'ARM_SWITCH',
]

# MAV_SYS_STATUS_SENSOR_RC_RECEIVER = 0x40000 (bit 18)
RC_RECEIVER_HEALTH_BIT = 1 << 18


def log(msg):
    print(f"[rctest] {msg}", file=sys.stderr, flush=True)


def list_usbmodem_ports():
    return sorted(glob.glob('/dev/cu.usbmodem*'))


def list_usbserial_ports():
    return sorted(glob.glob('/dev/cu.usbserial-*'))


# ---------- Betaflight MSP (v1)

class MSP:
    def __init__(self, port, baud=115200):
        import serial
        self.s = serial.Serial(port, baud, timeout=0.3)
        time.sleep(0.3)

    def close(self):
        try: self.s.close()
        except Exception: pass

    def v1(self, cmd, payload=b'', wait=0.4):
        size = len(payload)
        frame = b'$M<' + bytes([size, cmd]) + payload
        cs = 0
        for b in frame[3:]:
            cs ^= b
        frame += bytes([cs])
        self.s.write(frame); self.s.flush()
        end = time.time() + wait
        buf = b''
        while time.time() < end:
            c = self.s.read(256)
            if c:
                buf += c
                idx = buf.find(b'$M>')
                if idx >= 0 and len(buf) >= idx + 6:
                    sz = buf[idx+3]
                    if len(buf) >= idx + 5 + sz + 1:
                        return buf[idx+5:idx+5+sz]
        return None


def msp_probe_variant(port, timeout=1.0):
    """Return FC variant string (e.g. 'BTFL') or None if port doesn't speak MSP."""
    try:
        msp = MSP(port)
    except Exception:
        return None
    try:
        r = msp.v1(2, wait=timeout)
        if r and len(r) >= 4:
            return r[:4].decode('ascii', errors='replace')
        return None
    finally:
        msp.close()


def probe_mavlink(port, baud=115200, attempts=3, per_attempt=4.0):
    """MAVLink-first AP probe.

    Opens pymavlink with our GCS identity, sends 4× HEARTBEAT(MAV_TYPE_GCS)
    over ~0.8s to keep AP's USB CDC in MAVLink mode (it multiplexes MSP+MAV,
    and an MSP-first speaker can lock USB into MSP and stop MAVLink streaming
    until power-cycle), then waits for an FC HEARTBEAT.

    Retries up to `attempts` because AP's USB multiplexer can take a moment
    to switch back from MSP if a prior poll locked it.

    Returns True iff any HEARTBEAT was decoded. Closes the connection cleanly
    so the caller can reopen for the actual session.

    BF FCs don't speak MAVLink at all — this just times out harmlessly there.
    """
    try:
        from pymavlink import mavutil
    except ImportError:
        log("pymavlink not installed — can't probe MAVLink")
        return False
    for attempt in range(1, attempts + 1):
        m = None
        try:
            m = mavutil.mavlink_connection(port, baud=baud,
                                           source_system=255, source_component=190)
            for _ in range(4):
                m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                     mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                time.sleep(0.2)
            hb = m.wait_heartbeat(timeout=per_attempt)
            if hb is not None:
                log(f"MAVLink heartbeat received (attempt {attempt}/{attempts})")
                return True
            log(f"  no heartbeat (attempt {attempt}/{attempts})")
        except Exception as e:
            log(f"  MAVLink probe error (attempt {attempt}/{attempts}): {e}")
        finally:
            if m is not None:
                try: m.close()
                except Exception: pass
            time.sleep(0.3)
    return False


def bf_read_rc(msp):
    """MSP_RC (cmd 105) → list of channel values (uint16 us)."""
    r = msp.v1(105, wait=0.4)
    if not r or len(r) < 2:
        return None
    n = len(r) // 2
    return list(struct.unpack(f'<{n}H', r[:n*2]))


def bf_read_status_ex(msp):
    """MSP_STATUS_EX (cmd 150). Returns dict of fields we care about, or None.

    Layout (BF 4.x), little-endian:
      u16 cycleTime
      u16 i2c_errors
      u16 sensor flags
      u32 mode flags  (low 32 of activeFlightModes)
      u8  currentPidProfile
      u16 cpuLoadPercent
      u8  flightModeFlagsCount
      u8  armingDisableFlagsCount  (number of *defined* bits, NOT a length)
      u32 armingDisableFlags
      u8  configStateFlag
    Newer builds append:
      u16 cpuTemperature
      u16 averageSystemLoadPercent
    """
    r = msp.v1(150, wait=0.6)
    if not r or len(r) < 20:
        return None
    try:
        cycleTime    = struct.unpack_from('<H', r, 0)[0]
        i2c_errors   = struct.unpack_from('<H', r, 2)[0]
        sensors      = struct.unpack_from('<H', r, 4)[0]
        modeFlags    = struct.unpack_from('<I', r, 6)[0]
        pidProfile   = r[10]
        cpuLoad      = struct.unpack_from('<H', r, 11)[0]
        # 13: flightModeFlagsCount, 14: armingDisableFlagsCount
        armDisable   = struct.unpack_from('<I', r, 15)[0]
        return {
            'cycleTime': cycleTime,
            'i2c_errors': i2c_errors,
            'sensors': sensors,
            'modeFlags': modeFlags,
            'pidProfile': pidProfile,
            'cpuLoad': cpuLoad,
            'armingDisable': armDisable,
        }
    except struct.error:
        return None


def decode_arming_disable(flags):
    if not flags:
        return []
    out = []
    for i in range(32):
        if flags & (1 << i):
            out.append(ARMING_DISABLE_FLAGS[i] if i < len(ARMING_DISABLE_FLAGS) else f'BIT_{i}')
    return out


def bf_sample_rc(msp, duration, on_sample=None):
    """Sample MSP_RC for `duration` seconds, returning list of (t_ms, channels)."""
    samples = []
    t0 = time.time()
    while time.time() - t0 < duration:
        rc = bf_read_rc(msp)
        if rc:
            t_ms = int((time.time() - t0) * 1000)
            samples.append((t_ms, rc))
            if on_sample:
                on_sample(t_ms, rc)
        # MSP_RC is cheap — let it run as fast as the FC will respond
    return samples


def bf_print_status_summary(status):
    if not status:
        print("  MSP_STATUS_EX: <no response>")
        return
    flags = decode_arming_disable(status['armingDisable'])
    print(f"  cycleTime={status['cycleTime']}us  cpuLoad={status['cpuLoad']}%")
    if not flags:
        print(f"  armingDisable: <none> — FC believes it is arm-ready")
    else:
        rx_related = [f for f in flags if f in ('FAILSAFE', 'RX_FAILSAFE', 'BAD_RX_RECOVERY', 'BOXFAILSAFE')]
        if rx_related:
            print(f"  armingDisable (RX-related): {', '.join(rx_related)}  <-- RX link bad / failsafe active")
        else:
            print(f"  armingDisable: {', '.join(flags)}  (none are RX-related)")
    print()


# ---------- ArduPilot MAVLink

def ap_connect(port, baud, timeout=10.0):
    """Open a MAVLink connection, advertise our GCS heartbeat, and confirm an
    ArduPilot heartbeat.

    We MUST send a few GCS heartbeats immediately after opening — AP's USB CDC
    multiplexes MSP+MAVLink, and a prior MSP poll (or simply not announcing
    ourselves) can leave the channel in MSP mode with no MAVLink stream. See
    feedback_ap_mavlink_first_detection.md.
    """
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(port, baud=baud,
                                   source_system=255, source_component=190)
    for _ in range(4):
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        time.sleep(0.2)
    hb = m.wait_heartbeat(timeout=timeout)
    if hb is None:
        m.close()
        return None
    if hb.autopilot != 3:  # MAV_AUTOPILOT_ARDUPILOTMEGA
        m.close()
        return None
    return m


def ap_request_rc_stream(m, rate_hz=50):
    """Ask the FC to stream RC_CHANNELS at a known rate.

    Uses MAV_CMD_SET_MESSAGE_INTERVAL (rate-based, MAVLink2 standard).
    Falls back gracefully if the FC ignores it — the default SR1_RC_CHAN
    stream rate (usually 5Hz) is enough for a coarse jitter read.
    """
    from pymavlink import mavutil
    msg_id_rc_channels = 65
    interval_us = int(1_000_000 / max(1, rate_hz))
    try:
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            msg_id_rc_channels, interval_us,
            0, 0, 0, 0, 0)
    except Exception:
        pass


def ap_read_rc_health(m, timeout=2.0):
    """Read SYS_STATUS from the autopilot component (not a peripheral) and
    decode RC_RECEIVER health/present/enabled bits.

    Peripherals (gimbals, companion computers, OSD daughterboards) also
    publish SYS_STATUS with their own sensor-bit conventions — typically all
    zeros for RC_RECEIVER, since they don't own RC. An unfiltered recv_match
    can grab one of those by accident and produce a bogus "RC_RECEIVER
    unhealthy" reading.
    """
    from pymavlink import mavutil
    autopilot_compid = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1  # = 1
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        msg = m.recv_match(type='SYS_STATUS', blocking=True, timeout=remaining)
        if msg is None:
            return None
        # Only trust SYS_STATUS from the autopilot itself (compid=1). pymavlink's
        # target_component often stays at 0 (broadcast) even after heartbeat, so
        # don't filter on that — pin to MAV_COMP_ID_AUTOPILOT1 explicitly.
        src_sys = msg.get_srcSystem()
        src_comp = msg.get_srcComponent()
        if src_sys != m.target_system or src_comp != autopilot_compid:
            log(f"  ignoring SYS_STATUS from sys={src_sys} comp={src_comp} "
                f"(want sys={m.target_system} comp={autopilot_compid})")
            continue
        return {
            'present': bool(msg.onboard_control_sensors_present & RC_RECEIVER_HEALTH_BIT),
            'enabled': bool(msg.onboard_control_sensors_enabled & RC_RECEIVER_HEALTH_BIT),
            'healthy': bool(msg.onboard_control_sensors_health & RC_RECEIVER_HEALTH_BIT),
        }
    return None


def ap_extract_channels(msg, max_channels=18):
    """Pull chan1_raw..chanN_raw from an RC_CHANNELS msg, skipping unused
    trailing slots (UINT16_MAX = 65535 means not provided)."""
    chans = []
    for i in range(1, max_channels + 1):
        v = getattr(msg, f'chan{i}_raw', None)
        if v is None:
            break
        chans.append(v)
    # Trim trailing "not provided" slots so the table doesn't show garbage.
    chancount = getattr(msg, 'chancount', 0) or 0
    if chancount and chancount <= len(chans):
        chans = chans[:chancount]
    else:
        while chans and chans[-1] == 65535:
            chans.pop()
    return chans


def ap_sample_rc(m, duration, on_sample=None):
    """Collect RC_CHANNELS messages for `duration` seconds."""
    samples = []
    t0 = time.time()
    while time.time() - t0 < duration:
        msg = m.recv_match(type='RC_CHANNELS', blocking=True, timeout=0.5)
        if msg is None:
            continue
        chans = ap_extract_channels(msg)
        if not chans:
            continue
        t_ms = int((time.time() - t0) * 1000)
        samples.append((t_ms, chans))
        if on_sample:
            on_sample(t_ms, chans)
    return samples


def ap_print_status_summary(health, last_rssi=None):
    if health is None:
        print("  SYS_STATUS: <no response within timeout>")
        print()
        return
    bits = []
    if health['present']:  bits.append('present')
    if health['enabled']:  bits.append('enabled')
    if health['healthy']:  bits.append('healthy')
    if not bits:
        bits = ['<none>']
    print(f"  RC_RECEIVER sensor: {', '.join(bits)}")
    if not health['healthy']:
        print("    <-- ArduPilot reports RC receiver UNHEALTHY (failsafe likely active)")
    if last_rssi is not None and last_rssi != 255:
        print(f"  RC_CHANNELS.rssi = {last_rssi}  (0=no signal, 254=max, 255=unknown)")
    print()


# ---------- Shared verdict logic

def channel_stats(samples, n_channels):
    """Per-channel min/max/last/jitter across all samples."""
    stats = []
    for ch in range(n_channels):
        vals = [s[1][ch] for s in samples if ch < len(s[1]) and s[1][ch] != 65535]
        if not vals:
            stats.append(None)
            continue
        mn, mx = min(vals), max(vals)
        stats.append({
            'min': mn,
            'max': mx,
            'last': vals[-1],
            'jitter': mx - mn,
        })
    return stats


def is_throttle_resting(v):
    """Throttle value that looks like 'TX is on but stick held min/idle'.
    A typical BF rx_min_usec is ~885, rc midrc 1500, and idle throttle ~1000.
    ArduPilot's FS_THR_VALUE default is 975, also lands in this band.
    Anything outside these resting bands suggests the user (or failsafe) is
    actively driving throttle."""
    return (870 <= v <= 1020) or (1490 <= v <= 1510)


def verdict(stats, ap_health=None, ap_rssi=None):
    """Decide whether the link looks live.
    Returns (live: bool, reasons: list[str], warnings: list[str])

    Primary signals, strongest first:
      1. AP rssi in [1, 254]    — the RX itself reports a non-zero signal
         level. This is the cleanest "is RC arriving" check on AP, and it
         works even for digital protocols (ELRS/CRSF) where frozen values
         are normal at rest.
      2. AP RC_RECEIVER healthy — AP's own `has_valid_input()` gate. If set,
         AP would let you arm.
      3. jitter >= 3us          — analog RX (SBUS/PPM) noise floor. Useless
         for digital protocols at rest.
      4. throttle moving outside resting band, with non-zero jitter
      5. AUX switch thrown, with non-zero jitter
    """
    reasons = []
    warnings = []
    if not stats or all(s is None for s in stats):
        return False, [], ['no RC frames received at all']

    # 1. AP rssi — strongest non-jitter signal we have. AP populates this
    #    from rc().get_rssi(); 0 = no signal, 254 = max, 255 = "RX doesn't
    #    report rssi" (e.g. SBUS without out-of-band rssi).
    if ap_rssi is not None and 1 <= ap_rssi <= 254:
        reasons.append(f"AP reports RC_CHANNELS.rssi = {ap_rssi} "
                       f"({ap_rssi*100//254}% — RX sees signal from TX)")

    # 2. AP RC_RECEIVER healthy bit — AP's own arm-gate.
    if ap_health is not None and ap_health.get('healthy'):
        reasons.append("AP SYS_STATUS reports RC_RECEIVER healthy "
                       "(has_valid_input() = true; FC would let you arm)")

    # 3. Jitter (useful for analog protocols, ignored for digital).
    any_jitter = False
    for ch, s in enumerate(stats):
        if s and s['jitter'] >= 3:
            any_jitter = True
            reasons.append(f"{CHAN_NAMES[ch] if ch < len(CHAN_NAMES) else f'ch{ch+1}'} jittered {s['jitter']}us")
            break  # one is enough to call it live

    # 4 & 5: stick/switch position, but only if values are MOVING — a frozen
    # value is just stale fill, not user input.
    thr = stats[2] if len(stats) > 2 and stats[2] else None
    if thr and thr['jitter'] > 0 and not is_throttle_resting(thr['last']):
        reasons.append(f"throttle at {thr['last']}us (outside resting band)")
    for ch in range(4, len(stats)):
        s = stats[ch]
        if not s or s['jitter'] == 0:
            continue
        if s['last'] <= 1400 or s['last'] >= 1600:
            reasons.append(f"{CHAN_NAMES[ch] if ch < len(CHAN_NAMES) else f'ch{ch+1}'} thrown to {s['last']}us")

    # Diagnostic warning: AP's RC_RECEIVER healthy bit OFF while we have other
    # evidence of life is suspicious — surface it but don't override.
    if (ap_health is not None
            and not ap_health.get('healthy')
            and reasons):
        warnings.append("AP SYS_STATUS reports RC_RECEIVER unhealthy despite other "
                        "live signals — could be transient failsafe latch or a "
                        "SYS_STATUS-from-peripheral race. If you can arm, you're fine.")

    live = bool(reasons)
    return live, reasons, warnings


def print_table(stats, n_channels):
    print()
    print(f"  {'channel':10s} {'last':>6s} {'min':>6s} {'max':>6s} {'jitter':>7s}  notes")
    print(f"  {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*7}  {'-'*30}")
    for ch in range(n_channels):
        s = stats[ch]
        name = CHAN_NAMES[ch] if ch < len(CHAN_NAMES) else f'ch{ch+1}'
        if not s:
            print(f"  {name:10s} {'-':>6s} {'-':>6s} {'-':>6s} {'-':>7s}  (no data)")
            continue
        notes = []
        if ch == 2:  # throttle
            if 870 <= s['last'] <= 900:
                notes.append("throttle min/failsafe")
            elif 990 <= s['last'] <= 1020:
                notes.append("throttle idle")
            elif s['last'] >= 1100:
                notes.append("THROTTLE UP")
        elif ch >= 4:  # aux
            if s['last'] <= 1300:
                notes.append("switch LOW")
            elif s['last'] >= 1700:
                notes.append("switch HIGH")
            elif 1450 <= s['last'] <= 1550:
                notes.append("switch MID/center")
        if s['jitter'] >= 3:
            notes.append(f"live jitter")
        elif s['jitter'] == 0:
            notes.append(f"FROZEN")
        print(f"  {name:10s} {s['last']:>6d} {s['min']:>6d} {s['max']:>6d} {s['jitter']:>6d}u  {', '.join(notes)}")
    print()


# ---------- Port + firmware resolution

def resolve_port(explicit_port):
    """Return (port, baud, hint_firmware).
    hint_firmware ∈ {None, 'ap'} — usbserial-0001 forces AP-only (RC dongle).
    """
    if explicit_port:
        if 'usbserial' in explicit_port:
            return explicit_port, 460800, 'ap'
        return explicit_port, 115200, None
    usbmodem = list_usbmodem_ports()
    if usbmodem:
        port = usbmodem[0]
        if len(usbmodem) > 1:
            log(f"multiple usbmodem ports, picking {port}")
        return port, 115200, None
    # No direct USB to FC — try the RC-MAVLink dongle path
    if '/dev/cu.usbserial-0001' in list_usbserial_ports():
        log("no usbmodem port; falling back to /dev/cu.usbserial-0001 @ 460800 (RC-MAVLink dongle)")
        return '/dev/cu.usbserial-0001', 460800, 'ap'
    return None, None, None


def passive_listen_mavlink(port, baud=115200, listen_sec=0.6):
    """Read-only sniff for MAVLink magic bytes ($FD/$FE). Sends nothing."""
    import serial
    try:
        s = serial.Serial(port, baud, timeout=0.1)
        time.sleep(0.05)
        s.reset_input_buffer()
        end = time.time() + listen_sec
        buf = bytearray()
        while time.time() < end:
            c = s.read(4096)
            if c:
                buf.extend(c)
                if buf.count(b'\xfd') + buf.count(b'\xfe') >= 2:
                    s.close()
                    return True
        s.close()
        return False
    except Exception:
        return False


def detect_firmware(port, baud, hint, force_ap, force_bf):
    """Return 'bf' or 'ap' or None.

    PASSIVE-LISTEN-FIRST (2026-05-20). Sniff for AP MAVLink stream WITHOUT
    sending anything. If AP is streaming, we hear it and never MSP-probe (so
    AP's USB CDC stays in MAVLink mode — no wedge). Silent → MSP probe
    (BTFL=BF, ARDU=AP via DisplayPort). Last resort: MAVLink heartbeat probe.
    """
    if force_bf:
        return 'bf'
    if force_ap:
        return 'ap'
    if hint == 'ap':
        return 'ap'
    log("passive-listen sniff for MAVLink stream (0.6 s; no probe sent)...")
    if passive_listen_mavlink(port, baud=baud):
        log("  MAVLink stream detected -> AP")
        return 'ap'
    log("no MAVLink stream; trying MSP variant probe...")
    variant = msp_probe_variant(port, timeout=1.0)
    if variant == 'BTFL':
        return 'bf'
    if variant == 'ARDU':
        import time as _t
        _t.sleep(0.5)
        return 'ap'
    if variant in ('INAV', 'EMUF'):
        log(f"detected MSP variant {variant!r} — /rctest supports BF + AP only")
        return None
    log("MSP silent; last-resort MAVLink heartbeat probe...")
    if probe_mavlink(port, baud=baud, attempts=2, per_attempt=3.0):
        return 'ap'
    return None


# ---------- Per-firmware drivers

def run_bf(port, duration, n_channels_max, raw):
    msp = MSP(port)
    try:
        print()
        print("=== FC status before RC sampling (Betaflight) ===")
        status = bf_read_status_ex(msp)
        bf_print_status_summary(status)

        first = bf_read_rc(msp)
        if first is None:
            print("[error] MSP_RC returned no data — RX may be unbound or "
                  "feature RX_SERIAL disabled", file=sys.stderr)
            return 3
        n_channels = min(n_channels_max, len(first))
        log(f"sampling {n_channels} channels for {duration:.1f}s (BF/MSP)...")

        if raw:
            def on_sample(t_ms, rc):
                vals = ' '.join(f"{v:4d}" for v in rc[:n_channels])
                print(f"  t={t_ms:5d}ms  {vals}")
            samples = bf_sample_rc(msp, duration, on_sample=on_sample)
        else:
            samples = bf_sample_rc(msp, duration)

        if not samples:
            print("[error] no MSP_RC samples in window", file=sys.stderr)
            return 4
        log(f"got {len(samples)} samples ({len(samples)/duration:.1f} Hz)")

        stats = channel_stats(samples, n_channels)
        print_table(stats, n_channels)
        return _print_verdict(stats, firmware='bf', ap_health=None)
    finally:
        msp.close()


def run_ap(port, baud, duration, n_channels_max, raw):
    m = ap_connect(port, baud, timeout=5.0)
    if m is None:
        print(f"[error] no ArduPilot heartbeat on {port} @ {baud}", file=sys.stderr)
        return 2
    try:
        print()
        print("=== FC status before RC sampling (ArduPilot) ===")
        # Ask for SYS_STATUS @ ~2 Hz briefly so we get one in the timeout window.
        ap_request_rc_stream(m, rate_hz=50)  # also bumps RC stream rate up
        health = ap_read_rc_health(m, timeout=2.0)

        # Peek one RC_CHANNELS to learn channel count + rssi
        first_msg = m.recv_match(type='RC_CHANNELS', blocking=True, timeout=3.0)
        if first_msg is None:
            ap_print_status_summary(health)
            print("[error] no RC_CHANNELS messages received — RX may be unbound "
                  "or the RC stream is gated. Check SERIAL*_PROTOCOL for the RX "
                  "UART (typically 23 = RCIN) and RC_PROTOCOLS bitmask.",
                  file=sys.stderr)
            return 3
        first = ap_extract_channels(first_msg)
        last_rssi = getattr(first_msg, 'rssi', 255)
        ap_print_status_summary(health, last_rssi=last_rssi)

        n_channels = min(n_channels_max, len(first))
        log(f"sampling {n_channels} channels for {duration:.1f}s (AP/MAVLink)...")

        if raw:
            def on_sample(t_ms, rc):
                vals = ' '.join(f"{v:4d}" for v in rc[:n_channels])
                print(f"  t={t_ms:5d}ms  {vals}")
            samples = ap_sample_rc(m, duration, on_sample=on_sample)
        else:
            samples = ap_sample_rc(m, duration)

        if not samples:
            print("[error] no RC_CHANNELS samples in window", file=sys.stderr)
            return 4
        log(f"got {len(samples)} samples ({len(samples)/duration:.1f} Hz)")

        stats = channel_stats(samples, n_channels)
        print_table(stats, n_channels)
        return _print_verdict(stats, firmware='ap', ap_health=health, ap_rssi=last_rssi)
    finally:
        try: m.close()
        except Exception: pass


def _print_verdict(stats, firmware, ap_health=None, ap_rssi=None):
    live, reasons, warnings = verdict(stats, ap_health=ap_health, ap_rssi=ap_rssi)
    print("=== verdict ===")
    if live:
        print("  RX link looks LIVE — FC is receiving RC frames from the radio.")
        for r in reasons:
            print(f"    - {r}")
    else:
        print("  RX link does NOT look live — no convincing signal of TX input.")
        print("    Possible causes:")
        print("      - TX powered off / out of range / not bound to RX")
        if firmware == 'bf':
            print("      - RX wired but not configured (check `feature RX_SERIAL`,")
            print("        `serialrx_provider`, and the UART's `serial` function bit 64)")
        else:
            print("      - RX UART not configured (SERIAL*_PROTOCOL=23 for RCIN,")
            print("        or RX on dedicated RCIN pin with BRD_ALT_CONFIG appropriate)")
            print("      - RC_PROTOCOLS bitmask doesn't include the receiver's protocol")
            if ap_health and not ap_health['healthy']:
                print("      - ArduPilot itself reports RC_RECEIVER unhealthy (above)")
        print("      - RX powered but not pushing frames (check RX LED)")
    for w in warnings:
        print(f"  WARNING: {w}")
    print()
    return 0 if live else 5


# ---------- Main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', default=None,
                    help='serial port; auto-detect if omitted '
                         '(usbmodem preferred, usbserial-0001 fallback)')
    ap.add_argument('--duration', type=float, default=3.0,
                    help='seconds to sample RC frames (default 3)')
    ap.add_argument('--channels', type=int, default=12,
                    help='how many channels to show in table (default 12)')
    ap.add_argument('--raw', action='store_true',
                    help='print every sample as it arrives instead of summary')
    ap.add_argument('--force-ap', action='store_true',
                    help='skip autodetect, assume ArduPilot')
    ap.add_argument('--force-bf', action='store_true',
                    help='skip autodetect, assume Betaflight')
    args = ap.parse_args()

    if args.force_ap and args.force_bf:
        print("[error] --force-ap and --force-bf are mutually exclusive", file=sys.stderr)
        return 2

    port, baud, hint = resolve_port(args.port)
    if not port:
        print("[error] no /dev/cu.usbmodem* and no /dev/cu.usbserial-0001 found — "
              "is the FC plugged in or the RC-MAVLink dongle attached?",
              file=sys.stderr)
        return 1
    log(f"port: {port} @ {baud}")

    fw = detect_firmware(port, baud, hint, args.force_ap, args.force_bf)
    if fw is None:
        print(f"[error] could not identify firmware on {port} — neither MSP "
              "(BTFL) nor MAVLink heartbeat responded.", file=sys.stderr)
        return 2
    log(f"firmware: {'ArduPilot' if fw == 'ap' else 'Betaflight'}")

    if fw == 'bf':
        return run_bf(port, args.duration, args.channels, args.raw)
    else:
        return run_ap(port, baud, args.duration, args.channels, args.raw)


if __name__ == '__main__':
    sys.exit(main())
