#!/usr/bin/env python3
"""/satest — SmartAudio/Tramp sanity test on a Betaflight OR ArduPilot FC.

Auto-detects firmware:
  - MAVLink HEARTBEAT (autopilot=ArduPilot) → AP path (param-based VTX I/O).
  - MSP variant == 'BTFL'                   → BF path (vtxtable + MSP_VTX_CONFIG).

BF flow:
  1. vtxtable health autofix (canonical 5-band Tramp template).
  2. Read MSP_VTX_CONFIG (cmd 88) → device_type, device_is_ready.
  3. If either fails, print recommendations and exit non-zero.
  4. Print status. Toggle R1 → R2 → wait → R1, each via MSP_SET_VTX_CONFIG +
     MSP_EEPROM_WRITE (FC reboots after each set). Power forced to the 25 mW
     vtxtable slot.

AP flow:
  1. Read VTX_ENABLE, VTX_TYPE, VTX_BAND, VTX_CHANNEL, VTX_POWER, VTX_FREQ,
     VTX_OPTIONS, VTX_MAX_POWER.
  2. Health checks: VTX_ENABLE != 0, VTX_TYPE != 0.
  3. Print status (decoded VTX_TYPE: 1=Tramp, 2=SmartAudio, 3=DJI, 4=MSP).
  4. Toggle R1 → R2 → wait → R1 via PARAM_SET (no reboot — AP pushes live
     to the VTX over SA/Tramp). Verify each step via PARAM_VALUE readback.
  5. Restore the operator-facing power they had before the toggle.

Usage:
  satest.py                 # full run
  satest.py --status-only   # status only, no toggle
  satest.py --port /dev/... # override port
"""
import argparse
import glob
import struct
import sys
import time


# ---------- Canonical vtxtable
#
# Hardcoded for the dominant fleet hardware: 5-band × 8-channel × 5-power-level
# Tramp-class analog VTX (5.8 GHz). The 5-band frequency tables (Boscam A/B/E,
# Fatshark, Raceband) are universal across all analog 5.8 GHz VTXes; the
# powervalues / powerlabels are Tramp-specific (25/100/200/400/600 mW).
#
# CAVEAT: if a future drone has a different VTX (e.g. 4-level SmartAudio,
# or HD VTX with a non-standard table), this template will misconfigure it.
# Pass --no-vtxtable-fix on those builds, or extend this to dispatch on
# bands_count / power_levels_count.
CANONICAL_VTXTABLE = [
    "vtxtable bands 5",
    "vtxtable channels 8",
    "vtxtable band 1 BOSCAM_A A CUSTOM 5865 5845 5825 5805 5785 5765 5745 5725",
    "vtxtable band 2 BOSCAM_B B CUSTOM 5733 5752 5771 5790 5809 5828 5847 5866",
    "vtxtable band 3 BOSCAM_E E CUSTOM 5705 5685 5665 5645 5885 5905 5925 5945",
    "vtxtable band 4 FATSHARK F CUSTOM 5740 5760 5780 5800 5820 5840 5860 5880",
    "vtxtable band 5 RACEBAND R CUSTOM 5658 5695 5732 5769 5806 5843 5880 5917",
    "vtxtable powerlevels 5",
    "vtxtable powervalues 25 100 200 400 600",
    "vtxtable powerlabels 25 200 500 1.5 2.5",
]
CANONICAL_BANDS_COUNT = 5
CANONICAL_CHANNELS_COUNT = 8
CANONICAL_POWERLEVELS_COUNT = 5


# ---------- USB port discovery

def list_ports():
    return sorted(glob.glob('/dev/cu.usbmodem*'))


def wait_for_port(exclude=None, timeout=15, poll=2.0):
    """Slow poll for /dev/cu.usbmodem*. Default 2s — don't hammer USB during BF boot
    (memory: feedback_bf_boot_cycle_quiet.md)."""
    exclude = set(exclude or [])
    end = time.time() + timeout
    while time.time() < end:
        new = [p for p in list_ports() if p not in exclude]
        if new:
            return new
        time.sleep(poll)
    return []


def log(msg):
    print(f"[satest] {msg}", file=sys.stderr, flush=True)


# ---------- MSP framing (v1 + v2)

class MSP:
    def __init__(self, port, baud=115200):
        import serial
        self.s = serial.Serial(port, baud, timeout=0.3)
        time.sleep(0.3)

    def close(self):
        try: self.s.close()
        except Exception: pass

    def v1(self, cmd, payload=b'', wait=0.6):
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

    def v2(self, cmd, payload=b'', wait=0.6):
        def crc8(data):
            c = 0
            for b in data:
                c ^= b
                for _ in range(8):
                    c = ((c << 1) ^ 0xD5) & 0xFF if c & 0x80 else (c << 1) & 0xFF
            return c
        hdr = bytes([0]) + struct.pack('<HH', cmd, len(payload)) + payload
        frame = b'$X<' + hdr + bytes([crc8(hdr)])
        self.s.write(frame); self.s.flush()
        end = time.time() + wait
        buf = b''
        while time.time() < end:
            c = self.s.read(256)
            if c:
                buf += c
                idx = buf.find(b'$X>')
                if idx >= 0 and len(buf) >= idx + 8:
                    sz = struct.unpack('<H', buf[idx+6:idx+8])[0]
                    if len(buf) >= idx + 8 + sz + 1:
                        return buf[idx+8:idx+8+sz]
        return None


# ---------- Probes

DEVICE_TYPE_NAME = {
    0: 'NONE',
    1: 'RTC6705',
    3: 'SmartAudio',
    4: 'Tramp',
    5: 'MSP-VTX',
}


def probe_variant(port):
    try:
        m = MSP(port)
        r = m.v1(2, wait=1.0)
        m.close()
        if r and len(r) >= 4:
            return r[:4].decode('ascii', errors='replace')
    except Exception:
        pass
    return None


