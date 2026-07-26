"""Shared MAVLink v2 frame builders for offline link tests.

Frames are built with the project's own TX encoder (pllink_proto.bm) and the
real CRC_EXTRA table, so the bytes are wire-exact — identical to what an FC
or this GCS would put on the line.
"""

import struct

from backend.crc_extras import CRC_EXTRA
from backend.pllink_proto import bm


def fc_frame(mid: int, payload: bytes, seq: int = 0) -> bytes:
    """An FC-originated frame (sysid 1) — what the GCS receives."""
    return bm(mid, payload, seq, CRC_EXTRA[mid], sysid=1, compid=1)


def heartbeat(mode: int = 4, armed: bool = True, seq: int = 0, autopilot: int = 3) -> bytes:
    # HEARTBEAT: custom_mode u32 @0, type u8 @4, autopilot u8 @5,
    # base_mode u8 @6 (0x80 = armed), system_status u8 @7, version u8 @8.
    base_mode = 0x80 | 0x10 if armed else 0x10
    return fc_frame(0, struct.pack("<IBBBBB", mode, 2, autopilot, base_mode, 4, 3), seq)


def attitude(roll_rad: float = 0.1, seq: int = 0) -> bytes:
    # ATTITUDE: time_boot_ms u32, roll/pitch/yaw f @4/8/12, rates @16/20/24
    return fc_frame(30, struct.pack("<Iffffff", 1000, roll_rad, 0.0, 0.5, 0, 0, 0), seq)


def global_position(lat: float = 31.2304, lon: float = 121.4737, seq: int = 0) -> bytes:
    # GLOBAL_POSITION_INT: time u32, lat/lon 1e7 i32 @4/8, alt mm i32 @12,
    # rel_alt mm i32 @16, vx/vy/vz cm/s i16 @20/22/24, hdg cdeg u16 @26
    return fc_frame(
        33,
        struct.pack("<Iiiiihhhh", 1000, int(lat * 1e7), int(lon * 1e7), 15000, 5000, 100, 0, 0, 9000),
        seq,
    )


def param_value(name: bytes, value: float, count: int, index: int, seq: int = 0) -> bytes:
    # PARAM_VALUE: value f32 @0, param_count u16 @4, param_index u16 @6,
    # param_id char[16] @8, param_type u8 @24
    payload = struct.pack("<fHH", value, count, index) + name.ljust(16, b"\x00") + b"\x09"
    return fc_frame(22, payload, seq)


def write_tlog(path, frames, t0_usec: int = 1_700_000_000_000_000, spacing_usec: int = 1000) -> None:
    """Write frames in tlog format: 8-byte big-endian usec timestamp prefix
    per message (pymavlink mavutil.mavlogfile.pre_message)."""
    with open(path, "wb") as f:
        for i, frame in enumerate(frames):
            f.write(struct.pack(">Q", t0_usec + i * spacing_usec) + frame)


# A minimal but state-bearing session: armed GUIDED heartbeat + attitude + GPS.
SESSION = [heartbeat(mode=4, armed=True, seq=0), attitude(0.1, seq=1), global_position(seq=2)]
