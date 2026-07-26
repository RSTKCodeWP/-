#!/usr/bin/env python3
"""mgrsosd — minimal: ensure OSD feature is on, then paste the .rtf CLI lines.

Usage:
  mgrsosd.py [--file PATH] [--port /dev/...]

Default file: ./diff_bf_osd.rtf (relative to current working directory)

Flow (deliberately tiny):
  1. find Betaflight FC on /dev/cu.usbmodem*
  2. enter CLI (send bare '#')
  3. run `feature`; if 'OSD' is not in the active list, send `feature OSD`
  4. parse the RTF (strip Cocoa preamble), send each CLI line as-is
  5. stop after `save` (FC reboots) — no further probes, no verify
"""
import argparse
import glob
import re
import sys
import time
from pathlib import Path

import serial  # pyserial

DEFAULT_RTF = Path("diff_bf_osd.rtf")


def log(msg):
    print(f"[mgrsosd] {msg}", file=sys.stderr, flush=True)


# ---------- MSP variant probe (single shot)

def msp_variant(port, timeout=2.0):
    try:
        s = serial.Serial(port, 115200, timeout=0.5)
        time.sleep(0.3)
        s.reset_input_buffer()
        # MSP v1 request: cmd 2 (MSP_FC_VARIANT), no payload
        body = bytes([0, 2])
        s.write(b"$M<" + body + bytes([0 ^ 2]))
        s.flush()
        buf = bytearray()
        end = time.time() + timeout
        while time.time() < end:
            c = s.read(1)
            if not c:
                continue
            buf.extend(c)
            # look for: $M> <len=4> <cmd=2> <4 bytes payload>
            if len(buf) >= 9 and bytes(buf[:5]) == b"$M>\x04\x02":
                s.close()
                return buf[5:9].decode("ascii", errors="replace")
        s.close()
    except Exception as e:
        log(f"msp_variant probe error on {port}: {e}")
    return None


# ---------- RTF → CLI lines

def parse_rtf(path):
    raw = path.read_text()
    m = re.search(r"\\cf0\s+", raw)
    body = raw[m.end():] if m else raw
    out = []
    # Cocoa RTF terminates each logical line with '\' + newline
    for line in body.split("\\\n"):
        line = line.rstrip("\\")
        # strip any leftover RTF control words
        line = re.sub(r"\\[a-zA-Z0-9]+", "", line).strip()
        # also strip trailing '}'
        line = line.rstrip("}").strip()
        if not line:
            continue
        out.append(line)
    return out


# ---------- CLI helpers

def cli_open(port, baud=115200):
    s = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write(b"#")  # bare '#' — '#\n' is flaky after Configurator disconnect
    s.flush()
    buf = bytearray()
    end = time.time() + 3.0
    while time.time() < end:
        chunk = s.read(256)
        if chunk:
            buf.extend(chunk)
            if b"# " in buf:
                return s
    s.close()
    raise SystemExit(f"[mgrsosd] CLI prompt not seen on {port}")


def cli_send(s, line, timeout=5.0):
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


# ---------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(DEFAULT_RTF))
    ap.add_argument("--port", default=None)
    args = ap.parse_args()

    # find FC
    if args.port:
        port = args.port
    else:
        ports = sorted(glob.glob("/dev/cu.usbmodem*"))
        if not ports:
            raise SystemExit("[mgrsosd] no /dev/cu.usbmodem* — is the FC plugged in?")
        port = ports[0]

    v = msp_variant(port)
    if v != "BTFL":
        raise SystemExit(f"[mgrsosd] {port} is not Betaflight (variant={v!r})")
    log(f"Betaflight @ {port}")

    # parse the file
    rtf_path = Path(args.file)
    if not rtf_path.exists():
        raise SystemExit(f"[mgrsosd] file not found: {rtf_path}")
    lines = parse_rtf(rtf_path)
    log(f"parsed {len(lines)} CLI lines from {rtf_path.name}")

    # enter CLI
    s = cli_open(port)
    log("CLI entered")

    # OSD feature check
    feat_out = cli_send(s, "feature")
    has_osd = re.search(r"\bOSD\b(?!\s*=)", feat_out) is not None
    if has_osd:
        log("OSD feature already enabled")
    else:
        log("OSD feature OFF — enabling")
        cli_send(s, "feature OSD")

    # paste the file's CLI lines
    sent = 0
    for line in lines:
        out = cli_send(s, line)
        sent += 1
        if any(marker in out for marker in ("###ERROR", "Invalid name", "Unknown command", "Bad option")):
            log(f"  rejected line {sent}: {line!r}")
            log(f"    → {out.strip()[:160]}")
        if line.strip() == "save":
            log(f"sent 'save' after {sent} lines — FC rebooting")
            break

    try:
        s.close()
    except Exception:
        pass
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
