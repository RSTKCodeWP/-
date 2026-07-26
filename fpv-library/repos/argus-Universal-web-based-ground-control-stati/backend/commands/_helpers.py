from __future__ import annotations

import struct
import time
from typing import TYPE_CHECKING

from ..config import cfg
from ..crc_extras import CRC_EXTRA
from ..pllink_proto import bm

if TYPE_CHECKING:
    from ..drone_link import DroneLink


def send_cmd(link: DroneLink, command: int, p1=0, p2=0, p3=0, p4=0, p5=0, p6=0, p7=0) -> None:
    payload = struct.pack(
        "<fffffffHBBB",
        float(p1),
        float(p2),
        float(p3),
        float(p4),
        float(p5),
        float(p6),
        float(p7),
        command,
        link.vehicle.sysid,
        1,
        0,
    )
    link.send(bm(76, payload, link.sq, CRC_EXTRA[76]))


def send_cmd_int(
    link: DroneLink,
    command: int,
    p1: float = 0.0,
    p2: float = 0.0,
    p3: float = 0.0,
    p4: float = 0.0,
    x: int = 0,
    y: int = 0,
    z: float = 0.0,
    frame: int = 0,
) -> None:
    # COMMAND_INT (msg 75, CRC_EXTRA 158). Use this instead of send_cmd when
    # the handler reads x/y/z as type-specific slots (scaled lat/lon int32,
    # or reinterpreted as bitfield) rather than as param5/6/7 floats — e.g.
    # AP_Mount::handle_command_do_gimbal_manager_pitchyaw at
    # libraries/AP_Mount/AP_Mount.cpp:363 reads packet.x as a uint32
    # GIMBAL_MANAGER_FLAGS bitfield, packet.z as the gimbal device id.
    payload = struct.pack(
        "<ffffiifHBBBBB",
        float(p1),
        float(p2),
        float(p3),
        float(p4),
        int(x),
        int(y),
        float(z),
        command,
        link.vehicle.sysid,
        1,
        frame,
        0,
        0,
    )
    link.send(bm(75, payload, link.sq, CRC_EXTRA[75]))


def send_set_mode(link: DroneLink, mode: int) -> None:
    payload = struct.pack("<IBB", mode, link.vehicle.sysid, 0x01)
    link.send(bm(11, payload, link.sq, CRC_EXTRA[11]))


def send_mission_count(link: DroneLink, count: int) -> None:
    link.send(bm(44, struct.pack("<HBB", count, link.vehicle.sysid, 1) + bytes([0]), link.sq, CRC_EXTRA[44]))


def send_fence_count(link: DroneLink, count: int) -> None:
    link.send(bm(44, struct.pack("<HBB", count, link.vehicle.sysid, 1) + bytes([1]), link.sq, CRC_EXTRA[44]))


def send_fence_item_int(link: DroneLink, item: dict) -> None:
    lat7 = int(float(item.get("lat", 0)) * 1e7)
    lon7 = int(float(item.get("lon", 0)) * 1e7)
    p = struct.pack(
        "<ffffiifHHBBBBBB",
        float(item.get("p1", 0)),
        float(item.get("p2", 0)),
        0.0,
        0.0,
        lat7,
        lon7,
        float(item.get("alt", 0)),
        item["seq"],
        item["cmd"],
        link.vehicle.sysid,
        1,
        3,
        0,
        1,
        1,
    )
    link.send(bm(73, p, link.sq, CRC_EXTRA[73]))


def send_rally_item_int(link: DroneLink, item: dict) -> None:
    # MAV_CMD_NAV_RALLY_POINT in mission_type=2. AP_Rally accepts items with
    # frame=MAV_FRAME_GLOBAL_RELATIVE_ALT (3) so the alt is relative to home.
    lat7 = int(float(item.get("lat", 0)) * 1e7)
    lon7 = int(float(item.get("lon", 0)) * 1e7)
    p = struct.pack(
        "<ffffiifHHBBBBBB",
        float(item.get("p1", 0)),
        float(item.get("p2", 0)),
        0.0,
        0.0,
        lat7,
        lon7,
        float(item.get("alt", 0)),
        item["seq"],
        item["cmd"],
        link.vehicle.sysid,
        1,
        3,
        0,
        1,
        2,
    )
    link.send(bm(73, p, link.sq, CRC_EXTRA[73]))