def probe_mavlink(port, attempts=3, per_attempt=4.0):
    """Open MAVLink, send our GCS heartbeat, wait for FC heartbeat. Returns
    True if any HEARTBEAT was decoded. Closes the connection cleanly so the
    caller can reopen later. Retries because ArduPilot's USB CDC multiplexer
    can take a moment to switch back from MSP to MAVLink if a prior MSP poll
    locked it. See feedback_ap_mavlink_first_detection.md."""
    try:
        from pymavlink import mavutil
    except ImportError:
        log("pymavlink not installed — can't probe MAVLink")
        return False
    for attempt in range(1, attempts + 1):
        m = None
        try:
            m = mavutil.mavlink_connection(port, baud=115200,
                                           source_system=255, source_component=190)
            # Send a few GCS heartbeats to nudge AP out of MSP-locked mode and
            # advertise ourselves on this channel.
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
                try:
                    m.close()
                except Exception:
                    pass
            time.sleep(0.3)
    return False


def passive_listen_mavlink(port, baud=115200, listen_sec=0.6):
    """Read-only sniff for MAVLink magic bytes ($FD/v2 or $FE/v1) on `port`.
    Returns True if 2+ magic bytes appear within `listen_sec`. Sends nothing —
    so a healthy AP's USB CDC stays in MAVLink mode (no MSP-lock risk)."""
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


def detect_firmware(port):
    """Return 'ardupilot' | 'betaflight' | 'unknown'.

    PASSIVE-LISTEN-FIRST (2026-05-20, supersedes MSP-first). Sniff the port
    read-only for MAVLink magic bytes for ~0.6 s. If we hear AP streaming,
    we're done — no probe sent, so AP's USB CDC stays in MAVLink mode and
    the next operation (PARAM_SET etc) works.

    If silent, MSP probe — 'BTFL'=Betaflight, 'ARDU'=ArduPilot via MSP
    DisplayPort. Last resort: short MAVLink heartbeat probe for AP boards
    that don't stream until a GCS knocks first.

    This sequence avoids the MSP-lock failure mode (see
    feedback_ap_mavlink_first_detection.md) by NEVER probing MSP on a
    streaming AP.
    """
    if passive_listen_mavlink(port):
        log("passive-listen: MAVLink magic bytes detected -> ardupilot")
        return 'ardupilot'
    variant = probe_variant(port)
    log(f"MSP variant: {variant!r}")
    if variant == 'BTFL':
        return 'betaflight'
    if variant == 'ARDU':
        time.sleep(0.5)
        return 'ardupilot'
    log("MSP silent; falling back to MAVLink heartbeat probe")
    if probe_mavlink(port, attempts=2, per_attempt=3.0):
        return 'ardupilot'
    return 'unknown'


# ---------- ArduPilot VTX helpers
#
# AP exposes VTX state as parameters. No reboot needed when changing
# band/channel — AP pushes the change live to the VTX over SA/Tramp.
#
# Band indices on AP are 0-based: 0=Boscam A, 1=Boscam B, 2=Boscam E,
# 3=FatShark, 4=Raceband, 5=Low. Channel indices are 0-based (R1 = ch 0).

AP_VTX_TYPE_NAME = {
    0: 'None',
    1: 'Tramp',
    2: 'SmartAudio',
    3: 'DJI HD',
    4: 'MSP',
    5: 'CRSF',
}

AP_BAND_NAME = {
    0: 'Boscam A',
    1: 'Boscam B',
    2: 'Boscam E',
    3: 'FatShark',
    4: 'Raceband',
    5: 'LowBand',
}

AP_RACEBAND_IDX = 4  # AP fixed mapping


def ap_connect(port, baud=115200):
    """Open MAVLink and immediately advertise our GCS heartbeat so AP's USB
    CDC multiplexer keeps streaming MAVLink (not MSP) for the rest of the
    session. See feedback_ap_mavlink_first_detection.md."""
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(port, baud=baud,
                                   source_system=255, source_component=190)
    for _ in range(4):
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        time.sleep(0.2)
    if not m.wait_heartbeat(timeout=10):
        raise SystemExit("[satest] no MAVLink heartbeat on AP path")
    return m


def ap_read_param(m, name, timeout=2.0, retries=3):
    """Read a single param. param_request_read_send can silently drop, so we
    retry up to 3x per the project CLAUDE.md note."""
    for _ in range(retries):
        m.mav.param_request_read_send(m.target_system, m.target_component,
                                       name.encode(), -1)
        end = time.time() + timeout
        while time.time() < end:
            msg = m.recv_match(type='PARAM_VALUE', blocking=False)
            if msg and msg.param_id.strip('\x00') == name:
                return msg.param_value
            time.sleep(0.02)
    return None


def ap_set_param(m, name, value, ptype=None):
    """Set a param and read it back. Returns the readback value (None on failure)."""
    from pymavlink import mavutil
    if ptype is None:
        ptype = mavutil.mavlink.MAV_PARAM_TYPE_INT16
    m.mav.param_set_send(m.target_system, m.target_component,
                         name.encode(), float(value), ptype)
    time.sleep(0.25)
    return ap_read_param(m, name, timeout=2.0)


def ap_read_vtx(port):
    """Read all the VTX_* params we care about. Returns dict (values may be None).

    AP has had several protocol-selector params across versions: older builds
    expose VTX_TYPE / VTX_TYPES / VTX_PROTOCOL; modern builds drop that and
    select the protocol from SERIAL*_PROTOCOL (36=Tramp, 37=SmartAudio) once
    VTX_ENABLE is on. We probe all three names and report the first that
    exists — None on all three means "this build has no type param,
    protocol comes from SERIAL_PROTOCOL".
    """
    m = ap_connect(port)
    try:
        out = {
            'enable':    ap_read_param(m, 'VTX_ENABLE'),
            'band':      ap_read_param(m, 'VTX_BAND'),
            'channel':   ap_read_param(m, 'VTX_CHANNEL'),
            'power':     ap_read_param(m, 'VTX_POWER'),
            'freq':      ap_read_param(m, 'VTX_FREQ'),
            'options':   ap_read_param(m, 'VTX_OPTIONS'),
            'max_power': ap_read_param(m, 'VTX_MAX_POWER'),
            'type':      None,
            'type_param_name': None,
        }
        for name in ('VTX_TYPE', 'VTX_TYPES', 'VTX_PROTOCOL'):
            v = ap_read_param(m, name)
            if v is not None:
                out['type'] = v
                out['type_param_name'] = name
                break
        return out
    finally:
        m.close()


