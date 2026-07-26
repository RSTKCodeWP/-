#!/usr/bin/env python3
"""Upload an OSD font (.mcm) to a connected Betaflight OR ArduPilot FC.

Autodetects the FC family on the USB port:
  - Betaflight (MSP_FC_VARIANT == 'BTFL')  -> MSP_OSD_CHAR_WRITE per char (MAX7456 NVM)
  - ArduPilot  (MAVLink heartbeat)         -> MAVFTP upload to /APM/font0.bin
                                              + toggle OSD_FONT to force reload

Default font is `clarity` for both families.

Usage:
  osdfont.py                     # autodetect FC, upload clarity
  osdfont.py clarity             # explicit name
  osdfont.py Bold                # case-insensitive
  osdfont.py clarity --page 2    # BF only: page 2 (extended chars)
  osdfont.py --list              # show available fonts
  osdfont.py clarity --dry-run   # download+parse, don't talk to FC
  osdfont.py clarity --probe     # show FC OSD status, don't upload
  osdfont.py clarity --port /dev/cu.usbmodemXYZ

Exit codes:
  0 success
  1 no port / no detection / unsupported FC
  2 bad font name / parse error
  3 MSP / MAVLink / MAVFTP error during upload
"""
import argparse
import glob
import json
import struct
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

# Known SD fonts in betaflight-configurator/resources/osd/{1,2}/
KNOWN_FONTS = [
    "betaflight", "bold", "clarity", "default", "digital",
    "extra_large", "impact", "impact_mini", "large", "vision",
]
DEFAULT_FONT = "clarity"

# ArduPilot's 5 ROMFS-embedded fonts (libraries/AP_OSD/fonts/font0..font4.bin).
# When OSD_FONT is 0..4 AP loads from ROMFS — no MAVFTP needed.
# Map BF-style font names → AP built-in OSD_FONT index.
AP_BUILTIN_FONTS = {
    "clarity": 0,         # libraries/AP_OSD/fonts/clarity.mcm
    "clarity_medium": 1,  # libraries/AP_OSD/fonts/clarity_medium.mcm
    "bfstyle": 2,         # libraries/AP_OSD/fonts/bfstyle.mcm
    "betaflight": 2,      # BF's "betaflight" font ≈ AP's BFStyle
    "bold": 3,            # libraries/AP_OSD/fonts/bold.mcm
    "digital": 4,         # libraries/AP_OSD/fonts/digital.mcm
}

FONT_URL = "https://raw.githubusercontent.com/betaflight/betaflight-configurator/master/resources/osd/{page}/{name}.mcm"
CACHE_DIR = Path.home() / ".cache" / "osdfont"

MAX_CHAR_COUNT = 256
NVM_CHAR_VISIBLE_BYTES = 54   # bytes of pixel data per char (BF + AP both use 54)
NVM_CHAR_FIELD_BYTES = 64     # bytes per char in the .mcm file (last 10 = metadata, dropped)
# AP_OSD_MAX7456 expects exactly NVM_RAM_SIZE(54) * 256 = 13824 bytes per font0.bin.
AP_FONT_BYTES = MAX_CHAR_COUNT * NVM_CHAR_VISIBLE_BYTES  # 13824

# Betaflight MSP commands
MSP_FC_VARIANT = 2
MSP_BOARD_INFO = 4
MSP_OSD_CONFIG = 84
MSP_OSD_CHAR_WRITE = 87

# OSD_FLAGS bits (BF MSP_OSD_CONFIG)
OSD_FLAGS = {
    0: "feature",
    3: "frskyosd",
    4: "max7456",
    5: "device_detected",
    6: "msp_displayport",
    7: "airbot_theia",
}
VIDEO_SYSTEM = {0: "AUTO", 1: "PAL", 2: "NTSC", 3: "HD"}

# ArduPilot OSD_TYPE values
AP_OSD_TYPE = {0: "NONE", 1: "MAX7456", 3: "SITL", 5: "MSP", 7: "MSP_DISPLAYPORT", 8: "TXONLY"}

# Where AP looks for its analog OSD font on the FC filesystem.
AP_FONT_REMOTE_PATH = "/APM/font0.bin"
AP_FONT_SLOT = 0  # we upload as font0.bin and select slot 0

MARKER_FILE = CACHE_DIR / "last_uploaded.json"


def log(msg):
    print(f"[osdfont] {msg}", file=sys.stderr, flush=True)


