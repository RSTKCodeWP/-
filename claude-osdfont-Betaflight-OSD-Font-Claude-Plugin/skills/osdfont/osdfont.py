#!/usr/bin/env python3
"""Upload an OSD font (.mcm) to a Betaflight FC over MSP.

Downloads the named font from the betaflight-configurator repo
(resources/osd/<page>/<name>.mcm), parses the MAX7456 .mcm format, and
uploads all 256 characters one at a time via MSP_OSD_CHAR_WRITE (cmd 87).

Usage:
  osdfont.py clarity            # upload Clarity (page 1)
  osdfont.py Bold               # case-insensitive
  osdfont.py clarity --page 2   # upload page 2 (extended chars)
  osdfont.py --list             # show available fonts
  osdfont.py clarity --dry-run  # download+parse, don't upload
  osdfont.py clarity --port /dev/cu.usbmodemXYZ

Exit codes:
  0 success
  1 no port / no detection / not Betaflight
  2 bad font name / parse error
  3 MSP error during upload
"""
import argparse
import glob
import json
import struct
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Known SD fonts in betaflight-configurator/resources/osd/{1,2}/
KNOWN_FONTS = [
    "betaflight", "bold", "clarity", "default", "digital",
    "extra_large", "impact", "impact_mini", "large", "vision",
]

FONT_URL = "https://raw.githubusercontent.com/betaflight/betaflight-configurator/master/resources/osd/{page}/{name}.mcm"
CACHE_DIR = Path.home() / ".cache" / "osdfont"

MAX_CHAR_COUNT = 256
NVM_CHAR_VISIBLE_BYTES = 54   # bytes of pixel data uploaded per char
NVM_CHAR_FIELD_BYTES = 64     # bytes in .mcm per char (last 10 = metadata, dropped)

MSP_FC_VARIANT = 2
MSP_BOARD_INFO = 4
MSP_OSD_CONFIG = 84
MSP_OSD_CHAR_WRITE = 87

# OSD_FLAGS bits (from BF src/main/msp/msp.c)
OSD_FLAGS = {
    0: "feature",
    3: "frskyosd",
    4: "max7456",
    5: "device_detected",
    6: "msp_displayport",
    7: "airbot_theia",
}
VIDEO_SYSTEM = {0: "AUTO", 1: "PAL", 2: "NTSC", 3: "HD"}

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
    # Fuzzy: pick the unique prefix match
    matches = [f for f in KNOWN_FONTS if f.startswith(n)]
    if len(matches) == 1:
        return matches[0]
    return None


def fetch_font(name, page=1):
    """Download .mcm into cache; return path. Page 1 or 2."""
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

def parse_mcm(path):
    """Return list of 256 bytes objects, each 54 bytes (visible char data)."""
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0].strip() != "MAX7456":
        raise SystemExit(f"[osdfont] not a MAX7456 .mcm file: {path}")
    body = [L.strip() for L in lines[1:] if L.strip()]
    expected_lines = MAX_CHAR_COUNT * NVM_CHAR_FIELD_BYTES  # 16384
    if len(body) < expected_lines:
        raise SystemExit(
            f"[osdfont] .mcm too short: {len(body)} lines, expected {expected_lines}"
        )
    chars = []
    for i in range(MAX_CHAR_COUNT):
        block = body[i * NVM_CHAR_FIELD_BYTES:(i + 1) * NVM_CHAR_FIELD_BYTES]
        char_bytes = bytearray(NVM_CHAR_FIELD_BYTES)
        for j, bits in enumerate(block):
            # each line is 8 ASCII '0'/'1' chars = 1 byte
            char_bytes[j] = int(bits, 2)
        chars.append(bytes(char_bytes[:NVM_CHAR_VISIBLE_BYTES]))
    return chars


# ---------- MSP I/O

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
        # MSP v1: '$M<' + len + cmd + payload + checksum(len^cmd^payload)
        if isinstance(payload, list):
            payload = bytes(payload)
        body = bytes([len(payload), cmd]) + payload
        frame = b"$M<" + body + bytes([self._checksum(body)])
        self.s.write(frame)
        self.s.flush()

    def recv(self, timeout=1.0):
        end = time.time() + timeout
        buf = bytearray()
        # Read header
        state = 0  # 0=$, 1=M, 2=dir, 3=len, 4=cmd, 5=payload, 6=cksum
        plen = 0
        cmd = 0
        payload = bytearray()
        while time.time() < end:
            b = self.s.read(1)
            if not b:
                continue
            b = b[0]
            if state == 0:
                if b == 0x24:  # '$'
                    state = 1
            elif state == 1:
                state = 2 if b == 0x4D else 0  # 'M'
            elif state == 2:
                if b == 0x3E:  # '>' response
                    state = 3
                elif b == 0x21:  # '!' error
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
                # checksum (ignored — we trust serial)
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
    """Returns dict with hardware type, device_detected, video_system. None on failure."""
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
    """Returns (board_id, target_name) for marker keying. None on failure."""
    try:
        m = MSP(port)
        r = m.request(MSP_BOARD_INFO, timeout=timeout)
        m.close()
        if not r or len(r) < 4:
            return None
        board_id = r[:4].decode("ascii", errors="replace")
        # Rest of payload has versions and optional name; we just need stable board id
        return board_id
    except Exception:
        return None