def read_vtx_config(port):
    """Return parsed MSP_VTX_CONFIG, or None on failure."""
    m = MSP(port)
    try:
        r = m.v1(88, wait=0.8)
        if not r or len(r) < 5:
            return None
        out = {
            'device_type': r[0],
            'band': r[1],
            'channel': r[2],
            'power': r[3],
            'pit': r[4],
            'freq': None,
            'device_is_ready': None,
            'low_power_disarm': None,
            'pit_mode_freq': None,
            'vtx_table_available': None,
            'bands_count': None,
            'channels_count': None,
            'power_levels_count': None,
            'raw': r.hex(),
        }
        if len(r) >= 7:
            out['freq'] = struct.unpack('<H', r[5:7])[0]
        if len(r) >= 8:
            out['device_is_ready'] = r[7]
        if len(r) >= 9:
            out['low_power_disarm'] = r[8]
        if len(r) >= 11:
            out['pit_mode_freq'] = struct.unpack('<H', r[9:11])[0]
        if len(r) >= 15:
            out['vtx_table_available'] = r[11]
            out['bands_count'] = r[12]
            out['channels_count'] = r[13]
            out['power_levels_count'] = r[14]
        return out
    finally:
        m.close()


def read_vtxtable_band(port, band_idx):
    """MSP2_GET_VTXTABLE_BAND (0x1009). Returns dict or None."""
    m = MSP(port)
    try:
        r = m.v2(0x1009, bytes([band_idx]), wait=0.8)
        if not r or len(r) < 4:
            return None
        idx = r[0]
        name_len = r[1]
        pos = 2
        name = r[pos:pos+name_len].decode('ascii', errors='replace')
        pos += name_len
        if pos + 3 > len(r):
            return None
        letter = chr(r[pos]) if r[pos] else '?'
        pos += 1
        is_factory = r[pos]; pos += 1
        ch_count = r[pos]; pos += 1
        freqs = []
        for i in range(ch_count):
            if pos + 2 > len(r):
                break
            freqs.append(struct.unpack('<H', r[pos:pos+2])[0])
            pos += 2
        return {
            'index': idx,
            'name': name.strip(),
            'letter': letter,
            'is_factory': bool(is_factory),
            'channel_count': ch_count,
            'frequencies': freqs,
        }
    finally:
        m.close()


def read_vtxtable_power(port, power_idx):
    """MSP2_GET_VTXTABLE_POWERLEVEL (0x100A). Returns dict or None."""
    m = MSP(port)
    try:
        r = m.v2(0x100A, bytes([power_idx]), wait=0.8)
        if not r or len(r) < 4:
            return None
        idx = r[0]
        value = struct.unpack('<H', r[1:3])[0]
        label_len = r[3]
        label = r[4:4+label_len].decode('ascii', errors='replace').strip()
        return {'index': idx, 'value': value, 'label': label}
    finally:
        m.close()


def find_raceband_index(port, bands_count, current_band, cli_bands=None):
    """Return (band_idx, source_str).

    Prefers CLI-parsed bands (when available) since MSP2_GET_VTXTABLE_BAND is
    buggy on BF 2025.12 — see ensure_vtxtable_healthy. Falls back to MSP2,
    then to current-band-if-4 (TBS observed), then BF default 5."""
    if cli_bands:
        for b in cli_bands:
            if b['letter'].upper() == 'R' or 'RACE' in b['name'].upper():
                return b['idx'], f"CLI vtxtable band {b['idx']} = '{b['name']}' (letter {b['letter']})"
    if bands_count and bands_count > 0:
        for i in range(1, bands_count + 1):
            info = read_vtxtable_band(port, i)
            if not info:
                continue
            name_upper = info['name'].upper()
            if info['letter'].upper() == 'R' or 'RACE' in name_upper:
                return info['index'], f"vtxtable band {info['index']} = '{info['name']}' (letter {info['letter']})"
    # Fallback: if current band reads as 4 (TBS observed) treat that as Raceband
    if current_band == 4:
        return 4, "fallback: current band==4 assumed Raceband (TBS Unify observed mapping)"
    return 5, "fallback: BF default vtxtable Raceband=5"


# ---------- VTX set / verify

def set_vtx_channel_runtime(port, band, channel, power):
    """MSP_SET_VTX_CONFIG only — applies to vtxSettingsConfig in RAM and the VTX
    driver picks it up in its next poll cycle (live SA command to VTX), but does
    NOT persist to flash and does NOT reboot. Returns the port unchanged.

    Use during the toggle test where the operator just needs to SEE the channel
    change on the goggles; we persist once at the end with save_vtx_eeprom().
    Cuts ~24 s off /satest by avoiding 2 of the 3 EEPROM_WRITE reboots."""
    m = MSP(port)
    try:
        bandChan = (band - 1) * 8 + (channel - 1)
        payload = struct.pack('<HBB', bandChan, power, 0)
        log(f"MSP_SET_VTX_CONFIG bandChan={bandChan} (band={band} ch={channel}) power={power}  [runtime, no save]")
        m.v1(89, payload, wait=1.0)
    finally:
        m.close()
    return port


def save_vtx_eeprom(port):
    """MSP_EEPROM_WRITE — persist the current vtxSettingsConfig and reboot FC.
    Call once at the end of the toggle dance. Returns the (possibly new) port
    after the FC re-enumerates."""
    m = MSP(port)
    try:
        log("MSP_EEPROM_WRITE (final persist; FC will reboot)")
        m.v1(250, b'', wait=2.5)
    finally:
        m.close()
    # BF boot cycle is sacred — 8 s pure quiet after EEPROM_WRITE reboot.
    # Aggressive polling stalls Dshot init → ESCs beep. memory: feedback_bf_boot_cycle_quiet.md
    log("post-EEPROM_WRITE quiet (8s — letting FC complete its boot cycle untouched)")
    time.sleep(8.0)
    new_ports = wait_for_port(exclude=[], timeout=15)
    return new_ports[0] if new_ports else port


def set_vtx_channel(port, band, channel, power):
    """Compatibility shim: runtime-set + immediate save. Kept for callers that
    want the legacy 'apply and persist now' semantics. New toggle flow should
    use set_vtx_channel_runtime + a single trailing save_vtx_eeprom."""
    set_vtx_channel_runtime(port, band, channel, power)
    return save_vtx_eeprom(port)