def send_mission_item_int(link: DroneLink, wp: dict) -> None:
    frame = 3 if wp["cmd"] in (16, 18, 19, 21, 22, 82) else 2
    lat7 = int(float(wp.get("lat", 0)) * 1e7)
    lon7 = int(float(wp.get("lon", 0)) * 1e7)
    p = struct.pack(
        "<ffffiifHHBBBBBB",
        float(wp.get("p1", 0)),
        float(wp.get("p2", 0)),
        float(wp.get("p3", 0)),
        float(wp.get("p4", 0)),
        lat7,
        lon7,
        float(wp.get("alt", 0)),
        wp["seq"],
        wp["cmd"],
        link.vehicle.sysid,
        1,
        frame,
        1 if wp["seq"] == 0 else 0,
        1,
        0,
    )
    link.send(bm(73, p, link.sq, CRC_EXTRA[73]))


def send_serial_control(link: DroneLink, text: str) -> None:
    data = (text + "\n").encode("ascii", "replace")[:70]
    flags = 0x06
    p = struct.pack("<IHBBB", 0, 0, 10, flags, len(data))
    p += data + b"\x00" * (70 - len(data))
    link.send(bm(126, p, link.sq, CRC_EXTRA[126]))


def send_heartbeat(link: DroneLink) -> None:
    # custom_mode=0, type=MAV_TYPE_GCS (6), autopilot=MAV_AUTOPILOT_INVALID (8),
    # base_mode=0, system_status=MAV_STATE_ACTIVE (4), mavlink_version=3.
    # Convention is for a healthy GCS to report MAV_STATE_ACTIVE; previously
    # we sent system_status=0 (MAV_STATE_UNINIT) which some FC monitoring
    # tools display as "GCS not ready".
    payload = struct.pack("<IBBBBB", 0, 6, 8, 0, 4, 3)
    link.send(bm(0, payload, link.sq, CRC_EXTRA[0]))


def request_streams(link: DroneLink) -> None:
    # Per-message stream rate, in microseconds. ATTITUDE (30) and
    # GLOBAL_POSITION_INT (33) drive every animated UI element — old
    # rate of 250000us = 4Hz made the heading needle / position arrow
    # visibly stutter, and they were redrawn TWICE between updates by
    # the 5Hz ws push. 100000us = 10Hz matches Mission Planner /
    # QGroundControl defaults.
    streams = [
        (30, 100000),
        (33, 100000),
        (24, 250000),
        (1, 1000000),
        (42, 1000000),
        (36, 500000),
        (65, 500000),
        (241, 1000000),
        (74, 500000),
        # MAG_CAL_PROGRESS / MAG_CAL_REPORT are not in the set above and only
        # ride the FC-side SRx_EXTRA3 stream group otherwise — with SR params
        # at 0 a compass cal completes on the FC while the GCS never sees a
        # single 191/192 (found by tests/sitl_calibrate.py against real SITL).
        # Interval-scheduling them is valid and idle-free: ArduPilot
        # GCS_Common.cpp:1139 maps both in mavlink_id_to_ap_message, and their
        # try_send_message cases (:6679/:6682) no-op while no cal is running.
        (191, 500000),
        (192, 500000),
        # RAW_IMU at 5Hz feeds the compass-cal sample sphere (mag milligauss,
        # GCS_Common.cpp:2237 send_raw_imu); ~220B/s — cheap even on radios.
        (27, 200000),
    ]
    for mid, interval in streams:
        payload = struct.pack("<fffffffHBBB", float(mid), float(interval), 0, 0, 0, 0, 0, 511, link.vehicle.sysid, 1, 0)
        link.send(bm(76, payload, link.sq, CRC_EXTRA[76]))
        time.sleep(cfg.STREAM_REQUEST_SPACING)
    send_cmd(link, 512, p1=148.0)
