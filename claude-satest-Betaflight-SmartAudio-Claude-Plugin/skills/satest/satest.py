#!/usr/bin/env python3
"""/satest — SmartAudio sanity test on a Betaflight FC.

Flow:
  1. Auto-detect /dev/cu.usbmodem* and confirm BF over MSP.
  2. Read MSP_VTX_CONFIG (cmd 88). Inspect:
       - device_type (byte 0): 0 = no VTX driver bound to a UART (or feature off)
       - deviceIsReady (byte 7, BF 4.2+): 0 = driver loaded but VTX isn't talking back
  3. If either flag indicates a problem, print actionable recommendations and
     exit non-zero.
  4. Otherwise, print Channel / Band / Power, then perform the toggle test:
       - if currently on Raceband ch1 → switch to R2, wait 5s, back to R1
       - if not on R1 → switch to R1, then do R1→R2→wait→R1
  5. Exit 0. The caller (Claude) prompts the user to confirm video changed.

Raceband index is looked up via MSP2_GET_VTXTABLE_BAND (0x1009) so we use the
FC's actual vtxtable rather than guessing. Falls back to current-band-if-it-
looks-like-Raceband, then BF default (5).

Usage:
  satest.py                 # full run
  satest.py --status-only   # just print SA status + current channel, no test
  satest.py --port /dev/... # override port
"""
import argparse
import glob
import struct
import sys
import time


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


def find_raceband_index(port, bands_count, current_band):
    """Return (band_idx, source_str). source_str describes how we found it."""
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

def set_vtx_channel(port, band, channel, power):
    """Apply band/channel, preserve power, save EEPROM. Returns new port (FC reboots)."""
    m = MSP(port)
    try:
        bandChan = (band - 1) * 8 + (channel - 1)
        payload = struct.pack('<HBB', bandChan, power, 0)
        log(f"MSP_SET_VTX_CONFIG bandChan={bandChan} (band={band} ch={channel}) power={power}")
        m.v1(89, payload, wait=1.0)
        log("MSP_EEPROM_WRITE (FC will reboot)")
        m.v1(250, b'', wait=2.5)
    finally:
        m.close()
    # BF boot cycle is sacred — 8s pure quiet after EEPROM_WRITE reboot.
    # Aggressive polling stalls Dshot init → ESCs beep. memory: feedback_bf_boot_cycle_quiet.md
    log("post-EEPROM_WRITE quiet (8s — letting FC complete its boot cycle untouched)")
    time.sleep(8.0)
    pre_existing = []
    new_ports = wait_for_port(exclude=pre_existing, timeout=15)
    return new_ports[0] if new_ports else None


def verify_band_channel(port, want_band, want_channel, retries=3):
    for _ in range(retries):
        cfg = read_vtx_config(port)
        if cfg and cfg['band'] == want_band and cfg['channel'] == want_channel:
            return True, cfg
        time.sleep(0.6)
    return False, cfg


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


# ---------- Main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default=None)
    ap.add_argument('--status-only', action='store_true',
                    help="Print status and exit; do not toggle channels")
    ap.add_argument('--wait', type=float, default=5.0,
                    help="Seconds to hold the R2 step (default 5)")
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

    # Detect BF
    variant = probe_variant(port)
    log(f"FC variant: {variant!r}")
    if variant != 'BTFL':
        print(f"[error] satest is Betaflight-only; got variant {variant!r}", file=sys.stderr)
        return 1

    cfg = read_vtx_config(port)
    if not cfg:
        print("[error] MSP_VTX_CONFIG returned nothing", file=sys.stderr)
        return 3
    log(f"raw VTX cfg: {cfg}")

    # Look up Raceband index + current power label
    raceband_idx, rb_src = find_raceband_index(port, cfg.get('bands_count'), cfg['band'])
    log(f"Raceband index → {raceband_idx} ({rb_src})")

    current_band_info = None
    if cfg.get('bands_count'):
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
    cur_band, cur_ch = cfg['band'], cfg['channel']
    on_r1 = (cur_band == raceband_idx and cur_ch == 1)

    if not on_r1:
        print(f"-> Not on Raceband ch1 (currently band={cur_band} ch={cur_ch}). Switching to R1 first.")
        new_port = set_vtx_channel(port, raceband_idx, 1, cfg['power'])
        if new_port:
            port = new_port
            log(f"reconnected on {port}")
        ok, _ = verify_band_channel(port, raceband_idx, 1)
        if not ok:
            print("[error] failed to land on R1 after reboot", file=sys.stderr)
            return 4

    # Now we're on R1. Do R1 -> R2 -> wait -> R1.
    print(f"-> On Raceband ch1. Switching to R2 for {args.wait:.0f}s (watch your goggles)...")
    new_port = set_vtx_channel(port, raceband_idx, 2, cfg['power'])
    if new_port:
        port = new_port
    ok, _ = verify_band_channel(port, raceband_idx, 2)
    if not ok:
        print("[error] R2 not confirmed by readback", file=sys.stderr)
        return 4
    print("   ...now on R2.")

    time.sleep(args.wait)

    print("-> Switching back to R1.")
    new_port = set_vtx_channel(port, raceband_idx, 1, cfg['power'])
    if new_port:
        port = new_port
    ok, after = verify_band_channel(port, raceband_idx, 1)
    if not ok:
        print(f"[error] R1 not confirmed by readback; current = {after}", file=sys.stderr)
        return 4
    print("   ...back on R1.")
    print()
    print("Test sequence complete. End state: Raceband ch1.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