def verify_band_channel(port, want_band, want_channel, retries=3):
    for _ in range(retries):
        cfg = read_vtx_config(port)
        if cfg and cfg['band'] == want_band and cfg['channel'] == want_channel:
            return True, cfg
        time.sleep(0.6)
    return False, cfg


# ---------- vtxtable health check + autofix
#
# NOTE on detection: BF 2025.12 has a bug where MSP2_GET_VTXTABLE_BAND (0x1009)
# returns garbage bytes even when the table is correctly stored. CLI `dump
# vtxtable` is the authoritative source — it reads BF's internal struct as
# human-readable text. We detect via CLI text, not MSP2 binary.

import re as _re


def _parse_vtxtable_lines(dump_text):
    """Parse `vtxtable band N NAME L MODE freqs...` lines out of dump output.
    Returns list of dicts: [{'idx':1,'name':'BOSCAM_A','letter':'A','mode':'CUSTOM','freqs':[..]}]."""
    out = []
    for line in dump_text.splitlines():
        m = _re.match(r"\s*vtxtable\s+band\s+(\d+)\s+(\S+)\s+(\S)\s+(\S+)\s+(.+)", line)
        if not m:
            continue
        try:
            freqs = [int(x) for x in m.group(5).split()]
        except ValueError:
            freqs = []
        out.append({
            'idx': int(m.group(1)),
            'name': m.group(2),
            'letter': m.group(3),
            'mode': m.group(4),
            'freqs': freqs,
        })
    return out


def _parse_vtxtable_power_lines(dump_text):
    """Parse `vtxtable powervalues ...` and `vtxtable powerlabels ...` from a
    BF CLI dump. Returns (powervalues, powerlabels) — each a list of strings
    (labels stay as strings since they can be '1.5', '2.5' etc.). Either may
    be [] if the line wasn't present."""
    values, labels = [], []
    for line in dump_text.splitlines():
        s = line.strip()
        m = _re.match(r"vtxtable\s+powervalues\s+(.+)", s)
        if m:
            values = m.group(1).split()
            continue
        m = _re.match(r"vtxtable\s+powerlabels\s+(.+)", s)
        if m:
            labels = m.group(1).split()
    return values, labels


def find_25mw_slot(powervalues, powerlabels):
    """Return (slot_idx_1based, why) for the 25mW power slot in this vtxtable.

    Lookup precedence:
      1. powerlabels has an entry whose label == '25' → that slot.
      2. powervalues has an entry == 25 (Tramp tables happen to use mW as the
         power-code value, so the value field doubles as a label).
      3. lowest-label slot (smallest number after stripping non-digits) — for
         VTXes that don't have a 25 mW slot at all (e.g. HD VTXes starting at 100).
      4. Slot 1 as ultimate fallback.
    Slot indexes are 1-based per BF's vtxtable convention.
    """
    if powerlabels:
        for i, lbl in enumerate(powerlabels):
            if lbl == '25':
                return i + 1, f"powerlabels[{i+1}] == '25'"
    if powervalues:
        for i, v in enumerate(powervalues):
            try:
                if int(v) == 25:
                    return i + 1, f"powervalues[{i+1}] == 25"
            except ValueError:
                pass
    # Lowest-numeric-label fallback
    if powerlabels:
        ranked = []
        for i, lbl in enumerate(powerlabels):
            try:
                n = float(lbl)
                ranked.append((n, i + 1, lbl))
            except ValueError:
                pass
        if ranked:
            ranked.sort()
            return ranked[0][1], f"no 25mW slot; using lowest-power slot {ranked[0][1]} (label '{ranked[0][2]}')"
    return 1, "no powerlabels/values parsed; defaulting to slot 1"


def _is_band_line_corrupted(b):
    """A vtxtable band line is broken if name/letter/freqs don't look right."""
    name = b.get('name') or ''
    if not name or not all(c.isalnum() or c == '_' for c in name):
        return f"name not alphanumeric: {name!r}"
    letter = b.get('letter') or ''
    if not letter.isalpha() or len(letter) != 1:
        return f"letter not A-Z: {letter!r}"
    freqs = b.get('freqs') or []
    if not freqs:
        return "no frequencies"
    for f in freqs:
        # TBS Unify's extended U-band uses freqs from 4990 (low) to 6013 (high),
        # both valid TBS hardware channels but outside the conventional 5GHz band.
        # The autofix MUST accept these so user-set Unify tables aren't destroyed.
        # Range widened 2026-05-21 after a "corruption fix" overwrote a user's
        # hand-configured Unify table.
        if not (4900 <= f <= 6100):
            return f"frequency out of 5GHz range: {f}"
    return None


def cli_open(port, baud=115200, timeout=3.0):
    """Enter BF CLI by sending a bare `#` (per memory: feedback_bf_cli_entry).
    Returns the open pyserial handle once the `# ` prompt is seen."""
    import serial
    s = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write(b"#")
    s.flush()
    buf = bytearray()
    end = time.time() + timeout
    while time.time() < end:
        chunk = s.read(256)
        if chunk:
            buf.extend(chunk)
            if b"# " in buf:
                return s
    s.close()
    raise SystemExit(f"[satest] CLI prompt not seen on {port}")


def cli_send(s, line, timeout=5.0):
    """Send a CLI line, wait for the next `# ` prompt. Returns BF's response text."""
    s.reset_input_buffer()
    s.write(line.encode() + b"\r")
    s.flush()
    buf = bytearray()
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = s.read(1024)
        except Exception as e:
            log(f"  serial read error on {line!r}: {e}")
            return buf.decode("utf-8", errors="replace")
        if chunk:
            buf.extend(chunk)
            if buf.endswith(b"# "):
                return buf[:-2].decode("utf-8", errors="replace")
    return buf.decode("utf-8", errors="replace")