# ---------- per-FC marker (tracks last font we uploaded, since BF can't read it back)

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


def marker_set(key, font_name, page):
    d = _marker_load()
    d[key] = {"font": font_name, "page": page, "ts": int(time.time())}
    _marker_save(d)


# ---------- ports

def list_ports():
    return sorted(glob.glob("/dev/cu.usbmodem*"))


def find_bf_port(explicit=None):
    if explicit:
        v = msp_get_variant(explicit)
        if v == "BTFL":
            return explicit
        raise SystemExit(f"[osdfont] {explicit} did not respond as Betaflight (got: {v!r})")
    ports = list_ports()
    if not ports:
        raise SystemExit("[osdfont] no /dev/cu.usbmodem* found — is the FC plugged in?")
    for p in ports:
        v = msp_get_variant(p)
        if v == "BTFL":
            log(f"found Betaflight on {p}")
            return p
        log(f"  {p}: variant={v!r}")
    raise SystemExit("[osdfont] no Betaflight FC detected on any USB port")


# ---------- upload

def upload_font(port, chars, page=1):
    """Write all 256 characters via MSP_OSD_CHAR_WRITE. Page 1 uses 1-byte addr; page 2 uses 2-byte addr."""
    m = MSP(port)
    is_tty = sys.stderr.isatty()
    bar_width = 40
    try:
        for i, data in enumerate(chars):
            if page == 1:
                addr = i
                payload = bytes([addr]) + data
            else:
                addr = 256 + i
                payload = struct.pack("<H", addr) + data
            m.send(MSP_OSD_CHAR_WRITE, payload)
            rcmd, _ = m.recv(timeout=2.0)
            if rcmd != MSP_OSD_CHAR_WRITE:
                raise SystemExit(
                    f"[osdfont] no/bad MSP reply at char {i} (got cmd={rcmd}). "
                    f"Aborting at {i}/{len(chars)} written."
                )
            time.sleep(0.015)  # MAX7456 NVM write ~12 ms; 15 ms gives margin
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


# ---------- preflight printer (shared by upload + --probe)

def _marker_key(port):
    """Per-FC key: port basename (includes USB serial, unique per FC). Board ID alone (e.g. 'H743') would conflate multiple FCs in the fleet."""
    return Path(port).name


def _print_preflight(port):
    """Print OSD/camera state + last-known font for this FC. Returns the marker key."""
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
            log("  hint: font still writes to MAX7456 NVM with no camera attached — it just")
            log("  won't display until camera + cable + VTX are wired up.")

    prev = marker_get(board)
    if prev:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(prev["ts"]))
        log(f"previous font (per local marker): {prev['font']} (page {prev['page']}, uploaded {ts})")
    else:
        log("previous font: unknown — BF firmware has no MSP_OSD_CHAR_READ, and "
            "this is the first /osdfont run on this FC.")
    return board


# ---------- main

def main():
    ap = argparse.ArgumentParser(description="Upload an OSD .mcm font to a Betaflight FC")
    ap.add_argument("name", nargs="?", help="font name (e.g. clarity, bold)")
    ap.add_argument("--page", type=int, default=1, choices=(1, 2),
                    help="font page (1 = chars 0-255, 2 = chars 256-511)")
    ap.add_argument("--list", action="store_true", help="list available fonts and exit")
    ap.add_argument("--dry-run", action="store_true", help="download+parse only; don't talk to FC")
    ap.add_argument("--probe", action="store_true", help="show FC camera/OSD status + last-known font, don't upload")
    ap.add_argument("--port", help="override port autodetect")
    args = ap.parse_args()

    if args.list:
        print("Available fonts (betaflight-configurator/resources/osd/):")
        for f in KNOWN_FONTS:
            print(f"  {f}")
        return 0

    if args.probe:
        port = find_bf_port(args.port)
        _print_preflight(port)
        return 0

    if not args.name:
        ap.print_usage()
        return 2

    name = resolve_font_name(args.name)
    if not name:
        log(f"unknown font {args.name!r}. Known: {', '.join(KNOWN_FONTS)}")
        return 2
    log(f"font: {name}  page: {args.page}")

    mcm_path = fetch_font(name, page=args.page)
    chars = parse_mcm(mcm_path)
    log(f"parsed {len(chars)} chars × {len(chars[0])} bytes")

    if args.dry_run:
        log("dry-run: skipping upload")
        return 0

    port = find_bf_port(args.port)
    board = _print_preflight(port)

    log(f"uploading {name} (page {args.page}) to {port} ...")
    t0 = time.time()
    upload_font(port, chars, page=args.page)
    marker_set(board, name, args.page)
    log(f"done in {time.time() - t0:.1f}s. Font persists in MAX7456 NVM; no reboot required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
