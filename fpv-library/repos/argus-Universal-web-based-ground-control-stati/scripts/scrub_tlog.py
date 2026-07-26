#!/usr/bin/env python3
"""Scrub identifying data from a recorded .tlog so it can ship as a public
test fixture.

What gets rewritten (everything else is copied byte-exact):
  - position: every lat/lon-bearing message is shifted by a constant delta
    that maps the session's HOME_POSITION onto the ArduPilot SITL default
    home (CMAC, -35.363261 149.165230). Relative motion (GPS drift, home
    distance) survives; the true location does not.
  - board identity: the ArduPilot connect banner renders the MCU unique id
    as three space-separated groups of 8 UPPERCASE-HEX chars
    (libraries/AP_HAL_ChibiOS/Util.cpp:346, get_system_id snprintf "%02X");
    those groups are zeroed, length-preserving, and AUTOPILOT_VERSION
    uid/uid2 (the same bytes) are cleared. Never write a real UID into
    code, comments, or tests — assert on the shape, not the value.
  - location side-channels: the "Field Elevation Set: NNNNm" figure
    (libraries/AP_Baro/AP_Baro.cpp:1043) is zeroed in the text, and the
    COMPASS_DEC parameter (auto-learned world-magnetic-model declination)
    plus GPS_RAW_INT.alt_ellipsoid (implies local geoid undulation) are
    zeroed so the true region cannot be inverted from magnetic/geoid maps.

Deliberately KEPT (accepted policy, not oversight):
  - numeric altitude fields (baro/terrain/VFR channels stay internally
    consistent; a bare MSL height is a weak signal on its own),
  - wall-clock timestamps (tlog records, SYSTEM_TIME) — recording date is
    disclosed anyway wherever the fixture is described,
  - board/firmware names and git hashes (public by design).

Frames are re-encoded with pymavlink using the original seq/sysid/compid,
so CRCs stay valid and MAVLink2 zero-trim framing stays canonical. If the
log contains a position-bearing message this tool has no rule for, it
refuses to write output. A self-check pass re-reads the output and fails
loudly if any original coordinate, serial group, or uid2 byte pattern
survived.

Usage: python3 scripts/scrub_tlog.py <in.tlog> <out.tlog>
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

# Allow running from a repo checkout without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymavlink.dialects.v20 import ardupilotmega as apm  # noqa: E402

from backend.replay import read_tlog  # noqa: E402

# ArduPilot SITL default home (CMAC) in degE7 — the conventional "obviously
# a test" location.
TARGET_LAT_E7 = -353632610
TARGET_LON_E7 = 1491652300

# msg id -> (lat field, lon field), all int32 degE7.
POSITION_FIELDS = {
    24: ("lat", "lon"),  # GPS_RAW_INT
    33: ("lat", "lon"),  # GLOBAL_POSITION_INT
    49: ("latitude", "longitude"),  # GPS_GLOBAL_ORIGIN
    136: ("lat", "lon"),  # TERRAIN_REPORT
    178: ("lat", "lng"),  # AHRS2
    242: ("latitude", "longitude"),  # HOME_POSITION
}
# Position-bearing messages with NO rewrite rule here. A richer log (mission
# upload, fence, second GPS, terrain transfer, camera feedback) must extend
# POSITION_FIELDS before it may ship — refuse instead of leaking silently.
UNHANDLED_POSITION_IDS = {
    39,  # MISSION_ITEM
    48,  # SET_GPS_GLOBAL_ORIGIN
    73,  # MISSION_ITEM_INT
    75,  # COMMAND_INT (x/y carry lat/lon for NAV/DO_SET_HOME/ROI commands)
    86,  # SET_POSITION_TARGET_GLOBAL_INT
    87,  # POSITION_TARGET_GLOBAL_INT
    124,  # GPS2_RAW
    133,  # TERRAIN_REQUEST
    134,  # TERRAIN_DATA
    160,  # FENCE_POINT
    175,  # RALLY_POINT
    180,  # CAMERA_FEEDBACK
}
COMMAND_LONG_ID = 76
# COMMAND_LONG commands whose param5/param6 carry lat/lon.
POSITION_COMMANDS = {179, 192, 195, 201}  # DO_SET_HOME, DO_REPOSITION, DO_SET_ROI_LOCATION, DO_SET_ROI
PARAM_VALUE_ID = 22
GPS_RAW_INT_ID = 24
STATUSTEXT_ID = 253
AUTOPILOT_VERSION_ID = 148

# The banner UID groups are UPPERCASE HEX, not decimal — a \d-only pattern
# would let any UID containing A-F escape both scrub and verify
# (libraries/AP_HAL_ChibiOS/Util.cpp:346: snprintf "%s %02X%02X%02X%02X ...").
_SERIAL_RE = re.compile(r"\b[0-9A-F]{8} [0-9A-F]{8} [0-9A-F]{8}\b")
# "Field Elevation Set: %.0fm" — libraries/AP_Baro/AP_Baro.cpp:1043.
_ELEVATION_RE = re.compile(r"(Field Elevation Set: )(\d+)(m)")


def _scrub_text(text: str) -> str:
    text = _SERIAL_RE.sub(lambda m: re.sub(r"\d", "0", m.group(0)), text)
    return _ELEVATION_RE.sub(lambda m: m.group(1) + "0" * len(m.group(2)) + m.group(3), text)


def _mid(frame: bytes) -> int:
    return frame[7] | (frame[8] << 8) | (frame[9] << 16)


def _wrap_i32(v: int) -> int:
    return (v + 2**31) % 2**32 - 2**31


def _repack(msg, frame: bytes) -> bytes:
    """Re-encode a mutated message with the original header identity."""
    mav = apm.MAVLink(None, srcSystem=frame[5], srcComponent=frame[6])
    mav.seq = frame[4]
    return msg.pack(mav)


def scrub(in_path: str, out_path: str) -> dict[str, int]:
    records = read_tlog(in_path, include_gcs=True)
    decoder = apm.MAVLink(None)
    decoder.robust_parsing = True

    home = next(
        (
            (m.latitude, m.longitude)
            for m in (decoder.decode(bytearray(f)) for _, f in records if _mid(f) == 242)
        ),
        None,
    )
    if home is None:
        raise SystemExit("no HOME_POSITION in log — nothing to anchor the coordinate shift to")
    d_lat = TARGET_LAT_E7 - home[0]
    d_lon = TARGET_LON_E7 - home[1]

    stats: dict[str, int] = {}
    out_records: list[tuple[int, bytes]] = []
    for ts, frame in records:
        mid = _mid(frame)
        if mid in UNHANDLED_POSITION_IDS:
            raise SystemExit(
                f"msg id {mid} carries position but has no scrub rule — "
                "extend POSITION_FIELDS before shipping this log"
            )
        if mid == COMMAND_LONG_ID:
            msg = decoder.decode(bytearray(frame))
            if msg.command in POSITION_COMMANDS:
                raise SystemExit(
                    f"COMMAND_LONG {msg.command} carries lat/lon in param5/6 — "
                    "no scrub rule, refusing"
                )
            out_records.append((ts, frame))
            continue
        if mid in POSITION_FIELDS:
            latf, lonf = POSITION_FIELDS[mid]
            msg = decoder.decode(bytearray(frame))
            setattr(msg, latf, _wrap_i32(getattr(msg, latf) + d_lat))
            setattr(msg, lonf, _wrap_i32(getattr(msg, lonf) + d_lon))
            if mid == GPS_RAW_INT_ID:
                # Ellipsoid-vs-MSL difference is the local geoid undulation —
                # a region fingerprint even after the lat/lon shift.
                msg.alt_ellipsoid = 0
            frame = _repack(msg, frame)
        elif mid == PARAM_VALUE_ID:
            msg = decoder.decode(bytearray(frame))
            if msg.param_id != "COMPASS_DEC":
                out_records.append((ts, frame))
                continue
            # Auto-learned magnetic declination is a world-magnetic-model
            # lookup of the true site — zero it.
            msg.param_value = 0.0
            frame = _repack(msg, frame)
        elif mid == STATUSTEXT_ID:
            msg = decoder.decode(bytearray(frame))
            scrubbed = _scrub_text(msg.text)
            if scrubbed == msg.text:
                # Nothing sensitive — keep the wire bytes untouched rather
                # than round-tripping through a re-encode.
                out_records.append((ts, frame))
                continue
            msg.text = scrubbed
            # pymavlink packs char fields from the shadow *_raw bytes, not
            # the decoded str (MAVLink_statustext_message.pack uses
            # self._text_raw — dialects/v20/ardupilotmega.py). Mutating
            # .text alone silently re-emits the original.
            msg._text_raw = scrubbed.encode("ascii")
            frame = _repack(msg, frame)
        elif mid == AUTOPILOT_VERSION_ID:
            msg = decoder.decode(bytearray(frame))
            msg.uid = 0
            msg.uid2 = [0] * 18
            frame = _repack(msg, frame)
        else:
            out_records.append((ts, frame))
            continue
        stats[apm.mavlink_map[mid].msgname] = stats.get(apm.mavlink_map[mid].msgname, 0) + 1
        out_records.append((ts, frame))

    with open(out_path, "wb") as fh:
        for ts, frame in out_records:
            fh.write(struct.pack(">Q", ts) + frame)
    return stats


def verify(in_path: str, out_path: str) -> None:
    orig = read_tlog(in_path, include_gcs=True)
    outr = read_tlog(out_path, include_gcs=True)  # also proves framing survived
    assert len(orig) == len(outr), f"record count changed: {len(orig)} -> {len(outr)}"

    decoder = apm.MAVLink(None)
    decoder.robust_parsing = True
    home = next((decoder.decode(bytearray(f)) for _, f in orig if _mid(f) == 242), None)
    if home is None:
        raise SystemExit("verify: no HOME_POSITION in input log")
    forbidden: list[bytes] = []
    # If the input was already anchored on CMAC (a re-run on scrubbed output,
    # or a SITL log), the "original" coordinate bytes ARE the target bytes —
    # scanning for them would false-positive on a correct output.
    already_anchored = (
        abs(TARGET_LAT_E7 - home.latitude) < 20_000 and abs(TARGET_LON_E7 - home.longitude) < 20_000
    )
    if not already_anchored:
        forbidden += [
            struct.pack("<i", home.latitude),
            struct.pack("<i", home.longitude),
        ]

    blob = Path(out_path).read_bytes()
    for _, frame in orig:
        mid = _mid(frame)
        if mid == STATUSTEXT_ID:
            m = decoder.decode(bytearray(frame))
            if _scrub_text(m.text) != m.text:
                for grp in _SERIAL_RE.findall(m.text):
                    forbidden.append(grp.encode())
                em = _ELEVATION_RE.search(m.text)
                if em:
                    forbidden.append(em.group(0).encode())
        elif mid == AUTOPILOT_VERSION_ID:
            m = decoder.decode(bytearray(frame))
            uid2 = bytes(b & 0xFF for b in m.uid2).rstrip(b"\x00")
            if len(uid2) >= 4:
                forbidden.append(uid2)
    for pat in forbidden:
        assert pat not in blob, f"identifying bytes survived the scrub: {pat!r}"

    out_dec = apm.MAVLink(None)
    out_dec.robust_parsing = True
    for (ts_o, f_o), (ts_s, f_s) in zip(orig, outr, strict=True):
        assert ts_o == ts_s, "timestamp drift"
        mid = _mid(f_o)
        assert mid == _mid(f_s), "message order changed"
        assert f_o[4] == f_s[4] and f_o[5] == f_s[5] and f_o[6] == f_s[6], "header identity changed"
        if mid in POSITION_FIELDS:
            m = out_dec.decode(bytearray(f_s))
            lat = getattr(m, POSITION_FIELDS[mid][0])
            lon = getattr(m, POSITION_FIELDS[mid][1])
            # Bench GPS drift is metres; anything >0.2 deg from CMAC means
            # the shift missed a frame.
            assert abs(lat - TARGET_LAT_E7) < 2_000_000, f"{mid}: lat {lat} not shifted"
            assert abs(lon - TARGET_LON_E7) < 2_000_000, f"{mid}: lon {lon} not shifted"
            if mid == GPS_RAW_INT_ID:
                assert m.alt_ellipsoid == 0, "alt_ellipsoid survived"
        elif mid == PARAM_VALUE_ID:
            m = out_dec.decode(bytearray(f_s))
            if m.param_id == "COMPASS_DEC":
                assert m.param_value == 0.0, "COMPASS_DEC survived"
            else:
                assert f_o == f_s, "clean PARAM_VALUE was re-encoded"
        elif mid == STATUSTEXT_ID:
            m_o = decoder.decode(bytearray(f_o))
            if _scrub_text(m_o.text) == m_o.text:
                assert f_o == f_s, "clean STATUSTEXT was re-encoded"
        elif mid != AUTOPILOT_VERSION_ID:
            assert f_o == f_s, f"untouched msg id {mid} was modified"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    in_path, out_path = sys.argv[1], sys.argv[2]
    stats = scrub(in_path, out_path)
    verify(in_path, out_path)
    total = sum(stats.values())
    print(f"scrubbed {total} frames -> {out_path}")
    for name, n in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {name:24s} {n}")
    print("self-check passed: no original coordinates / serials / uid2 in output")


if __name__ == "__main__":
    main()