def push_canonical_vtxtable(port):
    """Enter CLI, paste CANONICAL_VTXTABLE + save, wait through reboot.
    Returns the (possibly new) port the FC re-enumerates on."""
    log("pushing canonical vtxtable via CLI ...")
    for line in CANONICAL_VTXTABLE:
        print(f"   > {line}", flush=True)
    s = cli_open(port)
    for line in CANONICAL_VTXTABLE:
        cli_send(s, line)
    # save triggers reboot; serial drop is expected and benign
    try:
        s.write(b"save\r")
        s.flush()
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass
    log("save sent — FC rebooting (10 s boot quiet, then re-enum)")
    time.sleep(10.0)
    new_ports = wait_for_port(timeout=20)
    return new_ports[0] if new_ports else port


def cli_read_vtxtable(port):
    """Enter CLI, ask for `dump vtxtable`, parse out bands + power lines.
    Returns (open_serial_handle, bands, powervalues, powerlabels).
    Caller owns closing the handle."""
    s = cli_open(port)
    out = cli_send(s, "dump vtxtable", timeout=15.0)
    bands = _parse_vtxtable_lines(out)
    pvalues, plabels = _parse_vtxtable_power_lines(out)
    return s, bands, pvalues, plabels


def scan_vtxtable_health_via_cli(port):
    """Returns (bands, powervalues, powerlabels, broken).
    `broken` is [(idx, reason), ...] for any band failing validation."""
    s, bands, pvalues, plabels = cli_read_vtxtable(port)
    try:
        s.write(b"exit noreboot\r"); s.flush()
        time.sleep(0.3)
    except Exception:
        pass
    try: s.close()
    except Exception: pass

    if not bands:
        return [], pvalues, plabels, [("ALL", "no `vtxtable band` lines found in dump")]
    broken = []
    for b in bands:
        why = _is_band_line_corrupted(b)
        if why:
            broken.append((b['idx'], why))
    return bands, pvalues, plabels, broken


def ensure_vtxtable_healthy(port, cfg, autofix=True, force=False):
    """Run BEFORE any other /satest logic so the rest of the run sees a clean
    table. Reads via CLI text (the authoritative source; the MSP2 path has a
    known bug on BF 2025.12). Pushes the canonical template when:
      - any band looks corrupted, OR
      - `force=True` (caller passes --force-vtxtable — useful when the OSD
        renders '?' for power even though the stored table looks fine; symptom
        of BF failing to copy vtxtable into the runtime vtxDevice.capability).

    Returns (port, cfg) — both may be refreshed if a push landed."""
    log("checking vtxtable health via CLI (`dump vtxtable`) ...")
    try:
        bands, pvalues, plabels, broken = scan_vtxtable_health_via_cli(port)
    except Exception as e:
        log(f"vtxtable CLI check failed ({e}); skipping autofix")
        return port, cfg

    if not broken and not force:
        names = ", ".join(f"{b['idx']}={b['letter']}/{b['name']}" for b in bands)
        log(f"vtxtable looks healthy: {len(bands)} band(s) [{names}]")
        if plabels:
            log(f"  powerlabels: {plabels}  powervalues: {pvalues}")
        cfg['_cli_bands'] = bands
        cfg['_cli_powervalues'] = pvalues
        cfg['_cli_powerlabels'] = plabels
        return port, cfg

    if force and not broken:
        log("--force-vtxtable → pushing canonical template even though current is well-formed")
    else:
        log(f"vtxtable corruption detected ({len(broken)} band(s)):")
        for idx, why in broken:
            log(f"  band {idx}: {why}")

    if not autofix:
        log("--no-vtxtable-fix → leaving table alone")
        cfg['_cli_bands'] = bands
        cfg['_cli_powervalues'] = pvalues
        cfg['_cli_powerlabels'] = plabels
        return port, cfg

    new_port = push_canonical_vtxtable(port)
    if new_port != port:
        log(f"FC re-enumerated as {new_port}")
        port = new_port

    # Re-read the VTX cfg post-reboot. USB CDC stays present across BF reboot
    # on macOS, but writes can fail briefly while MSP is still coming up —
    # retry until MSP responds or we give up.
    new_cfg = None
    for attempt in range(8):
        try:
            new_cfg = read_vtx_config(port)
            if new_cfg:
                break
        except Exception as e:
            log(f"  post-fix MSP retry {attempt+1}/8: {e}")
        time.sleep(2.0)
    if not new_cfg:
        log("WARNING: MSP_VTX_CONFIG silent after vtxtable fix; using pre-fix cfg")
        cfg['_cli_bands'] = bands
        cfg['_cli_powervalues'] = pvalues
        cfg['_cli_powerlabels'] = plabels
        return port, cfg

    # Verify the fix landed via CLI again, and attach the post-fix bands to cfg.
    post_bands, post_pvalues, post_plabels = [], pvalues, plabels
    try:
        post_bands, post_pvalues, post_plabels, broken2 = scan_vtxtable_health_via_cli(port)
        if broken2:
            log(f"WARNING: vtxtable still reports corruption after fix ({len(broken2)} band)")
            for idx, why in broken2:
                log(f"  band {idx}: {why}")
        else:
            names = ", ".join(f"{b['idx']}={b['letter']}/{b['name']}" for b in post_bands)
            log(f"vtxtable now healthy: {len(post_bands)} band(s) [{names}]")
            if post_plabels:
                log(f"  powerlabels: {post_plabels}  powervalues: {post_pvalues}")
    except Exception as e:
        log(f"post-fix verify skipped: {e}")

    new_cfg['_cli_bands'] = post_bands or bands
    new_cfg['_cli_powervalues'] = post_pvalues or pvalues
    new_cfg['_cli_powerlabels'] = post_plabels or plabels
    log(f"post-fix VTX cfg: band={new_cfg['band']} ch={new_cfg['channel']} "
        f"freq={new_cfg.get('freq')}")
    return port, new_cfg


# ---------- Pretty printing

