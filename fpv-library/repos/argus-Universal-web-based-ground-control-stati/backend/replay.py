"""Offline replay of recorded MAVLink sessions (.tlog).

Every live connection records both link directions to logs/argus_*.tlog
(see DroneLink._record_tlog). This module turns those recordings back into
inputs: parsed frame lists for tests, or a full drive of the real
parse → dispatch → state path via DroneLink.feed().

Format per pymavlink mavutil.mavlogfile.pre_message: each MAVLink message
is prefixed with an 8-byte big-endian microsecond timestamp, so recordings
are also readable by mavlogdump.py / Mission Planner.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .drone_link import DroneLink

# GCS-originated frames carry sysid 255 (pllink_proto.bm default). Replay
# must skip them by default: handle_heartbeat latches connected/mode/armed
# from ANY sysid, so feeding our own recorded heartbeats back through the
# parser would fabricate vehicle state.
GCS_SYSID = 255


def read_tlog(path: str, include_gcs: bool = False) -> list[tuple[int, bytes]]:
    """Parse a .tlog into [(usec_timestamp, frame_bytes), ...].

    Only MAVLink v2 frames (0xFD magic) are expected — that is all the
    recorder writes. A malformed record means the file is corrupt or not a
    tlog; fail loud with the byte offset rather than silently skipping.
    """
    with open(path, "rb") as f:
        data = f.read()
    records: list[tuple[int, bytes]] = []
    ofs = 0
    while ofs < len(data):
        # Need ts(8) + magic + payload_len + incompat_flags readable before
        # the header fields below are touched — a disk-full short write can
        # truncate anywhere, and an off-by-two here surfaced as a bare
        # IndexError that escaped past every OSError handler upstream.
        if ofs + 11 > len(data):
            raise ValueError("truncated tlog record at byte %d in %s" % (ofs, path))
        (ts,) = struct.unpack_from(">Q", data, ofs)
        magic = data[ofs + 8]
        if magic != 0xFD:
            raise ValueError("bad frame magic 0x%02X at byte %d in %s (not a MAVLink v2 tlog?)" % (magic, ofs + 8, path))
        payload_len = data[ofs + 9]
        # MAVLink v2 framing: 10-byte header + payload + 2-byte CRC
        # (+13-byte signature when incompat flag 0x01 is set) — same layout
        # DroneLink._parse_mavlink_frame consumes.
        has_sig = bool(data[ofs + 10] & 0x01)
        frame_len = 12 + payload_len + (13 if has_sig else 0)
        if ofs + 8 + frame_len > len(data):
            raise ValueError("truncated frame at byte %d in %s" % (ofs + 8, path))
        frame = data[ofs + 8 : ofs + 8 + frame_len]
        if include_gcs or frame[5] != GCS_SYSID:
            records.append((ts, frame))
        ofs += 8 + frame_len
    return records


def replay_into(link: DroneLink, path: str) -> int:
    """Drive a recorded session through the real ingest path.

    Feeds each FC-originated frame to link.feed() — the same code the live
    link thread runs — so the resulting link.get_state() is what a live
    session would have produced. Returns frames processed."""
    frames = 0
    for _ts, frame in read_tlog(path):
        frames += link.feed(frame)
    return frames
