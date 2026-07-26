"""PL-Link protocol: XOR framing + MAVLink v2 message construction."""

import struct

XOR_KEY = bytes([0x4B, 0x65, 0x79, 0x50, 0x4C, 0x31, 0x21, 0x40])


def xp(d):
    o = bytearray(d)
    for i in range(len(o)):
        o[i] ^= XOR_KEY[i % 8]
    return bytes(o)


def c16(d):
    c = 0xFFFF
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def ple(p, s):
    x = xp(p)
    h = struct.pack("<HB", len(p), s & 0xFF)
    return bytes([0x50, 0x4C]) + h + x + struct.pack("<H", c16(h + x))


def pld(d):
    if len(d) < 7 or d[0] != 0x50 or d[1] != 0x4C:
        return None, max(1, len(d) > 0)
    l = d[2] | (d[3] << 8)
    if l < 1 or l > 280:
        return None, 2
    t = 7 + l
    if len(d) < t:
        return None, 0
    px = d[5 : 5 + l]
    cr = d[5 + l] | (d[6 + l] << 8)
    h = struct.pack("<HB", l, d[4])
    return (xp(px), t) if cr == c16(h + px) else (None, 2)


def mc(b, e):
    c = 0xFFFF
    for x in b:
        t = x ^ (c & 0xFF)
        t ^= (t << 4) & 0xFF
        c = ((c >> 8) ^ (t << 8) ^ (t << 3) ^ (t >> 4)) & 0xFFFF
    t = e ^ (c & 0xFF)
    t ^= (t << 4) & 0xFF
    c = ((c >> 8) ^ (t << 8) ^ (t << 3) ^ (t >> 4)) & 0xFFFF
    return c


def bm(mid, p, s, ce, sysid=255, compid=1):
    # MAVLink 2 payload length is a single byte; >=256 would silently overflow
    # the header field, producing a malformed frame that the FC would reject
    # (or worse, parse the next bytes as the next frame). Reject early with a
    # clear ValueError — callers should chunk large payloads themselves.
    if len(p) > 255:
        raise ValueError("MAVLink payload too long: %d bytes (max 255)" % len(p))
    h = bytes([len(p), 0, 0, s & 0xFF, sysid & 0xFF, compid & 0xFF, mid & 0xFF, (mid >> 8) & 0xFF, (mid >> 16) & 0xFF])
    return b"\xfd" + h + p + struct.pack("<H", mc(h + p, ce))