def print_status(cfg, raceband_info, power_info):
    dt = cfg['device_type']
    dt_name = DEVICE_TYPE_NAME.get(dt, f"unknown({dt})")
    print()
    print("=== VTX status ===")
    print(f"  device_type     : {dt} ({dt_name})")
    if cfg['device_is_ready'] is not None:
        rd = 'YES' if cfg['device_is_ready'] else 'NO'
        print(f"  device_is_ready : {cfg['device_is_ready']} ({rd})")
    else:
        print(f"  device_is_ready : <not reported by this BF version>")
    band_label = f"{cfg['band']}"
    if raceband_info:
        band_label += f" ({raceband_info['name']}/{raceband_info['letter']})"
    print(f"  Band            : {band_label}")
    print(f"  Channel         : {cfg['channel']}")
    pwr_label = f"{cfg['power']}"
    if power_info:
        pwr_label += f"  ({power_info['value']} → \"{power_info['label']}\")"
    print(f"  Power           : {pwr_label}")
    if cfg['freq']:
        print(f"  Frequency       : {cfg['freq']} MHz")
    if cfg['pit']:
        print(f"  Pit mode        : ON")
    print()


def print_sa_failure_recommendations(cfg):
    dt = cfg['device_type']
    rdy = cfg['device_is_ready']
    print()
    print("=== SmartAudio NOT working ===")
    print(f"  device_type     : {dt} ({DEVICE_TYPE_NAME.get(dt, '?')})")
    print(f"  device_is_ready : {rdy}")
    print()
    if dt == 0:
        print("device_type=0 → BF has no VTX driver bound. Check:")
        print("  1. CLI `get vtx_` — is `vtx_smartaudio` enabled?")
        print("     Then `feature VTX_SMARTAUDIO` (or `feature VTX_TRAMP`) + `save`.")
        print("  2. CLI `serial` — a UART must have function bit 2048 (VTX_SMARTAUDIO).")
        print("     e.g. `serial 1 2048 115200 57600 0 115200` (UART2 SA).")
        print("  3. Wiring: SA is single-wire on the UART's TX pin, FC GND ↔ VTX GND.")
        print("  4. After serial change, FC reboot is required.")
    elif rdy == 0:
        print("device_type set but device_is_ready=0 → driver is up, VTX isn't replying.")
        print("Check (in order):")
        print("  1. The VTX's *own* OSD menu: protocol must be SmartAudio, NOT CRSF/IRC-Tramp.")
        print("     This is the #1 cause (see memory: reference_tbs_unify_protocol.md).")
        print("  2. Single-wire SA goes to FC UART TX. Some VTXes need a 1k inline resistor.")
        print("  3. VTX powered? Many SA VTXes need >5V from a dedicated pad, not USB power.")
        print("  4. Try wiggling baud / inverting: BF CLI `set vtx_smartaudio_unify=ON` / OFF.")
        print("  5. Confirm UART assignment matches the wired pad (`serial` in CLI).")
    else:
        print("VTX reports ready but something's off — re-run /satest after reboot.")
    print()


# ---------- ArduPilot satest flow

def ap_print_status(cur):
    enable = cur.get('enable')
    vtype = cur.get('type')
    band = cur.get('band')
    channel = cur.get('channel')
    power = cur.get('power')
    freq = cur.get('freq')
    opts = cur.get('options')
    maxp = cur.get('max_power')

    print()
    print("=== VTX status (ArduPilot) ===")
    print(f"  VTX_ENABLE      : {_fmt_int(enable)}  ({'ON' if _i(enable) else 'OFF'})")
    type_name = cur.get('type_param_name')
    if type_name and vtype is not None:
        tname = AP_VTX_TYPE_NAME.get(_i(vtype), f'unknown({vtype})')
        print(f"  {type_name:15s} : {_fmt_int(vtype)}  ({tname})")
    else:
        print(f"  VTX_TYPE/PROTOCOL: <not on this AP build; protocol comes from SERIAL*_PROTOCOL=36/37>")
    bname = AP_BAND_NAME.get(_i(band), '?') if band is not None else '?'
    print(f"  VTX_BAND        : {_fmt_int(band)}  ({bname})")
    print(f"  VTX_CHANNEL     : {_fmt_int(channel)}" + (f"  (= ch{_i(channel)+1})" if channel is not None else ""))
    print(f"  VTX_POWER       : {_fmt_int(power)} mW")
    print(f"  VTX_MAX_POWER   : {_fmt_int(maxp)} mW")
    print(f"  VTX_FREQ        : {_fmt_int(freq)} MHz")
    print(f"  VTX_OPTIONS     : {_fmt_int(opts)}")
    print()


def _i(v):
    """Coerce a PARAM_VALUE float to int safely."""
    try: return int(v)
    except (TypeError, ValueError): return None


def _fmt_int(v):
    i = _i(v)
    return '<not read>' if i is None else str(i)


def ap_print_failure(cur):
    enable = _i(cur.get('enable'))
    vtype = _i(cur.get('type'))
    type_param_name = cur.get('type_param_name')
    print()
    print("=== VTX NOT configured (ArduPilot) ===")
    print(f"  VTX_ENABLE : {enable}")
    if type_param_name:
        print(f"  {type_param_name} : {vtype}")
    print()
    if not enable:
        print("VTX_ENABLE=0 → AP isn't driving the VTX at all.")
        print("  Fix: set VTX_ENABLE=1.")
        if type_param_name:
            print(f"  Then set {type_param_name} to your protocol:")
            print(f"  (1=Tramp, 2=SmartAudio, 3=DJI HD, 4=MSP).")
        print("  A SERIAL*_PROTOCOL line must also be set to the VTX protocol")
        print("  (SmartAudio=37, Tramp=36) and SERIAL*_BAUD matched (usually 4 → 4800).")
    elif type_param_name and vtype == 0:
        print(f"{type_param_name}=0 → driver disabled. Set {type_param_name} to your protocol")
        print("  (1=Tramp, 2=SmartAudio, 3=DJI HD, 4=MSP) and reboot.")
    else:
        print("Health check failed unexpectedly — readback may have dropped.")
        print("Retry the read, or check that the FC is still on USB.")
    print("Also verify the SERIAL UART carrying the VTX line:")
    print("  - SERIAL*_PROTOCOL = 37 (SmartAudio) or 36 (Tramp)")
    print("  - SERIAL*_BAUD     = 4  (4800)  — SmartAudio runs at 4800-ish")
    print()