# ---------- font name resolution + download

def resolve_font_name(user_name):
    """Match user input against KNOWN_FONTS, case-insensitive, with friendly aliases."""
    n = user_name.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "xl": "extra_large", "extra-large": "extra_large", "extralarge": "extra_large",
        "impactmini": "impact_mini", "mini": "impact_mini",
    }
    n = aliases.get(n, n)
    if n in KNOWN_FONTS:
        return n
    matches = [f for f in KNOWN_FONTS if f.startswith(n)]
    if len(matches) == 1:
        return matches[0]
    return None


def fetch_font(name, page=1):
    """Download .mcm into cache; return path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{page}_{name}.mcm"
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        log(f"using cached {cache_path}")
        return cache_path
    url = FONT_URL.format(page=page, name=name)
    log(f"downloading {url}")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[osdfont] font not found at {url}: HTTP {e.code}")
    except urllib.error.URLError as e:
        raise SystemExit(f"[osdfont] download failed: {e.reason}")
    cache_path.write_bytes(data)
    log(f"cached -> {cache_path} ({len(data)} bytes)")
    return cache_path


# ---------- .mcm parsing

def _mcm_body_lines(path):
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0].strip() != "MAX7456":
        raise SystemExit(f"[osdfont] not a MAX7456 .mcm file: {path}")
    body = [L.strip() for L in lines[1:] if L.strip()]
    expected = MAX_CHAR_COUNT * NVM_CHAR_FIELD_BYTES  # 16384
    if len(body) < expected:
        raise SystemExit(f"[osdfont] .mcm too short: {len(body)} lines, expected {expected}")
    return body


def parse_mcm_bf(path):
    """BF path: 256 chars × 54 visible bytes each (last 10 NVM metadata bytes dropped)."""
    body = _mcm_body_lines(path)
    chars = []
    for i in range(MAX_CHAR_COUNT):
        block = body[i * NVM_CHAR_FIELD_BYTES:(i + 1) * NVM_CHAR_FIELD_BYTES]
        buf = bytearray(NVM_CHAR_FIELD_BYTES)
        for j, bits in enumerate(block):
            buf[j] = int(bits, 2)
        chars.append(bytes(buf[:NVM_CHAR_VISIBLE_BYTES]))
    return chars


def parse_mcm_ap(path):
    """AP path: 256 × 54 visible pixel bytes = 13824 bytes raw (matches AP_OSD_MAX7456:
    expected size = NVM_RAM_SIZE(54) * 256). The 10 trailing NVM-metadata bytes per char
    in the .mcm are dropped — same as BF — verified against ROMFS font0.bin sizes."""
    body = _mcm_body_lines(path)
    out = bytearray(AP_FONT_BYTES)
    for i in range(MAX_CHAR_COUNT):
        block = body[i * NVM_CHAR_FIELD_BYTES:i * NVM_CHAR_FIELD_BYTES + NVM_CHAR_VISIBLE_BYTES]
        for j, bits in enumerate(block):
            out[i * NVM_CHAR_VISIBLE_BYTES + j] = int(bits, 2)
    return bytes(out)


# ---------- MSP I/O (Betaflight)

class MSP:
    def __init__(self, port, baud=115200):
        import serial
        self.s = serial.Serial(port, baud, timeout=0.5)
        time.sleep(0.2)
        self.s.reset_input_buffer()

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass

    @staticmethod
    def _checksum(data):
        c = 0
        for b in data:
            c ^= b
        return c

    def send(self, cmd, payload=b""):
        if isinstance(payload, list):
            payload = bytes(payload)
        body = bytes([len(payload), cmd]) + payload
        frame = b"$M<" + body + bytes([self._checksum(body)])
        self.s.write(frame)
        self.s.flush()

    def recv(self, timeout=1.0):
        end = time.time() + timeout
        state = 0
        plen = 0
        cmd = 0
        payload = bytearray()
        while time.time() < end:
            b = self.s.read(1)
            if not b:
                continue
            b = b[0]
            if state == 0:
                if b == 0x24:
                    state = 1
            elif state == 1:
                state = 2 if b == 0x4D else 0
            elif state == 2:
                if b == 0x3E or b == 0x21:
                    state = 3
                else:
                    state = 0
            elif state == 3:
                plen = b
                state = 4
            elif state == 4:
                cmd = b
                payload = bytearray()
                state = 5 if plen > 0 else 6
            elif state == 5:
                payload.append(b)
                if len(payload) >= plen:
                    state = 6
            elif state == 6:
                return cmd, bytes(payload)
        return None, None

    def request(self, cmd, payload=b"", timeout=1.0):
        self.send(cmd, payload)
        rcmd, rpayload = self.recv(timeout=timeout)
        return rpayload if rcmd == cmd else None


def msp_get_variant(port, timeout=1.0):
    try:
        m = MSP(port)
        r = m.request(MSP_FC_VARIANT, timeout=timeout)
        m.close()
        if r and len(r) >= 4:
            return r[:4].decode("ascii", errors="replace")
    except Exception as e:
        log(f"variant probe on {port} failed: {e}")
    return None


def msp_get_osd_config(port, timeout=1.0):
    try:
        m = MSP(port)
        r = m.request(MSP_OSD_CONFIG, timeout=timeout)
        m.close()
        if not r or len(r) < 2:
            return None
        flags = r[0]
        video = r[1]
        hw = []
        for bit, name in OSD_FLAGS.items():
            if flags & (1 << bit) and name not in ("feature", "device_detected"):
                hw.append(name)
        return {
            "flags": flags,
            "hardware": hw or ["unknown"],
            "device_detected": bool(flags & (1 << 5)),
            "video_system": VIDEO_SYSTEM.get(video, f"unknown({video})"),
        }
    except Exception as e:
        log(f"OSD_CONFIG probe failed: {e}")
        return None


def msp_get_board_info(port, timeout=1.0):
    try:
        m = MSP(port)
        r = m.request(MSP_BOARD_INFO, timeout=timeout)
        m.close()
        if not r or len(r) < 4:
            return None
        return r[:4].decode("ascii", errors="replace")
    except Exception:
        return None


# ---------- per-FC marker

def _marker_load():
    if MARKER_FILE.exists():
        try:
            return json.loads(MARKER_FILE.read_text())
        except Exception:
            return {}
    return {}


def _marker_save(d):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MARKER_FILE.write_text(json.dumps(d, indent=2))


def marker_get(key):
    return _marker_load().get(key)


def marker_set(key, font_name, page, family):
    d = _marker_load()
    d[key] = {"font": font_name, "page": page, "family": family, "ts": int(time.time())}
    _marker_save(d)


def _marker_key(port):
    """Per-FC key: port basename uniquely identifies the FC via its USB serial."""
    return Path(port).name


# ---------- port discovery

def list_ports():
    return sorted(glob.glob("/dev/cu.usbmodem*"))


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


def detect_fc(explicit=None):
    """Return (family, port). family is 'bf' or 'ap'. Raises SystemExit on failure.

    PASSIVE-LISTEN-FIRST (2026-05-20). Sniff each candidate port for the AP
    MAVLink stream WITHOUT sending anything. If AP is streaming, we hear it
    and never MSP-probe (so AP's USB CDC stays in MAVLink mode and downstream
    ops work). Silent → MSP probe (BTFL=BF, ARDU=AP via DisplayPort).
    Last resort: MAVLink heartbeat probe.
    """
    def _identify(p):
        if passive_listen_mavlink(p):
            log(f"detected ArduPilot on {p} (passive-listen: MAVLink stream)")
            return ("ap", p)
        v = msp_get_variant(p)
        if v == "BTFL":
            log(f"detected Betaflight on {p} (MSP variant 'BTFL')")
            return ("bf", p)
        if v == "ARDU":
            time.sleep(0.5)
            log(f"detected ArduPilot on {p} (MSP variant 'ARDU')")
            return ("ap", p)
        log(f"  {p}: MSP variant={v!r}; last-resort MAVLink heartbeat probe ...")
        if probe_mavlink(p, attempts=2, per_attempt=3.0):
            log(f"detected ArduPilot on {p} (MAVLink heartbeat)")
            return ("ap", p)
        return None

    if explicit:
        r = _identify(explicit)
        if r:
            return r
        raise SystemExit(f"[osdfont] {explicit}: unsupported FC (no MAVLink stream, no MSP BTFL/ARDU)")

    ports = list_ports()
    if not ports:
        raise SystemExit("[osdfont] no /dev/cu.usbmodem* found — is the FC plugged in?")
    for p in ports:
        r = _identify(p)
        if r:
            return r
    raise SystemExit("[osdfont] no Betaflight or ArduPilot FC detected on any USB port")


def probe_mavlink(port, attempts=3, per_attempt=4.0):
    """Open MAVLink at 115200, send 4× GCS heartbeats, wait for the FC's heartbeat.
    Closes cleanly so the caller can reopen. Retries because AP's USB multiplexer
    can take a moment to switch back from MSP to MAVLink mode.
    """
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
            for _ in range(4):
                m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                     mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                time.sleep(0.2)
            hb = m.wait_heartbeat(timeout=per_attempt)
            if hb is not None:
                return True
            log(f"  no MAVLink heartbeat on {port} (attempt {attempt}/{attempts})")
        except Exception as e:
            log(f"  MAVLink probe error on {port} (attempt {attempt}/{attempts}): {e}")
        finally:
            if m is not None:
                try:
                    m.close()
                except Exception:
                    pass
            time.sleep(0.3)
    return False


# ===========================================================================
# Betaflight upload path
# ===========================================================================

def upload_bf_font(port, chars, page=1):
    m = MSP(port)
    is_tty = sys.stderr.isatty()
    bar_width = 40
    try:
        for i, data in enumerate(chars):
            if page == 1:
                payload = bytes([i]) + data
            else:
                payload = struct.pack("<H", 256 + i) + data
            m.send(MSP_OSD_CHAR_WRITE, payload)
            rcmd, _ = m.recv(timeout=2.0)
            if rcmd != MSP_OSD_CHAR_WRITE:
                raise SystemExit(
                    f"[osdfont] no/bad MSP reply at char {i} (got cmd={rcmd}). "
                    f"Aborted at {i}/{len(chars)}."
                )
            time.sleep(0.015)  # MAX7456 NVM write ~12 ms
            if is_tty:
                filled = int((i + 1) / len(chars) * bar_width)
                sys.stderr.write(
                    f"\r[osdfont] [{'#' * filled}{'.' * (bar_width - filled)}] "
                    f"{i + 1}/{len(chars)}"
                )
                sys.stderr.flush()
            elif (i + 1) % 32 == 0 or (i + 1) == len(chars):
                log(f"  {i + 1}/{len(chars)}")
        if is_tty:
            sys.stderr.write("\n")
    finally:
        m.close()


def _bf_preflight(port):
    board_id = msp_get_board_info(port)
    board = _marker_key(port)
    if board_id:
        log(f"FC: board={board_id}  port={port}")
    osd = msp_get_osd_config(port)
    if osd is None:
        log("WARNING: MSP_OSD_CONFIG didn't respond — can't verify OSD hardware.")
    else:
        hw = ", ".join(osd["hardware"])
        cam = "video signal detected" if osd["device_detected"] else "NO video / camera not detected"
        log(f"OSD hardware: {hw}  |  status: {cam}  |  video: {osd['video_system']}")
        if not osd["device_detected"]:
            log("  hint: font still writes to MAX7456 NVM with no camera attached;")
            log("  it just won't display until camera + cable + VTX are wired up.")
    prev = marker_get(board)
    if prev:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(prev["ts"]))
        log(f"previous font (local marker): {prev['font']} "
            f"(page {prev.get('page', 1)}, {prev.get('family','?')}, uploaded {ts})")
    else:
        log("previous font: unknown — BF has no MSP_OSD_CHAR_READ, and this is the first "
            "/osdfont run on this FC.")
    return board


def run_bf(port, name, page):
    log(f"font: {name}  page: {page}  family: betaflight")
    mcm = fetch_font(name, page=page)
    chars = parse_mcm_bf(mcm)
    log(f"parsed {len(chars)} chars × {len(chars[0])} bytes")
    board = _bf_preflight(port)
    log(f"uploading {name} (page {page}) to {port} ...")
    t0 = time.time()
    upload_bf_font(port, chars, page=page)
    marker_set(board, name, page, "bf")
    log(f"done in {time.time() - t0:.1f}s. Font persists in MAX7456 NVM; no reboot required.")


# ===========================================================================
# ArduPilot upload path
# ===========================================================================

def _ap_connect(port):
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(port, baud=115200,
                                   source_system=255, source_component=190)
    # Advertise our GCS heartbeat first so AP's USB multiplexer keeps streaming
    # MAVLink (and doesn't slip back into MSP mode mid-session).
    for _ in range(4):
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        time.sleep(0.2)
    log("waiting for heartbeat ...")
    hb = m.wait_heartbeat(timeout=10)
    if hb is None:
        raise SystemExit("[osdfont] no MAVLink heartbeat — is this an AP FC?")
    log(f"connected sys={m.target_system} comp={m.target_component}")
    return m


def _ap_read_param(m, name, timeout=2.0, retries=3):
    """Read one parameter; retry per CLAUDE.md note about silent drops."""
    for _ in range(retries):
        m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
        t0 = time.time()
        while time.time() - t0 < timeout:
            msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=timeout)
            if msg is None:
                break
            n = msg.param_id
            if isinstance(n, bytes):
                n = n.decode("ascii", errors="ignore").rstrip("\x00")
            if n == name:
                return msg.param_value, msg.param_type
    return None, None


def _ap_set_param(m, name, value, ptype):
    from pymavlink import mavutil  # noqa
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value), ptype)
    t0 = time.time()
    while time.time() - t0 < 2.0:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if msg is None:
            continue
        n = msg.param_id
        if isinstance(n, bytes):
            n = n.decode("ascii", errors="ignore").rstrip("\x00")
        if n == name:
            return True, msg.param_value
    return False, None


def _ap_preflight(m, port):
    """Read current OSD_TYPE/OSD_TYPE2/OSD_FONT and print state. Returns dict."""
    board = _marker_key(port)
    osd_type, _ = _ap_read_param(m, "OSD_TYPE")
    osd_type2, _ = _ap_read_param(m, "OSD_TYPE2")
    osd_font, osd_font_t = _ap_read_param(m, "OSD_FONT")

    def _fmt_type(v):
        if v is None:
            return "?"
        i = int(round(v))
        return f"{i} ({AP_OSD_TYPE.get(i, 'unknown')})"

    log(f"FC: port={port}")
    log(f"  OSD_TYPE  = {_fmt_type(osd_type)}")
    log(f"  OSD_TYPE2 = {_fmt_type(osd_type2)}")
    log(f"  OSD_FONT  = {int(round(osd_font)) if osd_font is not None else '?'}")
    max7456_active = (osd_type is not None and int(round(osd_type)) == 1) or \
                     (osd_type2 is not None and int(round(osd_type2)) == 1)
    if not max7456_active:
        log("  NOTE: neither OSD_TYPE nor OSD_TYPE2 is MAX7456 (=1).")
        log("        Uploading font0.bin still works but won't change the visible OSD")
        log("        until a MAX7456 backend is enabled. HD/DisplayPort goggles hold")
        log("        their own font; the FC-side font0.bin doesn't apply to them.")

    prev = marker_get(board)
    if prev:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(prev["ts"]))
        log(f"  previous font (local marker): {prev['font']} "
            f"({prev.get('family','?')}, uploaded {ts})")
    else:
        log("  previous font: unknown — first /osdfont run on this FC.")
    return {
        "board": board,
        "osd_font_value": osd_font,
        "osd_font_type": osd_font_t,
        "max7456_active": max7456_active,
    }


def _ap_ftp_put(m, local_path, remote_path):
    """Upload `local_path` to FC `remote_path` via MAVFTP. Returns (ok, error_code).
    error_code is the FtpError enum value (or 0 on success).
    process_ftp_reply runs the full transaction internally — one call drives the
    whole put (CreateFile → WriteFile chunks → ACKs → idle).
    """
    from pymavlink import mavftp
    ftp = mavftp.MAVFTP(m, m.target_system, m.target_component)
    rc = ftp.cmd_put([str(local_path), remote_path])
    if rc.error_code.value != 0:
        return False, rc.error_code
    rc = ftp.process_ftp_reply("CreateFile", timeout=90)
    return rc.error_code.value == 0, rc.error_code


def _ap_ftp_writable(m):
    """Probe whether MAVFTP has a writable filesystem on this FC by putting a
    tiny temp file. Returns (path_that_worked, error_code_or_None).
    """
    import tempfile, os
    with tempfile.NamedTemporaryFile(prefix="osdfont_probe_", suffix=".tmp",
                                     delete=False) as tf:
        tf.write(b"probe\n")
        probe_local = tf.name
    try:
        from pymavlink import mavftp
        # Try the same candidate paths font0.bin would use.
        for candidate in ["/APM/font0.bin.probe", "/font0.bin.probe", "font0.bin.probe"]:
            ok, err = _ap_ftp_put(m, probe_local, candidate)
            if ok:
                # Clean up the probe file.
                ftp = mavftp.MAVFTP(m, m.target_system, m.target_component)
                ftp.cmd_rm([candidate])
                return candidate.replace(".probe", ""), None
        return None, err
    finally:
        try:
            os.unlink(probe_local)
        except Exception:
            pass


def _ap_trigger_font_reload(m, current_font_value, current_font_type):
    """Set OSD_FONT to AP_FONT_SLOT, toggling first if it already matches, to force reload."""
    from pymavlink import mavutil
    if current_font_type is None:
        ptype = mavutil.mavlink.MAV_PARAM_TYPE_INT8
    else:
        ptype = current_font_type

    cur = int(round(current_font_value)) if current_font_value is not None else -1
    if cur == AP_FONT_SLOT:
        # Force reload by toggling to a different value first.
        alt = 1 if AP_FONT_SLOT != 1 else 2
        log(f"  OSD_FONT already {AP_FONT_SLOT}; toggling {AP_FONT_SLOT} -> {alt} -> {AP_FONT_SLOT} "
            f"to force reload")
        _ap_set_param(m, "OSD_FONT", alt, ptype)
        time.sleep(0.5)
    else:
        log(f"  OSD_FONT {cur} -> {AP_FONT_SLOT}")
    ok, reported = _ap_set_param(m, "OSD_FONT", AP_FONT_SLOT, ptype)
    if not ok:
        log("  WARNING: OSD_FONT set didn't confirm — font may not reload until reboot")
        return False
    log(f"  OSD_FONT confirmed at {int(round(reported))}")
    return True


def run_ap(port, name):
    try:
        from pymavlink import mavutil  # noqa: F401
        from pymavlink import mavftp   # noqa: F401
    except ImportError as e:
        raise SystemExit(f"[osdfont] pymavlink/mavftp not available: {e}")

    log(f"font: {name}  family: ardupilot")

    m = _ap_connect(port)
    pre = _ap_preflight(m, port)

    # AP fast-path: 5 fonts are baked into ROMFS at libraries/AP_OSD/fonts/font0..font4.bin.
    # If the user asked for one of those, just set OSD_FONT — no MAVFTP needed.
    builtin_idx = AP_BUILTIN_FONTS.get(name)
    if builtin_idx is not None:
        log(f"'{name}' is built into AP ROMFS as font{builtin_idx}.bin "
            f"(no upload needed; setting OSD_FONT) ...")
        _ap_set_builtin_font(m, builtin_idx, pre["osd_font_value"], pre["osd_font_type"])
        marker_set(pre["board"], name, 1, "ap")
        if not pre["max7456_active"]:
            log("done. (Reminder: no MAX7456 backend active — visible OSD unchanged.)")
        else:
            log(f"done — OSD_FONT = {builtin_idx}; AP reloads on the next OSD draw.")
        return

    # Custom font — requires writable filesystem (SD card or LittleFS) to upload via MAVFTP.
    mcm = fetch_font(name, page=1)
    bin_data = parse_mcm_ap(mcm)
    log(f"parsed AP font: {len(bin_data)} bytes "
        f"({MAX_CHAR_COUNT} chars × {NVM_CHAR_VISIBLE_BYTES}, matches AP_OSD_MAX7456)")
    log(f"'{name}' is NOT one of AP's 5 ROMFS-baked fonts "
        f"({', '.join(sorted(AP_BUILTIN_FONTS))}) — needs MAVFTP upload.")

    log("probing FC filesystem for a writable path ...")
    write_path, probe_err = _ap_ftp_writable(m)
    if write_path is None:
        log(f"  no writable filesystem on this FC (MAVFTP put failed with {probe_err}).")
        log("  Per ArduPilot docs, custom fonts upload to the SD card root as font0..9.bin;")
        log("  this board has no SD card mounted and no LittleFS. Options:")
        log("    (a) add an SD card so the root becomes writable, OR")
        log("    (b) rebuild AP with your .bin baked into libraries/AP_OSD/fonts/ "
            "(replace font0..4), OR")
        log(f"    (c) pick one of AP's built-ins: {', '.join(sorted(AP_BUILTIN_FONTS))}")
        raise SystemExit("[osdfont] AP filesystem not writable — see hints above")
    log(f"  writable path: {write_path}")

    with tempfile.NamedTemporaryFile(prefix=f"osdfont_{name}_", suffix=".bin", delete=False) as tf:
        tf.write(bin_data)
        local_path = Path(tf.name)
    try:
        log(f"uploading {name} -> {write_path} ...")
        t0 = time.time()
        ok, err = _ap_ftp_put(m, local_path, write_path)
        if not ok:
            raise SystemExit(f"[osdfont] MAVFTP upload failed: {err}")
        log(f"  upload OK in {time.time() - t0:.1f}s")
        log("triggering font reload via OSD_FONT param ...")
        _ap_trigger_font_reload(m, pre["osd_font_value"], pre["osd_font_type"])
        marker_set(pre["board"], name, 1, "ap")
        if not pre["max7456_active"]:
            log("done. (Reminder: no MAX7456 backend active — visible OSD unchanged.)")
        else:
            log("done — AP reloads font0.bin on the OSD_FONT change; no reboot needed.")
    finally:
        try:
            local_path.unlink()
        except Exception:
            pass


def _ap_set_builtin_font(m, target_idx, current_value, current_type):
    """Set OSD_FONT to a built-in index. If already at target, toggle to force reload."""
    from pymavlink import mavutil
    ptype = current_type if current_type is not None else mavutil.mavlink.MAV_PARAM_TYPE_INT8
    cur = int(round(current_value)) if current_value is not None else -1
    if cur == target_idx:
        alt = (target_idx + 1) % 5
        log(f"  OSD_FONT already {target_idx}; toggling {target_idx} -> {alt} -> {target_idx} "
            f"to force reload")
        _ap_set_param(m, "OSD_FONT", alt, ptype)
        time.sleep(0.5)
    else:
        log(f"  OSD_FONT {cur} -> {target_idx}")
    ok, reported = _ap_set_param(m, "OSD_FONT", target_idx, ptype)
    if not ok:
        log("  WARNING: OSD_FONT set didn't confirm")
        return False
    log(f"  OSD_FONT confirmed at {int(round(reported))}")
    return True


# ===========================================================================
# main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(description="Upload an OSD .mcm font to a BF or AP FC")
    ap.add_argument("name", nargs="?", default=None,
                    help=f"font name (default: {DEFAULT_FONT})")
    ap.add_argument("--page", type=int, default=1, choices=(1, 2),
                    help="BF only: font page (1 = chars 0-255, 2 = 256-511)")
    ap.add_argument("--list", action="store_true", help="list available fonts and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="download+parse only; don't talk to FC")
    ap.add_argument("--probe", action="store_true",
                    help="show FC OSD status + last-known font, don't upload")
    ap.add_argument("--port", help="override port autodetect")
    ap.add_argument("--family", choices=("bf", "ap"),
                    help="force FC family (skip autodetect)")
    args = ap.parse_args()

    if args.list:
        print("Available fonts (betaflight-configurator/resources/osd/):")
        for f in KNOWN_FONTS:
            print(f"  {f}{'  (default)' if f == DEFAULT_FONT else ''}")
        return 0

    # Resolve font name (used by --probe display too, and required for upload).
    name_in = args.name or DEFAULT_FONT
    name = resolve_font_name(name_in)
    if not name:
        log(f"unknown font {name_in!r}. Known: {', '.join(KNOWN_FONTS)}")
        return 2

    if args.dry_run:
        log(f"font: {name}  page: {args.page}  (dry-run)")
        mcm = fetch_font(name, page=args.page)
        # Sanity-check both parse paths.
        bf_chars = parse_mcm_bf(mcm)
        ap_bin = parse_mcm_ap(mcm)
        log(f"BF parse: {len(bf_chars)} chars × {len(bf_chars[0])} bytes")
        log(f"AP parse: {len(ap_bin)} bytes")
        log("dry-run: skipping FC contact")
        return 0

    # Detect or use forced family.
    if args.family and args.port:
        family, port = args.family, args.port
    elif args.family:
        ports = list_ports()
        if not ports:
            raise SystemExit("[osdfont] no /dev/cu.usbmodem* found")
        port = ports[0]
        family = args.family
        log(f"forced family={family} on {port}")
    else:
        family, port = detect_fc(args.port)

    if args.probe:
        if family == "bf":
            _bf_preflight(port)
        else:
            m = _ap_connect(port)
            _ap_preflight(m, port)
        return 0

    if family == "bf":
        run_bf(port, name, args.page)
    elif family == "ap":
        if args.page != 1:
            log("note: --page 2 not supported on AP; ignoring")
        run_ap(port, name)
    else:
        raise SystemExit(f"[osdfont] unsupported family: {family}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