def ap_set_band_channel(m, band, channel, expect_band, expect_channel,
                        verify_timeout=2.0):
    """Set VTX_BAND and VTX_CHANNEL via PARAM_SET, then verify by readback.
    Returns (ok, after_band, after_channel)."""
    log(f"AP PARAM_SET VTX_BAND={band} VTX_CHANNEL={channel}")
    ap_set_param(m, 'VTX_BAND', band)
    ap_set_param(m, 'VTX_CHANNEL', channel)
    # Verify
    end = time.time() + verify_timeout
    last_b = last_c = None
    while time.time() < end:
        last_b = _i(ap_read_param(m, 'VTX_BAND'))
        last_c = _i(ap_read_param(m, 'VTX_CHANNEL'))
        if last_b == expect_band and last_c == expect_channel:
            return True, last_b, last_c
        time.sleep(0.3)
    return False, last_b, last_c


def ap_run_satest(port, args):
    """ArduPilot path: param-driven SA/Tramp sanity test, no reboot per toggle."""
    log("running ArduPilot satest flow")
    cur = ap_read_vtx(port)
    log(f"AP VTX state: {cur}")

    enable = _i(cur.get('enable'))
    vtype = _i(cur.get('type'))
    type_param_name = cur.get('type_param_name')

    # Health:
    #   - VTX_ENABLE must be on.
    #   - If this build has a VTX_TYPE/PROTOCOL param, it must be non-zero.
    #   - If the build has no such param, AP picks protocol from
    #     SERIAL*_PROTOCOL (36=Tramp, 37=SmartAudio) once VTX_ENABLE=1. We
    #     can't easily verify SERIAL_PROTOCOL here without scanning all
    #     SERIAL*_PROTOCOL params, so trust VTX_ENABLE=1 — the toggle test
    #     is the real ground truth.
    if not enable:
        ap_print_failure(cur)
        return 2
    if type_param_name and not vtype:
        ap_print_failure(cur)
        return 2

    ap_print_status(cur)

    if args.status_only:
        return 0

    # Toggle: R1 (band=4 ch=0) → R2 (band=4 ch=1) → wait → R1.
    # AP VTX_CHANNEL is 0-indexed: R1 = ch 0, R2 = ch 1.
    import subprocess as _sp
    def _say(text):
        try:
            _sp.Popen(["say", text], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        except Exception:
            pass

    m = ap_connect(port)
    try:
        cur_band = _i(cur.get('band'))
        cur_ch = _i(cur.get('channel'))
        on_r1 = (cur_band == AP_RACEBAND_IDX and cur_ch == 0)

        if not on_r1:
            print(f"-> Not on Raceband ch1 (band={cur_band} ch={cur_ch}+1). Switching to R1 first.")
            ok, b, c = ap_set_band_channel(m, AP_RACEBAND_IDX, 0,
                                            AP_RACEBAND_IDX, 0)
            if not ok:
                print(f"[error] R1 not confirmed; got band={b} ch={c}", file=sys.stderr)
                return 4
            print("   ...on R1.")

        _say("Switching to R2 in 3 seconds")
        time.sleep(3)
        print(f"-> On Raceband ch1. Switching to R2 for {args.wait:.0f}s (watch your goggles)...")
        ok, b, c = ap_set_band_channel(m, AP_RACEBAND_IDX, 1,
                                        AP_RACEBAND_IDX, 1)
        if not ok:
            print(f"[error] R2 not confirmed; got band={b} ch={c}", file=sys.stderr)
            return 4
        print("   ...now on R2.")

        time.sleep(max(0, args.wait - 3))
        _say("Switching back to R1 in 3 seconds")
        time.sleep(3)

        print("-> Switching back to R1.")
        ok, b, c = ap_set_band_channel(m, AP_RACEBAND_IDX, 0,
                                        AP_RACEBAND_IDX, 0)
        if not ok:
            print(f"[error] R1 not confirmed; got band={b} ch={c}", file=sys.stderr)
            return 4
        print("   ...back on R1.")

        # Force VTX_POWER=25 mW as the test post-condition (parity with BF
        # path's "lowest legal transmit power"). AP VTX_POWER is in mW
        # directly, so 25 is the value. After the back-to-back BAND/CHANNEL
        # sets the param-system can be busy enough that a single set lands
        # but the readback queue is stale — retry with verify until it
        # sticks or we give up.
        log("AP PARAM_SET VTX_POWER=25")
        final_pwr = None
        for attempt in range(5):
            ap_set_param(m, 'VTX_POWER', 25)
            time.sleep(0.5)
            final_pwr = _i(ap_read_param(m, 'VTX_POWER'))
            if final_pwr == 25:
                break
            log(f"  VTX_POWER readback = {final_pwr} (attempt {attempt+1}/5, retrying)")
        if final_pwr == 25:
            print("   ...power dropped to 25 mW.")
        else:
            log(f"WARNING: VTX_POWER still {final_pwr} mW after 5 attempts (wanted 25)")
    finally:
        m.close()

    print()
    print("Test sequence complete. End state: Raceband ch1 @ 25 mW.")
    return 0


# ---------- Betaflight satest flow (refactored from former main body)

def bf_run_satest(port, args):
    cfg = read_vtx_config(port)
    if not cfg:
        print("[error] MSP_VTX_CONFIG returned nothing", file=sys.stderr)
        return 3
    log(f"raw VTX cfg: {cfg}")

    # Heal vtxtable BEFORE looking up Raceband or running the toggle test —
    # otherwise we'd build a `raceband_info` from garbage and the OSD would
    # still render the band letter as `?`.
    port, cfg = ensure_vtxtable_healthy(port, cfg,
                                         autofix=not args.no_vtxtable_fix,
                                         force=args.force_vtxtable)
    cli_bands = cfg.get('_cli_bands') or []

    # Look up Raceband index + current power label. Prefer CLI-parsed bands
    # (MSP2_GET_VTXTABLE_BAND is buggy on this BF build).
    raceband_idx, rb_src = find_raceband_index(port, cfg.get('bands_count'), cfg['band'],
                                                cli_bands=cli_bands)
    log(f"Raceband index → {raceband_idx} ({rb_src})")

    current_band_info = None
    for b in cli_bands:
        if b['idx'] == cfg['band']:
            current_band_info = {'name': b['name'], 'letter': b['letter']}
            break
    if current_band_info is None and cfg.get('bands_count'):
        current_band_info = read_vtxtable_band(port, cfg['band'])
    power_info = None
    if cfg.get('power_levels_count') and cfg['power'] > 0:
        power_info = read_vtxtable_power(port, cfg['power'])

    # Failure paths
    sa_bad = (cfg['device_type'] == 0) or (cfg['device_is_ready'] == 0)
    if sa_bad:
        print_sa_failure_recommendations(cfg)
        return 2

    # Happy path: show status
    print_status(cfg, current_band_info, power_info)

    if args.status_only:
        return 0

    # Toggle test. End state must be R1.
    # ALWAYS force the power slot whose vtxtable label is "25" (mW). Across
    # different VTXes the slot index for 25 mW differs (Tramp tables put 25 mW
    # at slot 1; HD VTXes may start higher; some SmartAudio tables may shuffle).
    # Looking up by label keeps /satest's post-condition consistent — lowest
    # legal transmit power — regardless of hardware.
    SATEST_POWER, why = find_25mw_slot(
        cfg.get('_cli_powervalues') or [],
        cfg.get('_cli_powerlabels') or [],
    )
    log(f"toggle power slot → {SATEST_POWER} ({why})")
    cur_band, cur_ch = cfg['band'], cfg['channel']
    on_r1 = (cur_band == raceband_idx and cur_ch == 1)

    # Toggle test uses RUNTIME sets (no EEPROM_WRITE per step). vtxSettingsConfig
    # is updated in RAM and the SA driver pushes to the VTX live. We persist
    # once at the end. Cuts ~24 s vs the old per-step save approach.

    import subprocess as _sp
    def _say(text):
        try:
            _sp.Popen(["say", text], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        except Exception:
            pass

    if not on_r1:
        print(f"-> Not on Raceband ch1 (currently band={cur_band} ch={cur_ch}). Switching to R1 first.")
        set_vtx_channel_runtime(port, raceband_idx, 1, SATEST_POWER)
        ok, _ = verify_band_channel(port, raceband_idx, 1)
        if not ok:
            print("[error] failed to land on R1 (runtime set)", file=sys.stderr)
            return 4

    _say("Switching to R2 in 3 seconds")
    time.sleep(3)
    print(f"-> On Raceband ch1. Switching to R2 for {args.wait:.0f}s (watch your goggles)...")
    set_vtx_channel_runtime(port, raceband_idx, 2, SATEST_POWER)
    ok, _ = verify_band_channel(port, raceband_idx, 2)
    if not ok:
        print("[error] R2 not confirmed by readback", file=sys.stderr)
        return 4
    print("   ...now on R2.")

    time.sleep(max(0, args.wait - 3))
    _say("Switching back to R1 in 3 seconds")
    time.sleep(3)

    print("-> Switching back to R1.")
    set_vtx_channel_runtime(port, raceband_idx, 1, SATEST_POWER)
    ok, after = verify_band_channel(port, raceband_idx, 1)
    if not ok:
        print(f"[error] R1 not confirmed by readback; current = {after}", file=sys.stderr)
        return 4
    print("   ...back on R1.")

    # Single trailing save — persist the final R1 / power=25mW state.
    new_port = save_vtx_eeprom(port)
    if new_port:
        port = new_port

    print()
    print("Test sequence complete. End state: Raceband ch1.")
    return 0


# ---------- Main dispatcher

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default=None)
    ap.add_argument('--status-only', action='store_true',
                    help="Print status and exit; do not toggle channels")
    ap.add_argument('--wait', type=float, default=2.0,
                    help="Seconds to hold the R2 step (default 2). 3 s of that "
                         "is consumed by the pre-transition `say` cue, so any "
                         "value <=3 gives a fast back-to-back R1->R2->R1.")
    ap.add_argument('--no-vtxtable-fix', action='store_true',
                    help="(BF only) Skip the vtxtable corruption autofix. Use "
                         "when this drone has a non-Tramp 5x8 VTX (e.g. 4-level "
                         "SmartAudio or HD VTX) — the canonical template would "
                         "misconfigure it. Ignored on ArduPilot.")
    ap.add_argument('--force-vtxtable', action='store_true',
                    help="(BF only) Push the canonical 5-band Tramp template even "
                         "when the current table passes surface validation. Use "
                         "when the goggle OSD shows '?' for VTX power despite "
                         "vtx_power being set. Ignored on ArduPilot.")
    ap.add_argument('--firmware', choices=['auto', 'betaflight', 'ardupilot'],
                    default='auto',
                    help="Override firmware autodetection (default: auto).")
    args = ap.parse_args()

    # Pick port
    port = args.port
    if not port:
        ports = list_ports()
        if not ports:
            print("[error] no /dev/cu.usbmodem* found; plug in the drone", file=sys.stderr)
            return 1
        port = ports[0]
        if len(ports) > 1:
            log(f"multiple ports, picking {port}")
    log(f"port: {port}")

    # If Chrome (BF Configurator) holds the port, auto-close via AppleScript
    # helper (authorized 2026-05-21).
    try:
        import subprocess as _sp
        from pathlib import Path as _P
        helper = _P.home() / ".claude" / "skills" / "_helpers" / "close_bf_configurator.sh"
        if helper.exists():
            out = _sp.run(["lsof", port], capture_output=True, text=True).stdout
            if out.strip():
                owner = out.strip().splitlines()[-1].split()[0]
                if "Google" in owner or "Chrome" in owner:
                    log(f"{port} held by Chrome — auto-closing BF Configurator tab(s) "
                        "(first run may show macOS automation prompt — accept it) ...")
                    try:
                        _sp.run([str(helper)], timeout=20)
                    except _sp.TimeoutExpired:
                        log("  helper timed out — accept the macOS Automation prompt then retry")
                    time.sleep(1.2)
    except Exception:
        pass

    # Detect firmware
    if args.firmware == 'auto':
        fw = detect_firmware(port)
        log(f"firmware detected: {fw}")
    else:
        fw = args.firmware
        log(f"firmware forced: {fw}")

    if fw == 'betaflight':
        return bf_run_satest(port, args)
    if fw == 'ardupilot':
        return ap_run_satest(port, args)

    print(f"[error] unsupported firmware on {port}: {fw!r} "
          "(expected ArduPilot MAVLink or Betaflight MSP)", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
